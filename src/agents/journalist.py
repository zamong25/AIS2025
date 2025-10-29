"""
델파이 트레이딩 시스템 - 저널리스트 에이전트
상황적 분석을 담당하는 AI 에이전트
"""

import logging
from typing import Optional
# Google search tools removed for compatibility
from utils.openai_client import openai_client
from utils.time_manager import TimeManager
from utils.logging_config import get_logger


class JournalistAgent:
    """저널리스트 에이전트 - 헤로도토스"""
    
    def __init__(self, prompt_path: str = None):
        self.logger = get_logger('JournalistAgent')
        if prompt_path is None:
            # 프로젝트 루트 기준으로 프롬프트 경로 설정
            import os
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            prompt_path = os.path.join(project_root, "prompts", "journalist_final.txt")
        self.prompt_path = prompt_path
        self.agent_name = "헤로도토스"
    
    def analyze(self, asset_ticker: str, execution_time: dict = None) -> Optional[dict]:
        """
        자산의 상황적 요인을 분석하여 결과 반환
        
        Args:
            asset_ticker: 분석할 자산 심볼
            execution_time: 실행 시간 (없으면 현재 시간 사용)
            
        Returns:
            분석 결과 JSON 딕셔너리
        """
        self.logger.info(f"\n--- [{self.agent_name}] 저널리스트 분석 시작 ({asset_ticker}) ---")
        
        if execution_time is None:
            execution_time = TimeManager.get_execution_time()
        
        try:
            # 프롬프트 준비
            prompt = self._prepare_prompt(asset_ticker, execution_time['utc_iso'])
            if not prompt:
                return None
            
            # AI 분석 실행 (구글 검색 기능 임시 비활성화)
            result = openai_client.invoke_agent_json(
                "gpt-4o",
                prompt
            )
            
            if result:
                self.logger.info("✅ 저널리스트 분석 완료")
                
                # 종목명 추가
                result['asset'] = asset_ticker
                
                # 새로운 팩트 중심 구조 검증 및 정규화
                result = self._validate_and_normalize_facts(result)
                
                # Phase 2: 팩트 중심 로깅
                from utils.logging_config import log_agent_decision
                
                # 단기 뉴스 중 가장 영향력 있는 것 찾기
                max_short_news = max(result.get('short_term_news', [{'impact_level': 0}]), 
                                   key=lambda x: x.get('impact_level', 0), 
                                   default={'impact_level': 0})
                
                # 장기 뉴스 중 가장 영향력 있는 것 찾기
                max_long_news = max(result.get('long_term_news', [{'impact_level': 0}]), 
                                  key=lambda x: x.get('impact_level', 0), 
                                  default={'impact_level': 0})
                
                # 전체 영향도 계산 (단기 30%, 장기 70% 가중치)
                overall_impact = (max_short_news.get('impact_level', 0) * 0.3 + 
                                max_long_news.get('impact_level', 0) * 0.7) / 10
                
                decision_data = {
                    'confidence': overall_impact,
                    'rationale': f"단기: {max_short_news.get('content', 'N/A')[:50]}... / 장기: {max_long_news.get('content', 'N/A')[:50]}...",
                    'details': {
                        'short_term_count': len(result.get('short_term_news', [])),
                        'long_term_count': len(result.get('long_term_news', [])),
                        'max_short_impact': max_short_news.get('impact_level', 0),
                        'max_long_impact': max_long_news.get('impact_level', 0)
                    }
                }
                log_agent_decision('journalist', decision_data)
                
                # 뉴스 정보 로깅
                self.logger.info(f"📰 단기 뉴스: {len(result.get('short_term_news', []))}개")
                for news in result.get('short_term_news', [])[:3]:  # 상위 3개만
                    self.logger.info(f"  - [{news.get('impact_level', 0)}] {news.get('content', '')[:60]}...")
                
                self.logger.info(f"📅 장기 뉴스: {len(result.get('long_term_news', []))}개")
                for news in result.get('long_term_news', [])[:3]:  # 상위 3개만
                    self.logger.info(f"  - [{news.get('impact_level', 0)}] {news.get('content', '')[:60]}...")
                
                return result
            else:
                self.logger.error("❌ 저널리스트 분석 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 저널리스트 분석 중 오류: {e}")
            return None
    
    def _prepare_prompt(self, asset_ticker: str, timestamp_utc: str) -> Optional[str]:
        """프롬프트 준비"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            replacements = {
                "분석한 종목명": asset_ticker,
                "입력받은 보고서 작성 시간": timestamp_utc
            }
            
            for key, val in replacements.items():
                template = template.replace(key, str(val))
            
            return template
            
        except FileNotFoundError:
            self.logger.error(f"❌ 프롬프트 파일을 찾을 수 없습니다: {self.prompt_path}")
            return None
    
    def _validate_and_normalize_facts(self, result: dict) -> dict:
        """팩트 중심 구조 검증 및 정규화"""
        # current_price 제거 (synthesizer가 API에서 직접 가져옴)
        if 'current_price' in result:
            del result['current_price']
        
        if 'short_term_news' not in result:
            result['short_term_news'] = []
            self.logger.warning("⚠️ short_term_news 필드 없음 - 빈 리스트로 초기화")
        
        if 'long_term_news' not in result:
            result['long_term_news'] = []
            self.logger.warning("⚠️ long_term_news 필드 없음 - 빈 리스트로 초기화")
        
        # 뉴스 항목 검증
        for news_list_name in ['short_term_news', 'long_term_news']:
            news_list = result.get(news_list_name, [])
            for i, news in enumerate(news_list):
                # 필수 필드 확인
                if 'content' not in news:
                    news['content'] = '내용 없음'
                if 'impact_level' not in news:
                    news['impact_level'] = 5  # 기본값
                if 'timing' not in news:
                    news['timing'] = '시간 정보 없음'
                
                # impact_level 범위 확인 (1-10)
                if news['impact_level'] < 1:
                    news['impact_level'] = 1
                elif news['impact_level'] > 10:
                    news['impact_level'] = 10
        
        # data_metrics는 선택사항이므로 없어도 OK
        if 'data_metrics' not in result:
            result['data_metrics'] = {}
        
        # 뉴스를 impact_level 기준으로 정렬 (높은 순)
        result['short_term_news'] = sorted(
            result['short_term_news'], 
            key=lambda x: x.get('impact_level', 0), 
            reverse=True
        )
        result['long_term_news'] = sorted(
            result['long_term_news'], 
            key=lambda x: x.get('impact_level', 0), 
            reverse=True
        )
        
        return result


# 전역 저널리스트 에이전트 인스턴스
journalist_agent = JournalistAgent()