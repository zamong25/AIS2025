"""
포지션 상태 관리자 - 진실의 단일 소스(Single Source of Truth) 구현
바이낸스 API를 기준으로 모든 포지션 상태를 통합 관리
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
import json
import os
from binance.client import Client
import sqlite3

class PositionStateManager:
    """포지션 상태 통합 관리자"""

    def __init__(self, client: Client, db_path: str = None):
        self.client = client

        # db_path가 None이면 절대 경로로 설정
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, 'data', 'database')
            self.db_path = os.path.join(db_dir, 'delphi_trades.db')
        else:
            self.db_path = db_path

        self.logger = logging.getLogger('PositionStateManager')
        
        # 캐시 (성능 최적화용)
        self._position_cache = None
        self._last_update = None
        self._cache_ttl = 5  # 5초 캐시
        
    def get_current_position(self, symbol: str = "SOLUSDT") -> Optional[Dict]:
        """
        현재 포지션 상태를 반환 (진실의 단일 소스)
        
        우선순위:
        1. 바이낸스 API (실제 포지션)
        2. Trading Context (의도와 계획)
        3. DB (거래 기록)
        """
        
        # 1. 바이낸스에서 실제 포지션 조회
        binance_position = self._get_binance_position(symbol)
        
        if not binance_position:
            # 포지션이 없으면 정리 작업
            self._cleanup_stale_data()
            return None
            
        # 2. Trading Context 로드
        trading_context = self._load_trading_context()
        
        # 3. DB에서 관련 거래 정보 조회
        db_trades = self._get_related_trades(symbol, binance_position['direction'])
        
        # 4. 통합 포지션 정보 생성
        position = self._merge_position_data(
            binance_position, 
            trading_context, 
            db_trades
        )
        
        return position
    
    def _get_binance_position(self, symbol: str) -> Optional[Dict]:
        """바이낸스에서 실제 포지션 조회"""
        try:
            # 캐시 확인
            if self._is_cache_valid():
                return self._position_cache
                
            positions = self.client.futures_position_information(symbol=symbol)
            
            for pos in positions:
                position_amt = float(pos['positionAmt'])
                if position_amt != 0:
                    position = {
                        'symbol': pos['symbol'],
                        'quantity': abs(position_amt),
                        'direction': 'LONG' if position_amt > 0 else 'SHORT',
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                        'mark_price': float(pos['markPrice']),
                        'position_side': pos.get('positionSide', 'BOTH'),
                        'isolated': pos.get('isolated', True),
                        'leverage': int(pos.get('leverage', 1))
                    }
                    
                    # 캐시 업데이트
                    self._update_cache(position)
                    
                    self.logger.info(f"바이낸스 포지션 조회: {position['direction']} {position['quantity']} @ ${position['entry_price']}")
                    return position
                    
            return None
            
        except Exception as e:
            self.logger.error(f"바이낸스 포지션 조회 실패: {e}")
            # 캐시된 데이터라도 반환
            return self._position_cache
    
    def _load_trading_context(self) -> Optional[Dict]:
        """Trading Context 파일 로드"""
        context_file = os.path.join('data', 'active_trading_context.json')
        
        if not os.path.exists(context_file):
            return None
            
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # TEST_001이면 무시
            if data.get('thesis', {}).get('trade_id') == 'TEST_001':
                return None
                
            return data
            
        except Exception as e:
            self.logger.warning(f"Trading Context 로드 실패: {e}")
            return None
    
    def _get_related_trades(self, symbol: str, direction: str) -> List[Dict]:
        """DB에서 관련된 PENDING 거래 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # PENDING 상태의 같은 방향 거래들 조회
            cursor.execute("""
                SELECT trade_id, entry_price, position_size_percent, entry_time, 
                       stop_loss_price, take_profit_price, leverage
                FROM trade_records 
                WHERE asset = ? 
                AND direction = ? 
                AND outcome = 'PENDING'
                ORDER BY entry_time DESC
            """, (symbol, direction))
            
            trades = []
            for row in cursor.fetchall():
                trades.append({
                    'trade_id': row[0],
                    'entry_price': row[1],
                    'position_size_percent': row[2],
                    'entry_time': row[3],
                    'stop_loss': row[4],
                    'take_profit': row[5],
                    'leverage': row[6]
                })
                
            conn.close()
            return trades
            
        except Exception as e:
            self.logger.warning(f"DB 거래 조회 실패: {e}")
            return []
    
    def _merge_position_data(self, binance_pos: Dict, 
                           context: Optional[Dict], 
                           db_trades: List[Dict]) -> Dict:
        """여러 소스의 데이터를 통합"""
        
        # 기본은 바이낸스 데이터
        position = binance_pos.copy()
        
        # Trading Context 정보 추가
        if context and context.get('thesis'):
            thesis = context['thesis']
            position.update({
                'has_context': True,
                'trade_id': thesis.get('trade_id'),
                'entry_reason': thesis.get('entry_reason'),
                'primary_scenario': thesis.get('primary_scenario'),
                'target_price': thesis.get('target_price'),
                'stop_loss': thesis.get('stop_loss'),
                'initial_confidence': thesis.get('initial_confidence'),
                'context_entry_time': thesis.get('entry_time')
            })
        else:
            position['has_context'] = False
            
        # DB 거래 정보 추가
        if db_trades:
            # 가장 최근 거래 정보 사용
            latest_trade = db_trades[0]
            position.update({
                'db_trade_id': latest_trade['trade_id'],
                'db_entry_time': latest_trade['entry_time'],
                'db_trades_count': len(db_trades)  # 중복 진입 횟수
            })
            
            # 손절/익절가는 DB 정보 우선 (0이 아닌 경우)
            if latest_trade['stop_loss'] > 0:
                position['stop_loss'] = latest_trade['stop_loss']
            if latest_trade['take_profit'] > 0:
                position['target_price'] = latest_trade['take_profit']
        
        # 실제 손익률 계산
        if position['direction'] == 'LONG':
            position['pnl_percent'] = ((position['mark_price'] - position['entry_price']) / position['entry_price']) * 100
        else:  # SHORT
            position['pnl_percent'] = ((position['entry_price'] - position['mark_price']) / position['entry_price']) * 100
            
        # 포지션 상태 정보
        position['has_position'] = True
        position['last_updated'] = datetime.utcnow().isoformat()
        
        return position
    
    def _cleanup_stale_data(self):
        """포지션이 없을 때 오래된 데이터 정리"""
        # Trading Context 파일 삭제
        context_file = os.path.join('data', 'active_trading_context.json')
        if os.path.exists(context_file):
            try:
                # 날짜별 폴더 구조로 백업
                now = datetime.now()
                year = now.strftime("%Y")
                month = now.strftime("%m")
                
                # history 폴더 생성 (없을 경우)
                history_dir = os.path.join('data', 'history', year, month)
                os.makedirs(history_dir, exist_ok=True)
                
                # 백업 파일 이름
                backup_filename = f'context_{now.strftime("%Y%m%d_%H%M%S")}.json'
                backup_file = os.path.join(history_dir, backup_filename)
                
                # 파일 이동
                os.rename(context_file, backup_file)
                self.logger.info(f"Trading Context 백업 완료: {backup_file}")
            except Exception as e:
                self.logger.warning(f"Context 파일 정리 실패: {e}")
                
        # TODO: DB의 PENDING 거래들도 정리 필요
    
    def _is_cache_valid(self) -> bool:
        """캐시 유효성 확인"""
        if not self._position_cache or not self._last_update:
            return False
            
        elapsed = (datetime.utcnow() - self._last_update).total_seconds()
        return elapsed < self._cache_ttl
    
    def _update_cache(self, position: Dict):
        """캐시 업데이트"""
        self._position_cache = position
        self._last_update = datetime.utcnow()
    
    def sync_position_state(self) -> Dict:
        """
        포지션 상태 동기화 및 불일치 해결
        
        Returns:
            동기화 결과 리포트
        """
        report = {
            'status': 'success',
            'discrepancies': [],
            'actions_taken': []
        }
        
        # 1. 현재 포지션 상태 조회
        position = self.get_current_position()
        
        # 2. 불일치 검사
        if position:
            # DB에 여러 개의 PENDING 거래가 있는지 확인
            if position.get('db_trades_count', 0) > 1:
                report['discrepancies'].append(
                    f"중복 거래 발견: {position['db_trades_count']}개의 PENDING 거래"
                )
                
            # Trading Context와 실제 포지션 비교
            if position.get('has_context'):
                if abs(position['entry_price'] - position.get('target_price', 0)) < 0.01:
                    report['discrepancies'].append(
                        "Trading Context의 entry_price가 잘못됨"
                    )
        else:
            # 포지션이 없는데 Context나 DB에 데이터가 있는지 확인
            if os.path.exists('data/active_trading_context.json'):
                report['discrepancies'].append(
                    "포지션이 없는데 Trading Context 파일 존재"
                )
                
        # 3. 자동 정리 작업
        if not position:
            self._cleanup_stale_data()
            report['actions_taken'].append("오래된 데이터 정리 완료")
            
        return report


# 전역 인스턴스 (TradeExecutor에서 사용)
position_state_manager = None

def init_position_manager(client: Client):
    """포지션 상태 관리자 초기화"""
    global position_state_manager
    position_state_manager = PositionStateManager(client)
    return position_state_manager