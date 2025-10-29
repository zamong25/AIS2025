"""
델파이 트레이딩 시스템 - 거래 실행 모듈
신디사이저의 플레이북을 바이낸스 API로 실제 거래 실행
"""

import os
import logging
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv
from pathlib import Path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.trade_database import save_completed_trade, generate_trade_id
from data.trade_analyzer import trade_analyzer
from trading.oco_order_manager import OCOOrderManager
from trading.slippage_fee_calculator import slippage_fee_calculator, TradingSide, OrderType
from data.trading_context import trading_context
from trading.position_state_manager import init_position_manager
from trading.trade_history_sync import TradeHistorySync
from utils.discord_notifier import discord_notifier

# 환경 변수 로드 (config/.env)
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "config" / ".env")

# 로거 설정
logger = logging.getLogger(__name__)

class TradeExecutor:
    """실제 거래 실행을 담당하는 클래스"""
    
    def __init__(self, testnet: bool = False):
        """
        거래 실행기 초기화
        Args:
            testnet: True시 테스트넷 사용, False시 실제 거래
        """
        if testnet:
            self.api_key = os.getenv('BINANCE_TESTNET_API_KEY')
            self.api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY')
            self.client = Client(
                self.api_key,
                self.api_secret,
                testnet=True,
                requests_params={'timeout': 30}  # 30초 타임아웃
            )
            logger.debug("TESTNET 모드로 거래 실행기 초기화")
        else:
            self.api_key = os.getenv('BINANCE_API_KEY')
            self.api_secret = os.getenv('BINANCE_API_SECRET')
            self.client = Client(
                self.api_key,
                self.api_secret,
                requests_params={'timeout': 30}  # 30초 타임아웃
            )
            logger.debug("MAINNET 모드로 거래 실행기 초기화")

        # Binance 서버 시간 동기화
        self._sync_server_time()

        self.current_position = None
        self.testnet = testnet
        
        # OCO 주문 관리자 초기화
        self.oco_manager = OCOOrderManager(self.client, testnet)
        
        # Position State Manager 초기화
        self.position_manager = init_position_manager(self.client)
        
        # 거래 내역 동기화 관리자 초기화
        self.trade_sync = TradeHistorySync(self.client)
        
        # 프로그램 시작 시 거래 내역 동기화 및 포지션 복구
        self._sync_and_recover_on_startup()

    def _sync_server_time(self):
        """
        Binance 서버 시간 동기화하여 timestamp 오류 방지
        여러 번 측정하여 평균값 사용 (네트워크 지연 보정)
        """
        try:
            from datetime import datetime, timezone
            import time

            # 3번 측정하여 중간값 사용 (네트워크 지연 보정)
            offsets = []
            for i in range(3):
                # 요청 전 시간 기록
                before_request = int(datetime.now(timezone.utc).timestamp() * 1000)

                # 서버 시간 조회
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

            # Binance client의 timestamp_offset 설정
            self.client.timestamp_offset = time_offset

            logger.info(f"[TIME_SYNC] Binance 서버 시간 동기화 완료: offset = {time_offset}ms ({time_offset/1000:.2f}초)")
            logger.debug(f"[TIME_SYNC] 측정된 offset 값들: {offsets}")

        except Exception as e:
            logger.warning(f"[TIME_SYNC] 서버 시간 동기화 실패, offset=0 사용: {e}")
            self.client.timestamp_offset = 0

    def execute_synthesizer_playbook(self, playbook: Dict, agent_reports: Dict) -> Dict:
        """
        신디사이저 플레이북을 바탕으로 실제 거래 실행
        
        Args:
            playbook: 신디사이저가 생성한 거래 플레이북
            agent_reports: 4개 에이전트 보고서
            
        Returns:
            거래 실행 결과 딕셔너리
        """
        try:
            # V2와 기존 형식 모두 지원
            decision = playbook['final_decision'].get('action') or playbook['final_decision'].get('decision')
            
            if not decision:
                logger.error("❌ final_decision에 action 또는 decision 키가 없습니다")
                return {'status': 'error', 'error': 'Missing action/decision in final_decision'}
            
            if decision == "HOLD":
                logger.info("📊 신디사이저 결정: HOLD - 거래 실행하지 않음")
                return {'status': 'hold', 'reason': playbook['final_decision']['rationale']}
            
            if decision == "CLOSE_POSITION":
                logger.info("📊 신디사이저 결정: CLOSE_POSITION - 현재 포지션 청산")
                return self._close_current_position(playbook['final_decision']['rationale'], agent_reports)
            
            if decision == "HOLD_POSITION":
                logger.info("📊 신디사이저 결정: HOLD_POSITION - 현재 포지션 유지")
                return {'status': 'hold_position', 'reason': playbook['final_decision']['rationale']}
            
            if decision == "ADJUST_STOP":
                logger.info("📊 신디사이저 결정: ADJUST_STOP - 손절가 조정")
                return self._adjust_stop_loss(playbook, agent_reports)
            
            if decision == "ADJUST_TARGETS":
                logger.info("📊 신디사이저 결정: ADJUST_TARGETS - 익절가 조정")
                return self._adjust_take_profit(playbook, agent_reports)
            
            if decision == "ADJUST_BOTH":
                logger.info("📊 신디사이저 결정: ADJUST_BOTH - 손절가와 익절가 모두 조정")
                # 먼저 손절가 조정
                stop_result = self._adjust_stop_loss(playbook, agent_reports)
                if stop_result['status'] != 'adjusted':
                    return stop_result
                # 이어서 익절가 조정
                tp_result = self._adjust_take_profit(playbook, agent_reports)
                return {
                    'status': 'both_adjusted',
                    'stop_loss': stop_result,
                    'take_profit': tp_result
                }
            
            if decision == "ADJUST_POSITION":
                # 환경 변수 확인
                if os.getenv('ENABLE_POSITION_ADJUSTMENT', 'false').lower() != 'true':
                    logger.warning("⚠️ ADJUST_POSITION 기능이 비활성화되어 있습니다")
                    return {'status': 'disabled', 'reason': 'Position adjustment feature is disabled'}
                logger.info("📊 신디사이저 결정: ADJUST_POSITION - 포지션 크기 조정")
                return self._adjust_position_size(playbook, agent_reports)
            
            if decision in ["BUY", "SELL", "LONG", "SHORT"]:
                return self._execute_trade(playbook, agent_reports)
            
            # 알 수 없는 decision 처리
            logger.error(f"❌ 알 수 없는 거래 결정: {decision}")
            return {'status': 'error', 'error': f'Unknown decision: {decision}'}
            
        except Exception as e:
            logger.error(f"❌ 플레이북 실행 중 오류: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _cancel_all_open_orders(self, symbol: str):
        """심볼의 모든 열린 주문 취소"""
        try:
            # 모든 열린 주문 조회
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            
            if open_orders:
                logger.info(f"🔄 기존 주문 {len(open_orders)}개 취소 중...")
                for order in open_orders:
                    try:
                        self.client.futures_cancel_order(
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        logger.info(f"✅ 주문 취소됨: {order['type']} @ ${order.get('price', 'N/A')}")
                    except Exception as e:
                        logger.warning(f"⚠️ 주문 취소 실패: {e}")
                
                # 잠시 대기하여 취소 처리 확실히 하기
                time.sleep(0.5)
            else:
                logger.info("📋 취소할 기존 주문 없음")
                
        except Exception as e:
            logger.warning(f"⚠️ 기존 주문 조회/취소 중 오류: {e}")
    
    def _cancel_stop_orders_only(self, symbol: str) -> int:
        """손절 주문만 선택적으로 취소
        
        Returns:
            취소된 주문 수
        """
        try:
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            cancelled_count = 0
            
            for order in open_orders:
                # STOP_MARKET 타입만 취소 (손절 주문)
                if order['type'] == 'STOP_MARKET':
                    try:
                        self.client.futures_cancel_order(
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        logger.info(f"✅ 손절 주문 취소됨: {order['type']} @ ${order.get('stopPrice', 'N/A')}")
                        cancelled_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️ 손절 주문 취소 실패: {e}")
            
            if cancelled_count > 0:
                time.sleep(0.5)  # 취소 처리 대기
                
            return cancelled_count
            
        except Exception as e:
            logger.error(f"❌ 손절 주문 조회 중 오류: {e}")
            return 0
    
    def _cancel_take_profit_orders_only(self, symbol: str) -> int:
        """익절 주문만 선택적으로 취소
        
        Returns:
            취소된 주문 수
        """
        try:
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            cancelled_count = 0
            
            for order in open_orders:
                # LIMIT 타입만 취소 (익절 주문)
                if order['type'] == 'LIMIT':
                    try:
                        self.client.futures_cancel_order(
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        logger.info(f"✅ 익절 주문 취소됨: {order['type']} @ ${order.get('price', 'N/A')}")
                        cancelled_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️ 익절 주문 취소 실패: {e}")
            
            if cancelled_count > 0:
                time.sleep(0.5)  # 취소 처리 대기
                
            return cancelled_count
            
        except Exception as e:
            logger.error(f"❌ 익절 주문 조회 중 오류: {e}")
            return 0
    
    def _execute_trade(self, playbook: Dict, agent_reports: Dict) -> Dict:
        """실제 거래 주문 실행"""
        try:
            # 기존 포지션 확인
            current_pos = self.position_manager.get_current_position()
            if current_pos:
                logger.warning(f"⚠️ 이미 포지션이 존재합니다: {current_pos['direction']} {current_pos['quantity']}")
                
                # 같은 방향이면 추가 진입 경고
                # trade_direction이 없을 경우 action에서 유추
                execution_plan = playbook.get('execution_plan', {})
                if 'trade_direction' in execution_plan:
                    new_direction = execution_plan['trade_direction']
                else:
                    action = playbook.get('final_decision', {}).get('action', '')
                    new_direction = 'LONG' if action == 'BUY' else 'SHORT' if action == 'SELL' else None
                
                if new_direction and current_pos['direction'] == new_direction:
                    logger.error(f"❌ 동일 방향 추가 진입 시도 차단: 기존 {current_pos['direction']} vs 신규 {new_direction}")
                    return {
                        'status': 'blocked',
                        'error': f"이미 {current_pos['direction']} 포지션이 존재합니다. 포지션 중복을 방지하기 위해 거래를 차단했습니다.",
                        'existing_position': current_pos
                    }
                else:
                    # 반대 방향이면 기존 포지션 청산 후 진행
                    logger.info("🔄 반대 방향 신호 - 기존 포지션 청산 후 진행")
                    close_result = self._close_current_position("반대 방향 신호로 인한 포지션 전환")
                    if close_result['status'] != 'success':
                        return close_result
            execution_plan = playbook['execution_plan']
            # 심볼 결정 (기본값: SOLUSDT, 추후 확장 가능)
            symbol = execution_plan.get('symbol', 'SOLUSDT')
            
            # 기존 주문 취소 (새 거래 전에 정리)
            self._cancel_all_open_orders(symbol)
            
            # 거래 방향 결정
            if 'trade_direction' in execution_plan:
                direction = execution_plan['trade_direction']  # LONG/SHORT
            else:
                # final_decision.action에서 방향 유추
                action = playbook['final_decision']['action']
                direction = 'LONG' if action == 'BUY' else 'SHORT'
            side = SIDE_BUY if direction == "LONG" else SIDE_SELL
            trading_side = TradingSide.BUY if direction == "LONG" else TradingSide.SELL
            
            # 진입 가격 및 수량 계산
            entry_price = execution_plan.get('entry_price', 0)
            quantity = self._calculate_quantity(
                symbol=symbol,
                capital_percent=execution_plan.get('position_sizing', {}).get('percent_of_capital', execution_plan.get('position_size_percent', 20)),
                leverage=execution_plan.get('position_sizing', {}).get('leverage', execution_plan.get('leverage', 1)),
                entry_price=entry_price
            )
            
            # 수량이 0이면 자본금 부족으로 거래 중단
            if quantity == 0:
                try:
                    account = self.client.futures_account()
                    balance = float(account.get('availableBalance', 0))
                except:
                    balance = 0
                error_msg = f"자본금 부족으로 최소 주문 금액을 충족할 수 없습니다. (현재 잔고: ${balance:.2f})"
                logger.error(f"❌ {error_msg}")
                return {'status': 'failed', 'error': error_msg}
            
            # 거래 비용 사전 계산
            if 'risk_management' in execution_plan:
                exit_price = execution_plan['risk_management']['take_profit_1_price']
            else:
                exit_price = execution_plan.get('take_profit_1', 0)
            trade_cost = slippage_fee_calculator.calculate_trade_costs(
                symbol=symbol,
                side=trading_side,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                order_type=OrderType.MARKET,
                holding_time_hours=24.0
            )
            
            # 비용 효율성 분석
            expected_profit_pct = abs((exit_price - entry_price) / entry_price * 100)
            cost_analysis = slippage_fee_calculator.analyze_cost_efficiency(
                trade_cost, expected_profit_pct
            )
            
            # 높은 비용시 알림 및 거래 검토
            if not cost_analysis.get('is_cost_efficient', False):
                slippage_fee_calculator.send_cost_alert(
                    trade_cost, symbol, quantity * entry_price
                )
                logger.warning(f"⚠️ 높은 거래 비용: {trade_cost.cost_percentage:.2f}%")
            
            logger.info(f"💰 거래 비용 분석: {slippage_fee_calculator.get_cost_summary(trade_cost)}")
            
            # 주문 타입 확인 (STOP 또는 MARKET)
            order_type = execution_plan.get('order_type', 'MARKET')
            limit_price = execution_plan.get('limit_price', None)  # STOP_LIMIT을 위한 지정가
            
            # 주문 실행
            order_result = self._place_futures_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=entry_price,
                leverage=execution_plan.get('position_sizing', {}).get('leverage', execution_plan.get('leverage', 1)),
                direction=direction,
                order_type=order_type,
                limit_price=limit_price
            )
            
            if order_result['status'] == 'success':
                # 실제 체결 가격과 예상 가격 비교하여 슬리피지 데이터 업데이트
                actual_price = order_result.get('actual_price', entry_price)
                slippage_fee_calculator.update_slippage_data(
                    symbol, entry_price, actual_price, trading_side
                )
                
                # 실제 거래 비용 재계산 (체결 가격 기준)
                actual_trade_cost = slippage_fee_calculator.calculate_trade_costs(
                    symbol=symbol,
                    side=trading_side,
                    quantity=quantity,
                    entry_price=actual_price,
                    exit_price=exit_price,
                    order_type=OrderType.MARKET,
                    holding_time_hours=24.0
                )
                
                # STOP 주문은 대기 중이므로 OCO 주문을 나중에 생성
                if order_result.get('pending', False):
                    oco_result = {
                        'status': 'pending',
                        'message': 'STOP 주문이 체결될 때까지 OCO 주문 생성 대기',
                        'oco_orders': []
                    }
                else:
                    # MARKET 주문은 즉시 OCO 주문 생성
                    oco_result = self._create_oco_exit_orders(
                        symbol=symbol,
                        direction=direction,
                        quantity=quantity,
                        entry_price=actual_price,  # 실제 체결가 사용
                        stop_loss=execution_plan.get('risk_management', {}).get('stop_loss_price', execution_plan.get('stop_loss', 0)),
                        take_profit_1=execution_plan.get('risk_management', {}).get('take_profit_1_price', execution_plan.get('take_profit_1', 0)),
                        take_profit_2=execution_plan.get('risk_management', {}).get('take_profit_2_price', execution_plan.get('take_profit_2', 0))
                    )
                
                # 포지션 추적 정보 저장
                self.current_position = {
                    'trade_id': generate_trade_id(),
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': actual_price,  # 실제 체결가 저장
                    'expected_entry_price': entry_price,  # 예상 가격도 저장
                    'quantity': quantity,
                    'leverage': execution_plan.get('position_sizing', {}).get('leverage', execution_plan.get('leverage', 1)),
                    'stop_loss': execution_plan.get('risk_management', {}).get('stop_loss_price', execution_plan.get('stop_loss', 0)),
                    'take_profit_1': execution_plan.get('risk_management', {}).get('take_profit_1_price', execution_plan.get('take_profit_1', 0)),
                    'take_profit_2': execution_plan.get('risk_management', {}).get('take_profit_2_price', execution_plan.get('take_profit_2', 0)),
                    'entry_time': datetime.now(timezone.utc).isoformat(),
                    'agent_reports': agent_reports,
                    'playbook': playbook,
                    'oco_orders': oco_result.get('oco_orders', []),
                    'trade_cost': {
                        'expected_cost': trade_cost.__dict__,
                        'actual_cost': actual_trade_cost.__dict__
                    },
                    'order_type': order_result.get('order_type', 'MARKET'),
                    'order_id': order_result.get('order_id'),
                    'pending': order_result.get('pending', False),
                    'pending_order_id': order_result.get('order_id') if order_result.get('pending', False) else None,
                    'oco_created': False if order_result.get('pending', False) else True
                }
                
                # Trading Thesis 생성 (거래 연속성을 위한 컨텍스트)
                try:
                    thesis = trading_context.create_thesis_from_playbook(
                        trade_id=self.current_position['trade_id'],
                        playbook=playbook,
                        agent_reports=agent_reports
                    )
                    
                    # 실제 체결가로 업데이트
                    trading_context.update_entry_price(actual_price)
                    
                    logger.info("📋 Trading Thesis 생성 완료 - 거래 연속성 유지됨")
                except Exception as e:
                    logger.warning(f"⚠️ Trading Thesis 생성 실패: {e}")
                
                # PENDING 저장 제거 - 시스템 설계상 청산 시에만 저장
                
                if order_result.get('pending', False):
                    logger.info(f"⏳ STOP 주문 생성 성공: {direction} {symbol} @ ${entry_price} (트리거 대기)")
                else:
                    logger.info(f"✅ 거래 실행 성공: {direction} {symbol} @ ${actual_price}")
                
                # Discord 알림 발송
                try:
                    # 포지션 가치 계산
                    position_value = quantity * actual_price
                    
                    # 손절/익절 퍼센트 계산
                    if direction == "LONG":
                        stop_loss_price = execution_plan.get('risk_management', {}).get('stop_loss_price', execution_plan.get('stop_loss', 0))
                        take_profit_1_price = execution_plan.get('risk_management', {}).get('take_profit_1_price', execution_plan.get('take_profit_1', 0))
                        take_profit_2_price = execution_plan.get('risk_management', {}).get('take_profit_2_price', execution_plan.get('take_profit_2', 0))
                        stop_loss_percent = ((stop_loss_price - actual_price) / actual_price) * 100
                        take_profit_1_percent = ((take_profit_1_price - actual_price) / actual_price) * 100
                        take_profit_2_percent = ((take_profit_2_price - actual_price) / actual_price) * 100
                    else:  # SHORT
                        stop_loss_price = execution_plan.get('risk_management', {}).get('stop_loss_price', execution_plan.get('stop_loss', 0))
                        take_profit_1_price = execution_plan.get('risk_management', {}).get('take_profit_1_price', execution_plan.get('take_profit_1', 0))
                        take_profit_2_price = execution_plan.get('risk_management', {}).get('take_profit_2_price', execution_plan.get('take_profit_2', 0))
                        stop_loss_percent = ((actual_price - stop_loss_price) / actual_price) * 100
                        take_profit_1_percent = ((actual_price - take_profit_1_price) / actual_price) * 100
                        take_profit_2_percent = ((actual_price - take_profit_2_price) / actual_price) * 100
                    
                    # 최대 손실 계산
                    max_loss_usd = abs(stop_loss_percent / 100 * position_value)
                    
                    trade_alert_info = {
                        'direction': direction,
                        'symbol': symbol,
                        'entry_price': actual_price,
                        'quantity': quantity,
                        'leverage': execution_plan.get('position_sizing', {}).get('leverage', execution_plan.get('leverage', 1)),
                        'position_value': position_value,
                        'position_size_percent': execution_plan.get('position_sizing', {}).get('percent_of_capital', execution_plan.get('position_size_percent', 20)),
                        'stop_loss': stop_loss_price,
                        'stop_loss_percent': stop_loss_percent,
                        'take_profit_1': take_profit_1_price,
                        'take_profit_1_percent': take_profit_1_percent,
                        'take_profit_2': take_profit_2_price,
                        'take_profit_2_percent': take_profit_2_percent,
                        'max_loss_usd': max_loss_usd,
                        'trade_id': self.current_position['trade_id']
                        # 'is_exploration': 제거됨 - 더 이상 탐험모드 개념 사용 안함
                    }
                    
                    discord_notifier.send_trade_alert(trade_alert_info, alert_type="execution")
                except Exception as e:
                    logger.warning(f"⚠️ Discord 알림 발송 실패: {e}")
                
                # PENDING 거래 정리 제거 - 시스템 설계상 PENDING 상태를 사용하지 않음
                
                return {
                    'status': 'executed',
                    'trade_id': self.current_position['trade_id'],
                    'order_id': order_result['order_id'],
                    'position': self.current_position,
                    'entry_price': actual_price  # 실제 체결가 추가
                }
            else:
                logger.error(f"❌ 거래 실행 실패: {order_result['error']}")
                return {'status': 'failed', 'error': order_result['error']}
                
        except Exception as e:
            logger.error(f"❌ 거래 실행 중 예외 발생: {e}")
            return {'status': 'error', 'error': str(e)}
    
    
    def _calculate_quantity(self, symbol: str, capital_percent: float, leverage: float, entry_price: float) -> float:
        """포지션 크기 계산 (최소 주문 금액 체크 포함)"""
        try:
            # 계좌 잔고 조회
            account = self.client.futures_account()
            available_balance = float(account['availableBalance'])
            
            # 사용할 자본 계산
            capital_to_use = available_balance * (capital_percent / 100)
            
            # 레버리지 적용한 명목 포지션 크기
            notional_size = capital_to_use * leverage
            
            # 수량 계산 (가격 대비)
            quantity = notional_size / entry_price
            
            # 마진 사전 체크
            required_margin = (quantity * entry_price) / leverage
            if required_margin > available_balance:
                logger.warning(f"⚠️ 계산된 마진이 가용 잔고 초과: 필요 ${required_margin:.2f} > 가용 ${available_balance:.2f}")
                # 가용 잔고의 95%로 재계산
                capital_to_use = available_balance * 0.95
                notional_size = capital_to_use * leverage
                quantity = notional_size / entry_price
                logger.info(f"🔄 마진에 맞춰 수량 재계산: {quantity:.3f}")
            
            # 심볼별 최소 주문 단위 및 최소 주문 금액 확인
            min_notional = 10.0  # 기본값 10 USDT
            step_size = 0.001    # 기본값
            
            symbol_info = self.client.futures_exchange_info()
            for s in symbol_info['symbols']:
                if s['symbol'] == symbol:
                    # 필터에서 최소 주문 금액 찾기
                    for f in s['filters']:
                        if f['filterType'] == 'MIN_NOTIONAL':
                            min_notional = float(f['notional'])
                        elif f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                    break
            
            # 최소 주문 금액 체크
            current_notional = quantity * entry_price
            if current_notional < min_notional:
                logger.warning(f"⚠️ 최소 주문 금액 미달: {current_notional:.2f} USDT < {min_notional} USDT")
                
                # 최소 주문 금액에 맞춰 수량 조정
                min_quantity = (min_notional * 1.1) / entry_price  # 10% 여유 추가
                
                # 자본금 비율 재계산
                adjusted_capital_percent = (min_notional * 1.1) / (available_balance * leverage) * 100
                
                if adjusted_capital_percent > 100:
                    # 자본금이 부족한 경우
                    logger.error(f"❌ 자본금 부족: 최소 주문을 위해 {adjusted_capital_percent:.1f}% 필요")
                    return 0
                else:
                    logger.info(f"🔄 포지션 크기 조정: {capital_percent:.1f}% → {adjusted_capital_percent:.1f}%")
                    quantity = min_quantity
            
            # 수량을 최소 단위에 맞춰 조정
            # step_size의 소수점 자리수 계산 (더 안전한 방법)
            if '.' in str(step_size):
                decimal_places = len(str(step_size).rstrip('0').split('.')[-1])
            else:
                decimal_places = 0
            
            quantity = round(quantity / step_size) * step_size
            # 부동소수점 오류 방지를 위해 명시적으로 반올림
            quantity = round(quantity, decimal_places)
            
            # 최종 확인 로그
            final_notional = quantity * entry_price
            logger.info(f"💰 최종 주문: {quantity} {symbol.replace('USDT', '')} = {final_notional:.2f} USDT (정밀도: {decimal_places}자리)")
            
            return quantity
            
        except Exception as e:
            logger.error(f"❌ 수량 계산 실패: {e}")
            return 0
    
    def _sync_and_recover_on_startup(self):
        """프로그램 시작 시 거래 내역 동기화 및 포지션 복구"""
        try:
            # 1. 먼저 거래 내역 동기화 (최근 24시간)
            logger.info("🔄 거래 내역 동기화 시작...")
            sync_report = self.trade_sync.sync_recent_trades(hours=24)
            
            if sync_report.get('matched_trades', 0) > 0:
                logger.info(f"✅ {sync_report['matched_trades']}개 거래 동기화 완료")
            
            if sync_report.get('manual_positions'):
                logger.warning(f"⚠️ {len(sync_report['manual_positions'])}개 수동 포지션 감지")
                
        except Exception as e:
            logger.error(f"❌ 거래 내역 동기화 실패: {e}")
            
        # 2. 포지션 복구 (기존 로직)
        self._recover_position_on_startup()
    
    def _recover_position_on_startup(self):
        """프로그램 시작 시 기존 포지션 복구"""
        try:
            # Position State Manager에서 현재 포지션 조회
            position = self.position_manager.get_current_position()
            
            if position:
                logger.info("🔄 기존 포지션 감지 및 복구 시작")
                
                # 메모리에 포지션 정보 복구
                self.current_position = {
                    'symbol': position['symbol'],
                    'direction': position['direction'],
                    'entry_price': position['entry_price'],
                    'quantity': position['quantity'],
                    'leverage': position['leverage'],
                    'trade_id': position.get('trade_id', position.get('db_trade_id', 'RECOVERED')),
                    'entry_time': position.get('context_entry_time', position.get('db_entry_time', datetime.utcnow().isoformat())),
                    'has_context': position.get('has_context', False)
                }
                
                # 손절/익절 정보 복구
                if position.get('stop_loss', 0) > 0:
                    self.current_position['stop_loss'] = position['stop_loss']
                if position.get('target_price', 0) > 0:
                    self.current_position['take_profit_1'] = position['target_price']
                    
                # 포지션 상태 동기화
                sync_report = self.position_manager.sync_position_state()
                if sync_report.get('discrepancies'):
                    logger.warning(f"⚠️ 포지션 불일치 발견: {sync_report['discrepancies']}")
                    
                logger.info(f"✅ 포지션 복구 완료: {position['direction']} {position['quantity']} @ ${position['entry_price']}")
                logger.info(f"   현재 손익: {position['pnl_percent']:.2f}% (${position['unrealized_pnl']:.2f})")
                
                # Trading Context가 있으면 추가 정보 로깅
                if position.get('has_context'):
                    logger.info(f"   Trading Context 존재: {position.get('trade_id')}")
                    logger.info(f"   진입 사유: {position.get('entry_reason', 'N/A')[:50]}...")
                else:
                    logger.warning("   ⚠️ Trading Context 없음 - 거래 연속성 제한적")
                    
            else:
                logger.info("📊 복구할 기존 포지션 없음")
                self.current_position = None
                
        except Exception as e:
            logger.error(f"❌ 포지션 복구 중 오류: {e}")
            self.current_position = None
    
    def _place_futures_order(self, symbol: str, side: str, quantity: float, price: float, leverage: float, direction: str, order_type: str = "MARKET", limit_price: float = None) -> Dict:
        """선물 주문 실행"""
        try:
            # 레버리지 설정
            self.client.futures_change_leverage(symbol=symbol, leverage=int(leverage))
            
            # 마진 타입 설정 (ISOLATED)
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType=FUTURE_MARGIN_TYPE_ISOLATED)
            except:
                pass  # 이미 설정되어 있을 수 있음
            
            # 심볼별 정밀도 가져오기 (마진 체크 전에 먼저 수행)
            step_size = 0.001  # 기본값
            min_qty = 0.001
            try:
                symbol_info = self.client.futures_exchange_info()
                for s in symbol_info['symbols']:
                    if s['symbol'] == symbol:
                        for f in s['filters']:
                            if f['filterType'] == 'LOT_SIZE':
                                step_size = float(f['stepSize'])
                                min_qty = float(f['minQty'])
                        break
            except:
                pass
            
            # 주문 전 마진 체크
            required_margin = (quantity * price) / leverage
            account = self.client.futures_account()
            available_margin = float(account.get('availableBalance', 0))
            
            if required_margin > available_margin:
                logger.warning(f"⚠️ 마진 부족: 필요 ${required_margin:.2f} > 가용 ${available_margin:.2f}")
                # 가용 마진으로 가능한 수량 재계산
                max_quantity = (available_margin * leverage * 0.95) / price  # 5% 여유
                
                # 정밀도에 맞춰 수량 조정
                max_quantity = round(max_quantity / step_size) * step_size
                
                if max_quantity >= min_qty and max_quantity * price >= 10:  # 최소 수량 및 주문금액 체크
                    logger.info(f"🔄 마진 부족으로 수량 자동 조정: {quantity:.3f} → {max_quantity:.3f}")
                    quantity = max_quantity
                else:
                    return {'status': 'failed', 'error': f'마진 부족 (필요: ${required_margin:.2f}, 가용: ${available_margin:.2f}, 최소주문금액: $10)'}
            
            # 주문 전 최종 수량 정밀도 검증
            try:
                # step_size로 한번 더 반올림하여 부동소수점 오류 방지
                if '.' in str(step_size):
                    decimal_places = len(str(step_size).rstrip('0').split('.')[-1])
                else:
                    decimal_places = 0
                quantity = round(quantity, decimal_places)
                logger.info(f"📊 최종 주문 수량: {quantity} (정밀도: {decimal_places}자리)")
            except Exception as e:
                # 오류시 소수점 2자리로 기본 설정
                quantity = round(quantity, 2)
                logger.info(f"📊 최종 주문 수량: {quantity} (기본 정밀도: 2자리, 오류: {e})")
            
            # 주문 타입에 따른 주문 실행
            if order_type == "STOP" or order_type == "STOP_MARKET":
                # STOP_MARKET 주문 사용
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=FUTURE_ORDER_TYPE_STOP_MARKET,
                    stopPrice=price,  # 트리거 가격
                    quantity=quantity,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"🛑 STOP_MARKET 주문 생성: {side} {quantity} @ ${price} (trigger)")
            elif order_type == "STOP_LIMIT":
                # STOP_LIMIT 주문 사용 (트리거 가격과 지정가 모두 필요)
                # limit_price가 제공되지 않으면 stop_price에서 약간의 슬리피지 허용
                if limit_price is None:
                    if direction == "LONG":
                        limit_price = price * 1.001  # 0.1% 슬리피지 허용
                    else:  # SHORT
                        limit_price = price * 0.999  # 0.1% 슬리피지 허용
                
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=FUTURE_ORDER_TYPE_STOP,
                    stopPrice=price,  # 트리거 가격
                    price=limit_price,  # 지정가
                    quantity=quantity,
                    positionSide="LONG" if direction == "LONG" else "SHORT",
                    timeInForce='GTC'  # Good Till Cancelled
                )
                logger.info(f"🎯 STOP_LIMIT 주문 생성: {side} {quantity} @ ${price} (trigger) / ${limit_price} (limit)")
            elif order_type == "LIMIT":
                # LIMIT 주문 사용
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=FUTURE_ORDER_TYPE_LIMIT,
                    price=price,  # 지정가
                    quantity=quantity,
                    positionSide="LONG" if direction == "LONG" else "SHORT",
                    timeInForce='GTC'
                )
                logger.info(f"📌 LIMIT 주문 생성: {side} {quantity} @ ${price}")
            else:
                # MARKET 주문 (default)
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=FUTURE_ORDER_TYPE_MARKET,
                    quantity=quantity,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"💵 MARKET 주문 실행: {side} {quantity}")
            
            # 주문 타입별 처리
            if order_type in ["STOP", "STOP_MARKET", "STOP_LIMIT", "LIMIT"]:
                # 대기 주문들은 트리거/체결될 때까지 대기
                logger.info(f"⏳ {order_type} 주문 대기 중: Order ID {order['orderId']}")
                return {
                    'status': 'success',
                    'order_id': order['orderId'],
                    'order': order,
                    'actual_price': price,  # 대기 주문은 설정 가격을 임시로 사용
                    'order_type': order_type,
                    'pending': True
                }
            else:
                # MARKET 주문은 즉시 체결되므로 실제 가격 확인
                order_info = self.client.futures_get_order(
                    symbol=symbol,
                    orderId=order['orderId']
                )
                
                # 실제 체결 평균 가격 계산
                if order_info['status'] == 'FILLED':
                    actual_price = float(order_info['avgPrice'])
                else:
                    actual_price = price  # 체결되지 않은 경우 예상 가격 사용
                
                return {
                    'status': 'success',
                    'order_id': order['orderId'],
                    'order': order,
                    'actual_price': actual_price,
                    'order_type': 'MARKET',
                    'pending': False
                }
            
        except Exception as e:
            logger.error(f"❌ 선물 주문 실행 실패: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def _set_stop_loss_take_profit(self, symbol: str, direction: str, quantity: float,
                                 stop_loss: float, take_profit_1: float, take_profit_2: float):
        """손절매 및 익절 주문 설정"""
        try:
            # 가격 정밀도 조정 (SOL은 소수점 2자리)
            if symbol == "SOLUSDT":
                stop_loss = round(stop_loss, 2) if stop_loss > 0 else 0
                take_profit_1 = round(take_profit_1, 2) if take_profit_1 > 0 else 0
                take_profit_2 = round(take_profit_2, 2) if take_profit_2 > 0 else 0
            
            # 손절매 주문
            if stop_loss > 0:
                stop_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
                self.client.futures_create_order(
                    symbol=symbol,
                    side=stop_side,
                    type=FUTURE_ORDER_TYPE_STOP_MARKET,
                    quantity=quantity,
                    stopPrice=str(stop_loss),
                    timeInForce=TIME_IN_FORCE_GTC,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"🛑 손절매 주문 설정: ${stop_loss}")
            
            # 1차 익절 주문 (50% 물량)
            if take_profit_1 > 0:
                tp1_quantity = round(quantity * 0.5, 2)  # 수량도 정밀도 조정
                tp1_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp1_side,
                    type=FUTURE_ORDER_TYPE_LIMIT,
                    quantity=tp1_quantity,
                    price=str(take_profit_1),
                    timeInForce=TIME_IN_FORCE_GTC,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"🎯 1차 익절 주문 설정: ${take_profit_1}")
            
            # 2차 익절 주문 (나머지 50% 물량)
            if take_profit_2 > 0:
                tp2_quantity = round(quantity * 0.5, 2)  # 수량도 정밀도 조정
                tp2_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp2_side,
                    type=FUTURE_ORDER_TYPE_LIMIT,
                    quantity=tp2_quantity,
                    price=str(take_profit_2),
                    timeInForce=TIME_IN_FORCE_GTC,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"🎯 2차 익절 주문 설정: ${take_profit_2}")
                
        except Exception as e:
            logger.error(f"❌ 손절/익절 주문 설정 실패: {e}")
    
    def _create_oco_exit_orders(self, symbol: str, direction: str, quantity: float,
                              entry_price: float, stop_loss: float, 
                              take_profit_1: float, take_profit_2: float) -> Dict:
        """OCO 주문을 사용한 출구 전략 설정"""
        try:
            # Binance Futures는 OCO를 지원하지 않으므로 직접 개별 주문으로 처리
            logger.info("📋 Futures 거래는 OCO 대신 개별 손절/익절 주문으로 설정")
            return self._fallback_to_separate_orders(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2
            )
            
        except Exception as e:
            logger.error(f"❌ 출구 주문 설정 실패: {e}")
            # 오류 시 기존 방식으로 대체
            return self._fallback_to_separate_orders(symbol, direction, quantity, stop_loss, take_profit_1, take_profit_2)
    
    def _place_limit_order(self, symbol: str, side: str, quantity: float, 
                          price: float, direction: str, order_type: str = "리미트") -> Dict:
        """단순 리미트 주문 생성"""
        try:
            if self.testnet:
                # 테스트넷에서는 시뮬레이션
                order_id = f"SIMULATED_LIMIT_{int(time.time())}"
                logger.info(f"🧪 {order_type} 주문 시뮬레이션: {symbol} {side} {quantity} @ ${price}")
                return {
                    'status': 'success',
                    'order_id': order_id,
                    'simulation': True
                }
            
            # 가격 정밀도 조정 (SOL은 소수점 2자리)
            if symbol == "SOLUSDT":
                price = round(price, 2)
            
            # 실제 리미트 주문
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=str(price),
                positionSide="LONG" if direction == "LONG" else "SHORT"
            )
            
            logger.info(f"✅ {order_type} 주문 생성: {symbol} @ ${price}")
            return {
                'status': 'success',
                'order_id': order['orderId'],
                'order': order
            }
            
        except Exception as e:
            logger.error(f"❌ {order_type} 주문 생성 실패: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _fallback_to_separate_orders(self, symbol: str, direction: str, quantity: float,
                                   stop_loss: float, take_profit_1: float, take_profit_2: float) -> Dict:
        """OCO 실패시 기존 방식으로 대체"""
        try:
            logger.warning("⚠️ OCO 주문 실패, 개별 주문으로 대체")
            
            # 기존 방식으로 손절/익절 주문 설정
            self._set_stop_loss_take_profit(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2
            )
            
            return {
                'status': 'fallback_success',
                'oco_orders': [],
                'message': '개별 손절/익절 주문으로 설정됨'
            }
            
        except Exception as e:
            logger.error(f"❌ 대체 주문 설정도 실패: {e}")
            return {
                'status': 'failed',
                'oco_orders': [],
                'message': f'모든 출구 주문 설정 실패: {str(e)}'
            }
    
    def _get_current_price(self, symbol: str) -> float:
        """현재 시장가 조회"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"❌ 현재가 조회 실패: {e}")
            return 0
    
    def monitor_position(self) -> Optional[Dict]:
        """현재 포지션 모니터링 및 상태 업데이트 (OCO 주문 포함)"""
        # Position State Manager에서 현재 포지션 확인
        position = self.position_manager.get_current_position()
        if not position:
            return None
            
        # 메모리 상태와 동기화
        if not self.current_position and position:
            # 메모리에 없지만 Position State Manager에 있다면 복구
            self._recover_position_on_startup()
            
        if not self.current_position:
            return None
        
        try:
            symbol = position['symbol']
            
            # LIMIT 주문 체결 확인 (OCO 생성 전)
            if self.current_position.get('pending') and not self.current_position.get('oco_created'):
                pending_order_id = self.current_position.get('pending_order_id')
                if pending_order_id:
                    logger.debug(f"🔍 LIMIT 주문 체결 확인 중... Order ID: {pending_order_id}")
                    is_filled = self._check_order_filled(symbol, pending_order_id)
                    if is_filled:
                        logger.info(f"✅ LIMIT 주문 체결 확인! OCO 주문 생성 시작...")
                        self._create_oco_for_filled_limit()
            
            # OCO 주문 모니터링
            oco_monitoring = self.oco_manager.monitor_oco_orders()
            
            # 현재 포지션 상태 조회
            positions = self.client.futures_position_information(symbol=symbol)
            current_pos = None
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    current_pos = pos
                    break
            
            if not current_pos:
                # 포지션이 종료됨 - 거래 완료 처리
                return self._handle_position_closed()
            
            # 포지션이 여전히 열려있음
            current_price = self._get_current_price(symbol)
            unrealized_pnl = float(current_pos['unRealizedProfit'])
            
            # 포지션 정보 업데이트
            self.current_position.update({
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'last_update': datetime.now(timezone.utc).isoformat(),
                'oco_status': oco_monitoring  # OCO 주문 상태 추가
            })
            
            # OCO 주문이 체결되었는지 확인
            if oco_monitoring.get('completed_orders'):
                logger.info(f"🎯 OCO 주문 체결 감지: {len(oco_monitoring['completed_orders'])}개")
                
                # Discord 알림
                try:
                    from utils.discord_notifier import discord_notifier
                    for completed in oco_monitoring['completed_orders']:
                        executed_order = completed.get('executed_order', {})
                        execution_type = '익절' if executed_order.get('type') == 'LIMIT' else '손절'
                        
                        discord_notifier.send_alert(
                            f"🎯 {execution_type} 주문 체결!\n"
                            f"심볼: {symbol}\n"
                            f"체결가: ${float(executed_order.get('price', 0)):,.2f}\n"
                            f"수량: {executed_order.get('executedQty', 'N/A')}\n"
                            f"미실현 손익: ${unrealized_pnl:,.2f}",
                            level='success' if execution_type == '익절' else 'warning'
                        )
                except:
                    pass
            
            return {
                'status': 'active',
                'position': self.current_position,
                'unrealized_pnl': unrealized_pnl,
                'oco_monitoring': oco_monitoring
            }
            
        except Exception as e:
            logger.error(f"❌ 포지션 모니터링 실패: {e}")
            return None
    
    def _handle_position_closed(self) -> Dict:
        """포지션 종료 처리 및 거래 기록 저장"""
        try:
            if not self.current_position:
                return {'status': 'no_position'}
            
            # 거래 기록을 데이터베이스에 저장
            exit_data = {
                'price': self._get_current_price(self.current_position['symbol']),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'max_drawdown': 0  # 실제로는 추적해야 함
            }
            
            entry_data = {
                'asset': self.current_position['symbol'],
                'price': self.current_position['entry_price'],
                'direction': self.current_position['direction'],
                'leverage': self.current_position['leverage'],
                'position_size_percent': self.current_position.get('position_size_percent', 0),
                'timestamp': self.current_position['entry_time'],
                'stop_loss': self.current_position['stop_loss'],
                'take_profit': self.current_position['take_profit_1'],
                'market_conditions': {},  # 실제로는 진입 시점 데이터
                'agent_scores': {
                    'chartist_score': 50,  # 실제로는 agent_reports에서 추출
                    'journalist_score': 5
                }
            }
            
            # Phase 1: 메타데이터 포함 거래 기록 저장
            from data.trade_database import trade_db
            
            # 기본 거래 데이터
            trade_data = {
                'trade_id': self.current_position['trade_id'],
                'asset': self.current_position['symbol'],
                'entry_price': self.current_position['entry_price'],
                'exit_price': exit_data['price'],
                'direction': self.current_position['direction'],
                'leverage': self.current_position['leverage'],
                'position_size_percent': self.current_position.get('position_size_percent', 0),
                'entry_time': self.current_position['entry_time'],
                'exit_time': exit_data['timestamp'],
                'outcome': exit_data['outcome'],
                'pnl_percent': exit_data['pnl_percent'],
                'stop_loss_price': self.current_position['stop_loss'],
                'take_profit_price': self.current_position['take_profit_1']
            }
            
            # 에이전트 신호 데이터
            agent_signals = self.current_position.get('agent_reports', {})
            
            # 메타데이터와 함께 저장
            trade_db.save_trade_with_metadata(trade_data, agent_signals)
            
            # 기존 함수도 호출 (호환성 유지)
            save_completed_trade(entry_data, exit_data, self.current_position['agent_reports'])
            
            # 거래 성과 분석 실행 (자동 청산의 경우)
            try:
                pnl_percent = ((exit_data['price'] - entry_data['price']) / entry_data['price']) * 100
                if entry_data['direction'] == "SHORT":
                    pnl_percent = -pnl_percent
                
                trade_data_for_analysis = {
                    'trade_id': self.current_position['trade_id'],
                    'symbol': entry_data['asset'],
                    'direction': entry_data['direction'],
                    'entry_price': entry_data['price'],
                    'exit_price': exit_data['price'],
                    'pnl_percent': pnl_percent,
                    'entry_time': entry_data['timestamp'],
                    'exit_time': exit_data['timestamp'],
                    'reason': 'automatic_exit',
                    'leverage': entry_data['leverage']
                }
                
                analysis_result = trade_analyzer.analyze_completed_trade(
                    trade_data_for_analysis, 
                    self.current_position['agent_reports']
                )
                
                if analysis_result:
                    logger.info(f"📊 자동 청산 거래 분석 완료: {analysis_result.analysis_type}")
                
                # 스마트 라벨링 추가
                try:
                    label_result = trade_db.label_completed_trade(self.current_position['trade_id'])
                    if label_result:
                        logger.info(f"🏷️ 거래 라벨링 완료: {self.current_position['trade_id']}")
                    else:
                        logger.warning(f"⚠️ 거래 라벨링 실패: {self.current_position['trade_id']}")
                except Exception as label_error:
                    logger.warning(f"⚠️ 거래 라벨링 중 오류: {label_error}")
                    
            except Exception as e:
                logger.warning(f"⚠️ 자동 청산 거래 분석 중 오류: {e}")
            
            completed_position = self.current_position.copy()
            self.current_position = None
            
            # Trading Context 클리어 (거래 연속성 종료)
            try:
                trading_context.clear_context()
                logger.info("📋 Trading Context 클리어됨")
            except Exception as e:
                logger.warning(f"⚠️ Trading Context 클리어 실패: {e}")
            
            logger.info(f"✅ 포지션 종료 완료: {completed_position['trade_id']}")
            
            # Discord 알림 발송 (자동 청산)
            try:
                # 손익 계산
                if completed_position['direction'] == "LONG":
                    pnl_percent = ((exit_data['price'] - completed_position['entry_price']) / completed_position['entry_price']) * 100
                else:  # SHORT
                    pnl_percent = ((completed_position['entry_price'] - exit_data['price']) / completed_position['entry_price']) * 100
                
                pnl_usd = (pnl_percent / 100) * (completed_position.get('quantity', 0) * completed_position['entry_price'])
                
                # 거래 시간 계산
                try:
                    from datetime import datetime, timezone
                    entry_time = datetime.fromisoformat(completed_position['entry_time'].replace('Z', '+00:00'))
                    exit_time = datetime.now(timezone.utc)
                    duration = exit_time - entry_time
                    duration_str = f"{duration.days}일 {duration.seconds // 3600}시간 {(duration.seconds % 3600) // 60}분"
                except:
                    duration_str = "N/A"
                
                position_closed_info = {
                    'direction': completed_position['direction'],
                    'symbol': completed_position['symbol'],
                    'entry_price': completed_position['entry_price'],
                    'exit_price': exit_data['price'],
                    'quantity': completed_position.get('quantity', 0),
                    'pnl_usd': pnl_usd,
                    'pnl_percent': pnl_percent,
                    'exit_reason': '자동 청산 (손절/익절)',
                    'duration': duration_str,
                    'leverage': completed_position.get('leverage', 1),
                    'max_profit_percent': completed_position.get('max_profit_percent', 0),
                    'max_drawdown_percent': completed_position.get('max_drawdown_percent', 0),
                    'trade_id': completed_position['trade_id']
                }
                
                discord_notifier.send_trade_alert(position_closed_info, alert_type="position_closed")
            except Exception as e:
                logger.warning(f"⚠️ Discord 알림 발송 실패: {e}")
            
            return {
                'status': 'completed',
                'completed_position': completed_position
            }
            
        except Exception as e:
            logger.error(f"❌ 포지션 종료 처리 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def emergency_close_position(self) -> Dict:
        """긴급 포지션 종료"""
        try:
            if not self.current_position:
                return {'status': 'no_position'}
            
            symbol = self.current_position['symbol']
            direction = self.current_position['direction']
            
            # 현재 포지션 수량 조회
            positions = self.client.futures_position_information(symbol=symbol)
            position_amt = 0
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    position_amt = abs(float(pos['positionAmt']))
                    break
            
            if position_amt == 0:
                return {'status': 'no_position'}
            
            # 반대 방향 시장가 주문으로 포지션 종료
            close_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=position_amt,
                positionSide="LONG" if direction == "LONG" else "SHORT"
            )
            
            logger.info(f"🚨 긴급 포지션 종료 완료: {symbol}")
            
            # Discord 알림 발송 (긴급 청산)
            try:
                # 현재 가격 조회
                current_price = self._get_current_price(symbol)
                
                # 손익 계산
                entry_price = self.current_position.get('entry_price', 0)
                if direction == "LONG":
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                else:  # SHORT
                    pnl_percent = ((entry_price - current_price) / entry_price) * 100 if entry_price > 0 else 0
                
                pnl_usd = (pnl_percent / 100) * (position_amt * entry_price) if entry_price > 0 else 0
                
                # 거래 시간 계산
                try:
                    from datetime import datetime, timezone
                    entry_time = datetime.fromisoformat(self.current_position.get('entry_time', '').replace('Z', '+00:00'))
                    exit_time = datetime.now(timezone.utc)
                    duration = exit_time - entry_time
                    duration_str = f"{duration.days}일 {duration.seconds // 3600}시간 {(duration.seconds % 3600) // 60}분"
                except:
                    duration_str = "N/A"
                
                position_closed_info = {
                    'direction': direction,
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'quantity': position_amt,
                    'pnl_usd': pnl_usd,
                    'pnl_percent': pnl_percent,
                    'exit_reason': '🚨 긴급 청산',
                    'duration': duration_str,
                    'leverage': self.current_position.get('leverage', 1),
                    'max_profit_percent': 0,
                    'max_drawdown_percent': 0,
                    'trade_id': self.current_position.get('trade_id', 'EMERGENCY')
                }
                
                discord_notifier.send_trade_alert(position_closed_info, alert_type="position_closed")
            except Exception as e:
                logger.warning(f"⚠️ Discord 알림 발송 실패: {e}")
            
            return {
                'status': 'emergency_closed',
                'order_id': order['orderId']
            }
            
        except Exception as e:
            logger.error(f"❌ 긴급 포지션 종료 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_current_position_status(self) -> Optional[Dict]:
        """현재 포지션 상태 조회 (신디사이저용) - Position State Manager 사용"""
        try:
            # Position State Manager에서 통합된 포지션 정보 조회
            position = self.position_manager.get_current_position()
            
            if not position:
                return None
                
            # 신디사이저가 필요로 하는 형식으로 변환
            position_info = {
                'has_position': True,
                'symbol': position['symbol'],
                'direction': position['direction'],
                'entry_price': position['entry_price'],
                'quantity': position['quantity'],
                'unrealized_pnl': position['unrealized_pnl'],
                'unrealized_pnl_percent': position['pnl_percent'],
                'current_price': position['mark_price'],
                'leverage': position['leverage']
            }
            
            # Trading Context 정보 추가
            if position.get('has_context'):
                position_info.update({
                    'trade_id': position.get('trade_id'),
                    'stop_loss': position.get('stop_loss', 0),
                    'take_profit_1': position.get('target_price', 0),
                    'entry_time': position.get('context_entry_time'),
                    'has_context': True
                })
            else:
                # Context가 없으면 DB 정보 사용
                position_info.update({
                    'trade_id': position.get('db_trade_id', 'UNKNOWN'),
                    'stop_loss': position.get('stop_loss', 0),
                    'take_profit_1': position.get('target_price', 0),
                    'entry_time': position.get('db_entry_time'),
                    'has_context': False
                })
            
            # 중복 진입 경고
            if position.get('db_trades_count', 0) > 1:
                logger.warning(f"⚠️ 중복 진입 감지: {position['db_trades_count']}개의 PENDING 거래")
                position_info['duplicate_entries'] = position['db_trades_count']
            
            return position_info
            
        except Exception as e:
            logger.error(f"❌ 포지션 상태 조회 실패: {e}")
            return None
    
    def _calculate_days_held(self) -> float:
        """포지션 보유 기간 계산 (일 단위)"""
        try:
            from datetime import datetime, timezone
            entry_time = datetime.fromisoformat(self.current_position['entry_time'].replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            delta = current_time - entry_time
            return round(delta.total_seconds() / 86400, 2)  # 일 단위로 변환
        except Exception:
            return 0
    
    # _cancel_pending_trades_for_symbol 메서드 제거 - PENDING 상태를 사용하지 않음
    
    def _adjust_stop_loss(self, playbook: Dict, agent_reports: Dict) -> Dict:
        """현재 포지션의 손절가만 조정 (익절가 유지)"""
        try:
            if not self.current_position:
                logger.error("❌ 조정할 포지션이 없습니다")
                return {'status': 'error', 'error': 'No position to adjust'}
            
            symbol = self.current_position['symbol']
            direction = self.current_position['direction']
            quantity = self.current_position['quantity']
            
            # 새로운 손절가 가져오기
            new_stop_loss = playbook['execution_plan'].get('stop_loss', 0)
            if new_stop_loss <= 0:
                logger.error("❌ 유효하지 않은 손절가")
                return {'status': 'error', 'error': 'Invalid stop loss price'}
            
            # 손절 주문만 선택적으로 취소
            cancelled = self._cancel_stop_orders_only(symbol)
            logger.info(f"📋 {cancelled}개의 손절 주문 취소됨 (익절 주문은 유지)")
            
            # 새로운 손절 주문 설정
            if symbol == "SOLUSDT":
                new_stop_loss = round(new_stop_loss, 2)
            
            stop_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
            self.client.futures_create_order(
                symbol=symbol,
                side=stop_side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                quantity=quantity,
                stopPrice=str(new_stop_loss),
                timeInForce=TIME_IN_FORCE_GTC,
                positionSide="LONG" if direction == "LONG" else "SHORT"
            )
            
            logger.info(f"✅ 손절가 조정 완료: ${new_stop_loss}")
            
            # update_exit_decision 오류 제거 (메서드가 없음)
            # 대신 직접 로깅
            logger.info(f"📝 손절가 조정 사유: {playbook['final_decision'].get('rationale', '')}")
            
            return {
                'status': 'adjusted',
                'new_stop_loss': new_stop_loss,
                'reason': playbook['final_decision'].get('rationale', '')
            }
            
        except Exception as e:
            logger.error(f"❌ 손절가 조정 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _adjust_take_profit(self, playbook: Dict, agent_reports: Dict) -> Dict:
        """현재 포지션의 익절가만 조정 (손절가 유지)"""
        try:
            if not self.current_position:
                logger.error("❌ 조정할 포지션이 없습니다")
                return {'status': 'error', 'error': 'No position to adjust'}
            
            symbol = self.current_position['symbol']
            direction = self.current_position['direction']
            quantity = self.current_position['quantity']
            
            # 새로운 익절가 가져오기
            new_tp1 = playbook['execution_plan'].get('take_profit_1', 0)
            new_tp2 = playbook['execution_plan'].get('take_profit_2', 0)
            
            if new_tp1 <= 0 and new_tp2 <= 0:
                logger.error("❌ 유효하지 않은 익절가")
                return {'status': 'error', 'error': 'Invalid take profit prices'}
            
            # 익절 주문만 선택적으로 취소
            cancelled = self._cancel_take_profit_orders_only(symbol)
            logger.info(f"📋 {cancelled}개의 익절 주문 취소됨 (손절 주문은 유지)")
            
            # 새로운 익절 주문 설정
            if symbol == "SOLUSDT":
                new_tp1 = round(new_tp1, 2) if new_tp1 > 0 else 0
                new_tp2 = round(new_tp2, 2) if new_tp2 > 0 else 0
            
            tp_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
            
            # 1차 익절 주문 (50%)
            if new_tp1 > 0:
                tp1_quantity = round(quantity * 0.5, 2)
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp_side,
                    type=FUTURE_ORDER_TYPE_LIMIT,
                    quantity=tp1_quantity,
                    price=str(new_tp1),
                    timeInForce=TIME_IN_FORCE_GTC,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"🎯 1차 익절 조정: ${new_tp1} (50%)")
            
            # 2차 익절 주문 (50%)
            if new_tp2 > 0:
                tp2_quantity = round(quantity * 0.5, 2)
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp_side,
                    type=FUTURE_ORDER_TYPE_LIMIT,
                    quantity=tp2_quantity,
                    price=str(new_tp2),
                    timeInForce=TIME_IN_FORCE_GTC,
                    positionSide="LONG" if direction == "LONG" else "SHORT"
                )
                logger.info(f"🎯 2차 익절 조정: ${new_tp2} (50%)")
            
            logger.info(f"📝 익절가 조정 사유: {playbook['final_decision'].get('rationale', '')}")
            
            return {
                'status': 'adjusted',
                'new_take_profit_1': new_tp1,
                'new_take_profit_2': new_tp2,
                'reason': playbook['final_decision'].get('rationale', '')
            }
            
        except Exception as e:
            logger.error(f"❌ 익절가 조정 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _close_current_position(self, reason: str, agent_reports: Dict = None) -> Dict:
        """현재 포지션 강제 청산 (신디사이저 요청)"""
        try:
            # Position State Manager에서 포지션 확인
            position = self.position_manager.get_current_position()
            if not position:
                logger.warning("⚠️ 청산할 포지션이 없습니다")
                return {'status': 'no_position', 'reason': '청산할 포지션이 없음'}
                
            # 메모리 상태와 동기화
            if not self.current_position:
                # 메모리에 없으면 복구
                self.current_position = {
                    'symbol': position['symbol'],
                    'direction': position['direction'],
                    'entry_price': position['entry_price'],
                    'quantity': position['quantity'],
                    'leverage': position['leverage'],
                    'trade_id': position.get('trade_id', position.get('db_trade_id', 'RECOVERED')),
                    'entry_time': position.get('context_entry_time', position.get('db_entry_time')),
                    'stop_loss': position.get('stop_loss', 0),
                    'take_profit_1': position.get('target_price', 0),
                    'agent_reports': agent_reports or {}  # 전달받은 agent_reports 사용
                }
            
            symbol = position['symbol']
            direction = position['direction']
            quantity = position['quantity']
            
            logger.info(f"🚨 포지션 강제 청산 시작: {direction} {symbol} (이유: {reason})")
            
            # 현재 가격 조회
            current_price = self._get_current_price(symbol)
            
            # 반대 방향 시장가 주문으로 포지션 청산
            close_side = SIDE_SELL if direction == "LONG" else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=quantity,
                positionSide="LONG" if direction == "LONG" else "SHORT"
            )
            
            # 손익 계산
            entry_price = position['entry_price']
            if direction == "LONG":
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:  # SHORT
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
            
            # 거래 완료 처리 및 DB 저장
            exit_data = {
                'price': current_price,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'max_drawdown': 0  # 실제로는 추적 필요
            }
            
            entry_data = {
                'asset': symbol,
                'price': entry_price,
                'direction': direction,
                'leverage': position['leverage'],
                'position_size_percent': self.current_position.get('position_size_percent', 5),  # 기본값 5%
                'timestamp': position.get('context_entry_time', position.get('db_entry_time')),
                'stop_loss': position.get('stop_loss', 0),
                'take_profit': position.get('target_price', 0),
                'market_conditions': {},
                'agent_scores': {}
            }
            
            # DB에 거래 기록 저장 (MANUAL_EXIT으로 표시)
            # agent_reports가 전달되었으면 사용, 아니면 기존 것 사용
            reports_to_save = agent_reports if agent_reports else self.current_position.get('agent_reports', {})
            save_completed_trade(entry_data, exit_data, reports_to_save, exit_reason="MANUAL_EXIT")
            
            # 거래 성과 분석 실행 (백그라운드)
            try:
                trade_data_for_analysis = {
                    'trade_id': self.current_position['trade_id'],
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl_percent': pnl_percent,
                    'entry_time': self.current_position['entry_time'],
                    'exit_time': datetime.now(timezone.utc).isoformat(),
                    'reason': reason,
                    'leverage': self.current_position['leverage']
                }
                
                # 비동기 분석 실행 (실패해도 거래 완료에는 영향 없음)
                analysis_result = trade_analyzer.analyze_completed_trade(
                    trade_data_for_analysis, 
                    reports_to_save
                )
                
                if analysis_result:
                    logger.info(f"📊 거래 성과 분석 완료: {analysis_result.analysis_type}")
                else:
                    logger.warning("⚠️ 거래 성과 분석 실패 (거래 완료는 정상 처리됨)")
                
                # 스마트 라벨링 추가
                try:
                    label_result = trade_db.label_completed_trade(self.current_position['trade_id'])
                    if label_result:
                        logger.info(f"🏷️ 거래 라벨링 완료: {self.current_position['trade_id']}")
                    else:
                        logger.warning(f"⚠️ 거래 라벨링 실패: {self.current_position['trade_id']}")
                except Exception as label_error:
                    logger.warning(f"⚠️ 거래 라벨링 중 오류: {label_error}")
                    
            except Exception as e:
                logger.warning(f"⚠️ 거래 성과 분석 중 오류 (거래 완료는 정상): {e}")
            
            completed_position = self.current_position.copy()
            self.current_position = None  # 포지션 클리어
            
            # Trading Context 클리어 (거래 연속성 종료)
            try:
                trading_context.clear_context()
                logger.info("📋 Trading Context 클리어됨")
            except Exception as e:
                logger.warning(f"⚠️ Trading Context 클리어 실패: {e}")
            
            logger.info(f"✅ 포지션 강제 청산 완료: {symbol} (손익: {pnl_percent:.2f}%)")
            
            # Discord 알림 발송 (수동/강제 청산)
            try:
                # 손익 USD 계산
                pnl_usd = (pnl_percent / 100) * (quantity * entry_price)
                
                # 거래 시간 계산
                try:
                    entry_time_dt = datetime.fromisoformat(self.current_position['entry_time'].replace('Z', '+00:00'))
                    exit_time_dt = datetime.now(timezone.utc)
                    duration = exit_time_dt - entry_time_dt
                    duration_str = f"{duration.days}일 {duration.seconds // 3600}시간 {(duration.seconds % 3600) // 60}분"
                except:
                    duration_str = "N/A"
                
                position_closed_info = {
                    'direction': direction,
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'quantity': quantity,
                    'pnl_usd': pnl_usd,
                    'pnl_percent': pnl_percent,
                    'exit_reason': reason,
                    'duration': duration_str,
                    'leverage': self.current_position.get('leverage', 1),
                    'max_profit_percent': 0,  # 강제 청산시에는 추적하지 않음
                    'max_drawdown_percent': 0,
                    'trade_id': self.current_position['trade_id']
                }
                
                discord_notifier.send_trade_alert(position_closed_info, alert_type="position_closed")
            except Exception as e:
                logger.warning(f"⚠️ Discord 알림 발송 실패: {e}")
            
            return {
                'status': 'closed',
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl_percent': pnl_percent,
                'reason': reason,
                'order_id': order['orderId']
            }
            
        except Exception as e:
            logger.error(f"❌ 포지션 강제 청산 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _adjust_position_size(self, playbook: Dict, agent_reports: Dict) -> Dict:
        """포지션 크기 조정 (피라미딩)"""
        try:
            # 현재 포지션 확인
            position = self.position_manager.get_current_position()
            if not position:
                logger.error("❌ 조정할 포지션이 없습니다")
                return {'status': 'error', 'error': 'No position to adjust'}
            
            # 조정 계획 추출
            adjustment_plan = playbook.get('adjustment_plan', {})
            if not adjustment_plan:
                logger.error("❌ adjustment_plan이 없습니다")
                return {'status': 'error', 'error': 'Missing adjustment_plan'}
            
            # 환경 변수 검증
            min_profit = float(os.getenv('ADJUSTMENT_MIN_PROFIT', '2.0'))
            max_total_size = float(os.getenv('ADJUSTMENT_MAX_TOTAL_SIZE', '0.4'))
            
            # 수익률 검증
            current_pnl = position.get('unrealized_pnl_percent', 0)
            if current_pnl < min_profit:
                logger.warning(f"⚠️ 최소 수익률 미달: {current_pnl:.2f}% < {min_profit}%")
                return {'status': 'rejected', 'reason': f'Profit {current_pnl:.2f}% below minimum {min_profit}%'}
            
            # 포지션 크기 계산
            symbol = position['symbol']
            direction = position['direction']
            current_size = position['quantity']
            target_size = adjustment_plan['target_size']
            additional_size = target_size - current_size
            
            if additional_size <= 0:
                logger.error("❌ 추가 수량이 0 이하입니다")
                return {'status': 'error', 'error': 'Invalid additional size'}
            
            # 자본 대비 총 포지션 크기 검증
            account = self.get_account_status()
            total_balance = account.get('total_balance', 0)
            current_price = self._get_current_price(symbol)
            total_position_value = target_size * current_price
            position_ratio = total_position_value / total_balance if total_balance > 0 else 1.0
            
            if position_ratio > max_total_size:
                logger.warning(f"⚠️ 최대 포지션 크기 초과: {position_ratio:.2%} > {max_total_size:.0%}")
                return {'status': 'rejected', 'reason': f'Position size {position_ratio:.2%} exceeds maximum {max_total_size:.0%}'}
            
            # 조정 이력 확인 (이미 조정한 포지션인지)
            if hasattr(self, '_adjusted_positions'):
                if position.get('trade_id') in self._adjusted_positions:
                    logger.warning("⚠️ 이미 조정한 포지션입니다")
                    return {'status': 'rejected', 'reason': 'Position already adjusted once'}
            else:
                self._adjusted_positions = set()
            
            logger.info(f"📈 포지션 크기 조정 시작: {current_size} → {target_size} {symbol}")
            
            # 1. 추가 주문 실행
            order_side = SIDE_BUY if direction == "LONG" else SIDE_SELL
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=round(additional_size, 3),  # 수량 정밀도
                positionSide="LONG" if direction == "LONG" else "SHORT"
            )
            
            logger.info(f"✅ 추가 주문 체결: {additional_size} @ 시장가")
            
            # 2. 기존 손절/익절 주문 취소
            try:
                self._cancel_all_open_orders(symbol)
                logger.info("✅ 기존 주문 모두 취소")
            except Exception as e:
                logger.warning(f"⚠️ 기존 주문 취소 실패: {e}")
            
            # 3. 새로운 손절/익절 설정 (무손실 원칙)
            new_stop_loss = adjustment_plan['new_stop_loss']
            initial_entry_price = self.current_position.get('entry_price', position['entry_price'])
            
            # 무손실 원칙 적용
            if direction == "LONG":
                new_stop_loss = max(new_stop_loss, initial_entry_price)
            else:  # SHORT
                new_stop_loss = min(new_stop_loss, initial_entry_price)
            
            # 새로운 평균 진입가 계산 (Binance가 자동으로 계산하지만 로깅용)
            new_avg_price = ((current_size * position['entry_price']) + (additional_size * current_price)) / target_size
            
            # 손절/익절 재설정
            take_profit_1 = playbook['execution_plan'].get('take_profit_1', 0)
            take_profit_2 = playbook['execution_plan'].get('take_profit_2', 0)
            
            if take_profit_1 > 0:
                try:
                    self._set_stop_loss_take_profit(
                        symbol=symbol,
                        direction=direction,
                        stop_loss=new_stop_loss,
                        take_profit_1=take_profit_1,
                        take_profit_2=take_profit_2,
                        quantity=target_size
                    )
                    logger.info(f"✅ 새로운 손절가: ${new_stop_loss:.2f} (무손실 보장)")
                except Exception as e:
                    logger.error(f"❌ 손절/익절 설정 실패: {e}")
            
            # 조정 이력 저장
            self._adjusted_positions.add(position.get('trade_id'))
            
            # 포지션 상태 업데이트
            self.current_position['quantity'] = target_size
            self.current_position['adjusted'] = True
            self.current_position['adjustment_time'] = datetime.now(timezone.utc).isoformat()
            self.current_position['adjustment_reason'] = adjustment_plan.get('rationale', '')
            
            # Trading Context 업데이트
            try:
                trading_context.update_context({
                    'position_adjusted': True,
                    'adjustment_time': datetime.now(timezone.utc).isoformat(),
                    'original_size': current_size,
                    'new_size': target_size,
                    'new_stop_loss': new_stop_loss
                })
            except Exception as e:
                logger.warning(f"⚠️ Trading Context 업데이트 실패: {e}")
            
            # Discord 알림
            try:
                adjustment_info = {
                    'symbol': symbol,
                    'direction': direction,
                    'original_size': current_size,
                    'new_size': target_size,
                    'additional_size': additional_size,
                    'new_avg_price': new_avg_price,
                    'new_stop_loss': new_stop_loss,
                    'current_pnl_percent': current_pnl,
                    'rationale': adjustment_plan.get('rationale', '')
                }
                
                discord_notifier.send_trade_alert(adjustment_info, alert_type="position_adjusted")
            except Exception as e:
                logger.warning(f"⚠️ Discord 알림 실패: {e}")
            
            logger.info(f"✅ 포지션 크기 조정 완료: {current_size} → {target_size}")
            
            return {
                'status': 'adjusted',
                'original_size': current_size,
                'new_size': target_size,
                'new_avg_price': new_avg_price,
                'new_stop_loss': new_stop_loss
            }
            
        except Exception as e:
            logger.error(f"❌ 포지션 크기 조정 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_account_status(self) -> Dict:
        """계좌 상태 조회"""
        try:
            account = self.client.futures_account()
            return {
                'total_balance': float(account['totalWalletBalance']),
                'available_balance': float(account['availableBalance']),
                'unrealized_pnl': float(account['totalUnrealizedProfit']),
                'margin_ratio': float(account['totalMaintMargin']) / float(account['totalMarginBalance']) if float(account['totalMarginBalance']) > 0 else 0
            }
        except Exception as e:
            logger.error(f"❌ 계좌 상태 조회 실패: {e}")
            return {}
    
    def _check_order_filled(self, symbol: str, order_id: str) -> bool:
        """LIMIT 주문 체결 여부 확인"""
        try:
            order = self.client.futures_get_order(
                symbol=symbol,
                orderId=order_id
            )
            status = order.get('status', '')
            logger.debug(f"주문 상태: {status} (Order ID: {order_id})")
            
            # FILLED = 완전 체결, PARTIALLY_FILLED = 부분 체결
            # 안전을 위해 완전 체결만 처리
            return status == 'FILLED'
        except Exception as e:
            logger.error(f"❌ 주문 상태 확인 실패: {e}")
            return False
    
    def _create_oco_for_filled_limit(self):
        """체결된 LIMIT 주문에 대해 OCO 생성"""
        try:
            if not self.current_position:
                logger.error("❌ 포지션 정보가 없습니다")
                return
            
            # 실제 체결가 조회
            actual_entry_price = self._get_actual_fill_price(
                self.current_position['symbol'],
                self.current_position['pending_order_id']
            )
            
            if actual_entry_price <= 0:
                logger.error("❌ 실제 체결가를 가져올 수 없습니다")
                return
            
            logger.info(f"📊 LIMIT 주문 체결가: ${actual_entry_price:.2f} (예상: ${self.current_position['expected_entry_price']:.2f})")
            
            # OCO 주문 생성
            oco_result = self._create_oco_exit_orders(
                symbol=self.current_position['symbol'],
                direction=self.current_position['direction'],
                quantity=self.current_position['quantity'],
                entry_price=actual_entry_price,  # 실제 체결가 사용
                stop_loss=self.current_position['stop_loss'],
                take_profit_1=self.current_position['take_profit_1'],
                take_profit_2=self.current_position['take_profit_2']
            )
            
            if oco_result.get('status') in ['success', 'fallback_success']:
                # 상태 업데이트
                self.current_position['pending'] = False
                self.current_position['oco_created'] = True
                self.current_position['actual_entry_price'] = actual_entry_price
                self.current_position['entry_price'] = actual_entry_price  # 실제 체결가로 업데이트
                self.current_position['oco_orders'] = oco_result.get('oco_orders', [])
                
                logger.info("✅ LIMIT 주문 체결 후 OCO 주문 생성 완료")
                
                # Discord 알림
                try:
                    from utils.discord_notifier import discord_notifier
                    discord_notifier.send_alert(
                        f"✅ LIMIT 주문 체결 및 OCO 설정 완료\n"
                        f"심볼: {self.current_position['symbol']}\n"
                        f"체결가: ${actual_entry_price:.2f}\n"
                        f"손절가: ${self.current_position['stop_loss']:.2f}\n"
                        f"익절가1: ${self.current_position['take_profit_1']:.2f}\n"
                        f"익절가2: ${self.current_position['take_profit_2']:.2f}",
                        level='success'
                    )
                except:
                    pass
                
                # Trading Context 업데이트
                try:
                    from data.trading_context import trading_context
                    trading_context.update_entry_price(actual_entry_price)
                    logger.info("📋 Trading Context 업데이트 완료")
                except Exception as e:
                    logger.warning(f"⚠️ Trading Context 업데이트 실패: {e}")
            else:
                logger.error(f"❌ OCO 주문 생성 실패: {oco_result}")
                
        except Exception as e:
            logger.error(f"❌ LIMIT 주문 후 OCO 생성 실패: {e}")
    
    def _get_actual_fill_price(self, symbol: str, order_id: str) -> float:
        """실제 체결가 조회"""
        try:
            order = self.client.futures_get_order(
                symbol=symbol,
                orderId=order_id
            )
            
            # avgPrice가 0이면 price 사용 (LIMIT 주문의 경우)
            avg_price = float(order.get('avgPrice', 0))
            if avg_price > 0:
                return avg_price
            else:
                return float(order.get('price', 0))
                
        except Exception as e:
            logger.error(f"❌ 실제 체결가 조회 실패: {e}")
            return 0

# 전역 거래 실행기 인스턴스
trade_executor = TradeExecutor(testnet=False)  # 실제 거래용, testnet=True로 변경 시 테스트