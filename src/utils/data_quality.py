"""
델파이 트레이딩 시스템 - 데이터 품질 검증 모듈
API 실패시 0값 대체 문제를 해결하고 데이터 신뢰도를 관리
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

@dataclass
class DataQuality:
    """데이터 품질 정보"""
    value: Any
    reliable: bool
    confidence: float  # 0.0 ~ 1.0
    source: str
    timestamp: str
    error_message: Optional[str] = None

@dataclass
class QualityReport:
    """전체 데이터 품질 보고서"""
    overall_confidence: float  # 전체 신뢰도
    reliable_data_count: int
    total_data_count: int
    critical_failures: List[str]
    warnings: List[str]
    data_quality_map: Dict[str, DataQuality]

class DataQualityManager:
    """데이터 품질 관리자"""
    
    # 데이터별 중요도 (critical/high/medium/low)
    DATA_IMPORTANCE = {
        'open_interest': 'high',
        'oi_delta': 'medium', 
        'funding_rate': 'high',
        'btc_dominance': 'medium',
        'btc_correlation': 'medium',
        'price': 'critical',
        'volume': 'critical',
        'ema_20': 'high',
        'ema_50': 'high',
        'rsi': 'high',
        'atr': 'medium',
        'obv': 'medium'
    }
    
    # 중요도별 최소 신뢰도 요구사항
    MIN_CONFIDENCE_THRESHOLDS = {
        'critical': 0.95,  # 95% 이상
        'high': 0.8,       # 80% 이상
        'medium': 0.6,     # 60% 이상
        'low': 0.4         # 40% 이상
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_quality_data(self, key: str, value: Any, success: bool, 
                          error_msg: str = None, source: str = "binance") -> DataQuality:
        """품질 정보가 포함된 데이터 생성"""
        
        # 중요도 확인
        importance = self.DATA_IMPORTANCE.get(key, 'low')
        
        if success:
            # 성공적으로 수집된 데이터
            confidence = 0.95 if importance == 'critical' else 0.9
            return DataQuality(
                value=value,
                reliable=True,
                confidence=confidence,
                source=source,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_message=None
            )
        else:
            # 실패한 데이터 - 중요도에 따라 처리
            if importance == 'critical':
                # Critical 데이터는 실패시 None 반환 (분석 중단)
                return DataQuality(
                    value=None,
                    reliable=False,
                    confidence=0.0,
                    source=source,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_message=error_msg
                )
            else:
                # Critical이 아닌 데이터는 기본값 사용하되 신뢰도 표시
                default_value = self._get_safe_default(key)
                return DataQuality(
                    value=default_value,
                    reliable=False,
                    confidence=0.1,  # 매우 낮은 신뢰도
                    source=f"{source}_default",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_message=error_msg
                )
    
    def _get_safe_default(self, key: str) -> Any:
        """안전한 기본값 반환 (완전히 임의값 대신 의미있는 기본값)"""
        
        # 비율/퍼센트 값들
        if key in ['oi_delta', 'btc_correlation']:
            return 0.0  # 변화 없음을 의미
        
        # 도미넌스
        elif key == 'btc_dominance':
            return 50.0  # 비트코인 도미넌스 평균값
        
        # 펀딩비
        elif key == 'funding_rate':
            return 0.0001  # 일반적인 펀딩비
        
        # 기술적 지표들
        elif key == 'rsi':
            return 50.0  # 중립 RSI
        
        elif key in ['ema_20', 'ema_50', 'price']:
            return None  # Critical 데이터는 기본값 없음
        
        else:
            return 0.0
    
    def validate_data_collection(self, data_map: Dict[str, DataQuality]) -> QualityReport:
        """데이터 수집 결과 종합 검증"""
        
        reliable_count = sum(1 for dq in data_map.values() if dq.reliable)
        total_count = len(data_map)
        
        # 전체 신뢰도 계산 (중요도 가중 평균)
        total_weight = 0
        weighted_confidence = 0
        
        for key, dq in data_map.items():
            importance = self.DATA_IMPORTANCE.get(key, 'low')
            weight = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}[importance]
            
            total_weight += weight
            weighted_confidence += dq.confidence * weight
        
        overall_confidence = weighted_confidence / total_weight if total_weight > 0 else 0
        
        # Critical 실패 확인
        critical_failures = []
        warnings = []
        
        for key, dq in data_map.items():
            importance = self.DATA_IMPORTANCE.get(key, 'low')
            min_confidence = self.MIN_CONFIDENCE_THRESHOLDS[importance]
            
            if dq.confidence < min_confidence:
                if importance == 'critical':
                    critical_failures.append(f"{key}: {dq.error_message or 'Unknown error'}")
                else:
                    warnings.append(f"{key}: 낮은 신뢰도 ({dq.confidence:.2f})")
        
        return QualityReport(
            overall_confidence=overall_confidence,
            reliable_data_count=reliable_count,
            total_data_count=total_count,
            critical_failures=critical_failures,
            warnings=warnings,
            data_quality_map=data_map
        )
    
    def should_proceed_with_analysis(self, quality_report: QualityReport) -> bool:
        """분석을 계속 진행해도 되는지 판단"""
        
        # Critical 실패가 있으면 분석 중단
        if quality_report.critical_failures:
            self.logger.error(f"Critical 데이터 실패: {quality_report.critical_failures}")
            return False
        
        # 전체 신뢰도가 너무 낮으면 분석 중단
        if quality_report.overall_confidence < 0.5:
            self.logger.warning(f"전체 데이터 신뢰도 너무 낮음: {quality_report.overall_confidence:.2f}")
            return False
        
        return True
    
    def extract_values_for_analysis(self, data_map: Dict[str, DataQuality], 
                                  include_unreliable: bool = False) -> Dict[str, Any]:
        """분석용 데이터 값 추출 (신뢰도 정보 제거)"""
        
        result = {}
        for key, dq in data_map.items():
            if dq.reliable or include_unreliable:
                if dq.value is not None:
                    result[key] = dq.value
        
        return result
    
    def generate_quality_summary(self, quality_report: QualityReport) -> str:
        """데이터 품질 요약 생성"""
        
        summary = f"""
📊 데이터 품질 보고서
전체 신뢰도: {quality_report.overall_confidence:.2%}
신뢰할 수 있는 데이터: {quality_report.reliable_data_count}/{quality_report.total_data_count}

"""
        
        if quality_report.critical_failures:
            summary += "🚨 Critical 실패:\n"
            for failure in quality_report.critical_failures:
                summary += f"  • {failure}\n"
            summary += "\n"
        
        if quality_report.warnings:
            summary += "⚠️ 경고사항:\n"
            for warning in quality_report.warnings:
                summary += f"  • {warning}\n"
            summary += "\n"
        
        # 데이터별 상세 정보
        summary += "📋 데이터별 상세 정보:\n"
        for key, dq in quality_report.data_quality_map.items():
            status = "✅" if dq.reliable else "❌"
            summary += f"  {status} {key}: {dq.confidence:.2%} ({dq.source})\n"
        
        return summary


# 전역 데이터 품질 관리자 인스턴스
data_quality_manager = DataQualityManager()