"""
포지션 모니터링을 위한 트리거 관리자
포지션 진입 후 손익률, 시간, 변동성 등을 기반으로 트리거 생성
"""

import logging
from typing import Dict, List
from datetime import datetime

class PositionTriggerManager:
    """포지션별 트리거 관리"""
    
    def __init__(self, trigger_manager):
        self.trigger_manager = trigger_manager
        self.logger = logging.getLogger(__name__)
        
    def create_position_triggers(self, position: Dict, market_data: Dict) -> List[Dict]:
        """포지션 진입 시 모니터링 트리거 생성"""
        triggers = []
        
        # 포지션 정보 추출
        trade_id = position.get('trade_id')
        entry_price = position.get('entry_price', 0)
        direction = position.get('direction', 'LONG')
        
        # ATR 기반 동적 임계값 설정
        atr = market_data.get('atr', entry_price * 0.02)  # 기본 2%
        
        self.logger.info(f"포지션 트리거 생성 시작: {trade_id}, 진입가: {entry_price}, ATR: {atr}")
        
        # 1. 손실 제한 트리거 (MDD)
        if direction == "LONG":
            stop_price = entry_price - (atr * 2)  # 2 ATR 손실
            emergency_price = entry_price - (atr * 3)  # 3 ATR 긴급
        else:  # SHORT
            stop_price = entry_price + (atr * 2)
            emergency_price = entry_price + (atr * 3)
            
        triggers.append({
            'trigger_id': f'mdd_{trade_id}',
            'trigger_type': 'position',
            'condition_type': 'mdd',
            'price': stop_price,
            'direction': direction,
            'threshold_percent': -4.0,  # -4% MDD
            'action': 'analyze',
            'urgency': 'high',
            'expires_hours': 168  # 7일
        })
        
        # 2. 긴급 손실 트리거
        triggers.append({
            'trigger_id': f'emergency_{trade_id}',
            'trigger_type': 'position',
            'condition_type': 'emergency',
            'price': emergency_price,
            'direction': direction,
            'threshold_percent': -8.0,  # -8% 긴급
            'action': 'emergency_analyze',
            'urgency': 'critical',
            'expires_hours': 168
        })
        
        # 3. 이익 실현 트리거
        if direction == "LONG":
            tp_price = entry_price + (atr * 3)  # 3 ATR 이익
        else:
            tp_price = entry_price - (atr * 3)
            
        triggers.append({
            'trigger_id': f'tp_{trade_id}',
            'trigger_type': 'position',
            'condition_type': 'profit',
            'price': tp_price,
            'direction': direction,
            'threshold_percent': 6.0,  # +6% 이익
            'action': 'analyze',
            'urgency': 'medium',
            'expires_hours': 168
        })
        
        # 4. 시간 기반 트리거 (장기 정체)
        triggers.append({
            'trigger_id': f'time_{trade_id}',
            'trigger_type': 'position',
            'condition_type': 'time',
            'hours_in_position': 24,  # 24시간
            'min_movement_percent': 1.0,  # 1% 미만 움직임
            'action': 'analyze',
            'urgency': 'low',
            'expires_hours': 48  # 2일 후 만료
        })
        
        # 5. 변동성 급증 트리거
        current_volatility = market_data.get('volatility')
        if current_volatility is not None and current_volatility > 0:
            triggers.append({
                'trigger_id': f'volatility_{trade_id}',
                'trigger_type': 'position',
                'condition_type': 'volatility_spike',
                'baseline_volatility': current_volatility,
                'threshold_multiplier': 2.0,  # 2배 증가
                'action': 'analyze',
                'urgency': 'high',
                'expires_hours': 72  # 3일
            })
        
        # 트리거 매니저에 추가
        self.trigger_manager.add_position_triggers(triggers)
        
        self.logger.info(
            f"📍 {len(triggers)}개 포지션 트리거 생성 완료: "
            f"MDD@{stop_price:.2f}, TP@{tp_price:.2f}, 시간/변동성 트리거"
        )
        
        return triggers