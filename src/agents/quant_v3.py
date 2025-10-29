"""
델파이 트레이딩 시스템 - 퀀트 에이전트 v3.0
변화 추적 및 캐시 시스템을 포함한 계량적 분석 에이전트
"""

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from utils.openai_client import openai_client
from utils.time_manager import TimeManager
from utils.logging_config import get_logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.scenario_searcher import ScenarioSimilaritySearcher
from data.market_analyzer import MarketContextAnalyzer
import sqlite3


class IndicatorCache:
    """지표 값을 캐싱하여 시계열 추적"""
    
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.cache = {
            '5m': {},
            '15m': {},
            '1h': {}
        }
        
    def add_value(self, timeframe: str, indicator: str, value: Any):
        """새로운 값 추가"""
        if timeframe not in self.cache:
            return
            
        if indicator not in self.cache[timeframe]:
            self.cache[timeframe][indicator] = []
            
        self.cache[timeframe][indicator].append({
            'value': value,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # 최대 개수 유지
        if len(self.cache[timeframe][indicator]) > self.max_history:
            self.cache[timeframe][indicator].pop(0)
            
    def get_sequence(self, timeframe: str, indicator: str, count: int = 5) -> List[Any]:
        """최근 n개 값의 시퀀스 반환"""
        if timeframe not in self.cache or indicator not in self.cache[timeframe]:
            return []
            
        values = [item['value'] for item in self.cache[timeframe][indicator]]
        return values[-count:] if len(values) >= count else values
        
    def clear(self):
        """캐시 초기화"""
        for tf in self.cache:
            self.cache[tf].clear()


class QuantAgentV3:
    """퀀트 에이전트 v3.0 - 피타고라스"""
    
    def __init__(self, prompt_path: str = None):
        self.logger = get_logger('QuantAgentV3')
        if prompt_path is None:
            import os
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            prompt_path = os.path.join(project_root, "prompts", "quant_v3.txt")
        self.prompt_path = prompt_path
        self.agent_name = "피타고라스"
        self.cache = IndicatorCache()
        
    def analyze(self, chartist_json: dict, journalist_json: dict, 
               market_data: dict, execution_time: dict = None) -> Optional[dict]:
        """
        변화 추적 기반 계량적 분석
        
        Args:
            chartist_json: 차티스트 분석 결과
            journalist_json: 저널리스트 분석 결과  
            market_data: 현재 시장 데이터 (다층 시간대 포함)
            execution_time: 실행 시간
            
        Returns:
            분석 결과 JSON
        """
        self.logger.info(f"\n--- [{self.agent_name}] 퀀트 v3.0 분석 시작 ---")
        
        if execution_time is None:
            execution_time = TimeManager.get_execution_time()
            
        try:
            # 1. 현재 지표값 캐시에 추가
            self._update_cache(market_data)
            
            # 2. DB에서 유사 패턴 검색
            pattern_analysis = self._analyze_similar_patterns(market_data, chartist_json)
            
            # 3. 지표 시계열 추출
            indicator_sequences = self._extract_indicator_sequences()
            
            # 4. 프롬프트 준비
            prompt = self._prepare_prompt(
                chartist_json, 
                journalist_json,
                market_data,
                pattern_analysis,
                indicator_sequences,
                execution_time['utc_iso']
            )
            
            if not prompt:
                return None
                
            # 5. AI 분석 실행
            result = openai_client.invoke_agent_json("gpt-4o", prompt)
            
            if result:
                self.logger.info("✅ 퀀트 v3.0 분석 완료")
                
                # 에이전트 의사결정 로깅
                from utils.logging_config import log_agent_decision
                
                confidence = result.get('db_analysis', {}).get('confidence_level', 'LOW')
                confidence_map = {'HIGH': 0.8, 'MEDIUM': 0.5, 'LOW': 0.2}
                
                decision_data = {
                    'confidence': confidence_map.get(confidence, 0.2),
                    'rationale': result.get('integrated_analysis', {}).get('momentum_assessment', ''),
                    'details': {
                        'similar_patterns': result.get('db_analysis', {}).get('similar_patterns_found', 0),
                        'recommended_direction': result.get('db_analysis', {}).get('recommended_direction', 'NEUTRAL'),
                        'long_win_rate': result.get('db_analysis', {}).get('pattern_outcomes', {}).get('long_trades', {}).get('win_rate', 0),
                        'short_win_rate': result.get('db_analysis', {}).get('pattern_outcomes', {}).get('short_trades', {}).get('win_rate', 0)
                    }
                }
                log_agent_decision('quant', decision_data)
                
                return result
            else:
                self.logger.error("❌ 퀀트 분석 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 퀀트 분석 중 오류: {e}")
            return None
            
    def _update_cache(self, market_data: dict):
        """현재 지표값을 캐시에 추가"""
        try:
            # 각 시간대별 지표 추가
            for timeframe in ['5m', '15m', '1h']:
                tf_data = market_data.get(f'indicators_{timeframe}', {})
                
                if tf_data:
                    # RSI
                    if 'rsi' in tf_data:
                        self.cache.add_value(timeframe, 'rsi', tf_data['rsi'])
                    
                    # MACD
                    if 'macd_histogram' in tf_data:
                        self.cache.add_value(timeframe, 'macd_histogram', tf_data['macd_histogram'])
                    
                    # 거래량 비율
                    if 'volume_ratio' in tf_data:
                        self.cache.add_value(timeframe, 'volume_ratio', tf_data['volume_ratio'])
                    
                    # 가격 vs EMA
                    if 'price_vs_ema5' in tf_data:
                        self.cache.add_value(timeframe, 'price_vs_ema5', tf_data['price_vs_ema5'])
                        
                    # 볼린저 밴드 포지션
                    if 'bollinger_position' in tf_data:
                        self.cache.add_value(timeframe, 'bollinger_position', tf_data['bollinger_position'])
                        
                    # EMA 배열
                    if 'ema_alignment' in tf_data:
                        self.cache.add_value(timeframe, 'ema_alignment', tf_data['ema_alignment'])
                        
        except Exception as e:
            self.logger.warning(f"캐시 업데이트 실패: {e}")
            
    def _extract_indicator_sequences(self) -> dict:
        """캐시에서 지표 시계열 추출"""
        sequences = {}
        
        for timeframe in ['5m', '15m', '1h']:
            sequences[timeframe] = {}
            
            # 각 지표별 시퀀스 추출
            indicators = ['rsi', 'macd_histogram', 'volume_ratio', 'price_vs_ema5', 
                         'bollinger_position', 'ema_alignment']
            
            for indicator in indicators:
                seq = self.cache.get_sequence(timeframe, indicator, count=5)
                if seq:
                    sequences[timeframe][indicator] = seq
                    
        return sequences
        
    def _analyze_similar_patterns(self, market_data: dict, chartist_json: dict) -> dict:
        """DB에서 유사 패턴 분석"""
        try:
            # 현재 시장 상태 특징 추출
            current_features = {
                'rsi_5m': market_data.get('indicators_5m', {}).get('rsi', 50),
                'rsi_15m': market_data.get('indicators_15m', {}).get('rsi', 50),
                'rsi_1h': market_data.get('indicators_1h', {}).get('rsi', 50),
                'volume_ratio_5m': market_data.get('indicators_5m', {}).get('volume_ratio', 1.0),
                'macd_histogram_15m': market_data.get('indicators_15m', {}).get('macd_histogram', 0),
                'market_state': chartist_json.get('market_state', 'unknown')
            }
            
            # 새로운 시나리오 기반 DB에서 유사 거래 검색
            db_path = "data/database/delphi_trades.db"
            searcher = ScenarioSimilaritySearcher(db_path)
            
            # 현재 시장 컨텍스트 분석
            analyzer = MarketContextAnalyzer()
            # prices 데이터 추가 (15분봉 종가 사용)
            enhanced_market_data = market_data.copy()
            if 'candles_15m' in market_data:
                enhanced_market_data['prices'] = [float(candle[4]) for candle in market_data['candles_15m']]  # 종가들
            else:
                enhanced_market_data['prices'] = []
            
            current_context = analyzer.analyze(enhanced_market_data)
            
            # 가장 가능성 높은 시나리오 추출
            scenarios = chartist_json.get('market_scenarios', [])
            likely_scenario = 'neutral'  # 기본값
            if scenarios:
                likely_scenario = max(scenarios, key=lambda x: x.get('probability', 0)).get('type', 'neutral')
            
            # 유사 거래 검색
            search_result = searcher.find_similar_trades(likely_scenario, current_context)
            
            if search_result.get('status') != 'success' or search_result.get('count', 0) < 10:
                return {
                    'similar_patterns_found': 0,
                    'pattern_outcomes': {
                        'long_trades': {'count': 0, 'win_rate': 0, 'avg_return': 0},
                        'short_trades': {'count': 0, 'win_rate': 0, 'avg_return': 0}
                    },
                    'recommended_direction': 'NEUTRAL',
                    'confidence_level': 'LOW'
                }
            
            # 새로운 시나리오 기반 분석 결과 사용
            statistics = search_result.get('statistics', {})
            patterns = search_result.get('patterns', [])
            insights = search_result.get('insights', {})
            
            # 통계 변환
            long_stats = {
                'count': statistics.get('total_long_trades', 0),
                'win_rate': statistics.get('long_win_rate', 0),
                'avg_return': statistics.get('long_avg_return', 0)
            }
            short_stats = {
                'count': statistics.get('total_short_trades', 0),
                'win_rate': statistics.get('short_win_rate', 0),
                'avg_return': statistics.get('short_avg_return', 0)
            }
            
            # 추천 방향 결정
            if long_stats['win_rate'] > 60 and long_stats['avg_return'] > 1.5:
                recommended = 'LONG'
                confidence = 'HIGH' if long_stats['count'] >= 10 else 'MEDIUM'
            elif short_stats['win_rate'] > 60 and short_stats['avg_return'] > 1.5:
                recommended = 'SHORT'
                confidence = 'HIGH' if short_stats['count'] >= 10 else 'MEDIUM'
            else:
                recommended = 'NEUTRAL'
                confidence = search_result.get('confidence', 'LOW')
            
            return {
                'similar_patterns_found': search_result.get('count', 0),
                'pattern_outcomes': {
                    'long_trades': long_stats,
                    'short_trades': short_stats
                },
                'recommended_direction': recommended,
                'confidence_level': confidence,
                'key_success_factors': insights.get('key_patterns', [])
            }
            
        except Exception as e:
            self.logger.warning(f"패턴 분석 중 오류: {e}")
            return {
                'similar_patterns_found': 0,
                'pattern_outcomes': {
                    'long_trades': {'count': 0, 'win_rate': 0, 'avg_return': 0},
                    'short_trades': {'count': 0, 'win_rate': 0, 'avg_return': 0}
                },
                'recommended_direction': 'NEUTRAL',
                'confidence_level': 'LOW'
            }
            
    def _calculate_trade_stats(self, trades: List[dict]) -> dict:
        """거래 통계 계산"""
        if not trades:
            return {'count': 0, 'win_rate': 0, 'avg_return': 0}
            
        wins = [t for t in trades if t.get('outcome') == 'WIN']
        returns = [t.get('pnl_percent', 0) for t in trades]
        
        # 베스트 케이스 찾기
        best_trade = max(trades, key=lambda x: x.get('pnl_percent', 0)) if trades else None
        
        stats = {
            'count': len(trades),
            'win_rate': (len(wins) / len(trades)) * 100 if trades else 0,
            'avg_return': sum(returns) / len(returns) if returns else 0
        }
        
        if best_trade:
            stats['best_case'] = {
                'date': best_trade.get('entry_time', '').split('T')[0],
                'return_percent': best_trade.get('pnl_percent', 0),
                'holding_time': self._calculate_holding_time(best_trade)
            }
            
        return stats
        
    def _calculate_holding_time(self, trade: dict) -> str:
        """홀딩 시간 계산"""
        try:
            if 'entry_time' in trade and 'exit_time' in trade:
                entry = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
                exit = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
                duration = exit - entry
                
                hours = duration.total_seconds() / 3600
                if hours < 1:
                    return f"{int(duration.total_seconds() / 60)}분"
                elif hours < 24:
                    return f"{int(hours)}시간"
                else:
                    return f"{int(hours / 24)}일"
            else:
                return "N/A"
        except:
            return "N/A"
            
    def _extract_success_factors(self, trades: List[dict]) -> List[str]:
        """성공 요인 추출"""
        factors = []
        
        try:
            # RSI 패턴 분석
            rsi_wins = [t for t in trades if t.get('outcome') == 'WIN' and 
                       t.get('indicators', {}).get('rsi_5m', 50) < 30]
            if len(rsi_wins) >= 3:
                win_rate = (len(rsi_wins) / len([t for t in trades if 
                          t.get('indicators', {}).get('rsi_5m', 50) < 30])) * 100
                factors.append(f"RSI below 30 with sharp rebound - {win_rate:.0f}% success rate")
            
            # 거래량 + MACD 패턴
            volume_macd_wins = [t for t in trades if t.get('outcome') == 'WIN' and
                               t.get('indicators', {}).get('volume_ratio_5m', 1) > 1.5 and
                               t.get('indicators', {}).get('macd_histogram_15m', 0) > 0]
            if len(volume_macd_wins) >= 3:
                avg_return = sum([t.get('pnl_percent', 0) for t in volume_macd_wins]) / len(volume_macd_wins)
                factors.append(f"Volume 1.5x + MACD golden cross: avg +{avg_return:.1f}%")
                
            # EMA 정배열 패턴
            ema_wins = [t for t in trades if t.get('outcome') == 'WIN' and
                       t.get('indicators', {}).get('ema_alignment_15m') == 'bullish']
            if len(ema_wins) >= 3:
                factors.append("15m EMA bullish alignment: target reached within 4 hours")
                
        except Exception as e:
            self.logger.warning(f"성공 요인 추출 실패: {e}")
            
        return factors[:3]  # 상위 3개만 반환
        
    def _prepare_prompt(self, chartist_json: dict, journalist_json: dict,
                       market_data: dict, pattern_analysis: dict, 
                       indicator_sequences: dict, timestamp_utc: str) -> Optional[str]:
        """프롬프트 준비"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
                
            # 입력 데이터 구성
            input_data = {
                'current_market_data': market_data,
                'pattern_analysis': pattern_analysis,
                'indicator_sequences': indicator_sequences,
                'chartist_summary': chartist_json.get('summary', ''),
                'journalist_news_count': {
                    'short_term': len(journalist_json.get('short_term_news', [])),
                    'long_term': len(journalist_json.get('long_term_news', []))
                },
                'chartist_scenarios': chartist_json.get('scenarios', [])
            }
            
            replacements = {
                "분석한 종목": chartist_json.get("asset", "SOLUSDT"),
                "입력받은 시간": timestamp_utc,
                "입력 데이터": json.dumps(input_data, indent=2, ensure_ascii=False)
            }
            
            for key, val in replacements.items():
                template = template.replace(key, str(val))
                
            return template
            
        except FileNotFoundError:
            self.logger.error(f"❌ 프롬프트 파일을 찾을 수 없습니다: {self.prompt_path}")
            return None


# 전역 퀀트 에이전트 인스턴스
quant_agent_v3 = QuantAgentV3()