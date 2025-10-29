"""
델파이 트레이딩 시스템 - 심장박동 체크 모듈
1분마다 포지션 상태, 계좌 위험도, 시스템 상태를 모니터링하고
위험 발생시 긴급 청산 및 알림을 담당
"""

import os
import sys
import time
import logging
import smtplib
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.trading.trade_executor import TradeExecutor
from src.data.binance_connector import get_current_price
from src.utils.time_manager import TimeManager
from src.utils.discord_notifier import DiscordNotifier
from src.monitoring.websocket_monitor import WebSocketMonitor
from src.utils.smart_scheduler import SmartScheduler
from src.monitoring.price_history import PriceHistory
from src.monitoring.position_monitor import SmartPositionMonitor
import asyncio

class HeartbeatChecker:
    """시스템 심장박동 체크 및 위험 모니터링"""
    
    def __init__(self, config_path: str = None):
        """
        심장박동 체커 초기화
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or os.path.join(project_root, 'config', 'config.yaml')
        self.config = self._load_config()
        
        # 거래 실행기 초기화
        self.trade_executor = TradeExecutor(testnet=False)
        
        # Discord 알림기 초기화
        self.discord_notifier = DiscordNotifier()
        
        # 트리거 매니저 초기화
        from src.agents.trigger_manager import TriggerManager
        self.trigger_manager = TriggerManager()
        
        # 포지션 모니터링 시스템 초기화
        self.smart_scheduler = SmartScheduler()
        self.price_history = PriceHistory(max_size=1000)
        self.position_monitor = SmartPositionMonitor(
            scheduler=self.smart_scheduler,
            price_history=self.price_history
        )
        
        # 웹소켓 모니터 초기화
        self.websocket_monitor = None
        self.websocket_enabled = self.config.get('monitoring', {}).get('websocket_enabled', True)
        
        # 모니터링 상태
        self.last_heartbeat = TimeManager.utc_now()
        self.consecutive_errors = 0
        self.daily_loss_tracking = []
        self.risk_alerts_sent = []
        
        # 로깅 설정
        logging.basicConfig(
            level=getattr(logging, self.config.get('system', {}).get('log_level', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(project_root, 'logs', 'heartbeat.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("💓 델파이 심장박동 체커 초기화 완료")
    
    async def start_websocket_monitoring(self):
        """웹소켓 실시간 모니터링 시작"""
        try:
            if not self.websocket_enabled:
                self.logger.info("📡 웹소켓 모니터링이 비활성화되어 있습니다")
                return
            
            if self.websocket_monitor:
                self.logger.warning("⚠️ 웹소켓 모니터링이 이미 실행 중입니다")
                return
            
            # API 키 로드
            import os
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')
            
            if not api_key or not api_secret:
                self.logger.error("❌ 바이낸스 API 키가 설정되지 않음")
                return
            
            # 웹소켓 모니터 초기화
            self.websocket_monitor = WebSocketMonitor(api_key, api_secret, testnet=False)
            
            # 콜백 함수 등록
            self.websocket_monitor.add_account_callback(self._on_account_update)
            self.websocket_monitor.add_price_callback(self._on_price_update) 
            self.websocket_monitor.add_order_callback(self._on_order_update)
            
            # 모니터링할 심볼 설정
            symbols = self.config.get('monitoring', {}).get('symbols', ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'])
            
            self.logger.info(f"🚀 웹소켓 실시간 모니터링 시작: {symbols}")
            
            # 웹소켓 모니터링 시작 (비동기)
            await self.websocket_monitor.start_monitoring(symbols)
            
        except Exception as e:
            self.logger.error(f"❌ 웹소켓 모니터링 시작 실패: {e}")
            self.websocket_monitor = None
    
    def stop_websocket_monitoring(self):
        """웹소켓 모니터링 중지"""
        try:
            if self.websocket_monitor:
                self.websocket_monitor.stop_monitoring()
                self.websocket_monitor = None
                self.logger.info("🛑 웹소켓 모니터링 중지 완료")
            else:
                self.logger.info("📡 웹소켓 모니터링이 실행되고 있지 않음")
        except Exception as e:
            self.logger.error(f"❌ 웹소켓 모니터링 중지 실패: {e}")
    
    async def _on_account_update(self, account_data: Dict):
        """웹소켓 계좌 업데이트 콜백"""
        try:
            unrealized_pnl = account_data.get('unrealized_pnl', 0)
            margin_ratio = account_data.get('margin_ratio', 0)
            
            # 즉시 위험 상황 체크
            if unrealized_pnl < -1000:  # $1000 이상 손실
                await self._send_immediate_alert(
                    "🚨 큰 손실 발생",
                    f"미실현 손익: ${unrealized_pnl:,.2f}",
                    "danger"
                )
            
            if margin_ratio > 0.9:  # 마진율 90% 초과
                await self._send_immediate_alert(
                    "⚠️ 위험한 마진율",
                    f"현재 마진율: {margin_ratio:.1%}",
                    "warning"
                )
            
            self.logger.debug(f"📊 계좌 업데이트: PnL ${unrealized_pnl:,.2f}, 마진 {margin_ratio:.1%}")
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 업데이트 콜백 실패: {e}")
    
    async def _on_price_update(self, symbol: str, price: float, change_pct: float):
        """웹소켓 가격 업데이트 콜백"""
        try:
            # 큰 가격 변동 감지 (5% 이상)
            if abs(change_pct) > 5.0:
                await self._send_immediate_alert(
                    f"📈 {symbol} 급격한 가격 변동",
                    f"현재가: ${price:,.2f} ({change_pct:+.2f}%)",
                    "info"
                )
            
            self.logger.debug(f"💹 {symbol}: ${price:,.2f} ({change_pct:+.2f}%)")
            
        except Exception as e:
            self.logger.error(f"❌ 가격 업데이트 콜백 실패: {e}")
    
    async def _on_order_update(self, order_data: Dict):
        """웹소켓 주문 업데이트 콜백"""
        try:
            symbol = order_data.get('symbol', '')
            status = order_data.get('status', '')
            side = order_data.get('side', '')
            
            # 주문 체결 알림
            if status in ['FILLED', 'PARTIALLY_FILLED']:
                await self._send_immediate_alert(
                    f"📋 {symbol} 주문 체결",
                    f"{side} 주문이 체결되었습니다",
                    "success"
                )
            
            self.logger.debug(f"📋 주문 업데이트: {symbol} {side} ({status})")
            
        except Exception as e:
            self.logger.error(f"❌ 주문 업데이트 콜백 실패: {e}")
    
    async def _send_immediate_alert(self, title: str, message: str, level: str):
        """즉시 알림 발송 (웹소켓 콜백용)"""
        try:
            self.discord_notifier.send_alert(
                f"{title}\n{message}",
                level=level
            )
        except Exception as e:
            self.logger.error(f"❌ 즉시 알림 발송 실패: {e}")
    
    def get_websocket_status(self) -> Dict:
        """웹소켓 모니터링 상태 조회"""
        try:
            if not self.websocket_monitor:
                return {
                    'enabled': self.websocket_enabled,
                    'running': False,
                    'status': '웹소켓 모니터링이 시작되지 않음'
                }
            
            status = self.websocket_monitor.get_monitoring_status()
            return {
                'enabled': self.websocket_enabled,
                'running': status['is_monitoring'],
                'connections': status['active_connections'],
                'symbols': status['monitored_symbols'],
                'last_heartbeat': status['last_heartbeat'],
                'account_data': status['current_account']
            }
        except Exception as e:
            return {
                'enabled': self.websocket_enabled,
                'running': False,
                'error': str(e)
            }
    
    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"❌ 설정 파일 로드 실패: {e}")
            return {}
    
    def run_heartbeat_check(self) -> Dict:
        """심장박동 체크 실행 - 모든 위험 요소 점검"""
        try:
            self.last_heartbeat = TimeManager.utc_now()
            self.logger.info("💓 심장박동 체크 시작")
            
            # 1. 계좌 상태 체크
            account_status = self._check_account_status()
            
            # 2. 포지션 위험도 체크
            position_risk = self._check_position_risk()
            
            # 3. 시스템 상태 체크
            system_status = self._check_system_status()
            
            # 3.5. 트리거 체크 및 자동 재분석
            trigger_status = self._check_triggers()
            
            # 4. 일일 손실 추적
            daily_loss = self._track_daily_loss(account_status)
            
            # 5. 종합 위험 평가
            risk_assessment = self._assess_overall_risk(
                account_status, position_risk, system_status, daily_loss
            )
            
            # 6. 긴급 조치 판단 및 실행
            emergency_action = self._handle_emergency_conditions(risk_assessment)
            
            # 7. 알림 발송
            self._send_notifications_if_needed(risk_assessment, emergency_action)
            
            # 에러 카운터 리셋 (성공적 실행)
            self.consecutive_errors = 0
            
            result = {
                'timestamp': self.last_heartbeat.isoformat(),
                'status': 'healthy',
                'account_status': account_status,
                'position_risk': position_risk,
                'system_status': system_status,
                'daily_loss': daily_loss,
                'risk_assessment': risk_assessment,
                'emergency_action': emergency_action
            }
            
            self.logger.info(f"✅ 심장박동 체크 완료 - 위험도: {risk_assessment['risk_level']}")
            return result
            
        except Exception as e:
            self.consecutive_errors += 1
            self.logger.error(f"❌ 심장박동 체크 실패 ({self.consecutive_errors}회): {e}")
            
            # 연속 에러가 임계치를 넘으면 긴급 알림
            if self.consecutive_errors >= self.config.get('notifications', {}).get('emergency_conditions', {}).get('system_error_count', 3):
                self._send_emergency_alert(f"시스템 연속 에러 {self.consecutive_errors}회 발생", str(e))
            
            return {
                'timestamp': TimeManager.utc_now().isoformat(),
                'status': 'error',
                'error': str(e),
                'consecutive_errors': self.consecutive_errors
            }
    
    def _check_account_status(self) -> Dict:
        """계좌 상태 점검"""
        try:
            account_info = self.trade_executor.get_account_status()
            
            if not account_info:
                return {'status': 'error', 'error': '계좌 정보 조회 실패'}
            
            total_balance = account_info.get('total_balance', 0)
            available_balance = account_info.get('available_balance', 0)
            unrealized_pnl = account_info.get('unrealized_pnl', 0)
            margin_ratio = account_info.get('margin_ratio', 0)
            
            # 위험 신호 체크
            warnings = []
            if margin_ratio > 0.8:  # 마진 비율 80% 초과
                warnings.append(f"높은 마진 비율: {margin_ratio:.2%}")
            
            if available_balance < total_balance * 0.1:  # 가용 자금 10% 미만
                warnings.append(f"낮은 가용 자금: ${available_balance:.2f}")
            
            if unrealized_pnl < -total_balance * 0.05:  # 미실현 손실 5% 초과
                warnings.append(f"큰 미실현 손실: ${unrealized_pnl:.2f}")
            
            return {
                'status': 'healthy' if not warnings else 'warning',
                'total_balance': total_balance,
                'available_balance': available_balance,
                'unrealized_pnl': unrealized_pnl,
                'margin_ratio': margin_ratio,
                'warnings': warnings
            }
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 상태 체크 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _check_position_risk(self) -> Dict:
        """포지션 위험도 점검"""
        try:
            position_info = self.trade_executor.monitor_position()
            
            if not position_info:
                return {'status': 'no_position'}
            
            if position_info.get('status') == 'completed':
                return {'status': 'position_closed', 'details': position_info}
            
            position = position_info.get('position', {})
            if not position:
                return {'status': 'no_position'}
            
            # 현재 가격과 손절매 가격 비교
            current_price = position.get('current_price', 0)
            stop_loss = position.get('stop_loss', 0)
            entry_price = position.get('entry_price', 0)
            direction = position.get('direction', '')
            unrealized_pnl = position_info.get('unrealized_pnl', 0)
            
            warnings = []
            risk_level = 'low'
            
            # 손절매 근접 체크
            if stop_loss > 0 and current_price > 0:
                if direction == "LONG":
                    stop_distance_percent = ((current_price - stop_loss) / current_price) * 100
                    if stop_distance_percent < 2:  # 손절가 2% 이내 접근
                        warnings.append(f"손절가 근접: 현재가 ${current_price:.4f}, 손절가 ${stop_loss:.4f}")
                        risk_level = 'high'
                else:  # SHORT
                    stop_distance_percent = ((stop_loss - current_price) / current_price) * 100
                    if stop_distance_percent < 2:
                        warnings.append(f"손절가 근접: 현재가 ${current_price:.4f}, 손절가 ${stop_loss:.4f}")
                        risk_level = 'high'
            
            # 급격한 변동성 체크 (5% 이상 급변)
            if entry_price > 0 and current_price > 0:
                price_change_percent = abs((current_price - entry_price) / entry_price) * 100
                if price_change_percent > 10:  # 10% 이상 급변
                    warnings.append(f"급격한 가격 변동: {price_change_percent:.1f}%")
                    risk_level = 'medium' if risk_level == 'low' else risk_level
            
            # 큰 미실현 손실 체크
            if unrealized_pnl < -50:  # $50 이상 손실
                warnings.append(f"큰 미실현 손실: ${unrealized_pnl:.2f}")
                risk_level = 'medium' if risk_level == 'low' else risk_level
            
            return {
                'status': 'active',
                'position': position,
                'risk_level': risk_level,
                'warnings': warnings,
                'unrealized_pnl': unrealized_pnl,
                'current_price': current_price
            }
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 위험도 체크 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _check_system_status(self) -> Dict:
        """시스템 상태 점검"""
        try:
            warnings = []
            
            # 파일 시스템 체크
            required_files = [
                os.path.join(project_root, 'config', 'config.yaml'),
                os.path.join(project_root, 'data', 'database', 'delphi_trades.db'),
                os.path.join(project_root, 'logs', 'delphi.log')
            ]
            
            for file_path in required_files:
                if not os.path.exists(file_path):
                    warnings.append(f"필수 파일 없음: {file_path}")
            
            # 로그 파일 크기 체크 (100MB 초과시 경고)
            log_file = os.path.join(project_root, 'logs', 'delphi.log')
            if os.path.exists(log_file):
                log_size_mb = os.path.getsize(log_file) / (1024 * 1024)
                if log_size_mb > 100:
                    warnings.append(f"로그 파일 크기 초과: {log_size_mb:.1f}MB")
            
            # 데이터베이스 접근성 체크
            try:
                import sqlite3
                db_path = os.path.join(project_root, 'data', 'database', 'delphi_trades.db')
                conn = sqlite3.connect(db_path)
                conn.execute("SELECT COUNT(*) FROM trades").fetchone()
                conn.close()
            except Exception as db_e:
                warnings.append(f"데이터베이스 접근 오류: {str(db_e)}")
            
            return {
                'status': 'healthy' if not warnings else 'warning',
                'warnings': warnings,
                'consecutive_errors': self.consecutive_errors
            }
            
        except Exception as e:
            self.logger.error(f"❌ 시스템 상태 체크 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _check_triggers(self) -> Dict:
        """트리거 체크 및 자동 재분석 실행"""
        try:
            from src.data.binance_connector import get_current_price
            
            # 현재 가격 조회
            current_price = get_current_price("SOLUSDT")
            if not current_price:
                return {'status': 'error', 'error': '가격 조회 실패'}
            
            # 현재 포지션 상태 확인
            position_info = self.trade_executor.monitor_position()
            has_position = (position_info and 
                          position_info.get('status') == 'active' and 
                          position_info.get('position'))
            
            result = {'status': 'monitoring', 'current_price': current_price}
            
            if has_position:
                # 포지션이 있는 경우 - 포지션 트리거 체크
                position = position_info['position']
                triggers = self.trigger_manager.load_triggers()
                position_triggers = [t for t in triggers if t.get('trigger_type') == 'position']
                
                # 시장 데이터 준비
                market_data = {
                    'current_price': current_price,
                    'volatility': 0,  # TODO: 실제 변동성 계산
                    'volume_ratio': 1.0,  # TODO: 실제 거래량 비율
                    'trend_strength': 0  # TODO: 실제 추세 강도
                }
                
                # 포지션 모니터링 실행
                position_action = self.position_monitor.check_position_triggers(
                    position, current_price, market_data, position_triggers
                )
                
                if position_action:
                    if position_action['action'] == 'emergency_action':
                        # 긴급 상황 처리
                        self._handle_emergency_action(position_action)
                        result['position_emergency'] = position_action
                    elif position_action['action'] == 'request_ai_analysis':
                        # AI 재분석 요청
                        self._request_position_reanalysis(position_action)
                        result['position_reanalysis'] = position_action
                
                result['position_triggers_count'] = len(position_triggers)
                result['has_position'] = True
                
            else:
                # 포지션이 없는 경우 - HOLD 트리거 체크
                triggered = self.trigger_manager.check_triggers(current_price)
                
                if triggered:
                    self.logger.info(f"HOLD 트리거 발동! {triggered['trigger_id']} - {triggered['rationale']}")
                    
                    # Discord 트리거 발동 알림
                    try:
                        self.discord_notifier.send_trigger_activation(triggered, current_price)
                        self.logger.info("Discord 알림 발송 완료")
                    except Exception as e:
                        self.logger.warning(f"Discord 알림 실패: {e}")
                    
                    # 전체 시스템 재분석 실행
                    try:
                        self.logger.info("트리거 발동으로 인한 전체 시스템 재분석 시작")
                        from src.main import DelphiOrchestrator
                        orchestrator = DelphiOrchestrator()
                        results = orchestrator.run_full_analysis()
                        
                        if results.get('synthesizer_playbook'):
                            self.logger.info("트리거 발동 재분석 완료")
                            result.update({
                                'status': 'triggered',
                                'trigger_id': triggered['trigger_id'],
                                'price': current_price,
                                'reanalysis_completed': True
                            })
                        else:
                            self.logger.warning("트리거 발동 재분석 실패")
                            result.update({
                                'status': 'triggered',
                                'trigger_id': triggered['trigger_id'],
                                'price': current_price,
                                'reanalysis_completed': False
                            })
                            
                    except Exception as e:
                        self.logger.error(f"트리거 발동 재분석 실행 실패: {e}")
                        result.update({
                            'status': 'triggered',
                            'trigger_id': triggered['trigger_id'],
                            'price': current_price,
                            'reanalysis_error': str(e)
                        })
                else:
                    # HOLD 트리거 미발동
                    hold_triggers = [t for t in self.trigger_manager.load_triggers() 
                                   if t.get('trigger_type') != 'position']
                    result['hold_triggers_count'] = len(hold_triggers)
                    result['has_position'] = False
            
            return result
                
        except Exception as e:
            self.logger.error(f"트리거 체크 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _track_daily_loss(self, account_status: Dict) -> Dict:
        """일일 손실 추적"""
        try:
            current_time = TimeManager.utc_now()
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 24시간 이전 데이터 정리
            self.daily_loss_tracking = [
                loss for loss in self.daily_loss_tracking 
                if datetime.fromisoformat(loss['timestamp'].replace('Z', '+00:00')) > today_start
            ]
            
            total_balance = account_status.get('total_balance', 0)
            unrealized_pnl = account_status.get('unrealized_pnl', 0)
            
            # 오늘의 손실 계산 (단순화 - 실제로는 더 정교한 추적 필요)
            daily_loss_usd = abs(min(0, unrealized_pnl))
            daily_loss_percent = (daily_loss_usd / max(total_balance, 1)) * 100 if total_balance > 0 else 0
            
            # 손실 기록 추가
            if daily_loss_usd > 0:
                self.daily_loss_tracking.append({
                    'timestamp': current_time.isoformat(),
                    'loss_usd': daily_loss_usd,
                    'loss_percent': daily_loss_percent
                })
            
            # 일일 손실 한도 체크
            daily_limit_percent = self.config.get('notifications', {}).get('emergency_conditions', {}).get('daily_loss_percent', 5.0)
            
            return {
                'daily_loss_usd': daily_loss_usd,
                'daily_loss_percent': daily_loss_percent,
                'daily_limit_percent': daily_limit_percent,
                'limit_exceeded': daily_loss_percent > daily_limit_percent,
                'total_events_today': len(self.daily_loss_tracking)
            }
            
        except Exception as e:
            self.logger.error(f"❌ 일일 손실 추적 실패: {e}")
            return {'error': str(e)}
    
    def _assess_overall_risk(self, account_status: Dict, position_risk: Dict, 
                           system_status: Dict, daily_loss: Dict) -> Dict:
        """종합 위험 평가"""
        try:
            risk_factors = []
            risk_score = 0
            
            # 계좌 위험도 평가
            if account_status.get('status') == 'warning':
                risk_score += 30
                risk_factors.extend(account_status.get('warnings', []))
            elif account_status.get('status') == 'error':
                risk_score += 50
                risk_factors.append("계좌 상태 조회 오류")
            
            # 포지션 위험도 평가
            pos_risk_level = position_risk.get('risk_level', 'low')
            if pos_risk_level == 'high':
                risk_score += 40
            elif pos_risk_level == 'medium':
                risk_score += 20
            risk_factors.extend(position_risk.get('warnings', []))
            
            # 시스템 위험도 평가
            if system_status.get('status') == 'warning':
                risk_score += 15
                risk_factors.extend(system_status.get('warnings', []))
            elif system_status.get('status') == 'error':
                risk_score += 30
            
            # 일일 손실 평가
            if daily_loss.get('limit_exceeded', False):
                risk_score += 50
                risk_factors.append(f"일일 손실 한도 초과: {daily_loss.get('daily_loss_percent', 0):.1f}%")
            
            # 연속 에러 평가
            if self.consecutive_errors >= 2:
                risk_score += 20
                risk_factors.append(f"시스템 연속 에러 {self.consecutive_errors}회")
            
            # 종합 위험도 결정
            if risk_score >= 70:
                risk_level = 'critical'
            elif risk_score >= 40:
                risk_level = 'high'
            elif risk_score >= 20:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            return {
                'risk_level': risk_level,
                'risk_score': risk_score,
                'risk_factors': risk_factors,
                'requires_action': risk_score >= 70
            }
            
        except Exception as e:
            self.logger.error(f"❌ 위험 평가 실패: {e}")
            return {'risk_level': 'unknown', 'error': str(e)}
    
    def _handle_emergency_conditions(self, risk_assessment: Dict) -> Dict:
        """긴급 상황 처리"""
        try:
            if not risk_assessment.get('requires_action', False):
                return {'action': 'none', 'reason': '정상 상태'}
            
            risk_level = risk_assessment.get('risk_level', 'low')
            risk_factors = risk_assessment.get('risk_factors', [])
            
            # 긴급 청산 조건 체크
            emergency_conditions = [
                "일일 손실 한도 초과",
                "손절가 근접",
                "큰 미실현 손실",
                "높은 마진 비율"
            ]
            
            should_emergency_close = any(
                any(condition in factor for condition in emergency_conditions)
                for factor in risk_factors
            ) or risk_level == 'critical'
            
            if should_emergency_close:
                self.logger.warning(f"🚨 긴급 청산 조건 발생: {', '.join(risk_factors)}")
                
                # 긴급 포지션 청산 실행
                close_result = self.trade_executor.emergency_close_position()
                
                if close_result.get('status') == 'emergency_closed':
                    self.logger.info("🚨 긴급 포지션 청산 완료")
                    return {
                        'action': 'emergency_close',
                        'reason': ', '.join(risk_factors),
                        'result': close_result
                    }
                elif close_result.get('status') == 'no_position':
                    return {
                        'action': 'none',
                        'reason': '청산할 포지션 없음'
                    }
                else:
                    self.logger.error(f"❌ 긴급 청산 실패: {close_result}")
                    return {
                        'action': 'emergency_close_failed',
                        'reason': close_result.get('error', '알 수 없는 오류'),
                        'risk_factors': risk_factors
                    }
            
            return {
                'action': 'monitor',
                'reason': f'위험도 {risk_level} - 지속 모니터링',
                'risk_factors': risk_factors
            }
            
        except Exception as e:
            self.logger.error(f"❌ 긴급 상황 처리 실패: {e}")
            return {'action': 'error', 'error': str(e)}
    
    def _send_notifications_if_needed(self, risk_assessment: Dict, emergency_action: Dict):
        """필요시 알림 발송 (Discord)"""
        try:
            notification_config = self.config.get('notifications', {})
            discord_config = notification_config.get('discord', {})
            
            if not discord_config.get('enabled', False):
                self.logger.warning("⚠️ Discord 알림이 비활성화됨")
                return
            
            risk_level = risk_assessment.get('risk_level', 'low')
            action = emergency_action.get('action', 'none')
            
            # 알림 발송 조건
            should_notify = (
                risk_level in ['high', 'critical'] or
                action in ['emergency_close', 'emergency_close_failed'] or
                self.consecutive_errors >= 3
            )
            
            if should_notify:
                # 중복 알림 방지 (같은 내용 1시간 내 재발송 금지)
                alert_key = f"{risk_level}_{action}"
                current_time = TimeManager.utc_now()
                
                # 최근 1시간 내 같은 알림이 발송되었는지 체크
                recent_alerts = [
                    alert for alert in self.risk_alerts_sent
                    if (current_time - datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))).total_seconds() < 3600
                    and alert['key'] == alert_key
                ]
                
                if not recent_alerts:
                    # Discord 심장박동 알림 발송
                    if self.discord_notifier.send_heartbeat_alert(risk_assessment, emergency_action):
                        self.risk_alerts_sent.append({
                            'timestamp': current_time.isoformat(),
                            'key': alert_key,
                            'level': risk_level
                        })
                        self.logger.info(f"💬 Discord 위험 알림 발송 완료: {risk_level}")
                    else:
                        self.logger.error("❌ Discord 위험 알림 발송 실패")
                else:
                    self.logger.info(f"⏭️ 중복 알림 방지: {alert_key}")
                    
        except Exception as e:
            self.logger.error(f"❌ 알림 발송 처리 실패: {e}")
    
    def _create_alert_message(self, risk_assessment: Dict, emergency_action: Dict) -> str:
        """알림 메시지 생성"""
        current_time = TimeManager.utc_now()
        
        message = f"""
🚨 델파이 트레이딩 시스템 위험 알림

📅 발생 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC

⚠️ 위험도: {risk_assessment.get('risk_level', 'unknown').upper()}
📊 위험 점수: {risk_assessment.get('risk_score', 0)}/100

🔍 위험 요인:
"""
        
        for factor in risk_assessment.get('risk_factors', []):
            message += f"  • {factor}\n"
        
        message += f"\n🎯 조치 사항: {emergency_action.get('action', 'none')}"
        if emergency_action.get('reason'):
            message += f"\n📝 조치 이유: {emergency_action.get('reason')}"
        
        if emergency_action.get('result'):
            result = emergency_action['result']
            if result.get('status') == 'emergency_closed':
                message += f"\n✅ 긴급 청산 완료 (주문 ID: {result.get('order_id', 'N/A')})"
            elif 'error' in result:
                message += f"\n❌ 긴급 청산 실패: {result.get('error', 'Unknown error')}"
        
        message += f"""

🔧 시스템 상태:
  • 연속 에러 횟수: {self.consecutive_errors}
  • 마지막 정상 체크: {self.last_heartbeat.strftime('%H:%M:%S')} UTC

이 메시지는 델파이 트레이딩 시스템에서 자동 발송되었습니다.
"""
        
        return message
    
    def _send_email_alert(self, subject: str, message: str) -> bool:
        """이메일 알림 발송"""
        try:
            email_config = self.config.get('notifications', {}).get('email', {})
            
            smtp_server = email_config.get('smtp_server')
            smtp_port = email_config.get('smtp_port', 587)
            username = email_config.get('username')
            password = email_config.get('password')
            recipients = email_config.get('recipients', [])
            
            if not all([smtp_server, username, password, recipients]):
                self.logger.warning("⚠️ 이메일 설정 불완전 - 알림 발송 생략")
                return False
            
            # 이메일 메시지 구성
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            # SMTP 서버 연결 및 발송
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 이메일 발송 실패: {e}")
            return False
    
    def _send_emergency_alert(self, title: str, details: str):
        """긴급 상황 알림 (즉시 발송)"""
        message = f"""
🚨🚨🚨 **델파이 시스템 긴급 상황** 🚨🚨🚨

**{title}**

📝 **상세 내용:**
{details}

📅 **발생 시간**: {TimeManager.utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC

⚠️ **즉시 시스템을 점검하시기 바랍니다.**
"""
        
        if self.discord_notifier.send_alert(f"🚨 긴급상황: {title}", message, "critical"):
            self.logger.warning(f"🚨 Discord 긴급 알림 발송 완료: {title}")
        else:
            self.logger.error(f"❌ Discord 긴급 알림 발송 실패: {title}")
    
    def _handle_emergency_action(self, position_action: Dict):
        """포지션 긴급 상황 처리"""
        try:
            reason = position_action.get('reason', '알 수 없는 긴급 상황')
            self.logger.critical(f"포지션 긴급 상황 발생: {reason}")
            
            # 긴급 청산 실행
            close_result = self.trade_executor.emergency_close_position()
            
            if close_result.get('status') == 'emergency_closed':
                self.logger.info("긴급 포지션 청산 완료")
                self._send_emergency_alert(
                    "포지션 긴급 청산 완료",
                    f"사유: {reason}\n주문 ID: {close_result.get('order_id', 'N/A')}"
                )
            else:
                self.logger.error(f"긴급 청산 실패: {close_result}")
                self._send_emergency_alert(
                    "포지션 긴급 청산 실패",
                    f"사유: {reason}\n오류: {close_result.get('error', '알 수 없는 오류')}"
                )
                
        except Exception as e:
            self.logger.error(f"긴급 상황 처리 실패: {e}")
            self._send_emergency_alert("긴급 상황 처리 오류", str(e))
    
    def _request_position_reanalysis(self, position_action: Dict):
        """포지션 재분석 요청"""
        try:
            trigger = position_action.get('trigger', {})
            reason = position_action.get('reason', '')
            
            # 스케줄러 체크 - 재분석 가능한지 확인
            if not self.smart_scheduler.should_run_scheduled_analysis():
                self.logger.info(f"재분석 쿨다운 중 - {reason}")
                return
            
            self.logger.info(f"포지션 재분석 시작: {reason}")
            
            # Discord 알림
            try:
                self.discord_notifier.send_alert(
                    f"포지션 재분석: {trigger.get('condition_type', 'unknown')}",
                    f"트리거: {trigger.get('trigger_id', 'N/A')}\n사유: {reason}",
                    level="info"
                )
            except Exception as e:
                self.logger.warning(f"Discord 알림 실패: {e}")
            
            # 전체 시스템 재분석 실행
            try:
                from src.main import DelphiOrchestrator
                orchestrator = DelphiOrchestrator()
                results = orchestrator.run_full_analysis()
                
                if results.get('synthesizer_playbook'):
                    self.logger.info("포지션 재분석 완료")
                else:
                    self.logger.warning("포지션 재분석 실패")
                    
            except Exception as e:
                self.logger.error(f"포지션 재분석 실행 실패: {e}")
                
        except Exception as e:
            self.logger.error(f"포지션 재분석 요청 실패: {e}")


def run_single_heartbeat():
    """단일 심장박동 체크 실행 (테스트용)"""
    checker = HeartbeatChecker()
    result = checker.run_heartbeat_check()
    print(f"심장박동 체크 결과: {result['status']}")
    if result.get('risk_assessment'):
        print(f"위험도: {result['risk_assessment']['risk_level']}")
    return result


def run_continuous_heartbeat(interval_seconds: int = 60):
    """지속적 심장박동 체크 (운영용)"""
    checker = HeartbeatChecker()
    checker.logger.info(f"💓 지속적 심장박동 체크 시작 (간격: {interval_seconds}초)")
    
    try:
        while True:
            result = checker.run_heartbeat_check()
            
            if result['status'] == 'healthy':
                checker.logger.info(f"💚 시스템 정상 - 위험도: {result.get('risk_assessment', {}).get('risk_level', 'unknown')}")
            else:
                checker.logger.warning(f"⚠️ 시스템 주의 - 상태: {result['status']}")
            
            # 다음 체크까지 대기
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        checker.logger.info("🛑 심장박동 체크 수동 중단")
    except Exception as e:
        checker.logger.error(f"❌ 심장박동 체크 시스템 오류: {e}")
        # 긴급 알림 발송
        checker._send_emergency_alert("심장박동 체크 시스템 오류", str(e))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="델파이 트레이딩 시스템 심장박동 체커")
    parser.add_argument('--mode', choices=['single', 'continuous'], default='single',
                       help='실행 모드: single(단일 실행) 또는 continuous(지속 실행)')
    parser.add_argument('--interval', type=int, default=60,
                       help='지속 실행시 체크 간격(초)')
    
    args = parser.parse_args()
    
    if args.mode == 'single':
        run_single_heartbeat()
    else:
        run_continuous_heartbeat(args.interval)