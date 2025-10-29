"""
트리거 관리 시스템
HOLD 결정 시 설정된 가격 트리거를 관리하고 모니터링
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

class TriggerManager:
    def __init__(self, trigger_file: str = "data/triggers.json"):
        self.trigger_file = trigger_file
        self.logger = logging.getLogger(__name__)
        self._ensure_trigger_file()
    
    def _ensure_trigger_file(self):
        """트리거 파일이 없으면 생성"""
        # 빈 경로나 잘못된 경로 처리
        if not self.trigger_file or self.trigger_file.strip() == "":
            self.trigger_file = "data/triggers.json"
            
        trigger_dir = os.path.dirname(self.trigger_file)
        if trigger_dir:  # 디렉토리가 있는 경우만
            os.makedirs(trigger_dir, exist_ok=True)
            
        if not os.path.exists(self.trigger_file):
            with open(self.trigger_file, 'w') as f:
                json.dump({"active_triggers": []}, f)
    
    def load_triggers(self) -> List[Dict]:
        """활성 트리거 로드"""
        try:
            with open(self.trigger_file, 'r') as f:
                data = json.load(f)
                return data.get("active_triggers", [])
        except Exception as e:
            self.logger.error(f"트리거 로드 실패: {e}")
            return []
    
    def save_triggers(self, triggers: List[Dict]):
        """트리거 저장"""
        try:
            with open(self.trigger_file, 'w') as f:
                json.dump({"active_triggers": triggers}, f, indent=2)
        except Exception as e:
            self.logger.error(f"트리거 저장 실패: {e}")
    
    def add_triggers(self, new_triggers: List[Dict]):
        """새 트리거 추가 (기존 트리거 모두 삭제)"""
        # 포지션 진입 시 기존 트리거 모두 제거
        self.clear_all_triggers()
        
        # 새 트리거 추가
        for trigger in new_triggers:
            trigger['created_at'] = datetime.now().isoformat()
            trigger['expires_at'] = (
                datetime.now() + timedelta(hours=trigger['expires_hours'])
            ).isoformat()
        
        self.save_triggers(new_triggers)
        self.logger.info(f"{len(new_triggers)}개 트리거 추가됨")
    
    def clear_all_triggers(self):
        """모든 트리거 삭제"""
        self.save_triggers([])
        self.logger.info("모든 트리거 삭제됨")
    
    def clear_hold_triggers(self):
        """HOLD 트리거만 삭제"""
        triggers = self.load_triggers()
        position_triggers = [t for t in triggers if t.get('trigger_type') == 'position']
        self.save_triggers(position_triggers)
        self.logger.info(f"HOLD 트리거 삭제, {len(position_triggers)}개 포지션 트리거 유지")
    
    def clear_position_triggers(self):
        """포지션 트리거만 삭제"""
        triggers = self.load_triggers()
        hold_triggers = [t for t in triggers if t.get('trigger_type') != 'position']
        self.save_triggers(hold_triggers)
        self.logger.info(f"포지션 트리거 삭제, {len(hold_triggers)}개 HOLD 트리거 유지")
    
    def add_position_triggers(self, new_triggers: List[Dict]):
        """포지션 트리거 추가 (기존 HOLD 트리거 유지)"""
        triggers = self.load_triggers()
        
        # 포지션 트리거에 필수 필드 추가
        for trigger in new_triggers:
            trigger['trigger_type'] = 'position'
            trigger['created_at'] = datetime.now().isoformat()
            if 'expires_hours' in trigger:
                trigger['expires_at'] = (
                    datetime.now() + timedelta(hours=trigger['expires_hours'])
                ).isoformat()
        
        triggers.extend(new_triggers)
        self.save_triggers(triggers)
        self.logger.info(f"{len(new_triggers)}개 포지션 트리거 추가됨")
    
    def check_triggers(self, current_price: float) -> Optional[Dict]:
        """현재 가격으로 트리거 체크"""
        triggers = self.load_triggers()
        now = datetime.now()
        
        # 만료된 트리거 제거
        active_triggers = []
        triggered = None
        
        for trigger in triggers:
            expires_at = datetime.fromisoformat(trigger['expires_at'])
            
            # 만료 체크
            if now > expires_at:
                self.logger.info(f"트리거 만료: {trigger['trigger_id']}")
                continue
            
            # 가격 도달 체크
            if self._is_triggered(trigger, current_price):
                self.logger.info(f"트리거 발동! {trigger['trigger_id']} @ {current_price}")
                triggered = trigger
                # 트리거 발동 시 모든 트리거 제거
                self.clear_all_triggers()
                break
            
            active_triggers.append(trigger)
        
        # 트리거되지 않은 것들만 저장
        if not triggered:
            self.save_triggers(active_triggers)
        
        return triggered
    
    def _is_triggered(self, trigger: Dict, current_price: float) -> bool:
        """트리거 조건 확인"""
        trigger_price = trigger['price']
        direction = trigger['direction']
        
        # 가격 허용 오차 (0.1%)
        tolerance = trigger_price * 0.001
        
        if direction == "LONG":
            # LONG: 현재가가 트리거가 이하로 떨어졌을 때
            return current_price <= trigger_price + tolerance
        else:  # SHORT
            # SHORT: 현재가가 트리거가 이상으로 올라갔을 때
            return current_price >= trigger_price - tolerance
    
    def update_trigger_confidence(self, trigger_id: str, new_confidence: int):
        """트리거 신뢰도 업데이트"""
        triggers = self.load_triggers()
        
        for trigger in triggers:
            if trigger['trigger_id'] == trigger_id:
                trigger['confidence'] = new_confidence
                trigger['updated_at'] = datetime.now().isoformat()
                break
        
        self.save_triggers(triggers)
    
    def get_active_triggers_summary(self) -> str:
        """활성 트리거 요약"""
        triggers = self.load_triggers()
        
        if not triggers:
            return "활성 트리거 없음"
        
        summary = f"활성 트리거 {len(triggers)}개:\n"
        for trigger in triggers:
            expires_in = (
                datetime.fromisoformat(trigger['expires_at']) - datetime.now()
            ).total_seconds() / 3600
            
            summary += (
                f"- {trigger['direction']} @ ${trigger['price']:.2f} "
                f"(신뢰도: {trigger['confidence']}%, "
                f"만료: {expires_in:.1f}시간 후)\n"
            )
        
        return summary.strip()
    
    # Phase 2: 트리거 조건 확장
    def add_volatility_trigger(self, current_volatility: float, threshold: float = 0.05):
        """변동성 급증 시 재분석 트리거 추가"""
        trigger = {
            'trigger_id': f'volatility_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'type': 'volatility_spike',
            'threshold': threshold,
            'baseline_volatility': current_volatility,
            'rationale': f'변동성이 {threshold*100}% 이상 증가 시 재분석',
            'created_at': datetime.now().isoformat(),
            'expires_hours': 24,
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        triggers = self.load_triggers()
        triggers.append(trigger)
        self.save_triggers(triggers)
        
        self.logger.info(f"변동성 트리거 추가: 기준 {current_volatility:.3f}, 임계값 {threshold*100}%")
        return trigger
    
    def add_volume_anomaly_trigger(self, average_volume: float, volume_multiplier: float = 3.0):
        """거래량 이상 감지 트리거 추가"""
        trigger = {
            'trigger_id': f'volume_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'type': 'volume_anomaly',
            'threshold': volume_multiplier,
            'baseline_volume': average_volume,
            'rationale': f'거래량이 평균의 {volume_multiplier}배 이상 시 재분석',
            'created_at': datetime.now().isoformat(),
            'expires_hours': 12,
            'expires_at': (datetime.now() + timedelta(hours=12)).isoformat()
        }
        
        triggers = self.load_triggers()
        triggers.append(trigger)
        self.save_triggers(triggers)
        
        self.logger.info(f"거래량 트리거 추가: 기준 {average_volume:.0f}, 배수 {volume_multiplier}x")
        return trigger
    
    def check_extended_triggers(self, current_price: float, current_volatility: float = None, 
                               current_volume: float = None) -> Optional[Dict]:
        """확장된 트리거 체크 (가격, 변동성, 거래량)"""
        # 기존 가격 트리거 체크
        price_trigger = self.check_triggers(current_price)
        if price_trigger:
            return price_trigger
        
        triggers = self.load_triggers()
        now = datetime.now()
        triggered = None
        
        for trigger in triggers:
            expires_at = datetime.fromisoformat(trigger['expires_at'])
            
            # 만료 체크
            if now > expires_at:
                continue
            
            # 변동성 트리거 체크
            if trigger['type'] == 'volatility_spike' and current_volatility:
                baseline = trigger['baseline_volatility']
                threshold = trigger['threshold']
                volatility_change = (current_volatility - baseline) / baseline
                
                if volatility_change >= threshold:
                    self.logger.info(f"변동성 트리거 발동! 변화율: {volatility_change*100:.1f}%")
                    triggered = trigger
                    self.clear_all_triggers()
                    break
            
            # 거래량 트리거 체크
            elif trigger['type'] == 'volume_anomaly' and current_volume:
                baseline = trigger['baseline_volume']
                threshold = trigger['threshold']
                volume_ratio = current_volume / baseline
                
                if volume_ratio >= threshold:
                    self.logger.info(f"거래량 트리거 발동! 배수: {volume_ratio:.1f}x")
                    triggered = trigger
                    self.clear_all_triggers()
                    break
        
        return triggered