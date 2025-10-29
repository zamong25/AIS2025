"""
델파이 트레이딩 시스템 - 시장 이벤트 추적기
Phase 3: 가격 급변동, 거래량 이상, 뉴스 이벤트를 자동으로 감지하고 기록
순수 기록 목적으로 거래 결정에는 영향을 주지 않음
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import deque
import statistics

# 프로젝트 루트를 Python path에 추가
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import get_logger
from data.binance_connector import get_current_price, get_full_quant_data

@dataclass
class MarketEvent:
    """시장 이벤트 데이터 구조"""
    event_id: str
    event_type: str  # price_spike, volume_anomaly, news_event
    timestamp: str
    asset: str
    details: Dict
    context: Dict

class MarketEventTracker:
    """시장 이벤트 자동 추적기"""
    
    def __init__(self, asset: str = "SOLUSDT"):
        self.logger = get_logger('MarketEventTracker')
        self.asset = asset
        
        # 이벤트 저장 경로
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.events_dir = os.path.join(project_root, 'data', 'market_events')
        os.makedirs(self.events_dir, exist_ok=True)
        
        # 가격 변동 추적을 위한 버퍼 (최근 60개 가격)
        self.price_buffer = deque(maxlen=60)
        
        # 거래량 추적을 위한 버퍼 (최근 24개 시간별 거래량)
        self.volume_buffer = deque(maxlen=24)
        
        # 이벤트 임계값
        self.thresholds = {
            'price_spike_percent': 5.0,      # 5% 이상 급변동
            'volume_anomaly_multiplier': 3.0, # 평균의 3배 이상
            'rapid_price_change_minutes': 5   # 5분 내 급변동
        }
        
        # 최근 이벤트 (중복 방지)
        self.recent_events = deque(maxlen=100)
        
    def track_price_movements(self) -> Optional[MarketEvent]:
        """가격 급변동 자동 감지 및 기록"""
        try:
            current_price = get_current_price(self.asset)
            if not current_price:
                return None
                
            self.price_buffer.append({
                'price': current_price,
                'timestamp': datetime.now()
            })
            
            # 버퍼가 충분히 채워진 경우만 분석
            if len(self.price_buffer) < 10:
                return None
            
            # 5분 전 가격과 비교
            five_min_ago = datetime.now() - timedelta(minutes=5)
            old_prices = [p for p in self.price_buffer 
                         if p['timestamp'] >= five_min_ago]
            
            if old_prices:
                old_price = old_prices[0]['price']
                price_change_percent = ((current_price - old_price) / old_price) * 100
                
                if abs(price_change_percent) >= self.thresholds['price_spike_percent']:
                    # 가격 급변동 감지
                    event = MarketEvent(
                        event_id=f"price_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        event_type='price_spike',
                        timestamp=datetime.now().isoformat(),
                        asset=self.asset,
                        details={
                            'current_price': current_price,
                            'old_price': old_price,
                            'change_percent': price_change_percent,
                            'time_window': '5분',
                            'direction': 'UP' if price_change_percent > 0 else 'DOWN'
                        },
                        context=self._get_market_context()
                    )
                    
                    # 중복 체크
                    if not self._is_duplicate_event(event):
                        self._save_event(event)
                        self.logger.info(f"🚨 가격 급변동 감지: {price_change_percent:+.1f}% in 5분")
                        return event
                        
        except Exception as e:
            self.logger.debug(f"가격 추적 중 오류: {e}")
            
        return None
    
    def track_volume_anomalies(self) -> Optional[MarketEvent]:
        """거래량 이상 감지"""
        try:
            market_data = get_full_quant_data(self.asset)
            if not market_data:
                return None
                
            current_volume = market_data.get('volume_24h', 0)
            if current_volume <= 0:
                return None
                
            self.volume_buffer.append({
                'volume': current_volume,
                'timestamp': datetime.now()
            })
            
            # 버퍼가 충분히 채워진 경우만 분석
            if len(self.volume_buffer) < 5:
                return None
                
            # 평균 거래량 계산
            volumes = [v['volume'] for v in self.volume_buffer]
            avg_volume = statistics.mean(volumes[:-1])  # 현재 제외한 평균
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            if volume_ratio >= self.thresholds['volume_anomaly_multiplier']:
                # 거래량 이상 감지
                event = MarketEvent(
                    event_id=f"volume_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    event_type='volume_anomaly',
                    timestamp=datetime.now().isoformat(),
                    asset=self.asset,
                    details={
                        'current_volume': current_volume,
                        'average_volume': avg_volume,
                        'volume_ratio': volume_ratio,
                        'threshold': self.thresholds['volume_anomaly_multiplier']
                    },
                    context=self._get_market_context()
                )
                
                if not self._is_duplicate_event(event):
                    self._save_event(event)
                    self.logger.info(f"📊 거래량 이상 감지: {volume_ratio:.1f}x 평균")
                    return event
                    
        except Exception as e:
            self.logger.debug(f"거래량 추적 중 오류: {e}")
            
        return None
    
    def track_news_events(self, journalist_report: Dict = None) -> Optional[MarketEvent]:
        """주요 뉴스 이벤트 자동 감지 (저널리스트 분석 결과 활용)"""
        try:
            if not journalist_report:
                return None
                
            # 높은 임팩트 뉴스 확인
            impact = journalist_report.get('impact_assessment', {}).get('market_impact', '')
            key_events = journalist_report.get('key_events', [])
            
            if impact in ['HIGH', 'CRITICAL'] and key_events:
                # 주요 뉴스 이벤트
                event = MarketEvent(
                    event_id=f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    event_type='news_event',
                    timestamp=datetime.now().isoformat(),
                    asset=self.asset,
                    details={
                        'impact_level': impact,
                        'key_event': key_events[0] if key_events else {},
                        'sentiment': journalist_report.get('sentiment_analysis', {}).get('overall_sentiment', ''),
                        'event_count': len(key_events)
                    },
                    context=self._get_market_context()
                )
                
                if not self._is_duplicate_event(event):
                    self._save_event(event)
                    self.logger.info(f"📰 주요 뉴스 이벤트 감지: {impact} 임팩트")
                    return event
                    
        except Exception as e:
            self.logger.debug(f"뉴스 이벤트 추적 중 오류: {e}")
            
        return None
    
    def _get_market_context(self) -> Dict:
        """현재 시장 상황 컨텍스트"""
        try:
            market_data = get_full_quant_data(self.asset)
            
            return {
                'price': get_current_price(self.asset),
                'rsi': market_data.get('rsi', 0) if market_data else 0,
                'volatility': market_data.get('volatility', 0) if market_data else 0,
                'trend': market_data.get('trend', '') if market_data else '',
                'timestamp': datetime.now().isoformat()
            }
        except:
            return {'timestamp': datetime.now().isoformat()}
    
    def _is_duplicate_event(self, event: MarketEvent) -> bool:
        """중복 이벤트 체크 (5분 내 유사 이벤트)"""
        current_time = datetime.now()
        
        for recent in self.recent_events:
            if recent.event_type == event.event_type:
                event_time = datetime.fromisoformat(recent.timestamp)
                if (current_time - event_time).total_seconds() < 300:  # 5분
                    return True
                    
        self.recent_events.append(event)
        return False
    
    def _save_event(self, event: MarketEvent):
        """이벤트를 파일로 저장"""
        try:
            # 일별 파일로 저장
            date_str = datetime.now().strftime('%Y%m%d')
            filename = f"events_{date_str}.json"
            filepath = os.path.join(self.events_dir, filename)
            
            # 기존 이벤트 로드
            events = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            
            # 새 이벤트 추가
            events.append(asdict(event))
            
            # 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
                
            self.logger.debug(f"이벤트 저장: {filepath}")
            
        except Exception as e:
            self.logger.error(f"이벤트 저장 실패: {e}")
    
    def get_recent_events(self, hours: int = 24) -> List[Dict]:
        """최근 이벤트 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_events = []
            
            # 최근 파일들 확인
            for i in range(3):  # 최대 3일치
                date = datetime.now() - timedelta(days=i)
                date_str = date.strftime('%Y%m%d')
                filename = f"events_{date_str}.json"
                filepath = os.path.join(self.events_dir, filename)
                
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        events = json.load(f)
                        
                    for event in events:
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if event_time >= cutoff_time:
                            recent_events.append(event)
            
            return sorted(recent_events, key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"이벤트 조회 실패: {e}")
            return []
    
    def track_all_events(self, journalist_report: Dict = None) -> List[MarketEvent]:
        """모든 이벤트 추적 실행"""
        events = []
        
        # 가격 변동 추적
        price_event = self.track_price_movements()
        if price_event:
            events.append(price_event)
        
        # 거래량 이상 추적
        volume_event = self.track_volume_anomalies()
        if volume_event:
            events.append(volume_event)
        
        # 뉴스 이벤트 추적
        if journalist_report:
            news_event = self.track_news_events(journalist_report)
            if news_event:
                events.append(news_event)
        
        return events

# 전역 이벤트 추적기 인스턴스
market_event_tracker = MarketEventTracker()

if __name__ == "__main__":
    # 테스트 실행
    tracker = MarketEventTracker()
    
    # 가격 변동 추적 테스트
    for i in range(10):
        tracker.track_price_movements()
        import time
        time.sleep(1)
    
    # 최근 이벤트 조회
    recent = tracker.get_recent_events(24)
    print(f"최근 24시간 이벤트: {len(recent)}개")