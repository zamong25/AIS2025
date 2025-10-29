"""
바이낸스 거래 내역 동기화 모듈
수동 거래나 시스템 외부 거래를 감지하고 DB와 동기화
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from binance.client import Client
import sqlite3
from decimal import Decimal

class TradeHistorySync:
    """거래 내역 동기화 관리자"""

    def __init__(self, client: Client, db_path: str = None):
        self.client = client

        # db_path가 None이면 절대 경로로 설정
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, 'data', 'database')
            self.db_path = os.path.join(db_dir, 'delphi_trades.db')
        else:
            self.db_path = db_path

        self.logger = logging.getLogger('TradeHistorySync')

        # Binance 서버 시간과 로컬 시간 차이 계산
        self.time_offset = self._calculate_time_offset()
        
    def sync_recent_trades(self, symbol: str = "SOLUSDT", hours: int = 24) -> Dict:
        """
        최근 거래 내역을 바이낸스에서 조회하고 DB와 동기화

        Returns:
            동기화 결과 리포트
        """
        try:
            self.logger.debug(f"🔄 {symbol} 최근 {hours}시간 거래 내역 동기화 시작")

            # 1. 바이낸스에서 거래 내역 조회
            # startTime과 endTime은 UTC 절대 시간 (offset 적용 안 함)
            # client.timestamp_offset이 자동으로 API 요청 timestamp에 적용됨
            from datetime import timezone
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            end_time = current_time_ms
            start_time = current_time_ms - (hours * 3600 * 1000)

            # API 호출 with timeout handling
            try:
                self.logger.info(f"Binance API 호출 중... (symbol={symbol}, hours={hours})")
                trades = self.client.futures_account_trades(
                    symbol=symbol,
                    startTime=start_time,
                    endTime=end_time,
                    limit=1000
                )
                self.logger.info(f"Binance API 응답 받음: {len(trades)}개 거래")
            except Exception as api_error:
                # 이모지 없이 로깅 (유니코드 에러 방지)
                self.logger.error(f"[ERROR] Binance API call failed: {str(api_error)}")
                return {
                    'error': f'Binance API call failed: {str(api_error)}',
                    'trades_found': 0,
                    'pending_trades': 0,
                    'matched_trades': 0
                }
            
            self.logger.debug(f"📊 바이낸스에서 {len(trades)}개 거래 조회됨")
            
            # 2. DB의 PENDING 거래 조회
            pending_trades = self._get_pending_trades(symbol)
            self.logger.debug(f"📋 DB에서 {len(pending_trades)}개 PENDING 거래 발견")
            
            # 3. 거래 매칭 및 업데이트
            sync_report = {
                'trades_found': len(trades),
                'pending_trades': len(pending_trades),
                'matched_trades': 0,
                'updated_trades': [],
                'unmatched_trades': []
            }
            
            # 거래를 포지션별로 그룹화
            position_groups = self._group_trades_by_position(trades)
            
            # 각 PENDING 거래에 대해 매칭 시도
            for pending in pending_trades:
                matched = self._match_and_update_trade(pending, position_groups)
                if matched:
                    sync_report['matched_trades'] += 1
                    sync_report['updated_trades'].append(matched)
                else:
                    sync_report['unmatched_trades'].append(pending['trade_id'])
            
            # 4. 수동으로 열린 새 포지션 감지
            new_positions = self._detect_manual_positions(trades, pending_trades)
            if new_positions:
                self.logger.warning(f"⚠️ {len(new_positions)}개의 수동 포지션 감지됨")
                sync_report['manual_positions'] = new_positions
            
            self.logger.debug(f"✅ 동기화 완료: {sync_report['matched_trades']}개 거래 업데이트")
            return sync_report
            
        except Exception as e:
            self.logger.error(f"❌ 거래 내역 동기화 실패: {e}")
            return {'error': str(e)}
    
    def _group_trades_by_position(self, trades: List[Dict]) -> Dict:
        """거래를 포지션별로 그룹화"""
        positions = {}
        current_position = None
        
        # 시간순 정렬
        sorted_trades = sorted(trades, key=lambda x: x['time'])
        
        for trade in sorted_trades:
            side = trade['side']
            qty = float(trade['qty'])
            
            if current_position is None:
                # 새 포지션 시작
                current_position = {
                    'start_time': trade['time'],
                    'direction': 'LONG' if side == 'BUY' else 'SHORT',
                    'entry_trades': [trade],
                    'exit_trades': [],
                    'net_qty': qty if side == 'BUY' else -qty
                }
            else:
                # 기존 포지션에 추가
                if (current_position['direction'] == 'LONG' and side == 'BUY') or \
                   (current_position['direction'] == 'SHORT' and side == 'SELL'):
                    # 같은 방향 = 추가 진입
                    current_position['entry_trades'].append(trade)
                    current_position['net_qty'] += qty if side == 'BUY' else -qty
                else:
                    # 반대 방향 = 청산
                    current_position['exit_trades'].append(trade)
                    current_position['net_qty'] -= qty if side == 'SELL' else -qty
                    
                    # 포지션 완전 청산됨
                    if abs(current_position['net_qty']) < 0.001:
                        current_position['end_time'] = trade['time']
                        position_key = f"{current_position['start_time']}_{current_position['direction']}"
                        positions[position_key] = current_position
                        current_position = None
        
        # 아직 열려있는 포지션
        if current_position and abs(current_position['net_qty']) > 0.001:
            position_key = f"{current_position['start_time']}_{current_position['direction']}"
            positions[position_key] = current_position
            
        return positions
    
    def _match_and_update_trade(self, pending_trade: Dict, position_groups: Dict) -> Optional[Dict]:
        """PENDING 거래와 실제 거래 매칭 및 DB 업데이트"""
        try:
            # 진입 시간 기준으로 매칭
            entry_time = datetime.fromisoformat(pending_trade['entry_time'].replace('Z', '+00:00'))
            entry_timestamp = int(entry_time.timestamp() * 1000)
            
            # 시간 오차 허용 (5분)
            time_tolerance = 5 * 60 * 1000
            
            for pos_key, position in position_groups.items():
                # 방향 일치 확인
                if position['direction'] != pending_trade['direction']:
                    continue
                    
                # 시간 매칭
                if abs(position['start_time'] - entry_timestamp) < time_tolerance:
                    # 매칭됨!
                    if position.get('exit_trades'):
                        # 청산됨
                        exit_trade = position['exit_trades'][-1]  # 마지막 청산
                        exit_price = float(exit_trade['price'])
                        exit_time = datetime.fromtimestamp(exit_trade['time'] / 1000)
                        
                        # 손익 계산
                        entry_price = pending_trade['entry_price']
                        if entry_price > 0:  # 0으로 나누기 방지
                            if pending_trade['direction'] == 'LONG':
                                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                            else:
                                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
                        else:
                            pnl_percent = 0.0
                            self.logger.warning(f"⚠️ 진입가가 0인 거래 발견: {pending_trade['trade_id']}")
                        
                        # DB 업데이트
                        self._update_trade_record(
                            trade_id=pending_trade['trade_id'],
                            exit_price=exit_price,
                            exit_time=exit_time.isoformat(),
                            pnl_percent=pnl_percent,
                            outcome='MANUAL_EXIT'
                        )
                        
                        return {
                            'trade_id': pending_trade['trade_id'],
                            'exit_price': exit_price,
                            'exit_time': exit_time.isoformat(),
                            'pnl_percent': pnl_percent
                        }
                    
            return None
            
        except Exception as e:
            self.logger.error(f"매칭 중 오류: {e}")
            return None
    
    def _get_pending_trades(self, symbol: str) -> List[Dict]:
        """DB에서 PENDING 거래 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT trade_id, entry_price, direction, entry_time,
                       position_size_percent, leverage
                FROM trade_records 
                WHERE asset = ? AND outcome = 'PENDING'
                ORDER BY entry_time DESC
            """, (symbol,))
            
            trades = []
            for row in cursor.fetchall():
                trades.append({
                    'trade_id': row[0],
                    'entry_price': row[1],
                    'direction': row[2],
                    'entry_time': row[3],
                    'position_size': row[4],
                    'leverage': row[5]
                })
                
            conn.close()
            return trades
            
        except Exception as e:
            self.logger.error(f"DB 조회 오류: {e}")
            return []
    
    def _update_trade_record(self, trade_id: str, exit_price: float, 
                           exit_time: str, pnl_percent: float, outcome: str):
        """거래 기록 업데이트"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE trade_records 
                SET exit_price = ?, exit_time = ?, pnl_percent = ?, 
                    outcome = ?, updated_at = ?
                WHERE trade_id = ?
            """, (exit_price, exit_time, pnl_percent, outcome, 
                  datetime.utcnow().isoformat(), trade_id))
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"✅ 거래 업데이트: {trade_id} (손익: {pnl_percent:.2f}%)")
            
        except Exception as e:
            self.logger.error(f"DB 업데이트 오류: {e}")
    
    def _detect_manual_positions(self, trades: List[Dict], pending_trades: List[Dict]) -> List[Dict]:
        """시스템에 기록되지 않은 수동 포지션 감지"""
        manual_positions = []
        
        # 포지션 그룹화
        position_groups = self._group_trades_by_position(trades)
        
        # PENDING 거래의 시간 목록
        pending_times = [
            int(datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00')).timestamp() * 1000)
            for t in pending_trades
        ]
        
        for pos_key, position in position_groups.items():
            # 시스템 거래와 매칭되지 않는 포지션
            is_manual = True
            for pending_time in pending_times:
                if abs(position['start_time'] - pending_time) < 5 * 60 * 1000:  # 5분 오차
                    is_manual = False
                    break
                    
            # net_qty가 0에 가까우면 포지션이 닫힌 것으로 판단
            is_closed = abs(position.get('net_qty', 0)) < 0.001
            
            if is_manual and not is_closed:
                # 24시간 이내 포지션만 감지
                current_time = datetime.now().timestamp() * 1000
                position_age_hours = (current_time - position['start_time']) / (1000 * 3600)
                
                if position_age_hours <= 24:
                    entry_trades = position['entry_trades']
                    total_qty = sum(float(t['qty']) for t in entry_trades)
                    if total_qty > 0:  # 0으로 나누기 방지
                        avg_entry_price = sum(float(t['price']) * float(t['qty']) for t in entry_trades) / total_qty
                    else:
                        avg_entry_price = 0.0
                        self.logger.warning(f"⚠️ 수량이 0인 포지션 발견")
                    
                    manual_positions.append({
                        'direction': position['direction'],
                        'entry_time': datetime.fromtimestamp(position['start_time'] / 1000).isoformat(),
                        'entry_price': avg_entry_price,
                        'quantity': total_qty,
                        'is_closed': False
                    })
                else:
                    self.logger.debug(f"오래된 포지션 무시: {position_age_hours:.1f}시간 경과")

        return manual_positions

    def _calculate_time_offset(self) -> int:
        """
        Binance 서버 시간과 로컬 시간의 차이를 계산하여 timestamp 오류 방지
        여러 번 측정하여 중간값 사용 (네트워크 지연 보정)

        Returns:
            int: 시간 차이 (밀리초)
        """
        try:
            from datetime import timezone
            import time

            # 3번 측정하여 중간값 사용 (네트워크 지연 보정)
            offsets = []
            for i in range(3):
                # 요청 전 시간 기록
                before_request = int(datetime.now(timezone.utc).timestamp() * 1000)

                # Binance 서버 시간 가져오기
                server_time = self.client.get_server_time()
                server_time_ms = server_time['serverTime']

                # 요청 후 시간 기록
                after_request = int(datetime.now(timezone.utc).timestamp() * 1000)

                # 중간 시간 계산 (네트워크 지연 보정)
                local_time_ms = (before_request + after_request) // 2
                time_offset = server_time_ms - local_time_ms

                offsets.append(time_offset)

                # 마지막 측정이 아니면 짧은 대기
                if i < 2:
                    time.sleep(0.1)

            # 중간값 사용 (극단값 제거)
            offsets.sort()
            time_offset = offsets[1]  # 3개 중 중간값

            # Binance client의 timestamp_offset도 설정
            self.client.timestamp_offset = time_offset

            self.logger.info(f"[TIME_SYNC] 시간 동기화 완료: offset = {time_offset}ms ({time_offset/1000:.2f}초)")
            self.logger.debug(f"[TIME_SYNC] 측정된 offset 값들: {offsets}")

            return time_offset

        except Exception as e:
            self.logger.warning(f"[TIME_SYNC] 시간 동기화 실패, offset=0 사용: {e}")
            return 0