"""
지능적 포지션 모니터링 시스템
포지션 진입 후 손익률, 시장 변화, 긴급 상황 등을 모니터링하여
적절한 시점에 AI 분석을 요청
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

class SmartPositionMonitor:
    """지능적 포지션 모니터링"""
    
    def __init__(self, scheduler, price_history):
        """
        포지션 모니터 초기화
        
        Args:
            scheduler: SmartScheduler 인스턴스
            price_history: PriceHistory 인스턴스
        """
        self.scheduler = scheduler
        self.price_history = price_history
        self.logger = logging.getLogger(__name__)
        self.emergency_cooldown = {}  # trade_id: cooldown_until
        
        self.logger.info("SmartPositionMonitor 초기화 완료")
        
    def check_position_triggers(self, position: Dict, current_price: float, 
                              market_data: Dict, triggers: List[Dict]) -> Optional[Dict]:
        """
        포지션 트리거 체크 및 스마트 분석
        
        Args:
            position: 현재 포지션 정보
            current_price: 현재 가격
            market_data: 시장 데이터
            triggers: 활성 트리거 리스트
            
        Returns:
            액션이 필요한 경우 결과 딕셔너리, 없으면 None
        """
        # 가격 히스토리 업데이트
        self.price_history.add_price(position['symbol'], current_price)
        
        # 1. 긴급 상황 우선 체크
        emergency_check = self._check_emergency_conditions(position, current_price, market_data)
        if emergency_check:
            self.logger.critical(f"긴급 상황 감지: {emergency_check['reason']}")
            return emergency_check
            
        # 2. 포지션 트리거 평가
        triggered_items = []
        for trigger in triggers:
            if trigger.get('trigger_type') != 'position':
                continue
                
            if self._is_position_trigger_met(trigger, position, current_price, market_data):
                triggered_items.append(trigger)
                self.logger.info(
                    f"트리거 조건 충족: {trigger['trigger_id']} "
                    f"(타입: {trigger['condition_type']})"
                )
                
        if not triggered_items:
            return None
            
        # 3. 가장 높은 우선순위 트리거 선택
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        triggered_items.sort(key=lambda x: priority_order.get(x.get('urgency', 'low'), 4))
        
        highest_priority = triggered_items[0]
        self.logger.info(
            f"최고 우선순위 트리거: {highest_priority['trigger_id']} "
            f"(긴급도: {highest_priority.get('urgency', 'low')})"
        )
        
        # 4. AI 호출 여부 결정
        if highest_priority['urgency'] in ['critical', 'high']:
            # 고우선순위는 즉시 AI 분석
            self.scheduler.record_ai_call('trigger', {'trigger': highest_priority})
            return {
                'action': 'request_ai_analysis',
                'trigger': highest_priority,
                'reason': f"{highest_priority['condition_type']} 트리거 발동"
            }
            
        elif self._should_analyze_smart(position, market_data, highest_priority):
            # 스마트 조건 충족 시
            self.scheduler.record_ai_call('trigger', {'trigger': highest_priority})
            return {
                'action': 'request_ai_analysis',
                'trigger': highest_priority,
                'reason': '스마트 분석 조건 충족'
            }
            
        self.logger.debug(
            f"트리거 {highest_priority['trigger_id']} 발동했으나 "
            f"AI 호출 조건 미충족"
        )
        return None
        
    def _check_emergency_conditions(self, position: Dict, current_price: float, 
                                  market_data: Dict) -> Optional[Dict]:
        """
        긴급 상황 체크
        
        Returns:
            긴급 상황인 경우 액션 딕셔너리, 아니면 None
        """
        trade_id = position['trade_id']
        
        # 쿨다운 체크
        if trade_id in self.emergency_cooldown:
            if datetime.now() < self.emergency_cooldown[trade_id]:
                remaining = (self.emergency_cooldown[trade_id] - datetime.now()).total_seconds() / 60
                self.logger.debug(f"긴급 알림 쿨다운 중: {remaining:.1f}분 남음")
                return None
                
        # PnL 계산
        pnl_percent = self._calculate_pnl_percent(position, current_price)
        
        # 1. 극단적 손실 (-8% 이상)
        if pnl_percent < -8.0:
            self._set_emergency_cooldown(trade_id, 30)  # 30분 쿨다운
            self.logger.error(f"극단적 손실 감지: {pnl_percent:.2f}%")
            return {
                'action': 'emergency_action',
                'reason': f'극단적 손실: {pnl_percent:.2f}%',
                'urgency': 'critical'
            }
            
        # 2. 플래시 크래시 감지 (1분 내 3% 이상 급변)
        price_1m_ago = self.price_history.get_price_ago(position['symbol'], 1)
        if price_1m_ago:
            rapid_change = abs((current_price - price_1m_ago) / price_1m_ago * 100)
            if rapid_change > 3.0:
                self._set_emergency_cooldown(trade_id, 15)  # 15분 쿨다운
                self.logger.error(f"플래시 크래시 감지: {rapid_change:.2f}% 급변")
                return {
                    'action': 'emergency_action',
                    'reason': f'플래시 크래시 감지: {rapid_change:.2f}% 급변',
                    'urgency': 'critical'
                }
                
        # 3. 거래량 폭발 (평균의 5배 이상)
        volume_ratio = market_data.get('volume_ratio', 1.0)
        if volume_ratio > 5.0:
            self._set_emergency_cooldown(trade_id, 20)  # 20분 쿨다운
            self.logger.error(f"거래량 폭발 감지: {volume_ratio:.1f}배")
            return {
                'action': 'emergency_action',
                'reason': f'거래량 폭발: {volume_ratio:.1f}배',
                'urgency': 'critical'
            }
                
        return None
        
    def _is_position_trigger_met(self, trigger: Dict, position: Dict, 
                                current_price: float, market_data: Dict) -> bool:
        """
        개별 트리거 조건 체크
        
        Returns:
            트리거 조건이 충족되면 True
        """
        condition_type = trigger.get('condition_type')
        
        try:
            if condition_type == 'mdd':
                pnl = self._calculate_pnl_percent(position, current_price)
                threshold = trigger.get('threshold_percent', -4.0)
                if pnl <= threshold:
                    self.logger.debug(f"MDD 트리거: PnL {pnl:.2f}% <= {threshold}%")
                    return True
                    
            elif condition_type == 'profit':
                pnl = self._calculate_pnl_percent(position, current_price)
                threshold = trigger.get('threshold_percent', 6.0)
                if pnl >= threshold:
                    self.logger.debug(f"이익 트리거: PnL {pnl:.2f}% >= {threshold}%")
                    return True
                    
            elif condition_type == 'time':
                # entry_time이 datetime 객체인지 확인
                entry_time = position.get('entry_time')
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)
                    
                hours_held = (datetime.now() - entry_time).total_seconds() / 3600
                required_hours = trigger.get('hours_in_position', 24)
                
                if hours_held >= required_hours:
                    # 추가로 움직임 체크
                    price_change = abs(self._calculate_pnl_percent(position, current_price))
                    min_movement = trigger.get('min_movement_percent', 1.0)
                    if price_change < min_movement:
                        self.logger.debug(
                            f"시간 트리거: {hours_held:.1f}시간 경과, "
                            f"움직임 {price_change:.2f}% < {min_movement}%"
                        )
                        return True
                        
            elif condition_type == 'volatility_spike':
                current_vol = market_data.get('volatility', 0)
                baseline = trigger.get('baseline_volatility', 0)
                if baseline > 0:
                    vol_ratio = current_vol / baseline
                    threshold_mult = trigger.get('threshold_multiplier', 2.0)
                    if vol_ratio >= threshold_mult:
                        self.logger.debug(
                            f"변동성 트리거: {vol_ratio:.2f}x >= {threshold_mult}x"
                        )
                        return True
                        
        except Exception as e:
            self.logger.error(f"트리거 조건 체크 중 오류: {e}")
            
        return False
        
    def _should_analyze_smart(self, position: Dict, market_data: Dict, 
                            trigger: Dict) -> bool:
        """
        스마트 분석 조건 판단
        
        Returns:
            스마트 분석이 필요하면 True
        """
        # 1. 마지막 AI 분석으로부터 충분한 시간 경과
        stats = self.scheduler.get_ai_call_stats(1)  # 최근 1시간
        if stats['total_calls'] > 4:  # 시간당 4회 초과
            self.logger.debug(f"시간당 AI 호출 초과: {stats['total_calls']}회")
            return False
            
        # 2. 시장 조건 변화
        market_condition = self._analyze_market_condition(market_data)
        if market_condition in ['high_volatility', 'trending']:
            self.logger.info(f"시장 조건 변화 감지: {market_condition}")
            return True
            
        # 3. 포지션 수익률이 의미있는 수준
        # current_price를 market_data에서 가져오거나 position에서 추정
        current_price = market_data.get('current_price', position.get('current_price', 0))
        pnl = self._calculate_pnl_percent(position, current_price)
        if abs(pnl) > 3.0:  # ±3% 이상
            self.logger.info(f"의미있는 PnL 변화: {pnl:.2f}%")
            return True
            
        return False
        
    def _calculate_pnl_percent(self, position: Dict, current_price: float) -> float:
        """
        손익률 계산
        
        Returns:
            손익률 (%)
        """
        entry_price = position.get('entry_price', 0)
        if entry_price <= 0:
            self.logger.error(f"잘못된 진입가격: {entry_price}")
            return 0.0
            
        direction = position.get('direction', 'LONG')
        
        if direction == 'LONG':
            pnl = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl = ((entry_price - current_price) / entry_price) * 100
            
        return pnl
            
    def _analyze_market_condition(self, market_data: Dict) -> str:
        """
        시장 상태 분석
        
        Returns:
            시장 상태 문자열
        """
        volatility = market_data.get('volatility', 0)
        avg_volatility = market_data.get('avg_volatility', volatility * 0.8)
        volume_ratio = market_data.get('volume_ratio', 1.0)
        trend_strength = market_data.get('trend_strength', 0)
        
        if volatility > avg_volatility * 1.5:
            return 'high_volatility'
        elif volume_ratio > 2.0:
            return 'high_volume'
        elif trend_strength > 25:  # ADX > 25
            return 'trending'
        else:
            return 'normal'
            
    def _set_emergency_cooldown(self, trade_id: str, minutes: int):
        """
        긴급 알림 쿨다운 설정
        
        Args:
            trade_id: 거래 ID
            minutes: 쿨다운 시간 (분)
        """
        self.emergency_cooldown[trade_id] = datetime.now() + timedelta(minutes=minutes)
        self.logger.info(f"긴급 알림 쿨다운 설정: {trade_id} - {minutes}분")
        
    def clear_position_cooldown(self, trade_id: str):
        """
        포지션 청산 시 쿨다운 제거
        
        Args:
            trade_id: 거래 ID
        """
        if trade_id in self.emergency_cooldown:
            del self.emergency_cooldown[trade_id]
            self.logger.info(f"긴급 쿨다운 제거: {trade_id}")