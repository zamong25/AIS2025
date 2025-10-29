"""
델파이 트레이딩 시스템 - MDD/MFE 추적기
실시간으로 포지션의 최대 손실(MDD)과 최대 이익(MFE)을 추적
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List
import sqlite3
import json


class MDDTracker:
    """실시간 MDD/MFE 추적"""
    
    def __init__(self, db_path: str = "data/database/delphi_trades.db"):
        self.db_path = db_path
        self.positions = {}  # 메모리 캐시
        self.logger = logging.getLogger('MDDTracker')
        self.logger.info("📉 MDD 추적기 초기화")
    
    def update_position(self, trade_id: str, current_price: float) -> Dict:
        """포지션 업데이트 (15분마다 호출)"""
        try:
            # 포지션 정보 가져오기
            position = self._get_position(trade_id)
            if not position:
                self.logger.warning(f"포지션 정보 없음: {trade_id}")
                return {}
            
            # MDD/MFE 계산
            self._calculate_excursions(position, current_price)
            
            # 스냅샷 저장
            self._save_snapshot(trade_id, current_price, position)
            
            # DB 업데이트
            self._update_trade_record(trade_id, position)
            
            self.logger.debug(f"포지션 업데이트: {trade_id}, 가격: ${current_price}")
            return position
            
        except Exception as e:
            self.logger.error(f"❌ MDD 업데이트 실패 ({trade_id}): {e}")
            return {}
    
    def _get_position(self, trade_id: str) -> Optional[Dict]:
        """포지션 정보 조회 (캐시 또는 DB)"""
        # 캐시 확인
        if trade_id in self.positions:
            return self.positions[trade_id]
        
        # DB에서 조회
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT trade_id, entry_price, direction, stop_loss_price, take_profit_price
                FROM trade_records 
                WHERE trade_id = ? AND exit_time IS NULL
            """, (trade_id,))
            
            row = cursor.fetchone()
            if row:
                position = {
                    'trade_id': row[0],
                    'entry_price': row[1],
                    'direction': row[2],
                    'stop_loss': row[3],
                    'take_profit': row[4],
                    'current_mdd': 0,
                    'current_mfe': 0
                }
                
                # 기존 MDD/MFE 값 조회
                cursor.execute("""
                    SELECT max_adverse_excursion, max_favorable_excursion
                    FROM trade_records WHERE trade_id = ?
                """, (trade_id,))
                
                mdd_row = cursor.fetchone()
                if mdd_row and mdd_row[0] is not None:
                    position['current_mdd'] = mdd_row[0]
                    position['current_mfe'] = mdd_row[1] or 0
                
                # 캐시에 저장
                self.positions[trade_id] = position
                return position
            
            return None
            
        finally:
            conn.close()
    
    def _calculate_excursions(self, position: Dict, current_price: float):
        """MDD/MFE 계산"""
        entry_price = position['entry_price']
        direction = position['direction']
        
        if direction == 'LONG':
            # 최고가 업데이트
            if 'highest' not in position:
                position['highest'] = entry_price
            position['highest'] = max(position['highest'], current_price)
            
            # MDD 계산 (%)
            if position['highest'] > 0:
                drawdown = (position['highest'] - current_price) / position['highest'] * 100
                position['current_mdd'] = max(position.get('current_mdd', 0), drawdown)
            
            # MFE 계산 (%)
            if entry_price > 0:
                position['current_mfe'] = (position['highest'] - entry_price) / entry_price * 100
                
        else:  # SHORT
            # 최저가 업데이트
            if 'lowest' not in position:
                position['lowest'] = entry_price
            position['lowest'] = min(position['lowest'], current_price)
            
            # MDD 계산 (%)
            if position['lowest'] > 0:
                drawdown = (current_price - position['lowest']) / position['lowest'] * 100
                position['current_mdd'] = max(position.get('current_mdd', 0), drawdown)
            
            # MFE 계산 (%)
            if entry_price > 0:
                position['current_mfe'] = (entry_price - position['lowest']) / entry_price * 100
    
    def _save_snapshot(self, trade_id: str, current_price: float, position: Dict):
        """포지션 스냅샷 저장"""
        # PnL 계산
        entry_price = position['entry_price']
        if position['direction'] == 'LONG':
            pnl_percent = (current_price - entry_price) / entry_price * 100
        else:
            pnl_percent = (entry_price - current_price) / entry_price * 100
        
        # 시나리오 상태 체크
        scenario_status = self._check_scenario_status(position, current_price)
        
        # 스냅샷 저장
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO position_snapshots
                (trade_id, timestamp, current_price, pnl_percent, 
                 current_mdd, current_mfe, scenario_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                trade_id,
                datetime.now().isoformat(),
                current_price,
                round(pnl_percent, 2),
                round(position.get('current_mdd', 0), 2),
                round(position.get('current_mfe', 0), 2),
                scenario_status
            ])
            
            conn.commit()
            
        finally:
            conn.close()
    
    def _check_scenario_status(self, position: Dict, current_price: float) -> str:
        """시나리오 진행 상태 체크"""
        direction = position['direction']
        entry_price = position['entry_price']
        stop_loss = position.get('stop_loss', 0)
        take_profit = position.get('take_profit', 0)
        
        # 무효화 체크
        if direction == 'LONG':
            if stop_loss and current_price <= stop_loss:
                return 'invalidated'
            elif take_profit and current_price >= take_profit * 0.95:
                return 'near_target'
        else:  # SHORT
            if stop_loss and current_price >= stop_loss:
                return 'invalidated'
            elif take_profit and current_price <= take_profit * 1.05:
                return 'near_target'
        
        # PnL 기반 상태
        if direction == 'LONG':
            pnl_percent = (current_price - entry_price) / entry_price * 100
        else:
            pnl_percent = (entry_price - current_price) / entry_price * 100
        
        if pnl_percent > 0.5:
            return 'on_track'
        elif pnl_percent < -1.0:
            return 'warning'
        else:
            return 'neutral'
    
    def _update_trade_record(self, trade_id: str, position: Dict):
        """trade_records 테이블의 MDD/MFE 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE trade_records
                SET max_adverse_excursion = ?,
                    max_favorable_excursion = ?
                WHERE trade_id = ?
            """, [
                round(position.get('current_mdd', 0), 2),
                round(position.get('current_mfe', 0), 2),
                trade_id
            ])
            
            conn.commit()
            
        finally:
            conn.close()
    
    def get_position_history(self, trade_id: str) -> List[Dict]:
        """특정 포지션의 스냅샷 히스토리 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT timestamp, current_price, pnl_percent, 
                       current_mdd, current_mfe, scenario_status
                FROM position_snapshots
                WHERE trade_id = ?
                ORDER BY timestamp
            """, (trade_id,))
            
            snapshots = []
            for row in cursor.fetchall():
                snapshots.append({
                    'timestamp': row[0],
                    'price': row[1],
                    'pnl_percent': row[2],
                    'mdd': row[3],
                    'mfe': row[4],
                    'status': row[5]
                })
            
            return snapshots
            
        finally:
            conn.close()
    
    def clear_position_cache(self, trade_id: str):
        """포지션 종료 시 캐시 클리어"""
        if trade_id in self.positions:
            del self.positions[trade_id]
            self.logger.debug(f"포지션 캐시 클리어: {trade_id}")
    
    def get_statistics(self, trade_id: str) -> Dict:
        """포지션의 MDD/MFE 통계"""
        position = self._get_position(trade_id)
        if not position:
            return {}
        
        history = self.get_position_history(trade_id)
        if not history:
            return {
                'current_mdd': position.get('current_mdd', 0),
                'current_mfe': position.get('current_mfe', 0),
                'snapshots': 0
            }
        
        # 통계 계산
        pnls = [h['pnl_percent'] for h in history]
        
        return {
            'current_mdd': position.get('current_mdd', 0),
            'current_mfe': position.get('current_mfe', 0),
            'max_pnl': max(pnls) if pnls else 0,
            'min_pnl': min(pnls) if pnls else 0,
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
            'snapshots': len(history),
            'last_update': history[-1]['timestamp'] if history else None
        }
    
    def analyze_mdd_patterns(self, limit: int = 100) -> Dict:
        """전체 거래의 MDD 패턴 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT direction, outcome, max_adverse_excursion, max_favorable_excursion
                FROM trade_records
                WHERE exit_time IS NOT NULL 
                  AND max_adverse_excursion IS NOT NULL
                ORDER BY exit_time DESC
                LIMIT ?
            """, (limit,))
            
            trades = cursor.fetchall()
            if not trades:
                return {'message': 'MDD 데이터 없음'}
            
            # 방향별/결과별 통계
            stats = {
                'LONG': {'WIN': [], 'LOSS': []},
                'SHORT': {'WIN': [], 'LOSS': []}
            }
            
            for direction, outcome, mdd, mfe in trades:
                if direction in stats and outcome in stats[direction]:
                    stats[direction][outcome].append({
                        'mdd': mdd,
                        'mfe': mfe or 0
                    })
            
            # 평균 계산
            analysis = {}
            for direction in ['LONG', 'SHORT']:
                analysis[direction] = {}
                for outcome in ['WIN', 'LOSS']:
                    trades_list = stats[direction][outcome]
                    if trades_list:
                        mdds = [t['mdd'] for t in trades_list]
                        mfes = [t['mfe'] for t in trades_list]
                        analysis[direction][outcome] = {
                            'count': len(trades_list),
                            'avg_mdd': sum(mdds) / len(mdds),
                            'max_mdd': max(mdds),
                            'avg_mfe': sum(mfes) / len(mfes) if mfes else 0
                        }
            
            return {
                'total_trades': len(trades),
                'analysis': analysis,
                'insights': self._generate_mdd_insights(analysis)
            }
            
        finally:
            conn.close()
    
    def _generate_mdd_insights(self, analysis: Dict) -> List[str]:
        """MDD 분석에서 인사이트 생성"""
        insights = []
        
        # 승리 거래의 평균 MDD 비교
        long_win_mdd = analysis.get('LONG', {}).get('WIN', {}).get('avg_mdd', 0)
        short_win_mdd = analysis.get('SHORT', {}).get('WIN', {}).get('avg_mdd', 0)
        
        if long_win_mdd > 0 and short_win_mdd > 0:
            if long_win_mdd < short_win_mdd:
                insights.append(f"LONG 승리 거래가 SHORT보다 안정적 (MDD: {long_win_mdd:.1f}% vs {short_win_mdd:.1f}%)")
            else:
                insights.append(f"SHORT 승리 거래가 LONG보다 안정적 (MDD: {short_win_mdd:.1f}% vs {long_win_mdd:.1f}%)")
        
        # 패배 거래의 MDD 패턴
        long_loss_mdd = analysis.get('LONG', {}).get('LOSS', {}).get('avg_mdd', 0)
        if long_loss_mdd > 3:
            insights.append(f"LONG 패배 거래의 평균 MDD가 높음 ({long_loss_mdd:.1f}%) - 손절 개선 필요")
        
        return insights