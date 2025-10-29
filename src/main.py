"""
델파이 트레이딩 시스템 v3.0 - 메인 오케스트레이터 (모듈화 버전)
5개 AI 에이전트를 조합하여 자율 거래 시스템 구현
"""

import os
import sys
import io
import logging
import json
import threading
import time
from typing import Dict, Optional
from datetime import datetime

# 프로젝트 루트를 Python path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# WebSocket 클라이언트
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("⚠️ websocket-client 라이브러리가 설치되지 않았습니다. 대시보드 실시간 연동이 비활성화됩니다.")

# 모듈 임포트
from utils.time_manager import TimeManager
from utils.performance_optimizer import performance_optimizer, health_checker
from agents.chartist import chartist_agent
from agents.journalist import journalist_agent
# quant_agent는 조건부로 import (아래에서 처리)
from agents.stoic import stoic_agent
from agents.synthesizer import synthesizer_agent
from agents.trigger_manager import TriggerManager
from agents.position_trigger_manager import PositionTriggerManager
from data.binance_connector import get_full_quant_data, get_current_price
from trading.trade_executor import trade_executor
from utils.discord_notifier import DiscordNotifier
from data.trade_database import get_trade_history
from data.trading_context import trading_context
from integration.scenario_system_integration import scenario_integration

# 통합 로깅 설정
from utils.logging_config import init_logging, get_logger

# 로깅 시스템 초기화
init_logging()

class DashboardReporter:
    """대시보드로 실시간 데이터 전송"""

    def __init__(self, dashboard_url=None):
        # 환경변수 우선, 없으면 기본값
        self.dashboard_url = dashboard_url or os.getenv("DASHBOARD_WS_URL", "ws://localhost:8001/ws")
        self.ws = None
        self.connected = False
        self.lock = threading.Lock()
        self._runner_thread = None

        # run_id 생성 (각 실행마다 고유 ID)
        self.run_id = datetime.now().strftime("RUN_%Y%m%d_%H%M%S")

        if WEBSOCKET_AVAILABLE:
            self._start_ws_client()

    def _start_ws_client(self):
        """수신 스레드를 갖는 WebSocketApp 시작 (ping/pong, 자동재연결)"""
        logger = get_logger('DashboardReporter')

        def on_open(ws):
            self.connected = True
            logger.info(f"[OK] 대시보드 연결 성공: {self.dashboard_url}")

        def on_close(ws, close_status_code, close_msg):
            self.connected = False
            logger.warning("[WARN] 대시보드 연결 종료")

        def on_error(ws, err):
            self.connected = False
            logger.error(f"[WS ERROR] {err}")

        def on_message(ws, msg):
            # 대시보드가 push하는 system_status/metrics 등은 소비만 하고 버린다
            # (안 받으면 수신버퍼가 꽉 차서 10053이 재발)
            pass

        self.ws = websocket.WebSocketApp(
            self.dashboard_url,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
        )

        def runner():
            # ping_interval로 keepalive, 끊기면 자동 재접속 루프
            while True:
                try:
                    self.ws.run_forever(
                        ping_interval=20,
                        ping_timeout=10,
                        reconnect=5,
                    )
                except Exception as e:
                    logger.error(f"[WS runner] 예외: {e}")
                time.sleep(3)  # 재시도 백오프

        self._runner_thread = threading.Thread(target=runner, daemon=True)
        self._runner_thread.start()

    def send_log(self, level: str, message: str):
        """로그 메시지 전송"""
        if not self.connected:
            return  # runner가 재연결 시도 중

        logger = get_logger('DashboardReporter')
        try:
            with self.lock:
                data = {
                    "type": "log",
                    "level": level,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
                self.ws.send(json.dumps(data))
        except Exception as e:
            logger.error(f"로그 전송 실패: {e}")
            self.connected = False

    def send_run_start(self):
        """새 실행 시작 알림 전송"""
        if not self.connected:
            return

        logger = get_logger('DashboardReporter')
        try:
            with self.lock:
                data = {
                    "type": "run_start",
                    "run_id": self.run_id,
                    "timestamp": datetime.now().isoformat()
                }
                self.ws.send(json.dumps(data))
                logger.info(f"[OK] 실행 시작 알림 전송 (run_id: {self.run_id})")
        except Exception as e:
            logger.error(f"실행 시작 알림 전송 실패: {e}")
            self.connected = False

    def send_agent_analysis(self, agent_name: str, result: Dict):
        """에이전트 분석 결과 전송"""
        if not self.connected:
            return  # runner가 재연결 시도 중

        logger = get_logger('DashboardReporter')
        try:
            with self.lock:
                data = {
                    "type": "agent_analysis",
                    "run_id": self.run_id,
                    "agent": agent_name,
                    "analysis": result,
                    "timestamp": datetime.now().isoformat()
                }
                self.ws.send(json.dumps(data))
                logger.info(f"[OK] {agent_name} 분석 결과 전송 완료")
        except Exception as e:
            logger.error(f"에이전트 분석 전송 실패: {e}")
            self.connected = False

    def close(self):
        """연결 종료"""
        if self.ws and self.connected:
            try:
                self.ws.close()
            except:
                pass

class DelphiOrchestrator:
    """델파이 트레이딩 시스템의 메인 오케스트레이터"""
    
    def __init__(self):
        self.logger = get_logger('DelphiOrchestrator')
        self.execution_time = TimeManager.get_system_start_time()
        # 프로젝트 루트 기준으로 차트 이미지 경로 설정
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.chart_image_paths = [
            os.path.join(project_root, "data", "screenshots", "chart_5m.png"),
            os.path.join(project_root, "data", "screenshots", "chart_15m.png"),
            os.path.join(project_root, "data", "screenshots", "chart_1H.png"),
            os.path.join(project_root, "data", "screenshots", "chart_1D.png")
        ]
        self.target_asset = "SOLUSDT"

        # Discord 알림기 초기화
        self.discord_notifier = DiscordNotifier()

        # 트리거 매니저 초기화
        self.trigger_manager = TriggerManager(
            trigger_file=os.path.join(project_root, "data", "triggers.json")
        )

        # 포지션 트리거 매니저 초기화
        self.position_trigger_manager = PositionTriggerManager(self.trigger_manager)

        # 시나리오 학습 시스템 초기화
        self.scenario_integration = scenario_integration

        # 대시보드 리포터 초기화
        self.dashboard_reporter = DashboardReporter()

        # PENDING 거래 정리 제거 - 시스템 설계상 PENDING 상태를 사용하지 않음
        
    
    def run_full_analysis(self) -> Dict:
        """전체 분석 프로세스 실행"""
        self.logger.info("✅ '프로젝트 델파이' 오케스트레이터 v3.0 시작")

        # 대시보드에 새 실행 시작 알림
        if hasattr(self, 'dashboard_reporter'):
            self.dashboard_reporter.send_run_start()

        # Phase 2: 확장된 트리거 체크
        try:
            from data.binance_connector import get_current_price
            current_price = get_current_price(self.target_asset)
            
            # 변동성과 거래량 데이터 수집 시도
            current_volatility = None
            current_volume = None
            
            try:
                from data.binance_connector import get_full_quant_data
                market_data = get_full_quant_data(self.target_asset)
                if market_data:
                    current_volatility = market_data.get('volatility', 0)
                    current_volume = market_data.get('volume_24h', 0)
            except Exception as e:
                self.logger.debug(f"추가 시장 데이터 수집 실패: {e}")
            
            # 확장된 트리거 체크 (가격, 변동성, 거래량)
            triggered = self.trigger_manager.check_extended_triggers(
                current_price, current_volatility, current_volume
            )
            
            if triggered:
                trigger_id = triggered.get('trigger_id', 'UNKNOWN')
                rationale = triggered.get('rationale', '사유 없음')
                self.logger.info(f"🎯 트리거 발동! {trigger_id} - {rationale}")
                self.logger.info("트리거에 의한 재분석을 시작합니다...")
            else:
                # 현재 활성 트리거 상태 로깅
                trigger_summary = self.trigger_manager.get_active_triggers_summary()
                self.logger.info(f"📌 {trigger_summary}")
        except Exception as e:
            self.logger.warning(f"⚠️ 트리거 체크 실패: {e}")
        
        # 시스템 상태 체크
        health_status = health_checker.run_health_checks()
        if health_status['overall_status'] != 'HEALTHY':
            self.logger.error("❌ 시스템 상태 체크 실패")
            for check_name, check_result in health_status['checks'].items():
                if check_result['status'] != 'PASS':
                    self.logger.error(f"  - {check_name}: {check_result}")
        
        
        results = {
            'execution_time': self.execution_time,
            'health_status': health_status,
            'reports': {},
            'execution_result': None,
            'triggered_by': triggered if triggered else None  # 트리거 정보 추가
        }
        
        # results를 인스턴스 변수로 저장하여 다른 메서드에서 접근 가능하게 함
        self.results = results
        
        try:
            # 1. 차트 캡처 (차티스트 분석 전 필수)
            self._capture_latest_charts()
            
            # 2. 차티스트 분석
            results['reports']['chartist'] = self._run_chartist_analysis()
            
            # 3. 저널리스트 분석
            results['reports']['journalist'] = self._run_journalist_analysis()
            
            # Phase 3: 시장 이벤트 추적 (순수 기록용)
            try:
                from monitoring.market_event_tracker import market_event_tracker
                
                # 저널리스트 리포트와 함께 이벤트 추적
                events = market_event_tracker.track_all_events(
                    journalist_report=results['reports'].get('journalist')
                )
                
                if events:
                    self.logger.info(f"📊 {len(events)}개 시장 이벤트 감지 및 기록")
                    for event in events:
                        self.logger.debug(f"  - {event.event_type}: {event.event_id}")
            except Exception as e:
                self.logger.debug(f"시장 이벤트 추적 실패 (거래에는 영향 없음): {e}")
            
            # Phase 1: 시장 상태 로깅 추가
            try:
                from utils.logging_config import log_market_state
                from data.binance_connector import get_current_price
                
                current_price = get_current_price(self.target_asset)
                market_data = {
                    'price': current_price,
                    'timestamp': TimeManager.get_execution_time()['utc_iso'],
                    'asset': self.target_asset
                }
                
                # 추가 시장 데이터 수집 시도
                try:
                    from data.binance_connector import get_full_quant_data
                    quant_data = get_full_quant_data(self.target_asset)
                    if quant_data:
                        market_data['volatility'] = quant_data.get('volatility', 0)
                        market_data['volume_ratio'] = quant_data.get('volume_24h_change', 0)
                        market_data['rsi'] = quant_data.get('rsi', 0)
                except:
                    pass
                
                log_market_state(market_data)
            except Exception as e:
                self.logger.warning(f"시장 상태 로깅 실패: {e}")
            
            # 4. 퀀트 분석
            if results['reports']['chartist'] and results['reports']['journalist']:
                # 시나리오 기반 유사 거래 검색
                results['reports'] = self.scenario_integration.enhance_agent_reports(
                    results['reports'], 
                    self.target_asset
                )
                
                results['reports']['quant'] = self._run_quant_analysis(
                    results['reports']['chartist'], 
                    results['reports']['journalist']
                )
            
            # 5. 스토익 분석
            if results['reports']['chartist'] and results['reports']['journalist']:
                results['reports']['stoic'] = self._run_stoic_analysis(
                    results['reports']['chartist'], 
                    results['reports']['journalist'],
                    results['reports'].get('quant')  # 퀀트 리포트 추가
                )
            
            # 6. 신디사이저 종합 판단
            if self._all_reports_ready(results['reports']):
                synthesizer_playbook = self._run_synthesizer_analysis(results['reports'])
                results['synthesizer_playbook'] = synthesizer_playbook
                
                # 7. 거래 실행
                if synthesizer_playbook:
                    results['execution_result'] = self._execute_trade(
                        synthesizer_playbook, results['reports']
                    )
            
            # 성능 보고서 출력
            performance_report = performance_optimizer.get_performance_report()
            self.logger.info(f"📊 성능 보고서: {performance_report}")
            results['performance_report'] = performance_report
            
            # Phase 1: 일일 성과 리포트 생성 (하루 마지막 실행 시)
            try:
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from monitoring.daily_reporter import generate_daily_report
                from datetime import datetime
                
                current_hour = datetime.now().hour
                # 매일 23시대에 실행되는 경우 일일 리포트 생성
                if current_hour == 23:
                    self.logger.info("📊 일일 성과 리포트 생성 중...")
                    daily_result = generate_daily_report()
                    if daily_result['success']:
                        self.logger.info("✅ 일일 성과 리포트 생성 완료")
                    
                    # 주간 리포트 생성 추가 (일요일 23시)
                    current_day = datetime.now().weekday()
                    self.scenario_integration.generate_weekly_report_if_needed(current_hour, current_day)
                    
                    # Phase 4 제거: 일일 분석은 시나리오 기반 주간 분석으로 통합됨
                    self.logger.info("📊 일일 분석은 시나리오 기반 주간 분석으로 통합됨")
                        
            except Exception as e:
                self.logger.warning(f"일일 리포트 생성 실패: {e}")
            
            # 성능 최적화 - 중복 로깅 제거 (main()에서 최종 결과 출력함)
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ 오케스트레이터 실행 중 오류: {e}")
            results['error'] = str(e)
            return results
    
    def _capture_latest_charts(self):
        """최신 차트 생성 실행 (Binance API 기반)"""
        self.logger.info("=== [차트 생성] Binance API 기반 차트 생성 시작 ===")

        try:
            # API 기반 차트 생성 스크립트 실행
            import subprocess
            import sys

            # scripts/generate_charts_from_api.py 경로
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            chart_generator_script = os.path.join(project_root, "scripts", "generate_charts_from_api.py")

            # Windows 가상환경 Python으로 차트 생성 실행
            venv_python = os.path.join(project_root, "new_venv", "Scripts", "python.exe")

            self.logger.info(f"차트 생성 실행: {venv_python} {chart_generator_script}")
            self.logger.info(f"대상 심볼: {self.target_asset}")

            # 차트 생성 실행 (출력 캡처)
            result = subprocess.run(
                [venv_python, chart_generator_script, "--symbol", self.target_asset],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=60  # 1분 타임아웃 (API는 빠름)
            )

            if result.returncode == 0:
                self.logger.info("✅ [차트 생성] 완료 - 성공")
                # 생성된 이미지 파일 존재 확인
                for image_path in self.chart_image_paths:
                    if os.path.exists(image_path):
                        file_size = os.path.getsize(image_path)
                        self.logger.info(f"📊 {os.path.basename(image_path)}: {file_size:,} bytes")
                    else:
                        self.logger.warning(f"⚠️ 이미지 파일 없음: {image_path}")

                # 생성 스크립트 출력 로그
                if result.stdout:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            self.logger.debug(f"   {line}")
            else:
                self.logger.error(f"❌ [차트 생성] 실패 - 반환코드: {result.returncode}")
                if result.stderr:
                    self.logger.error(f"에러 출력: {result.stderr}")
                if result.stdout:
                    self.logger.error(f"표준 출력: {result.stdout}")

        except subprocess.TimeoutExpired:
            self.logger.error("❌ [차트 생성] 타임아웃 (1분 초과)")
        except Exception as e:
            self.logger.error(f"❌ [차트 생성] 실행 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # 차트 생성 실패해도 기존 이미지로 계속 진행
            self.logger.warning("⚠️ 기존 차트 이미지로 분석을 계속 진행합니다")
    
    def _run_chartist_analysis(self) -> Optional[Dict]:
        """차티스트 분석 실행"""
        self.logger.info("[차티스트] 분석 시작")
        self.dashboard_reporter.send_log("INFO", "[차티스트] 분석 시작")

        try:
            result = chartist_agent.analyze(self.chart_image_paths, self.execution_time, self.target_asset)
            if result:
                self._print_report("차티스트 분석 결과", result)
                self.dashboard_reporter.send_agent_analysis("chartist", result)
            else:
                self.logger.error("❌ [차티스트] 분석 실패")
                self.dashboard_reporter.send_log("ERROR", "[차티스트] 분석 실패")
            return result
        except Exception as e:
            self.logger.error(f"❌ [차티스트] 분석 중 오류: {e}")
            self.dashboard_reporter.send_log("ERROR", f"[차티스트] 분석 중 오류: {e}")
            return None
    
    def _run_journalist_analysis(self) -> Optional[Dict]:
        """저널리스트 분석 실행"""
        self.logger.info("=== [저널리스트] 분석 시작 ===")
        self.dashboard_reporter.send_log("INFO", "[저널리스트] 분석 시작")

        try:
            result = journalist_agent.analyze(self.target_asset, self.execution_time)
            if result:
                self._print_report("저널리스트 분석 결과", result)
                self.dashboard_reporter.send_agent_analysis("journalist", result)
            else:
                self.logger.error("❌ [저널리스트] 분석 실패")
                self.dashboard_reporter.send_log("ERROR", "[저널리스트] 분석 실패")
            return result
        except Exception as e:
            self.logger.error(f"❌ [저널리스트] 분석 중 오류: {e}")
            self.dashboard_reporter.send_log("ERROR", f"[저널리스트] 분석 중 오류: {e}")
            return None
    
    def _run_quant_analysis(self, chartist_report: Dict, journalist_report: Dict) -> Optional[Dict]:
        """퀀트 분석 실행"""
        self.logger.info("=== [퀀트] 데이터 수집 및 분석 시작 ===")
        self.dashboard_reporter.send_log("INFO", "[퀀트] 데이터 수집 및 분석 시작")

        try:
            # Phase 3 체크: 새로운 퀀트 v3 사용 여부
            use_v3 = os.getenv('USE_QUANT_V3', 'true').lower() == 'true'
            
            if use_v3:
                # 새로운 다층 시간대 데이터 수집
                from data.multi_timeframe_collector import multi_tf_collector
                from agents.quant_v3 import quant_agent_v3
                quant_agent = quant_agent_v3
                
                self.logger.info("🔄 퀀트 v3.0 (변화 추적) 모드 활성화")
                
                # 다층 시간대 데이터 수집
                market_data = multi_tf_collector.collect_all_timeframes(self.target_asset)
                if not market_data:
                    self.logger.warning("⚠️ 다층 시간대 데이터 수집 실패 - 퀀트 분석 생략")
                    return None
                
                # 기존 퀀트 데이터도 포함
                additional_data = get_full_quant_data(self.target_asset)
                if additional_data:
                    market_data.update(additional_data)
                
                result = quant_agent_v3.analyze(
                    chartist_report, journalist_report, 
                    market_data, self.execution_time
                )
            else:
                # 기존 퀀트 분석
                quant_market_data = get_full_quant_data(self.target_asset)
                if not quant_market_data:
                    self.logger.warning("⚠️ 퀀트 데이터 수집 실패 - 퀀트 분석 생략")
                    return None
                
                result = quant_agent.analyze(
                    chartist_report, journalist_report, 
                    quant_market_data, self.execution_time
                )
            
            if result:
                self._print_report("퀀트 분석 결과", result)
                self.dashboard_reporter.send_agent_analysis("quant", result)
            else:
                self.logger.error("❌ [퀀트] 분석 실패")
                self.dashboard_reporter.send_log("ERROR", "[퀀트] 분석 실패")
            return result
        except Exception as e:
            self.logger.error(f"❌ [퀀트] 분석 중 오류: {e}")
            self.dashboard_reporter.send_log("ERROR", f"[퀀트] 분석 중 오류: {e}")
            return None
    
    def _run_stoic_analysis(self, chartist_report: Dict, journalist_report: Dict, quant_report: Dict = None) -> Optional[Dict]:
        """스토익 분석 실행"""
        self.logger.info("=== [스토익] 리스크 분석 시작 ===")
        self.dashboard_reporter.send_log("INFO", "[스토익] 리스크 분석 시작")

        try:
            # 시장 데이터 수집
            from data.binance_connector import get_current_price
            from data.multi_timeframe_collector import multi_tf_collector
            
            market_data = multi_tf_collector.collect_all_timeframes(self.target_asset)
            
            # 현재 포지션 정보 추가
            current_position = trade_executor.get_current_position_status()
            self.logger.info(f"[DEBUG] current_position from trade_executor: {current_position}")
            
            if current_position and current_position.get('has_position'):
                market_data['current_position'] = {
                    "direction": current_position.get("direction", "NONE"),
                    "size": current_position.get("quantity", 0),
                    "entry_price": current_position.get("entry_price", 0),
                    "unrealized_pnl_percent": current_position.get("unrealized_pnl_percent", 0)
                }
                self.logger.info(f"[DEBUG] Setting market_data['current_position']: {market_data['current_position']}")
            else:
                market_data['current_position'] = None
                self.logger.info("[DEBUG] No position found, setting current_position to None")
            
            result = stoic_agent.analyze(
                chartist_report, 
                journalist_report, 
                quant_report,
                market_data,
                self.execution_time
            )
            if result:
                self._print_report("스토익 분석 결과", result)
                self.dashboard_reporter.send_agent_analysis("stoic", result)
            else:
                self.logger.error("❌ [스토익] 분석 실패")
                self.dashboard_reporter.send_log("ERROR", "[스토익] 분석 실패")
            return result
        except Exception as e:
            self.logger.error(f"❌ [스토익] 분석 중 오류: {e}")
            self.dashboard_reporter.send_log("ERROR", f"[스토익] 분석 중 오류: {e}")
            return None
    
    def _run_synthesizer_analysis(self, reports: Dict) -> Optional[Dict]:
        """신디사이저 종합 판단 실행"""
        self.logger.info("=== [신디사이저] 최종 거래 플레이북 생성 시작 ===")
        self.dashboard_reporter.send_log("INFO", "[신디사이저] 최종 거래 플레이북 생성 시작")

        try:
            # 현재 포지션 상태 조회
            current_position = trade_executor.get_current_position_status()
            if current_position:
                self.logger.info(f"📊 현재 포지션: {current_position['direction']} {current_position['symbol']} (손익: {current_position.get('unrealized_pnl_percent', 0):.2f}%)")
            else:
                self.logger.info("📊 현재 포지션: 없음")
            
            # 최근 거래 이력 조회 (최근 10개)
            trade_history = get_trade_history(limit=10)
            self.logger.info(f"📋 거래 이력: {len(trade_history)}개")
            
            
            # 포지션 컨텍스트 가져오기
            position_context = None
            if current_position and current_position.get('has_position'):
                # 포지션이 있을 때만 컨텍스트 업데이트 및 가져오기
                try:
                    current_price = get_current_price(self.target_asset)
                    evaluation = trading_context.evaluate_position_progress(
                        current_price, reports
                    )
                    if evaluation:
                        position_context = trading_context.get_position_context_for_ai()
                        self.logger.info("📋 포지션 컨텍스트 준비 완료")
                except Exception as e:
                    self.logger.warning(f"⚠️ 포지션 컨텍스트 준비 실패: {e}")
            
            # 현재가 가져오기
            current_price = get_current_price(self.target_asset)
            
            # 트리거 정보 가져오기
            triggered_by = self.results.get('triggered_by') if hasattr(self, 'results') else None
            
            result = synthesizer_agent.synthesize(
                reports['chartist'], reports['journalist'],
                reports['quant'], reports['stoic'],
                self.execution_time, current_position, trade_history,
                position_context=position_context,
                chart_images=self.chart_image_paths,  # 차트 이미지 경로 추가
                current_price=current_price,  # 현재가 추가
                triggered_by=triggered_by  # 트리거 정보 추가
            )
            if result:
                self.logger.info("✅ [신디사이저] 분석 완료 - 성공")
                self.dashboard_reporter.send_log("INFO", "[신디사이저] 분석 완료 - 성공")
                self.dashboard_reporter.send_agent_analysis("synthesizer", result)

                self._print_report("🎯 최종 거래 플레이북", result)
                
                # 트리거 처리
                try:
                    decision = result.get('final_decision', {}).get('decision', 'HOLD')
                    
                    if decision == 'HOLD':
                        # HOLD 결정시 트리거 설정
                        price_triggers = result.get('contingency_plan', {}).get('if_hold_is_decided', {}).get('price_triggers', [])
                        if price_triggers:
                            self.trigger_manager.add_triggers(price_triggers)
                            self.logger.info(f"📍 {len(price_triggers)}개 가격 트리거 설정됨")
                        
                        # Phase 2: 추가 트리거 설정 (변동성, 거래량)
                        try:
                            # 현재 시장 데이터
                            from data.binance_connector import get_full_quant_data
                            market_data = get_full_quant_data(self.target_asset)
                            
                            if market_data:
                                # 변동성 트리거 추가
                                current_volatility = market_data.get('volatility', 0)
                                if current_volatility > 0:
                                    self.trigger_manager.add_volatility_trigger(current_volatility)
                                    self.logger.info("📊 변동성 급증 트리거 추가됨")
                                
                                # 거래량 트리거 추가
                                avg_volume = market_data.get('volume_24h', 0)
                                if avg_volume > 0:
                                    self.trigger_manager.add_volume_anomaly_trigger(avg_volume)
                                    self.logger.info("📈 거래량 이상 트리거 추가됨")
                        except Exception as e:
                            self.logger.debug(f"추가 트리거 설정 실패: {e}")
                    else:
                        # BUY/SELL 결정시 모든 트리거 삭제
                        self.trigger_manager.clear_all_triggers()
                        self.logger.info("🧹 포지션 진입으로 모든 트리거 삭제됨")
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ 트리거 처리 실패: {e}")
                
                # 📢 신디사이저 결정 Discord 알림 발송
                try:
                    self.discord_notifier.send_synthesizer_decision(result, reports)
                    self.logger.info("💬 신디사이저 결정 Discord 알림 발송 완료")
                except Exception as e:
                    self.logger.warning(f"⚠️ Discord 알림 발송 실패: {e}")
            else:
                self.logger.error("❌ [신디사이저] 분석 완료 - 실패 (결과 없음)")
                self.dashboard_reporter.send_log("ERROR", "[신디사이저] 분석 실패 (결과 없음)")

            return result
        except Exception as e:
            self.logger.error(f"❌ [신디사이저] 분석 중 오류: {e}")
            self.dashboard_reporter.send_log("ERROR", f"[신디사이저] 분석 중 오류: {e}")
            return None
    
    def _execute_trade(self, playbook: Dict, reports: Dict) -> Optional[Dict]:
        """거래 실행"""
        self.logger.info("=== [거래 실행] 신디사이저 플레이북 실행 시작 ===")
        
        try:
            execution_result = trade_executor.execute_synthesizer_playbook(playbook, reports)

            # 상태 정규화 (프로토콜 미스매치 방지)
            status_raw = (execution_result or {}).get('status', '')
            status_norm = str(status_raw).strip().lower().replace('-', '_')
            alias = {
                'hold_position': 'hold',
                'position_hold': 'hold',
                'no_action': 'hold',
                'kept': 'hold',
            }
            status = alias.get(status_norm, status_norm)
            if execution_result is not None:
                execution_result['status'] = status
            else:
                execution_result = {'status': 'error', 'error': 'empty execution_result'}

            if execution_result and execution_result.get('status') == 'executed':
                self.logger.info(f"✅ [거래 실행] 완료 - 성공! Trade ID: {execution_result['trade_id']}")
                
                # 시나리오 데이터 수집
                trade_id = execution_result['trade_id']
                self.scenario_integration.collect_trade_entry_data(trade_id, playbook, reports)
                
                # HOLD 트리거 삭제 및 포지션 트리거 생성
                try:
                    # HOLD 트리거만 삭제 (포지션 진입 후에는 불필요)
                    self.trigger_manager.clear_hold_triggers()
                    self.logger.info("HOLD 트리거 삭제 완료")
                    
                    # 포지션 모니터링을 위한 새 트리거 생성
                    position_info = {
                        'trade_id': trade_id,
                        'symbol': self.target_asset,
                        'direction': playbook.get('execution_plan', {}).get('trade_direction', 'UNKNOWN'),
                        'entry_price': execution_result.get('entry_price', 0),
                        'entry_time': datetime.now()
                    }
                    
                    # 시장 데이터 수집
                    # ATR을 직접 가져오기
                    try:
                        from data.binance_connector import get_full_quant_data
                        current_market_data = get_full_quant_data(self.target_asset)
                        atr_value = current_market_data.get('atr_14') if current_market_data else None
                    except Exception as e:
                        self.logger.error(f"ATR 데이터 수집 실패: {e}")
                        atr_value = None
                    
                    market_data = {
                        'atr': atr_value,
                        'volatility': reports.get('quant', {}).get('market_data', {}).get('volatility')
                    }
                    
                    # 포지션 트리거 생성
                    position_triggers = self.position_trigger_manager.create_position_triggers(
                        position_info, market_data
                    )
                    
                    # 트리거 추가
                    self.trigger_manager.add_position_triggers(position_triggers)
                    self.logger.info(f"포지션 모니터링 활성화: {len(position_triggers)}개 트리거 생성")
                    
                except Exception as e:
                    self.logger.error(f"포지션 트리거 생성 실패: {e}")
                
                # Phase 3: 향상된 거래 기록 저장
                try:
                    # 결정 컨텍스트 구성
                    decision_context = {
                        'strategy': playbook.get('conflict_context', {}).get('strategy', {}),
                        'timeframe_signals': playbook.get('conflict_context', {}).get('timeframe_signals', {}),
                        'narrative': playbook.get('conflict_context', {}).get('narrative', ''),
                        # 'exploration_mode': 제거됨 - 더 이상 사용하지 않음
                        'market_data': get_full_quant_data(self.target_asset) or {},
                        'thresholds': {}  # 적응형 임계값은 퀀트에서 가져와야 함
                    }
                    
                    # 거래 데이터
                    trade_data = {
                        'trade_id': execution_result['trade_id'],
                        'asset': self.target_asset,
                        'entry_price': execution_result.get('entry_price', 0),
                        'direction': playbook.get('execution_plan', {}).get('trade_direction', 'UNKNOWN'),
                        'leverage': playbook.get('execution_plan', {}).get('position_sizing', {}).get('leverage', 1),
                        'position_size_percent': playbook.get('execution_plan', {}).get('position_sizing', {}).get('percent_of_capital', 5),
                        'stop_loss_price': playbook.get('execution_plan', {}).get('risk_management', {}).get('stop_loss_price', 0),
                        'take_profit_price': playbook.get('execution_plan', {}).get('risk_management', {}).get('take_profit_1_price', 0),
                        'market_conditions': decision_context['market_data'],
                        'agent_scores': {
                            'chartist': reports.get('chartist', {}).get('quantitative_scorecard', {}).get('overall_bias_score', 50),
                            'journalist': reports.get('journalist', {}).get('quantitative_scorecard', {}).get('overall_contextual_bias', {}).get('score', 5),
                            'quant': reports.get('quant', {}).get('quantitative_scorecard', {}).get('overall_score', 50),
                            'stoic': reports.get('stoic', {}).get('risk_assessment', {}).get('overall_risk_score', 5)
                        }
                    }
                    
                    # 시나리오 시스템에서 처리하므로 제거
                    self.logger.info("📝 거래 기록은 시나리오 시스템에서 처리")
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ 향상된 거래 기록 저장 실패: {e}")
                
            elif execution_result and execution_result.get('status') == 'closed':
                self.logger.info("✅ [거래 실행] 완료 - 포지션 청산됨")
                action_taken = True
                
                # 포지션 트리거 삭제
                try:
                    self.trigger_manager.clear_position_triggers()
                    self.logger.info("포지션 트리거 삭제 완료")
                    
                    # 시나리오 청산 데이터 수집
                    if 'trade_id' in execution_result:
                        self.scenario_integration.collect_trade_exit_data(
                            execution_result['trade_id'],
                            execution_result
                        )
                except Exception as e:
                    self.logger.warning(f"포지션 트리거 삭제 실패: {e}")
                    
            elif execution_result and execution_result.get('status') == 'hold':
                self.logger.info("✅ [거래 실행] 완료 - HOLD 결정으로 거래 실행하지 않음")
                
                # HOLD 결정 시 재진입 트리거 생성
                if playbook and 'trigger_setup' in playbook:
                    try:
                        trigger_setup = playbook['trigger_setup']
                        if trigger_setup.get('trigger_price') and trigger_setup.get('direction'):
                            # 기존 트리거 삭제
                            self.trigger_manager.clear_all_triggers()
                            
                            # 새 트리거 생성
                            new_trigger = {
                                'trigger_id': f"HOLD_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                'price': trigger_setup['trigger_price'],
                                'direction': trigger_setup['direction'],
                                'rationale': trigger_setup.get('reason', trigger_setup.get('condition', '')),
                                'created_at': datetime.now().isoformat(),
                                'expires_hours': 24
                            }
                            
                            self.trigger_manager.add_trigger(new_trigger)
                            self.logger.info(f"HOLD 재진입 트리거 생성: {trigger_setup['direction']} @ ${trigger_setup['trigger_price']}")
                            
                            # Discord 알림
                            try:
                                current_price = get_current_price(self.target_asset)
                                self.discord_notifier.send_trigger_activation(new_trigger, current_price)
                                self.logger.info("트리거 설정 Discord 알림 발송 완료")
                            except Exception as e:
                                self.logger.warning(f"트리거 설정 Discord 알림 실패: {e}")
                    except Exception as e:
                        self.logger.error(f"HOLD 트리거 생성 실패: {e}")
            elif execution_result and execution_result.get('status') in ['adjusted', 'both_adjusted', 'position_adjusted']:
                self.logger.info(f"✅ [거래 실행] 완료 - 포지션 조정: {execution_result.get('status')}")
                action_taken = True
            elif execution_result and execution_result.get('status') in ['disabled', 'blocked']:
                self.logger.warning(f"⚠️ [거래 실행] 완료 - {execution_result.get('status')}: {execution_result.get('error', '비활성화됨')}")
            elif execution_result and execution_result.get('status') == 'error':
                self.logger.error(f"❌ [거래 실행] 완료 - 실패: {execution_result.get('error', '알 수 없는 오류')} (원본상태: {status_raw})")
            elif execution_result:
                self.logger.warning(f"⚠️ [거래 실행] 비표준 상태 수신: '{status_raw}' → 정규화 '{status}'")
            else:
                self.logger.error("❌ [거래 실행] 완료 - 실패: execution_result가 None")
            
            return execution_result
            
        except Exception as e:
            self.logger.error(f"❌ 거래 실행 중 예외 발생: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _all_reports_ready(self, reports: Dict) -> bool:
        """모든 필수 보고서가 준비되었는지 확인"""
        required_reports = ['chartist', 'journalist', 'quant', 'stoic']
        
        for report_name in required_reports:
            if not reports.get(report_name):
                missing_reports = [name for name in required_reports if not reports.get(name)]
                self.logger.warning(f"⚠️ 필수 보고서 누락으로 신디사이저 실행 불가: {', '.join(missing_reports)}")
                return False
        
        return True
    
    def _print_report(self, title: str, content: Dict):
        """보고서 출력"""
        self.logger.info(f"\n--- {title} ---")
        
        if isinstance(content, dict):
            import json
            report_text = json.dumps(content, indent=2, ensure_ascii=False)
            for line in report_text.split('\n'):
                self.logger.info(line)
        else:
            self.logger.info(content)
    
    def monitor_positions(self):
        """포지션 MDD 모니터링 (15분마다 실행)"""
        try:
            from trading.position_state_manager import position_state_manager
            from data.binance_connector import get_current_price
            
            # 열린 포지션 조회
            open_positions = position_state_manager.get_open_positions()
            
            for position in open_positions:
                trade_id = position.get('trade_id')
                if trade_id:
                    current_price = get_current_price(self.target_asset)
                    
                    # MDD 업데이트
                    self.scenario_integration.update_position_mdd(trade_id, current_price)
            
        except Exception as e:
            self.logger.error(f"포지션 모니터링 실패: {e}")

def main():
    """메인 실행 함수"""
    # Windows 환경에서의 UTF-8 인코딩 문제 해결
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # 오케스트레이터 생성 및 실행
    orchestrator = DelphiOrchestrator()
    results = orchestrator.run_full_analysis()
    
    # 실행 결과 요약
    logging.info("\n" + "=" * 60)
    logging.info("🎉 델파이 시스템 실행 완료")
    logging.info("=" * 60)
    
    if 'error' in results:
        logging.error(f"❌ 시스템 실행 중 오류 발생: {results['error']}")
    else:
        completed_reports = [name for name, report in results['reports'].items() if report is not None]
        logging.info(f"✅ 완료된 분석: {', '.join(completed_reports)}")
        
        if results.get('execution_result'):
            status = results['execution_result']['status']
            logging.info(f"📊 거래 실행 상태: {status}")

if __name__ == "__main__":
    main()