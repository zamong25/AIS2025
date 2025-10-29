# 델파이 트레이더 성능 최적화 계획

## 현황 분석

새 시스템이 레거시 대비 24% 느린 주요 원인:

1. **데이터 타입 오버헤드**
   - Decimal 사용: float 대비 344.7% 느림
   - Dataclass: Dictionary 대비 203.6% 느림

2. **Import 오버헤드**
   - 복잡한 의존성 체인으로 인한 지연
   - Position 서비스 import에 255.3ms 소요

3. **객체 생성 비용**
   - 불변 객체 패턴으로 인한 빈번한 재생성
   - 타입 변환 오버헤드

## 최적화 전략

### Phase 1: Quick Wins (10-15% 개선)

#### 1.1 Float 사용으로 전환
```python
# 기존 (Decimal)
entry_price: Decimal = Decimal("100.5")
quantity: Decimal = Decimal("10")

# 최적화 (float)
entry_price: float = 100.5
quantity: float = 10.0
```

**구현 방법:**
- 환경변수로 선택 가능: `USE_OPTIMIZED_MODELS=true`
- 정밀도가 중요한 금융 계산은 마지막 단계에서만 Decimal 사용

#### 1.2 __slots__ 사용
```python
@dataclass
class PositionOptimized:
    __slots__ = ('symbol', 'direction', 'entry_price', ...)
```

**효과:**
- 메모리 사용량 30-40% 감소
- 속성 접근 속도 향상

#### 1.3 불필요한 변환 제거
```python
# 기존
def __post_init__(self):
    self.entry_price = Decimal(str(self.entry_price))  # 불필요한 변환

# 최적화
def __post_init__(self):
    # 검증만 수행
    if self.quantity <= 0:
        raise ValueError(f"Invalid quantity: {self.quantity}")
```

### Phase 2: 캐싱 전략 (5-8% 개선)

#### 2.1 계산값 캐싱
```python
class PositionOptimized:
    _exposure_cache: Optional[float] = None
    
    @property
    def exposure(self) -> float:
        if self._exposure_cache is None:
            self._exposure_cache = self.entry_price * self.quantity * self.leverage
        return self._exposure_cache
```

#### 2.2 서비스 레벨 캐싱
```python
from functools import lru_cache

class PositionService:
    @lru_cache(maxsize=128)
    def calculate_portfolio_risk(self, positions_hash):
        # 계산 집약적인 작업
        pass
```

### Phase 3: 구조적 최적화 (5-10% 개선)

#### 3.1 지연 로딩
```python
class Bridge:
    def __init__(self):
        self._position_service = None  # 지연 초기화
    
    def get_position_manager(self):
        if not self._position_service:
            # 필요할 때만 로드
            from application.services.position_service import PositionService
            self._position_service = PositionService(...)
        return self._position_service
```

#### 3.2 객체 풀링
```python
class PositionPool:
    def __init__(self, size=100):
        self._pool = []
        self._size = size
    
    def acquire(self, **kwargs):
        if self._pool:
            position = self._pool.pop()
            position.update(**kwargs)
            return position
        return Position(**kwargs)
    
    def release(self, position):
        if len(self._pool) < self._size:
            self._pool.append(position)
```

## 구현 순서

### 1단계 (즉시)
1. ✅ `position_optimized.py` 생성
2. [ ] 환경변수 기반 모델 선택 로직 추가
3. [ ] 기존 테스트 통과 확인

### 2단계 (1일)
1. [ ] 캐싱 메커니즘 구현
2. [ ] 서비스 레이어 최적화
3. [ ] 성능 벤치마크 실행

### 3단계 (2-3일)
1. [ ] 지연 로딩 패턴 적용
2. [ ] 객체 풀링 구현
3. [ ] 전체 통합 테스트

## 예상 결과

- **전체 성능 향상**: 20-33%
- **메모리 사용량 감소**: 30-40%
- **초기화 시간 단축**: 50-80%
- **레거시 대비 성능 차이**: 24% → 10% 이내

## 주의사항

1. **정밀도 보장**
   - 금융 계산의 정확성 유지
   - 중요 계산은 Decimal 유지
   
2. **호환성 유지**
   - 기존 인터페이스 변경 없음
   - 환경변수로 선택 가능

3. **점진적 적용**
   - 각 단계별 테스트
   - 롤백 가능한 구조

## 모니터링

```python
# 성능 모니터링 데코레이터
def performance_monitor(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        if duration > 0.1:  # 100ms 이상
            logger.warning(f"{func.__name__} took {duration:.3f}s")
        
        return result
    return wrapper
```

## 다음 단계

1. Phase 1 구현 및 테스트
2. 성능 벤치마크 결과 확인
3. Phase 2-3 진행 여부 결정