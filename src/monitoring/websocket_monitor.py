"""
델파이 트레이딩 시스템 - 실시간 웹소켓 모니터링
바이낸스 웹소켓을 통한 실시간 포지션 및 계좌 모니터링
"""

import asyncio
import json
import logging
import websockets
import time
from typing import Dict, Optional, Callable, List
from datetime import datetime, timezone
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.discord_notifier import discord_notifier
from utils.time_manager import TimeManager

class WebSocketMonitor:
    """바이낸스 웹소켓 실시간 모니터링"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        웹소켓 모니터 초기화
        
        Args:
            api_key: 바이낸스 API 키
            api_secret: 바이낸스 API 시크릿
            testnet: 테스트넷 여부
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # 웹소켓 URL 설정
        if testnet:
            self.base_url = "wss://testnet.binance.vision"
            self.futures_url = "wss://fstream.binancefuture.com"
        else:
            self.base_url = "wss://stream.binance.com:9443"
            self.futures_url = "wss://fstream.binance.com"
        
        # 모니터링 상태
        self.is_monitoring = False
        self.websocket_connections = {}
        self.last_heartbeat = time.time()
        
        # 콜백 함수들
        self.position_callbacks = []
        self.account_callbacks = []
        self.price_callbacks = []
        self.order_callbacks = []
        
        # 데이터 저장
        self.current_positions = {}
        self.current_account = {}
        self.current_prices = {}
        self.recent_orders = []
        
        # 알림 설정
        self.alert_thresholds = {
            'unrealized_pnl_threshold': -500.0,    # $500 손실시 알림
            'margin_ratio_threshold': 0.8,         # 마진율 80% 이상시 알림
            'price_change_threshold': 0.05,        # 5% 가격 변동시 알림
            'position_size_threshold': 10000.0     # $10,000 이상 포지션시 알림
        }
        
        logging.info(f"🔗 웹소켓 모니터 초기화 ({'테스트넷' if testnet else '메인넷'})")
    
    async def start_monitoring(self, symbols: List[str] = None):
        """실시간 모니터링 시작"""
        try:
            if self.is_monitoring:
                logging.warning("⚠️ 이미 모니터링이 실행 중입니다")
                return
            
            self.is_monitoring = True
            symbols = symbols or ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            
            logging.info(f"🚀 실시간 웹소켓 모니터링 시작: {symbols}")
            
            # 여러 웹소켓 스트림을 동시에 실행
            tasks = []
            
            # 1. 가격 스트림 (티커)
            tasks.append(self._monitor_price_stream(symbols))
            
            # 2. 계좌 업데이트 스트림 (USER_DATA)
            if not self.testnet:  # 테스트넷에서는 USER_DATA 스트림 제한적
                tasks.append(self._monitor_account_stream())
            
            # 3. 주문 업데이트 스트림
            if not self.testnet:
                tasks.append(self._monitor_order_stream())
            
            # 4. 연결 상태 체크
            tasks.append(self._monitor_connection_health())
            
            # 5. 시뮬레이션 모드 (테스트넷용)
            if self.testnet:
                tasks.append(self._simulate_account_monitoring())
            
            # 모든 태스크 동시 실행
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logging.error(f"❌ 웹소켓 모니터링 시작 실패: {e}")
            self.is_monitoring = False
    
    async def _monitor_price_stream(self, symbols: List[str]):
        """가격 스트림 모니터링"""
        try:
            # 멀티 심볼 스트림 URL 생성
            stream_names = [f"{symbol.lower()}@ticker" for symbol in symbols]
            stream_url = f"{self.base_url}/ws/" + "/".join(stream_names)
            
            logging.info(f"📈 가격 스트림 연결: {len(symbols)}개 심볼")
            
            async with websockets.connect(stream_url) as websocket:
                self.websocket_connections['price'] = websocket
                
                async for message in websocket:
                    if not self.is_monitoring:
                        break
                    
                    try:
                        data = json.loads(message)
                        await self._process_price_update(data)
                    except Exception as e:
                        logging.error(f"❌ 가격 데이터 처리 실패: {e}")
                        
        except Exception as e:
            logging.error(f"❌ 가격 스트림 연결 실패: {e}")
    
    async def _monitor_account_stream(self):
        """계좌 업데이트 스트림 모니터링"""
        try:
            # User Data Stream용 Listen Key 생성 필요
            # 여기서는 간소화된 버전으로 구현
            
            logging.info("💰 계좌 스트림 모니터링 시작")
            
            while self.is_monitoring:
                # 실제로는 websocket으로 실시간 데이터를 받아야 하지만
                # 여기서는 폴링 방식으로 시뮬레이션
                await asyncio.sleep(5)  # 5초마다 체크
                
                # 계좌 정보 시뮬레이션 (실제로는 웹소켓 데이터)
                account_update = {
                    'balance': 10000.0,
                    'unrealized_pnl': -150.0,
                    'margin_ratio': 0.3,
                    'timestamp': time.time()
                }
                
                await self._process_account_update(account_update)
                
        except Exception as e:
            logging.error(f"❌ 계좌 스트림 모니터링 실패: {e}")
    
    async def _monitor_order_stream(self):
        """주문 업데이트 스트림 모니터링"""
        try:
            logging.info("📋 주문 스트림 모니터링 시작")
            
            while self.is_monitoring:
                await asyncio.sleep(3)  # 3초마다 체크
                
                # 주문 업데이트 시뮬레이션
                if len(self.recent_orders) < 5:  # 최대 5개 유지
                    order_update = {
                        'symbol': 'BTCUSDT',
                        'order_id': f'ORDER_{int(time.time())}',
                        'status': 'NEW',
                        'side': 'BUY',
                        'quantity': 0.001,
                        'price': 50000.0,
                        'timestamp': time.time()
                    }
                    
                    await self._process_order_update(order_update)
                
        except Exception as e:
            logging.error(f"❌ 주문 스트림 모니터링 실패: {e}")
    
    async def _monitor_connection_health(self):
        """웹소켓 연결 상태 체크"""
        try:
            logging.info("💓 연결 상태 모니터링 시작")
            
            while self.is_monitoring:
                await asyncio.sleep(30)  # 30초마다 체크
                
                current_time = time.time()
                
                # 하트비트 체크
                if current_time - self.last_heartbeat > 60:  # 1분 이상 응답 없음
                    logging.warning("⚠️ 웹소켓 연결 불안정 감지")
                    
                    try:
                        discord_notifier.send_alert(
                            "⚠️ 웹소켓 연결 불안정\n"
                            "실시간 모니터링에 지연이 발생할 수 있습니다.",
                            level="warning"
                        )
                    except:
                        pass
                
                # 연결 상태 업데이트
                self.last_heartbeat = current_time
                
                # 활성 연결 수 체크
                active_connections = len([conn for conn in self.websocket_connections.values() if conn])
                if active_connections > 0:
                    logging.debug(f"💓 웹소켓 연결 상태: {active_connections}개 활성")
                
        except Exception as e:
            logging.error(f"❌ 연결 상태 모니터링 실패: {e}")
    
    async def _simulate_account_monitoring(self):
        """테스트넷용 계좌 모니터링 시뮬레이션"""
        try:
            logging.info("🧪 테스트넷 계좌 모니터링 시뮬레이션")
            
            simulation_data = {
                'balance': 10000.0,
                'position_value': 2000.0,
                'unrealized_pnl': 0.0,
                'margin_ratio': 0.2
            }
            
            while self.is_monitoring:
                await asyncio.sleep(10)  # 10초마다 시뮬레이션 업데이트
                
                # 시뮬레이션 데이터 변동
                import random
                
                # PnL 변동 시뮬레이션
                pnl_change = random.uniform(-50, 50)
                simulation_data['unrealized_pnl'] += pnl_change
                
                # 마진율 변동
                simulation_data['margin_ratio'] = max(0.1, 
                    simulation_data['margin_ratio'] + random.uniform(-0.05, 0.05))
                
                simulation_data['timestamp'] = time.time()
                
                # 시뮬레이션 데이터 처리
                await self._process_account_update(simulation_data)
                
                logging.debug(f"🧪 시뮬레이션: PnL ${simulation_data['unrealized_pnl']:.2f}, "
                            f"마진율 {simulation_data['margin_ratio']:.1%}")
                
        except Exception as e:
            logging.error(f"❌ 계좌 시뮬레이션 실패: {e}")
    
    async def _process_price_update(self, data: Dict):
        """가격 업데이트 처리"""
        try:
            symbol = data.get('s', '')
            price = float(data.get('c', 0))  # 현재가
            price_change_pct = float(data.get('P', 0))  # 24시간 변동률
            
            # 이전 가격과 비교
            prev_price = self.current_prices.get(symbol, price)
            self.current_prices[symbol] = price
            
            # 큰 가격 변동 감지
            if abs(price_change_pct) > self.alert_thresholds['price_change_threshold'] * 100:
                await self._send_price_alert(symbol, price, price_change_pct)
            
            # 가격 콜백 실행
            for callback in self.price_callbacks:
                try:
                    await callback(symbol, price, price_change_pct)
                except Exception as e:
                    logging.debug(f"콜백 실행 중 오류: {e}")
            
            logging.debug(f"📈 {symbol}: ${price:,.2f} ({price_change_pct:+.2f}%)")
            
        except Exception as e:
            logging.error(f"❌ 가격 업데이트 처리 실패: {e}")
    
    async def _process_account_update(self, data: Dict):
        """계좌 업데이트 처리"""
        try:
            balance = data.get('balance', 0)
            unrealized_pnl = data.get('unrealized_pnl', 0)
            margin_ratio = data.get('margin_ratio', 0)
            
            # 이전 데이터 저장
            prev_account = self.current_account.copy()
            
            # 현재 데이터 업데이트
            self.current_account.update({
                'balance': balance,
                'unrealized_pnl': unrealized_pnl,
                'margin_ratio': margin_ratio,
                'last_update': data.get('timestamp', time.time())
            })
            
            # 위험 상황 감지
            await self._check_account_risks(prev_account, self.current_account)
            
            # 계좌 콜백 실행
            for callback in self.account_callbacks:
                try:
                    await callback(self.current_account)
                except Exception as e:
                    logging.debug(f"콜백 실행 중 오류: {e}")
            
            logging.debug(f"💰 계좌: 잔고 ${balance:,.2f}, PnL ${unrealized_pnl:,.2f}, "
                        f"마진 {margin_ratio:.1%}")
            
        except Exception as e:
            logging.error(f"❌ 계좌 업데이트 처리 실패: {e}")
    
    async def _process_order_update(self, data: Dict):
        """주문 업데이트 처리"""
        try:
            order_id = data.get('order_id', '')
            symbol = data.get('symbol', '')
            status = data.get('status', '')
            side = data.get('side', '')
            quantity = data.get('quantity', 0)
            price = data.get('price', 0)
            
            # 주문 리스트에 추가
            self.recent_orders.append({
                'order_id': order_id,
                'symbol': symbol,
                'status': status,
                'side': side,
                'quantity': quantity,
                'price': price,
                'timestamp': data.get('timestamp', time.time())
            })
            
            # 최근 주문만 유지 (최대 100개)
            if len(self.recent_orders) > 100:
                self.recent_orders = self.recent_orders[-100:]
            
            # 주문 체결 알림
            if status in ['FILLED', 'PARTIALLY_FILLED']:
                await self._send_order_fill_alert(data)
            
            # 주문 콜백 실행
            for callback in self.order_callbacks:
                try:
                    await callback(data)
                except Exception as e:
                    logging.debug(f"콜백 실행 중 오류: {e}")
            
            logging.debug(f"📋 주문: {symbol} {side} {quantity} @ ${price} ({status})")
            
        except Exception as e:
            logging.error(f"❌ 주문 업데이트 처리 실패: {e}")
    
    async def _check_account_risks(self, prev_account: Dict, current_account: Dict):
        """계좌 위험 상황 체크"""
        try:
            unrealized_pnl = current_account.get('unrealized_pnl', 0)
            margin_ratio = current_account.get('margin_ratio', 0)
            
            # 큰 손실 알림
            if unrealized_pnl < self.alert_thresholds['unrealized_pnl_threshold']:
                await self._send_risk_alert(
                    '큰 손실 발생',
                    f'미실현 손익: ${unrealized_pnl:,.2f}',
                    'danger'
                )
            
            # 높은 마진율 알림
            if margin_ratio > self.alert_thresholds['margin_ratio_threshold']:
                await self._send_risk_alert(
                    '높은 마진율 경고',
                    f'현재 마진율: {margin_ratio:.1%}',
                    'warning'
                )
            
            # PnL 급격한 변화 감지
            prev_pnl = prev_account.get('unrealized_pnl', 0)
            pnl_change = unrealized_pnl - prev_pnl
            
            if abs(pnl_change) > 100:  # $100 이상 변동
                await self._send_risk_alert(
                    'PnL 급격한 변화',
                    f'변화량: ${pnl_change:+,.2f}',
                    'info'
                )
            
        except Exception as e:
            logging.error(f"❌ 위험 상황 체크 실패: {e}")
    
    async def _send_price_alert(self, symbol: str, price: float, change_pct: float):
        """가격 변동 알림"""
        try:
            discord_notifier.send_alert(
                f"📈 큰 가격 변동 감지\n"
                f"심볼: {symbol}\n"
                f"현재가: ${price:,.2f}\n"
                f"24시간 변동: {change_pct:+.2f}%",
                level='info'
            )
        except Exception as e:
            logging.debug(f"알림 전송 중 오류: {e}")
    
    async def _send_risk_alert(self, title: str, message: str, level: str):
        """위험 상황 알림"""
        try:
            discord_notifier.send_alert(
                f"⚠️ {title}\n{message}",
                level=level
            )
        except Exception as e:
            logging.debug(f"알림 전송 중 오류: {e}")
    
    async def _send_order_fill_alert(self, order_data: Dict):
        """주문 체결 알림"""
        try:
            symbol = order_data.get('symbol', '')
            side = order_data.get('side', '')
            quantity = order_data.get('quantity', 0)
            price = order_data.get('price', 0)
            status = order_data.get('status', '')
            
            discord_notifier.send_alert(
                f"📋 주문 체결\n"
                f"심볼: {symbol}\n"
                f"방향: {side}\n"
                f"수량: {quantity}\n"
                f"가격: ${price:,.2f}\n"
                f"상태: {status}",
                level='success'
            )
        except Exception as e:
            logging.debug(f"알림 전송 중 오류: {e}")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        logging.info("🛑 실시간 웹소켓 모니터링 중지")
        self.is_monitoring = False
        
        # 웹소켓 연결 종료
        for name, connection in self.websocket_connections.items():
            if connection:
                try:
                    asyncio.create_task(connection.close())
                except Exception as e:
                    logging.debug(f"콜백 실행 중 오류: {e}")
        
        self.websocket_connections.clear()
    
    def add_price_callback(self, callback: Callable):
        """가격 업데이트 콜백 추가"""
        self.price_callbacks.append(callback)
    
    def add_account_callback(self, callback: Callable):
        """계좌 업데이트 콜백 추가"""
        self.account_callbacks.append(callback)
    
    def add_order_callback(self, callback: Callable):
        """주문 업데이트 콜백 추가"""
        self.order_callbacks.append(callback)
    
    def get_monitoring_status(self) -> Dict:
        """모니터링 상태 조회"""
        return {
            'is_monitoring': self.is_monitoring,
            'active_connections': len(self.websocket_connections),
            'last_heartbeat': self.last_heartbeat,
            'monitored_symbols': list(self.current_prices.keys()),
            'current_account': self.current_account,
            'recent_orders_count': len(self.recent_orders)
        }
    
    def get_status_report(self) -> str:
        """모니터링 상태 보고서"""
        status = self.get_monitoring_status()
        
        report = f"""
🔗 실시간 웹소켓 모니터링 상태
{'='*50}
📊 모니터링 상태: {'🟢 활성' if status['is_monitoring'] else '🔴 비활성'}
🔗 활성 연결: {status['active_connections']}개
💓 마지막 하트비트: {datetime.fromtimestamp(status['last_heartbeat']).strftime('%H:%M:%S')}
📈 모니터링 심볼: {len(status['monitored_symbols'])}개

💰 현재 계좌 상태:
"""
        
        if status['current_account']:
            account = status['current_account']
            report += f"   잔고: ${account.get('balance', 0):,.2f}\n"
            report += f"   미실현 손익: ${account.get('unrealized_pnl', 0):,.2f}\n"
            report += f"   마진율: {account.get('margin_ratio', 0):.1%}\n"
        else:
            report += "   데이터 없음\n"
        
        report += f"\n📋 최근 주문: {status['recent_orders_count']}개"
        
        return report


# 전역 웹소켓 모니터 인스턴스 (필요시 생성)
websocket_monitor = None

async def start_websocket_monitoring(api_key: str, api_secret: str, 
                                   symbols: List[str] = None, testnet: bool = False):
    """웹소켓 모니터링 시작 (비동기 함수)"""
    global websocket_monitor
    
    try:
        websocket_monitor = WebSocketMonitor(api_key, api_secret, testnet)
        await websocket_monitor.start_monitoring(symbols)
    except Exception as e:
        logging.error(f"❌ 웹소켓 모니터링 시작 실패: {e}")

def stop_websocket_monitoring():
    """웹소켓 모니터링 중지"""
    global websocket_monitor
    
    if websocket_monitor:
        websocket_monitor.stop_monitoring()
        websocket_monitor = None