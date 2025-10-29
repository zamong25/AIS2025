"""
델파이 트레이딩 시스템 - 차티스트 에이전트
기술적 분석을 담당하는 AI 에이전트
"""

import json
import logging
from typing import List, Optional
from utils.time_manager import TimeManager
from utils.logging_config import get_logger

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    print("⚠️ PIL not available - chartist will use mock mode")
    Image = None
    PIL_AVAILABLE = False

try:
    from utils.openai_client import openai_client
    OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ OpenAI not available - chartist will use mock mode")
    openai_client = None
    OPENAI_AVAILABLE = False


class ChartistAgent:
    """차티스트 에이전트 - 아르키메데스"""
    
    def __init__(self, prompt_path: str = None):
        self.logger = get_logger('ChartistAgent')
        if prompt_path is None:
            # 프로젝트 루트 기준으로 프롬프트 경로 설정
            import os
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            prompt_path = os.path.join(project_root, "prompts", "chartist_final.txt")
        self.prompt_path = prompt_path
        self.agent_name = "아르키메데스"
    
    def analyze(self, image_paths: List[str], execution_time: dict = None, asset: str = "SOLUSDT") -> Optional[dict]:
        """
        차트 이미지를 분석하여 기술적 분석 결과 반환
        
        Args:
            image_paths: 차트 이미지 파일 경로 목록
            execution_time: 실행 시간 (없으면 현재 시간 사용)
            
        Returns:
            분석 결과 JSON 딕셔너리
        """
        self.logger.info(f"\n--- [{self.agent_name}] 차티스트 분석 시작 ---")
        
        if execution_time is None:
            execution_time = TimeManager.get_execution_time()
        
        # Dependencies check - force real execution
        if not PIL_AVAILABLE:
            self.logger.error("❌ PIL 라이브러리가 필요합니다. pip install Pillow")
            return None
        if not OPENAI_AVAILABLE:
            self.logger.error("❌ OpenAI 클라이언트가 필요합니다.")
            return None
        
        try:
            # 시간 프레임 추출
            timeframes_list = [p.split('_')[-1].split('.')[0] for p in image_paths]
            timeframes = json.dumps(timeframes_list)
            
            # 프롬프트 준비
            prompt = self._prepare_prompt(execution_time['utc_iso'], timeframes, asset)
            if not prompt:
                return None
            
            # 이미지 로드
            images = self._load_images(image_paths)
            if not images:
                return None
            
            # AI 분석 실행
            result = openai_client.invoke_agent_json(
                "gpt-4o",
                prompt,
                images=images
            )
            
            if result:
                self.logger.info("✅ 차티스트 분석 완료")
                
                # 종목명 추가
                result['asset'] = asset
                
                # 시나리오 검증 및 정규화
                result = self._validate_and_normalize_scenarios(result)
                
                # Phase 1: 향상된 로깅 - 시나리오 기반으로 변경
                from utils.logging_config import log_agent_decision
                
                # 가장 높은 확률의 시나리오 찾기
                scenarios = result.get('scenarios', [])
                if scenarios:
                    max_scenario = max(scenarios, key=lambda x: x.get('probability', 0))
                    decision_data = {
                        'confidence': max_scenario.get('probability', 0) / 100,
                        'rationale': result.get('summary', ''),
                        'details': {
                            'scenario_type': max_scenario.get('type', 'N/A'),
                            'entry': max_scenario.get('entry', 'N/A'),
                            'risk_reward': max_scenario.get('risk_reward_ratio', 'N/A'),
                            'key_levels': f"지지: {result.get('key_levels', {}).get('strong_support', 'N/A')}, 저항: {result.get('key_levels', {}).get('strong_resistance', 'N/A')}"
                        }
                    }
                    log_agent_decision('chartist', decision_data)
                    
                    # 시나리오 정보 로깅
                    self.logger.info(f"📊 시나리오 생성: {len(scenarios)}개")
                    for s in scenarios:
                        self.logger.info(f"  - {s['type']}: {s['probability']}% (진입: ${s['entry']}, RR: {s['risk_reward_ratio']})")
                
                return result
            else:
                self.logger.error("❌ 차티스트 분석 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 차티스트 분석 중 오류: {e}")
            return None
    
    def _prepare_prompt(self, timestamp_utc: str, timeframes: str, asset: str) -> Optional[str]:
        """프롬프트 준비"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            replacements = {
                "입력받은 보고서 작성 시간": timestamp_utc,
                "입력받은 시간 프레임 명시": timeframes,
                "분석할 종목": asset
            }
            
            for key, val in replacements.items():
                template = template.replace(key, str(val))
            
            return template
            
        except FileNotFoundError:
            self.logger.error(f"❌ 프롬프트 파일을 찾을 수 없습니다: {self.prompt_path}")
            return None
    
    def _load_images(self, image_paths: List[str]) -> Optional[List]:
        """이미지 파일 로드"""
        try:
            images = [Image.open(p) for p in image_paths]
            self.logger.info(f"... {len(images)}개 이미지 로드 완료")
            return images
            
        except FileNotFoundError as e:
            self.logger.error(f"❌ 이미지 파일 로드 실패: {e}")
            return None
    
    def _validate_and_normalize_scenarios(self, result: dict) -> dict:
        """시나리오 검증 및 정규화"""
        scenarios = result.get('scenarios', [])
        
        # 1. 시나리오 개수 검증 (정확히 3개)
        if len(scenarios) < 3:
            # 부족한 경우 중립 시나리오 추가
            current_price = result.get('current_price', 0)
            remaining_prob = 100 - sum(s.get('probability', 0) for s in scenarios)
            
            while len(scenarios) < 3:
                scenarios.append({
                    'type': '박스권',
                    'probability': remaining_prob // (3 - len(scenarios)),
                    'entry_condition': f"${current_price * 0.995:.2f}~${current_price * 1.005:.2f} 범위 유지시",
                    'entry': current_price,
                    'take_profit': current_price * 1.01,
                    'stop_loss': current_price * 0.99,
                    'risk_reward_ratio': 1.0,
                    'reasoning': ['시나리오 부족으로 자동 생성된 중립 시나리오']
                })
        elif len(scenarios) > 3:
            # 초과하는 경우 확률 높은 3개만 선택
            scenarios = sorted(scenarios, key=lambda x: x.get('probability', 0), reverse=True)[:3]
        
        # 2. 확률 합계 100% 맞추기
        total_prob = sum(s.get('probability', 0) for s in scenarios)
        if total_prob != 100 and total_prob > 0:
            # 확률 정규화
            for s in scenarios:
                s['probability'] = round(s['probability'] * 100 / total_prob)
            
            # 반올림 오차 보정 (마지막 시나리오에 적용)
            scenarios[-1]['probability'] += 100 - sum(s['probability'] for s in scenarios)
        
        # 3. 필수 필드 검증
        for s in scenarios:
            # 필수 필드가 없으면 기본값 설정
            if 'type' not in s:
                s['type'] = '미정'
            if 'entry' not in s:
                s['entry'] = result.get('current_price', 0)
            if 'take_profit' not in s:
                s['take_profit'] = s['entry'] * 1.02
            if 'stop_loss' not in s:
                s['stop_loss'] = s['entry'] * 0.98
            if 'risk_reward_ratio' not in s:
                # 손익비 계산
                risk = abs(s['entry'] - s['stop_loss'])
                reward = abs(s['take_profit'] - s['entry'])
                s['risk_reward_ratio'] = round(reward / risk, 2) if risk > 0 else 1.0
        
        result['scenarios'] = scenarios
        return result
    


# 전역 차티스트 에이전트 인스턴스
chartist_agent = ChartistAgent()