"""
델파이 트레이딩 시스템 - 다층 시간대 데이터 수집기
5분, 15분, 1시간 지표를 동시에 수집하고 분석
"""

import pandas as pd
import pandas_ta as ta
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from binance.client import Client

from data.binance_connector import client, get_current_price
from utils.logging_config import get_logger


class MultiTimeframeCollector:
    """다층 시간대 데이터 수집 및 지표 계산"""
    
    def __init__(self):
        self.logger = get_logger('MultiTimeframeCollector')
        self.timeframes = {
            '5m': Client.KLINE_INTERVAL_5MINUTE,
            '15m': Client.KLINE_INTERVAL_15MINUTE,
            '1h': Client.KLINE_INTERVAL_1HOUR
        }
        
    def collect_all_timeframes(self, symbol: str = 'SOLUSDT') -> Dict[str, Any]:
        """
        모든 시간대의 데이터 수집 및 지표 계산
        
        Returns:
            {
                'current_price': 150.5,
                'indicators_5m': {...},
                'indicators_15m': {...},
                'indicators_1h': {...},
                'timestamp': '2025-01-08T12:00:00Z'
            }
        """
        try:
            result = {
                'current_price': get_current_price(symbol),
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            
            # 각 시간대별 데이터 수집
            for tf_name, interval in self.timeframes.items():
                indicators = self._collect_timeframe_data(symbol, tf_name, interval)
                result[f'indicators_{tf_name}'] = indicators
                
            self.logger.info(f"✅ 다층 시간대 데이터 수집 완료: {symbol}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 다층 시간대 데이터 수집 실패: {e}")
            return {}
            
    def _collect_timeframe_data(self, symbol: str, timeframe: str, 
                                interval: str) -> Dict[str, Any]:
        """특정 시간대의 데이터 수집 및 지표 계산"""
        try:
            # 캔들 데이터 수집 (100개)
            klines = client.get_klines(symbol=symbol, interval=interval, limit=100)
            
            # DataFrame 변환
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # 데이터 타입 변환
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
                
            # 지표 계산
            indicators = self._calculate_indicators(df, timeframe)
            
            # 변화율 계산
            indicators = self._calculate_changes(df, indicators)
            
            return indicators
            
        except Exception as e:
            self.logger.warning(f"❌ {timeframe} 데이터 수집 실패: {e}")
            return {}
            
    def _calculate_indicators(self, df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
        """기술적 지표 계산"""
        try:
            indicators = {}
            
            # 1. RSI
            period = 7 if timeframe == '5m' else 14
            rsi_series = ta.rsi(df['close'], length=period)
            indicators['rsi'] = round(rsi_series.iloc[-1], 2) if not rsi_series.empty else 50
            
            # RSI 시퀀스 (최근 5개)
            if len(rsi_series) >= 5:
                indicators['rsi_sequence'] = [round(x, 2) for x in rsi_series.iloc[-5:].tolist()]
            
            # 2. MACD
            macd = ta.macd(df['close'])
            if macd is not None and not macd.empty:
                indicators['macd_histogram'] = round(macd['MACDh_12_26_9'].iloc[-1], 4)
                indicators['macd_signal'] = round(macd['MACDs_12_26_9'].iloc[-1], 4)
                indicators['macd_line'] = round(macd['MACD_12_26_9'].iloc[-1], 4)
                
                # MACD 크로스 체크
                if len(macd) >= 2:
                    prev_hist = macd['MACDh_12_26_9'].iloc[-2]
                    curr_hist = macd['MACDh_12_26_9'].iloc[-1]
                    if prev_hist < 0 and curr_hist > 0:
                        indicators['macd_signal_cross'] = 'bullish_cross'
                    elif prev_hist > 0 and curr_hist < 0:
                        indicators['macd_signal_cross'] = 'bearish_cross'
                    else:
                        indicators['macd_signal_cross'] = 'none'
                        
            # 3. EMA
            ema5 = ta.ema(df['close'], length=5)
            ema8 = ta.ema(df['close'], length=8)
            ema13 = ta.ema(df['close'], length=13)
            
            if not ema5.empty:
                current_price = df['close'].iloc[-1]
                indicators['ema5'] = round(ema5.iloc[-1], 2)
                indicators['ema8'] = round(ema8.iloc[-1], 2)
                indicators['ema13'] = round(ema13.iloc[-1], 2)
                
                # 가격 vs EMA5 (%)
                indicators['price_vs_ema5'] = round((current_price - ema5.iloc[-1]) / ema5.iloc[-1] * 100, 2)
                
                # EMA 배열 상태
                if ema5.iloc[-1] > ema8.iloc[-1] > ema13.iloc[-1]:
                    indicators['ema_alignment'] = 'bullish'
                elif ema5.iloc[-1] < ema8.iloc[-1] < ema13.iloc[-1]:
                    indicators['ema_alignment'] = 'bearish'
                else:
                    indicators['ema_alignment'] = 'mixed'
                    
            # 4. 볼린저 밴드
            bb = ta.bbands(df['close'], length=20, std=2)
            if bb is not None and not bb.empty:
                current_price = df['close'].iloc[-1]
                upper = bb['BBU_20_2.0'].iloc[-1]
                middle = bb['BBM_20_2.0'].iloc[-1]
                lower = bb['BBL_20_2.0'].iloc[-1]
                
                indicators['bb_upper'] = round(upper, 2)
                indicators['bb_middle'] = round(middle, 2)
                indicators['bb_lower'] = round(lower, 2)
                
                # 밴드 내 위치
                if current_price >= upper * 0.98:
                    indicators['bollinger_position'] = 'upper'
                elif current_price <= lower * 1.02:
                    indicators['bollinger_position'] = 'lower'
                else:
                    indicators['bollinger_position'] = 'middle'
                    
                # 밴드폭
                band_width = (upper - lower) / middle * 100
                indicators['bb_width'] = round(band_width, 2)
                
            # 5. 거래량
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            indicators['volume_ratio'] = round(current_volume / avg_volume, 2) if avg_volume > 0 else 1.0
            
            # 거래량 시퀀스
            if len(df) >= 5:
                volume_seq = []
                for i in range(-5, 0):
                    vol_avg = df['volume'].rolling(window=20).mean().iloc[i]
                    vol_ratio = df['volume'].iloc[i] / vol_avg if vol_avg > 0 else 1.0
                    volume_seq.append(round(vol_ratio, 2))
                indicators['volume_ratio_sequence'] = volume_seq
                
            return indicators
            
        except Exception as e:
            self.logger.warning(f"지표 계산 실패 ({timeframe}): {e}")
            return {}
            
    def _calculate_changes(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """지표 변화율 계산"""
        try:
            # RSI 변화
            if 'rsi_sequence' in indicators and len(indicators['rsi_sequence']) >= 2:
                rsi_change = indicators['rsi_sequence'][-1] - indicators['rsi_sequence'][0]
                indicators['rsi_change'] = round(rsi_change, 2)
                
                # 변화 속도
                change_rate = abs(rsi_change) / len(indicators['rsi_sequence'])
                if change_rate > 10:
                    indicators['rsi_trend'] = 'sharp_rise' if rsi_change > 0 else 'sharp_fall'
                elif change_rate > 5:
                    indicators['rsi_trend'] = 'rise' if rsi_change > 0 else 'fall'
                else:
                    indicators['rsi_trend'] = 'sideways'
                    
            # MACD 히스토그램 변화
            macd_hist = ta.macd(df['close'])
            if macd_hist is not None and len(macd_hist) >= 5:
                hist_values = macd_hist['MACDh_12_26_9'].iloc[-5:].tolist()
                indicators['macd_histogram_sequence'] = [round(x, 4) for x in hist_values]
                
                # 추세 판단
                if all(hist_values[i] < hist_values[i+1] for i in range(len(hist_values)-1)):
                    indicators['macd_trend'] = 'accelerating_up'
                elif all(hist_values[i] > hist_values[i+1] for i in range(len(hist_values)-1)):
                    indicators['macd_trend'] = 'accelerating_down'
                else:
                    indicators['macd_trend'] = 'transitioning'
                    
            # 거래량 추세
            if 'volume_ratio_sequence' in indicators:
                vol_seq = indicators['volume_ratio_sequence']
                if vol_seq[-1] > 1.5 and vol_seq[-1] > vol_seq[-2]:
                    indicators['volume_trend'] = 'surge'
                elif vol_seq[-1] > 1.2:
                    indicators['volume_trend'] = 'increase'
                elif vol_seq[-1] < 0.8:
                    indicators['volume_trend'] = 'decrease'
                else:
                    indicators['volume_trend'] = 'normal'
                    
            return indicators
            
        except Exception as e:
            self.logger.warning(f"변화율 계산 실패: {e}")
            return indicators
            
    def check_divergence(self, symbol: str = 'SOLUSDT') -> Dict[str, Any]:
        """가격과 지표 간 다이버전스 체크"""
        try:
            divergences = []
            
            for tf_name, interval in self.timeframes.items():
                klines = client.get_klines(symbol=symbol, interval=interval, limit=50)
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                df['close'] = pd.to_numeric(df['close'])
                
                # RSI 다이버전스
                rsi = ta.rsi(df['close'], length=14)
                if len(rsi) >= 10:
                    # 최근 고점/저점 찾기
                    price_highs = df['close'].rolling(window=5).max()
                    price_lows = df['close'].rolling(window=5).min()
                    
                    # Bearish divergence: 가격은 신고점, RSI는 낮은 고점
                    if df['close'].iloc[-1] > price_highs.iloc[-10:-5].max() and \
                       rsi.iloc[-1] < rsi.iloc[-10:-5].max():
                        divergences.append({
                            'timeframe': tf_name,
                            'type': 'bearish',
                            'indicator': 'RSI'
                        })
                        
                    # Bullish divergence: 가격은 신저점, RSI는 높은 저점
                    if df['close'].iloc[-1] < price_lows.iloc[-10:-5].min() and \
                       rsi.iloc[-1] > rsi.iloc[-10:-5].min():
                        divergences.append({
                            'timeframe': tf_name,
                            'type': 'bullish',
                            'indicator': 'RSI'
                        })
                        
            return {
                'detected': len(divergences) > 0,
                'divergences': divergences
            }
            
        except Exception as e:
            self.logger.warning(f"다이버전스 체크 실패: {e}")
            return {'detected': False, 'divergences': []}


# 전역 수집기 인스턴스
multi_tf_collector = MultiTimeframeCollector()