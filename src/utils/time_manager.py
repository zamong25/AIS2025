"""
델파이 트레이딩 시스템 - 시간 관리 유틸리티
전체 시스템의 시간 동기화 및 관리
"""

from datetime import datetime, timezone, timedelta

def get_current_time():
    """Get current UTC time"""
    return datetime.now(timezone.utc)


class TimeManager:
    """전체 시스템의 시간 관리를 담당하는 클래스"""
    
    KST = timezone(timedelta(hours=9))
    
    @staticmethod
    def get_execution_time():
        """현재 실행 시점의 UTC/KST 시간을 반환"""
        utc_now = datetime.now(timezone.utc)
        kst_now = utc_now.astimezone(TimeManager.KST)
        
        return {
            'utc_iso': utc_now.isoformat(timespec="seconds") + "Z",
            'utc_timestamp': utc_now,
            'kst_display': kst_now.strftime("%Y-%m-%d %H:%M:%S KST"),
            'kst_timestamp': kst_now
        }
    
    @staticmethod
    def get_system_start_time():
        """시스템 시작 시점의 시간을 저장하고 반환"""
        if not hasattr(TimeManager, '_start_time'):
            TimeManager._start_time = TimeManager.get_execution_time()
        return TimeManager._start_time
    
    @staticmethod
    def utc_now():
        """현재 UTC 시간 반환"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def kst_now():
        """현재 KST 시간 반환"""
        return datetime.now(TimeManager.KST)
    
    @staticmethod
    def format_utc_iso(dt: datetime = None):
        """UTC ISO 형식으로 포맷"""
        if dt is None:
            dt = TimeManager.utc_now()
        return dt.isoformat(timespec="seconds") + "Z"
    
    @staticmethod
    def format_kst_display(dt: datetime = None):
        """KST 표시 형식으로 포맷"""
        if dt is None:
            dt = TimeManager.kst_now()
        elif dt.tzinfo != TimeManager.KST:
            dt = dt.astimezone(TimeManager.KST)
        return dt.strftime("%Y-%m-%d %H:%M:%S KST")