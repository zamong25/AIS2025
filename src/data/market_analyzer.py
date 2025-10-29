"""
델파이 트레이딩 시스템 - 시장 컨텍스트 분석기
시장 상황을 객관적 지표로 분석하여 정량화
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging


class MarketContextAnalyzer:
    """시장 상황 객관적 분석"""
    
    def __init__(self):
        self.logger = logging.getLogger('MarketAnalyzer')
        self.logger.info("📈 시장 컨텍스트 분석기 초기화")
    
    def analyze(self, market_data: Dict) -> Dict:
        """핵심 시장 지표 계산"""
        prices = market_data.get('prices', [])
        
        # 데이터 부족 시 기본값
        if len(prices) < 200:
            self.logger.warning(f"가격 데이터 부족: {len(prices)}개")
            return self._default_context()
        
        # 1. 변동성 지표
        atr = market_data.get('atr_14', 0)
        atr_history = market_data.get('atr_history', [atr] if atr else [])
        atr_percentile = self._calculate_percentile(atr, atr_history)
        
        # 2. 거래량 지표
        volume = market_data.get('volume', 0)
        avg_volume = market_data.get('avg_volume_20', 1)
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        
        # 3. 트렌드 지표
        trend_strength = self._calculate_trend_strength(prices)
        ma20_slope = self._calculate_slope(prices[-20:])
        ma20 = np.mean(prices[-20:])
        price_vs_ma20 = (prices[-1] - ma20) / prices[-1] if prices[-1] > 0 else 0
        
        # 4. 구조적 위치
        high20 = max(prices[-20:])
        low20 = min(prices[-20:])
        distance_from_high = (high20 - prices[-1]) / prices[-1] if prices[-1] > 0 else 0
        distance_from_low = (prices[-1] - low20) / prices[-1] if prices[-1] > 0 else 0
        structural_position = self._get_structural_position(prices[-1], high20, low20)
        
        # 5. 시간 정보
        now = datetime.now()
        
        return {
            'atr_value': round(atr, 2),
            'atr_percentile': round(atr_percentile, 2),
            'volume_ratio': round(volume_ratio, 2),
            'trend_strength': trend_strength,
            'ma20_slope': round(ma20_slope, 6),
            'price_vs_ma20': round(price_vs_ma20, 4),
            'distance_from_high20': round(distance_from_high, 4),
            'distance_from_low20': round(distance_from_low, 4),
            'structural_position': structural_position,
            'hour_of_day': now.hour,
            'day_of_week': now.weekday()
        }
    
    def _calculate_trend_strength(self, prices: List[float]) -> int:
        """트렌드 강도 계산 (-4 ~ +4)"""
        if len(prices) < 200:
            return 0
            
        score = 0
        
        # MA 정렬 체크
        ma20 = np.mean(prices[-20:])
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        
        if ma20 > ma50 > ma200:
            score += 2
        elif ma20 < ma50 < ma200:
            score -= 2
        
        # 현재 가격 위치
        if prices[-1] > ma20:
            score += 1
        else:
            score -= 1
        
        # 최근 모멘텀
        if len(prices) >= 5 and prices[-1] > prices[-5]:
            score += 1
        elif len(prices) >= 5:
            score -= 1
        
        return max(-4, min(4, score))
    
    def _calculate_slope(self, prices: List[float]) -> float:
        """가격 데이터의 기울기 계산"""
        if len(prices) < 2:
            return 0
        
        x = np.arange(len(prices))
        y = np.array(prices)
        
        # 선형 회귀
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]
        
        # 정규화 (일일 변화율로 변환)
        avg_price = np.mean(prices)
        if avg_price > 0:
            normalized_slope = slope / avg_price
        else:
            normalized_slope = 0
            
        return normalized_slope
    
    def _calculate_percentile(self, value: float, history: List[float]) -> float:
        """히스토리에서 현재 값의 백분위수 계산"""
        if not history or len(history) < 20:
            return 50.0
        
        # 현재 값보다 작은 값들의 비율
        smaller_count = sum(1 for h in history if h < value)
        percentile = (smaller_count / len(history)) * 100
        
        return percentile
    
    def _get_structural_position(self, current: float, high20: float, low20: float) -> str:
        """구조적 위치 판단"""
        if current >= high20 * 0.995:
            return "breakout"
        elif current <= low20 * 1.005:
            return "breakdown"
        elif abs(current - high20) < abs(current - low20):
            return "near_resistance"
        else:
            return "near_support"
    
    def _default_context(self) -> Dict:
        """데이터 부족 시 기본 컨텍스트"""
        now = datetime.now()
        
        return {
            'atr_value': 0,
            'atr_percentile': 50,
            'volume_ratio': 1,
            'trend_strength': 0,
            'ma20_slope': 0,
            'price_vs_ma20': 0,
            'distance_from_high20': 0,
            'distance_from_low20': 0,
            'structural_position': 'middle',
            'hour_of_day': now.hour,
            'day_of_week': now.weekday()
        }
    
    def analyze_from_chartist(self, chartist_data: Dict) -> Dict:
        """Chartist 데이터에서 시장 컨텍스트 추출 (호환성)"""
        # 기술적 지표에서 정보 추출
        indicators = chartist_data.get('technical_indicators', {})
        market_structure = chartist_data.get('market_structure_analysis', {})
        
        # 트렌드 강도 추론
        bias_score = chartist_data.get('quantitative_scorecard', {}).get('overall_bias_score', 50)
        trend_strength = int((bias_score - 50) / 12.5)  # -4 to 4로 변환
        
        # 구조적 위치 판단
        structural_position = "middle"
        if market_structure.get('immediate_resistance'):
            if 'Breaking above' in market_structure.get('key_observations', ''):
                structural_position = "breakout"
            else:
                structural_position = "near_resistance"
        elif market_structure.get('immediate_support'):
            if 'Breaking below' in market_structure.get('key_observations', ''):
                structural_position = "breakdown"
            else:
                structural_position = "near_support"
        
        # RSI에서 모멘텀 추론
        rsi = indicators.get('rsi', {}).get('value', 50)
        momentum_score = (rsi - 50) / 50  # -1 to 1로 정규화
        
        now = datetime.now()
        
        return {
            'atr_value': 0,  # Chartist에서 제공하지 않음
            'atr_percentile': 50,
            'volume_ratio': 1,
            'trend_strength': trend_strength,
            'ma20_slope': momentum_score * 0.01,  # 근사값
            'price_vs_ma20': 0,
            'distance_from_high20': 0,
            'distance_from_low20': 0,
            'structural_position': structural_position,
            'hour_of_day': now.hour,
            'day_of_week': now.weekday()
        }
    
    def get_market_regime(self, context: Dict) -> str:
        """시장 체제 분류"""
        trend = context.get('trend_strength', 0)
        volatility = context.get('atr_percentile', 50)
        
        if abs(trend) >= 3:
            if volatility > 70:
                return "trending_volatile"
            else:
                return "trending_stable"
        elif abs(trend) <= 1:
            if volatility > 70:
                return "ranging_volatile"
            else:
                return "ranging_stable"
        else:
            return "transitional"
    
    def calculate_similarity_score(self, context1: Dict, context2: Dict, 
                                 weights: Optional[Dict] = None) -> float:
        """두 시장 컨텍스트 간 유사도 점수 계산 (0-100)"""
        if weights is None:
            weights = {
                'trend_strength': 0.3,
                'atr_percentile': 0.2,
                'structural_position': 0.3,
                'volume_ratio': 0.2
            }
        
        score = 0
        
        # 트렌드 강도 차이
        trend_diff = abs(context1.get('trend_strength', 0) - context2.get('trend_strength', 0))
        trend_similarity = max(0, 1 - trend_diff / 8) * 100
        score += trend_similarity * weights['trend_strength']
        
        # ATR 백분위수 차이
        atr_diff = abs(context1.get('atr_percentile', 50) - context2.get('atr_percentile', 50))
        atr_similarity = max(0, 1 - atr_diff / 100) * 100
        score += atr_similarity * weights['atr_percentile']
        
        # 구조적 위치 일치
        if context1.get('structural_position') == context2.get('structural_position'):
            score += 100 * weights['structural_position']
        
        # 거래량 비율 차이
        vol_diff = abs(context1.get('volume_ratio', 1) - context2.get('volume_ratio', 1))
        vol_similarity = max(0, 1 - min(vol_diff, 2) / 2) * 100
        score += vol_similarity * weights['volume_ratio']
        
        return round(score, 2)