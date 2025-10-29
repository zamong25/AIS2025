"""
AI 호출 스케줄링 및 중복 방지 시스템
정규 15분 주기와 트리거 호출 간의 충돌을 방지하여 효율적인 AI 리소스 사용
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class SmartScheduler:
    """AI 호출 스케줄링 및 중복 방지"""
    
    def __init__(self, min_interval_minutes: int = 10):
        """
        스케줄러 초기화
        
        Args:
            min_interval_minutes: AI 호출 간 최소 간격 (분)
        """
        self.min_interval = timedelta(minutes=min_interval_minutes)
        self.call_history_file = "data/ai_call_history.json"
        self.logger = logging.getLogger(__name__)
        self._ensure_history_file()
        
        self.logger.info(f"SmartScheduler 초기화: 최소 간격 {min_interval_minutes}분")
        
    def _ensure_history_file(self):
        """히스토리 파일 생성"""
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.call_history_file), exist_ok=True)
            
            # 파일이 없으면 빈 리스트로 초기화
            if not os.path.exists(self.call_history_file):
                with open(self.call_history_file, 'w') as f:
                    json.dump([], f)
                self.logger.info(f"AI 호출 히스토리 파일 생성: {self.call_history_file}")
        except Exception as e:
            self.logger.error(f"히스토리 파일 생성 실패: {e}")
            # 메모리에서만 동작하도록 fallback
            self.call_history_file = None
    
    def should_run_scheduled_analysis(self) -> bool:
        """
        정규 15분 주기 실행 여부 결정
        
        Returns:
            True: 실행 가능
            False: 최소 간격 미충족으로 스킵
        """
        last_call = self._get_last_ai_call()
        
        # 첫 호출인 경우
        if not last_call:
            self.logger.info("첫 AI 호출 - 실행 허용")
            return True
            
        # 마지막 AI 호출 이후 경과 시간
        time_since_last = datetime.now() - last_call['timestamp']
        
        # 최소 간격 체크
        if time_since_last >= self.min_interval:
            self.logger.info(
                f"마지막 호출로부터 {time_since_last.total_seconds()/60:.1f}분 경과 - 실행 허용"
            )
            return True
        else:
            remaining = (self.min_interval - time_since_last).total_seconds() / 60
            self.logger.warning(
                f"마지막 호출로부터 {time_since_last.total_seconds()/60:.1f}분만 경과 - "
                f"{remaining:.1f}분 더 대기 필요"
            )
            return False
        
    def record_ai_call(self, call_type: str = "scheduled", 
                      trigger_info: Dict = None) -> None:
        """
        AI 호출 기록
        
        Args:
            call_type: 호출 타입 ('scheduled', 'trigger', 'emergency')
            trigger_info: 트리거 관련 추가 정보
        """
        try:
            history = self._load_history()
            
            record = {
                'timestamp': datetime.now().isoformat(),
                'type': call_type,
                'trigger_info': trigger_info
            }
            
            history.append(record)
            
            # 최근 100개만 유지 (메모리 관리)
            if len(history) > 100:
                history = history[-100:]
                self.logger.debug("히스토리 100개 초과 - 오래된 기록 삭제")
            
            self._save_history(history)
            
            trigger_id = ""
            if trigger_info and 'trigger' in trigger_info:
                trigger_id = f"(트리거: {trigger_info['trigger'].get('trigger_id', 'unknown')})"
            
            self.logger.info(f"AI 호출 기록: {call_type} {trigger_id}")
            
        except Exception as e:
            self.logger.error(f"AI 호출 기록 실패: {e}")
        
    def get_ai_call_stats(self, hours: int = 24) -> Dict:
        """
        AI 호출 통계
        
        Args:
            hours: 최근 N시간 통계
            
        Returns:
            통계 딕셔너리
        """
        try:
            history = self._load_history()
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            recent_calls = []
            for record in history:
                try:
                    timestamp = datetime.fromisoformat(record['timestamp'])
                    if timestamp > cutoff_time:
                        record_copy = record.copy()
                        record_copy['timestamp'] = timestamp
                        recent_calls.append(record_copy)
                except Exception as e:
                    self.logger.debug(f"통계 처리 중 오류 무시: {e}")
                    continue
            
            stats = {
                'total_calls': len(recent_calls),
                'scheduled_calls': len([h for h in recent_calls if h['type'] == 'scheduled']),
                'trigger_calls': len([h for h in recent_calls if h['type'] == 'trigger']),
                'emergency_calls': len([h for h in recent_calls if h['type'] == 'emergency']),
                'calls_per_hour': len(recent_calls) / hours if hours > 0 else 0,
                'last_call_time': recent_calls[-1]['timestamp'].isoformat() if recent_calls else None
            }
            
            self.logger.debug(f"최근 {hours}시간 AI 호출 통계: {stats['total_calls']}회")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"AI 호출 통계 조회 실패: {e}")
            return {
                'total_calls': 0,
                'scheduled_calls': 0,
                'trigger_calls': 0,
                'emergency_calls': 0,
                'calls_per_hour': 0,
                'last_call_time': None
            }
        
    def _get_last_ai_call(self) -> Optional[Dict]:
        """
        마지막 AI 호출 정보
        
        Returns:
            마지막 호출 정보 (timestamp는 datetime 객체로 변환됨)
        """
        try:
            history = self._load_history()
            if not history:
                return None
                
            last_record = history[-1].copy()
            last_record['timestamp'] = datetime.fromisoformat(last_record['timestamp'])
            return last_record
            
        except Exception as e:
            self.logger.error(f"마지막 AI 호출 조회 실패: {e}")
            return None
        
    def _load_history(self) -> List[Dict]:
        """
        히스토리 로드
        
        Returns:
            호출 히스토리 리스트
        """
        if not self.call_history_file:
            return []
            
        try:
            with open(self.call_history_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.debug("히스토리 파일 없음 - 빈 리스트 반환")
            return []
        except json.JSONDecodeError:
            self.logger.error("히스토리 파일 손상 - 초기화")
            return []
        except Exception as e:
            self.logger.error(f"히스토리 로드 실패: {e}")
            return []
            
    def _save_history(self, history: List[Dict]) -> None:
        """
        히스토리 저장
        
        Args:
            history: 저장할 히스토리 리스트
        """
        if not self.call_history_file:
            return
            
        try:
            with open(self.call_history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"히스토리 저장 실패: {e}")
            
    def get_cooldown_status(self) -> Dict:
        """
        현재 쿨다운 상태 조회
        
        Returns:
            쿨다운 상태 정보
        """
        last_call = self._get_last_ai_call()
        
        if not last_call:
            return {
                'in_cooldown': False,
                'can_call': True,
                'last_call_ago': None,
                'cooldown_remaining': 0
            }
            
        time_since_last = datetime.now() - last_call['timestamp']
        in_cooldown = time_since_last < self.min_interval
        
        return {
            'in_cooldown': in_cooldown,
            'can_call': not in_cooldown,
            'last_call_ago': time_since_last.total_seconds() / 60,
            'cooldown_remaining': max(0, (self.min_interval - time_since_last).total_seconds() / 60) if in_cooldown else 0
        }