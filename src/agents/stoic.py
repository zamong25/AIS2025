"""
델파이 트레이딩 시스템 - 스토익 에이전트
리스크 관리를 담당하는 AI 에이전트
"""

import json
import logging
from typing import Optional, Dict
from utils.openai_client import openai_client
from utils.time_manager import TimeManager
import os
from binance.client import Client
from dotenv import load_dotenv
from pathlib import Path

# 환경 변수 로드 (config/.env)
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "config" / ".env")


class StoicAgent:
    """스토익 에이전트 - 제논"""
    
    def __init__(self, prompt_path: str = None):
        if prompt_path is None:
            # 프로젝트 루트 기준으로 프롬프트 경로 설정
            import os
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            prompt_path = os.path.join(project_root, "prompts", "stoic_v2.txt")
        self.prompt_path = prompt_path
        self.agent_name = "제논"
    
    def analyze(self, chartist_json: dict, journalist_json: dict, 
               quant_json: dict = None, market_data: dict = None,
               execution_time: dict = None) -> Optional[dict]:
        """
        시나리오별 리스크 분석을 수행하여 결과 반환
        
        Args:
            chartist_json: 차티스트 분석 결과
            journalist_json: 저널리스트 분석 결과
            quant_json: 퀀트 분석 결과 (선택적)
            market_data: 시장 데이터 (선택적)
            execution_time: 실행 시간 (없으면 현재 시간 사용)
            
        Returns:
            분석 결과 JSON 딕셔너리
        """
        logging.info(f"\n--- [{self.agent_name}] 스토익 리스크 분석 시작 ---")
        
        if execution_time is None:
            execution_time = TimeManager.get_execution_time()
        
        try:
            # 거래 제안 브리핑 생성
            briefing = self._create_trading_briefing(chartist_json, journalist_json, quant_json, market_data)
            if not briefing:
                return None
            
            # 프롬프트 준비
            prompt = self._prepare_prompt(briefing, execution_time['utc_iso'])
            if not prompt:
                return None
            
            # AI 분석 실행
            result = openai_client.invoke_agent_json("gpt-4o", prompt)
            
            if result:
                logging.info("✅ 스토익 리스크 분석 완료")
                
                # Phase 1: 향상된 로깅 추가
                from utils.logging_config import log_agent_decision
                risk_level = result.get('risk_verdict', {}).get('overall_risk_level', '중간')
                # 리스크 레벨을 숫자로 변환 (낮음: 0.2, 중간: 0.5, 높음: 0.8)
                risk_score_map = {'낮음': 0.2, '중간': 0.5, '높음': 0.8}
                risk_score = risk_score_map.get(risk_level, 0.5)
                
                decision_data = {
                    'confidence': risk_score,
                    'rationale': result.get('risk_verdict', {}).get('rationale', ''),
                    'details': {
                        'risk_level': risk_level,
                        'stop_loss': result.get('trade_conditions', {}).get('hard_stop_loss', {}).get('price', 'N/A'),
                        'position_size': result.get('trade_conditions', {}).get('recommended_position_size', {}).get('position_size_percent_of_capital', 'N/A')
                    }
                }
                log_agent_decision('stoic', decision_data)
                
                return result
            else:
                logging.error("❌ 스토익 리스크 분석 실패")
                return None
                
        except Exception as e:
            logging.error(f"❌ 스토익 리스크 분석 중 오류: {e}")
            return None
    
    def _create_trading_briefing(self, chartist_json: dict, journalist_json: dict, 
                                quant_json: dict = None, market_data: dict = None) -> Optional[dict]:
        """시나리오 기반 거래 브리핑 생성"""
        try:
            # 기본 브리핑 정보
            briefing = {
                "chartist_report": {
                    "scenarios": chartist_json.get("scenarios", []),
                    "key_levels": chartist_json.get("key_levels", {}),
                    "market_state": chartist_json.get("market_state", "불명"),
                    "summary": chartist_json.get("summary", "")
                },
                "journalist_report": {
                    "short_term_news": journalist_json.get("short_term_news", []),
                    "long_term_news": journalist_json.get("long_term_news", []),
                    "data_metrics": journalist_json.get("data_metrics", {})
                }
            }
            
            # 퀀트 리포트 추가
            if quant_json:
                briefing["quant_report"] = {
                    "scenario_technical_view": quant_json.get("integrated_analysis", {}).get("scenario_technical_view", {}),
                    "risk_factors": quant_json.get("risk_factors", []),
                    "db_analysis": quant_json.get("db_analysis", {})
                }
            
            # 시장 데이터 및 ATR 추가
            if market_data:
                current_price = market_data.get("current_price", chartist_json.get("current_price", 150.0))
            else:
                # market_data가 없으면 API로 현재가 가져오기
                try:
                    api_key = os.getenv('BINANCE_API_KEY')
                    api_secret = os.getenv('BINANCE_API_SECRET')
                    
                    if api_key and api_secret:
                        client = Client(api_key, api_secret)
                        ticker = client.futures_ticker(symbol="SOLUSDT")
                        current_price = float(ticker['lastPrice'])
                    else:
                        current_price = chartist_json.get("current_price", 150.0)
                except:
                    current_price = chartist_json.get("current_price", 150.0)
            
            # 현재 포지션 정보 추가 (market_data에서 전달받음)
            if market_data and 'current_position' in market_data and market_data['current_position']:
                briefing["current_position"] = market_data['current_position']
                logging.info(f"[DEBUG] Stoic - Found position: {briefing['current_position']}")
            else:
                briefing["current_position"] = None
                logging.info("[DEBUG] Stoic - No position found, setting to None")
                
            # ATR 데이터 추가
            try:
                if market_data and "indicators_1h" in market_data:
                    atr_1h = market_data["indicators_1h"].get("atr", 1.5)
                    atr_percent = (atr_1h / current_price) * 100
                else:
                    # ATR 대체 값 사용
                    atr_percent = 1.0  # 기본값
                
                briefing["market_data"] = {
                    "current_price": current_price,
                    "atr_data": {
                        "atr_1h": round(atr_1h if 'atr_1h' in locals() else atr_percent * current_price / 100, 2),
                        "atr_percent": round(atr_percent, 2),
                        "volatility_state": "HIGH" if atr_percent > 1.5 else "NORMAL" if atr_percent > 0.5 else "LOW"
                    }
                }
                
            except Exception as e:
                logging.warning(f"⚠️ ATR 분석 실패, 기본값 사용: {e}")
                # ATR 실패시 기본값
                briefing["market_data"] = {
                    "current_price": current_price,
                    "atr_data": {
                        "atr_1h": 1.5,
                        "atr_percent": 1.0,
                        "volatility_state": "NORMAL"
                    }
                }
            
            logging.info("✅ 스토익 브리핑 생성 완료")
            return briefing
            
        except KeyError as e:
            logging.error(f"❌ JSON 키 누락: {e}")
            return None
    
    def _prepare_prompt(self, briefing: dict, timestamp_utc: str) -> Optional[str]:
        """프롬프트 준비"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            briefing_str = json.dumps(briefing, indent=2, ensure_ascii=False)
            
            replacements = {
                "입력 데이터": briefing_str,
                "입력받은 시간": timestamp_utc,
                "분석한 종목": "SOLUSDT"
            }
            
            for key, val in replacements.items():
                template = template.replace(key, str(val))
            
            return template
            
        except FileNotFoundError:
            logging.error(f"❌ 프롬프트 파일을 찾을 수 없습니다: {self.prompt_path}")
            return None


# 전역 스토익 에이전트 인스턴스
stoic_agent = StoicAgent()