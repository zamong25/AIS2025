"""
델파이 트레이딩 시스템 - OCO (One-Cancels-Other) 주문 관리자
고급 리스크 관리를 위한 OCO 주문 시스템
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone
from binance.client import Client
from binance.enums import *
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.discord_notifier import discord_notifier

# 로거 설정
logger = logging.getLogger('OCOOrderManager')

class OCOOrderManager:
    """OCO 주문 생성 및 관리 클래스"""
    
    def __init__(self, client: Client, testnet: bool = False):
        """
        OCO 주문 관리자 초기화
        
        Args:
            client: 바이낸스 클라이언트
            testnet: 테스트넷 여부
        """
        self.client = client
        self.testnet = testnet
        self.active_oco_orders = {}  # OCO 주문 추적
        self.order_history = []      # 주문 히스토리
        
        logger.info(f"📋 OCO 주문 관리자 초기화 ({'테스트넷' if testnet else '메인넷'})")
    
    def create_oco_order(self, symbol: str, side: str, quantity: float, 
                        stop_price: float, stop_limit_price: float, 
                        limit_price: float, position_id: str = None) -> Dict:
        """
        OCO 주문 생성
        
        Args:
            symbol: 거래 심볼 (예: BTCUSDT)
            side: 주문 방향 (BUY/SELL)
            quantity: 주문 수량
            stop_price: 손절 트리거 가격
            stop_limit_price: 손절 리미트 가격
            limit_price: 익절 리미트 가격
            position_id: 포지션 ID (추적용)
            
        Returns:
            OCO 주문 결과 딕셔너리
        """
        try:
            # 수량 정밀도 조정 (SOL의 경우 소수점 2자리)
            if symbol == "SOLUSDT":
                quantity = round(quantity, 2)
                logger.info(f"📊 SOL 수량 정밀도 조정: {quantity}")
            
            logger.info(f"📋 OCO 주문 생성 시도: {symbol} {side} {quantity}")
            
            # 1. 주문 파라미터 검증
            validation_result = self._validate_oco_parameters(
                symbol, side, quantity, stop_price, stop_limit_price, limit_price
            )
            
            if not validation_result['valid']:
                return {
                    'status': 'validation_failed',
                    'error': validation_result['error'],
                    'oco_order_id': None
                }
            
            # 2. 테스트넷에서는 시뮬레이션 모드
            if self.testnet:
                return self._create_simulated_oco_order(
                    symbol, side, quantity, stop_price, stop_limit_price, 
                    limit_price, position_id
                )
            
            # 3. 실제 OCO 주문 생성 (메인넷)
            oco_order = self.client.create_oco_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=str(limit_price),           # 익절 리미트 가격
                stopPrice=str(stop_price),        # 손절 트리거 가격
                stopLimitPrice=str(stop_limit_price),  # 손절 리미트 가격
                stopLimitTimeInForce=TIME_IN_FORCE_GTC
            )
            
            # 4. OCO 주문 정보 저장
            oco_order_id = oco_order['orderListId']
            
            oco_info = {
                'oco_order_id': oco_order_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'stop_price': stop_price,
                'stop_limit_price': stop_limit_price,
                'limit_price': limit_price,
                'position_id': position_id,
                'status': 'ACTIVE',
                'created_time': datetime.now(timezone.utc).isoformat(),
                'orders': oco_order['orders'],
                'raw_response': oco_order
            }
            
            self.active_oco_orders[oco_order_id] = oco_info
            self.order_history.append(oco_info.copy())
            
            # 5. Discord 알림
            try:
                discord_notifier.send_alert(
                    f"📋 OCO 주문 생성 완료\n"
                    f"심볼: {symbol}\n"
                    f"방향: {side}\n"
                    f"수량: {quantity}\n"
                    f"익절가: ${limit_price:,.2f}\n"
                    f"손절가: ${stop_limit_price:,.2f}\n"
                    f"OCO ID: {oco_order_id}",
                    level="info"
                )
            except Exception as e:
                logger.warning(f"Discord 알림 실패: {e}")
            
            logger.info(f"✅ OCO 주문 생성 성공: ID {oco_order_id}")
            
            return {
                'status': 'success',
                'oco_order_id': oco_order_id,
                'oco_info': oco_info
            }
            
        except Exception as e:
            logger.error(f"❌ OCO 주문 생성 실패: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'oco_order_id': None
            }
    
    def _validate_oco_parameters(self, symbol: str, side: str, quantity: float,
                                stop_price: float, stop_limit_price: float, 
                                limit_price: float) -> Dict:
        """OCO 주문 파라미터 검증"""
        try:
            # 1. 기본 파라미터 검증
            if not all([symbol, side, quantity > 0, stop_price > 0, 
                       stop_limit_price > 0, limit_price > 0]):
                return {
                    'valid': False,
                    'error': '필수 파라미터가 누락되었거나 잘못되었습니다'
                }
            
            # 2. 방향 검증
            if side not in [SIDE_BUY, SIDE_SELL]:
                return {
                    'valid': False,
                    'error': f'잘못된 주문 방향: {side}'
                }
            
            # 3. 가격 로직 검증
            current_price = self._get_current_price(symbol)
            if not current_price:
                return {
                    'valid': False,
                    'error': f'현재가 조회 실패: {symbol}'
                }
            
            # SELL OCO의 경우: 익절가 > 현재가 > 손절가
            # BUY OCO의 경우: 손절가 > 현재가 > 익절가
            if side == SIDE_SELL:
                if not (limit_price > current_price > stop_price):
                    return {
                        'valid': False,
                        'error': f'SELL OCO 가격 순서 오류: 익절({limit_price}) > 현재가({current_price}) > 손절({stop_price})'
                    }
                # 손절 리미트 가격은 손절 트리거 가격보다 낮아야 함
                if stop_limit_price > stop_price:
                    return {
                        'valid': False,
                        'error': f'손절 리미트가 트리거보다 높음: {stop_limit_price} > {stop_price}'
                    }
            else:  # BUY
                if not (stop_price > current_price > limit_price):
                    return {
                        'valid': False,
                        'error': f'BUY OCO 가격 순서 오류: 손절({stop_price}) > 현재가({current_price}) > 익절({limit_price})'
                    }
                # 손절 리미트 가격은 손절 트리거 가격보다 높아야 함
                if stop_limit_price < stop_price:
                    return {
                        'valid': False,
                        'error': f'손절 리미트가 트리거보다 낮음: {stop_limit_price} < {stop_price}'
                    }
            
            # 4. 심볼 정보 검증
            symbol_info = self._get_symbol_info(symbol)
            if not symbol_info:
                return {
                    'valid': False,
                    'error': f'심볼 정보 조회 실패: {symbol}'
                }
            
            # 5. 수량 필터 검증
            min_qty = symbol_info.get('min_qty', 0)
            step_size = symbol_info.get('step_size', 0)
            
            if quantity < min_qty:
                return {
                    'valid': False,
                    'error': f'최소 주문 수량 미달: {quantity} < {min_qty}'
                }
            
            # 수량이 step_size의 배수인지 확인
            if step_size > 0:
                remainder = (quantity - min_qty) % step_size
                if abs(remainder) > 1e-8:  # 부동소수점 오차 허용
                    return {
                        'valid': False,
                        'error': f'수량이 step_size({step_size})의 배수가 아님: {quantity}'
                    }
            
            return {'valid': True, 'error': None}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'검증 중 오류: {str(e)}'
            }
    
    def _create_simulated_oco_order(self, symbol: str, side: str, quantity: float,
                                  stop_price: float, stop_limit_price: float,
                                  limit_price: float, position_id: str = None) -> Dict:
        """테스트넷용 OCO 주문 시뮬레이션"""
        try:
            # 가상 OCO 주문 ID 생성
            oco_order_id = f"SIMULATED_OCO_{int(time.time())}"
            
            # 시뮬레이션 주문 정보
            simulated_orders = [
                {
                    'symbol': symbol,
                    'orderId': f"LIMIT_{int(time.time())}",
                    'side': side,
                    'type': 'LIMIT',
                    'quantity': str(quantity),
                    'price': str(limit_price),
                    'status': 'NEW'
                },
                {
                    'symbol': symbol,
                    'orderId': f"STOP_LOSS_LIMIT_{int(time.time()) + 1}",
                    'side': side,
                    'type': 'STOP_LOSS_LIMIT',
                    'quantity': str(quantity),
                    'price': str(stop_limit_price),
                    'stopPrice': str(stop_price),
                    'status': 'NEW'
                }
            ]
            
            oco_info = {
                'oco_order_id': oco_order_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'stop_price': stop_price,
                'stop_limit_price': stop_limit_price,
                'limit_price': limit_price,
                'position_id': position_id,
                'status': 'SIMULATED',
                'created_time': datetime.now(timezone.utc).isoformat(),
                'orders': simulated_orders,
                'simulation_mode': True
            }
            
            self.active_oco_orders[oco_order_id] = oco_info
            self.order_history.append(oco_info.copy())
            
            # Discord 알림
            try:
                discord_notifier.send_alert(
                    f"🧪 OCO 주문 시뮬레이션\n"
                    f"심볼: {symbol}\n"
                    f"방향: {side}\n"
                    f"수량: {quantity}\n"
                    f"익절가: ${limit_price:,.2f}\n"
                    f"손절가: ${stop_limit_price:,.2f}\n"
                    f"시뮬레이션 ID: {oco_order_id}",
                    level="info"
                )
            except Exception as e:
                logger.warning(f"Discord 알림 실패: {e}")
            
            logger.info(f"🧪 OCO 주문 시뮬레이션 생성: {oco_order_id}")
            
            return {
                'status': 'simulated',
                'oco_order_id': oco_order_id,
                'oco_info': oco_info
            }
            
        except Exception as e:
            logger.error(f"❌ OCO 시뮬레이션 생성 실패: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'oco_order_id': None
            }
    
    def monitor_oco_orders(self) -> Dict:
        """활성 OCO 주문들 모니터링"""
        try:
            monitoring_results = {
                'active_count': len(self.active_oco_orders),
                'completed_orders': [],
                'cancelled_orders': [],
                'error_orders': [],
                'still_active': []
            }
            
            if not self.active_oco_orders:
                return monitoring_results
            
            logger.info(f"📋 {len(self.active_oco_orders)}개 OCO 주문 모니터링 중...")
            
            for oco_id, oco_info in list(self.active_oco_orders.items()):
                try:
                    if oco_info.get('simulation_mode'):
                        # 시뮬레이션 모드는 별도 처리
                        monitoring_results['still_active'].append(oco_id)
                        continue
                    
                    # 실제 OCO 주문 상태 조회
                    oco_status = self.client.get_oco_order(orderListId=oco_id)
                    
                    list_status = oco_status['listStatusType']
                    
                    if list_status == 'EXEC_STARTED':
                        # 하나의 주문이 체결되어 다른 주문이 취소됨
                        executed_order = None
                        cancelled_order = None
                        
                        for order in oco_status['orders']:
                            if order['status'] == 'FILLED':
                                executed_order = order
                            elif order['status'] == 'CANCELED':
                                cancelled_order = order
                        
                        if executed_order:
                            self._handle_oco_execution(oco_id, oco_info, executed_order, cancelled_order)
                            monitoring_results['completed_orders'].append({
                                'oco_id': oco_id,
                                'executed_order': executed_order,
                                'cancelled_order': cancelled_order
                            })
                            
                            # 활성 목록에서 제거
                            del self.active_oco_orders[oco_id]
                    
                    elif list_status == 'ALL_DONE':
                        # 모든 주문이 완료됨 (취소 포함)
                        monitoring_results['cancelled_orders'].append(oco_id)
                        del self.active_oco_orders[oco_id]
                    
                    else:
                        # 여전히 활성 상태
                        monitoring_results['still_active'].append(oco_id)
                
                except Exception as e:
                    logger.error(f"❌ OCO 주문 {oco_id} 모니터링 실패: {e}")
                    monitoring_results['error_orders'].append({
                        'oco_id': oco_id,
                        'error': str(e)
                    })
            
            # 결과 로깅
            if monitoring_results['completed_orders']:
                logger.info(f"✅ {len(monitoring_results['completed_orders'])}개 OCO 주문 체결 완료")
            
            if monitoring_results['cancelled_orders']:
                logger.info(f"🚫 {len(monitoring_results['cancelled_orders'])}개 OCO 주문 취소됨")
            
            return monitoring_results
            
        except Exception as e:
            logger.error(f"❌ OCO 주문 모니터링 실패: {e}")
            return {'error': str(e)}
    
    def _handle_oco_execution(self, oco_id: str, oco_info: Dict, 
                            executed_order: Dict, cancelled_order: Dict):
        """OCO 주문 체결 처리"""
        try:
            executed_type = executed_order['type']
            execution_price = float(executed_order['price'])
            
            # 체결 유형 판단 (익절 vs 손절)
            if executed_type == 'LIMIT':
                execution_type = '익절'
                alert_level = 'success'
            else:  # STOP_LOSS_LIMIT
                execution_type = '손절'
                alert_level = 'warning'
            
            # Discord 알림
            try:
                discord_notifier.send_alert(
                    f"🎯 OCO 주문 체결: {execution_type}\n"
                    f"심볼: {oco_info['symbol']}\n"
                    f"체결가: ${execution_price:,.2f}\n"
                    f"수량: {executed_order['executedQty']}\n"
                    f"체결 시간: {executed_order.get('updateTime', 'N/A')}\n"
                    f"OCO ID: {oco_id}",
                    level=alert_level
                )
            except Exception as e:
                logger.warning(f"Discord 알림 실패: {e}")
            
            logger.info(f"🎯 OCO {execution_type} 체결: {oco_info['symbol']} @ ${execution_price:,.2f}")
            
            # 체결 정보를 oco_info에 추가
            oco_info.update({
                'execution_type': execution_type,
                'execution_price': execution_price,
                'executed_quantity': float(executed_order['executedQty']),
                'execution_time': executed_order.get('updateTime'),
                'status': 'EXECUTED'
            })
            
        except Exception as e:
            logger.error(f"❌ OCO 체결 처리 실패: {e}")
    
    def cancel_oco_order(self, oco_order_id: str) -> Dict:
        """OCO 주문 취소"""
        try:
            if oco_order_id not in self.active_oco_orders:
                return {
                    'status': 'not_found',
                    'message': f'OCO 주문 {oco_order_id}를 찾을 수 없습니다'
                }
            
            oco_info = self.active_oco_orders[oco_order_id]
            
            # 시뮬레이션 모드
            if oco_info.get('simulation_mode'):
                oco_info['status'] = 'CANCELLED'
                del self.active_oco_orders[oco_order_id]
                
                logger.info(f"🧪 OCO 시뮬레이션 취소: {oco_order_id}")
                return {
                    'status': 'simulated_cancelled',
                    'message': f'OCO 시뮬레이션 {oco_order_id} 취소됨'
                }
            
            # 실제 취소
            cancel_result = self.client.cancel_oco_order(
                symbol=oco_info['symbol'],
                orderListId=oco_order_id
            )
            
            oco_info['status'] = 'CANCELLED'
            oco_info['cancelled_time'] = datetime.now(timezone.utc).isoformat()
            del self.active_oco_orders[oco_order_id]
            
            # Discord 알림
            try:
                discord_notifier.send_alert(
                    f"🚫 OCO 주문 취소\n"
                    f"심볼: {oco_info['symbol']}\n"
                    f"OCO ID: {oco_order_id}",
                    level="warning"
                )
            except Exception as e:
                logger.warning(f"Discord 알림 실패: {e}")
            
            logger.info(f"🚫 OCO 주문 취소 완료: {oco_order_id}")
            
            return {
                'status': 'cancelled',
                'cancel_result': cancel_result
            }
            
        except Exception as e:
            logger.error(f"❌ OCO 주문 취소 실패: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """현재 시장가 조회"""
        try:
            # 선물 거래이므로 futures_ticker 사용
            ticker = self.client.futures_ticker(symbol=symbol)
            return float(ticker['lastPrice'])  # 'price'가 아니라 'lastPrice' 사용
        except Exception as e:
            logger.error(f"❌ 현재가 조회 실패 {symbol}: {e}")
            return None
    
    def _get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """심볼 정보 조회"""
        try:
            exchange_info = self.client.get_exchange_info()
            
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    # LOT_SIZE 필터에서 수량 정보 추출
                    min_qty = None
                    step_size = None
                    
                    for filter_info in s['filters']:
                        if filter_info['filterType'] == 'LOT_SIZE':
                            min_qty = float(filter_info['minQty'])
                            step_size = float(filter_info['stepSize'])
                            break
                    
                    return {
                        'symbol': symbol,
                        'status': s['status'],
                        'min_qty': min_qty,
                        'step_size': step_size
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 심볼 정보 조회 실패 {symbol}: {e}")
            return None
    
    def get_oco_status_report(self) -> str:
        """OCO 주문 현황 보고서"""
        try:
            active_count = len(self.active_oco_orders)
            total_history = len(self.order_history)
            
            report = f"""
📋 OCO 주문 관리자 현황
{'='*40}
🔄 활성 OCO 주문: {active_count}개
📊 총 주문 히스토리: {total_history}개
🧪 테스트넷 모드: {'예' if self.testnet else '아니오'}

"""
            
            if self.active_oco_orders:
                report += "🔄 활성 OCO 주문 목록:\n"
                for oco_id, oco_info in self.active_oco_orders.items():
                    status_icon = "🧪" if oco_info.get('simulation_mode') else "💰"
                    report += f"  {status_icon} {oco_id}: {oco_info['symbol']} {oco_info['side']}\n"
                    report += f"     익절: ${oco_info['limit_price']:,.2f} | 손절: ${oco_info['stop_limit_price']:,.2f}\n"
            
            # 최근 완료된 주문들
            completed_orders = [o for o in self.order_history if o.get('status') in ['EXECUTED', 'CANCELLED']]
            if completed_orders:
                recent_completed = completed_orders[-3:]  # 최근 3개
                report += f"\n📈 최근 완료된 OCO 주문 ({len(recent_completed)}개):\n"
                for order in recent_completed:
                    status_icon = "✅" if order.get('status') == 'EXECUTED' else "🚫"
                    report += f"  {status_icon} {order['oco_order_id']}: {order['symbol']}\n"
            
            return report
            
        except Exception as e:
            return f"❌ OCO 현황 보고서 생성 실패: {e}"