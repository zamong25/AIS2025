"""
효율적인 가격 히스토리 관리를 위한 순환 버퍼 구현
메모리 효율성을 위해 최대 크기를 제한하고 오래된 데이터는 자동 삭제
"""

from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Optional
import logging

class PriceHistory:
    """효율적인 가격 히스토리 관리 (순환 버퍼)"""
    
    def __init__(self, max_size: int = 1000):
        """
        가격 히스토리 초기화
        
        Args:
            max_size: 보관할 최대 가격 포인트 수
        """
        self.prices: Deque[Dict] = deque(maxlen=max_size)
        self.symbol_histories: Dict[str, Deque] = {}
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"PriceHistory 초기화: 최대 {max_size}개 가격 저장")
        
    def add_price(self, symbol: str, price: float, timestamp: datetime = None):
        """
        가격 추가
        
        Args:
            symbol: 심볼명 (예: SOLUSDT)
            price: 현재 가격
            timestamp: 시간 (None이면 현재 시간)
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        price_point = {
            'symbol': symbol,
            'price': price,
            'timestamp': timestamp
        }
        
        # 전체 히스토리에 추가
        self.prices.append(price_point)
        
        # 심볼별 히스토리 관리
        if symbol not in self.symbol_histories:
            self.symbol_histories[symbol] = deque(maxlen=self.prices.maxlen)
            self.logger.debug(f"새 심볼 히스토리 생성: {symbol}")
            
        self.symbol_histories[symbol].append(price_point)
        
        # 디버그: 10개마다 로깅
        if len(self.symbol_histories[symbol]) % 10 == 0:
            self.logger.debug(
                f"{symbol} 가격 히스토리: {len(self.symbol_histories[symbol])}개 저장됨"
            )
        
    def get_price_ago(self, symbol: str, minutes_ago: int) -> Optional[float]:
        """
        N분 전 가격 조회
        
        Args:
            symbol: 심볼명
            minutes_ago: 몇 분 전 가격을 조회할지
            
        Returns:
            N분 전 가격 (없으면 None)
        """
        if symbol not in self.symbol_histories:
            self.logger.warning(f"심볼 히스토리 없음: {symbol}")
            return None
            
        target_time = datetime.now() - timedelta(minutes=minutes_ago)
        history = self.symbol_histories[symbol]
        
        # 역순으로 탐색 (최신 데이터부터)
        closest_price = None
        closest_time_diff = float('inf')
        
        for price_point in reversed(history):
            if price_point['timestamp'] <= target_time:
                # 목표 시간 이전의 가장 가까운 가격
                time_diff = (target_time - price_point['timestamp']).total_seconds()
                if time_diff < closest_time_diff:
                    closest_time_diff = time_diff
                    closest_price = price_point['price']
                else:
                    # 시간순으로 정렬되어 있으므로 더 이상 볼 필요 없음
                    break
                    
        if closest_price is None:
            self.logger.debug(f"{symbol} {minutes_ago}분 전 가격 없음")
        else:
            self.logger.debug(
                f"{symbol} {minutes_ago}분 전 가격: {closest_price:.2f} "
                f"(실제 {closest_time_diff/60:.1f}분 전 데이터)"
            )
            
        return closest_price
        
    def calculate_change_rate(self, symbol: str, minutes: int) -> Optional[float]:
        """
        N분간 변화율 계산
        
        Args:
            symbol: 심볼명
            minutes: 변화율 계산 기간 (분)
            
        Returns:
            변화율 (%) (계산 불가능하면 None)
        """
        current_price = self.get_latest_price(symbol)
        past_price = self.get_price_ago(symbol, minutes)
        
        if current_price and past_price and past_price > 0:
            change_rate = ((current_price - past_price) / past_price) * 100
            self.logger.debug(
                f"{symbol} {minutes}분간 변화율: {change_rate:.2f}% "
                f"({past_price:.2f} -> {current_price:.2f})"
            )
            return change_rate
            
        return None
        
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        최신 가격 조회
        
        Args:
            symbol: 심볼명
            
        Returns:
            최신 가격 (없으면 None)
        """
        if symbol in self.symbol_histories and self.symbol_histories[symbol]:
            latest = self.symbol_histories[symbol][-1]['price']
            return latest
            
        self.logger.warning(f"{symbol} 최신 가격 없음")
        return None
        
    def get_price_range(self, symbol: str, minutes: int) -> Optional[Dict]:
        """
        특정 기간 동안의 가격 범위 조회
        
        Args:
            symbol: 심볼명
            minutes: 조회 기간 (분)
            
        Returns:
            {'high': 최고가, 'low': 최저가, 'count': 데이터 수}
        """
        if symbol not in self.symbol_histories:
            return None
            
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        prices = []
        
        for price_point in self.symbol_histories[symbol]:
            if price_point['timestamp'] >= cutoff_time:
                prices.append(price_point['price'])
                
        if not prices:
            return None
            
        result = {
            'high': max(prices),
            'low': min(prices),
            'count': len(prices)
        }
        
        self.logger.debug(
            f"{symbol} 최근 {minutes}분 범위: "
            f"최고 {result['high']:.2f}, 최저 {result['low']:.2f}, "
            f"데이터 {result['count']}개"
        )
        
        return result
        
    def clear_symbol_history(self, symbol: str):
        """
        특정 심볼의 히스토리 삭제
        
        Args:
            symbol: 삭제할 심볼명
        """
        if symbol in self.symbol_histories:
            del self.symbol_histories[symbol]
            self.logger.info(f"{symbol} 가격 히스토리 삭제됨")
            
    def get_stats(self) -> Dict:
        """
        현재 히스토리 통계
        
        Returns:
            통계 정보
        """
        stats = {
            'total_entries': len(self.prices),
            'symbols': list(self.symbol_histories.keys()),
            'symbol_counts': {
                symbol: len(history) 
                for symbol, history in self.symbol_histories.items()
            }
        }
        
        return stats