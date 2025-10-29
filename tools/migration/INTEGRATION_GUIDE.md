# 새 시스템 통합 가이드

## 개요
이 문서는 기존 시스템과 새 클린 아키텍처 시스템을 통합하는 방법을 설명합니다.

## 현재 상태
- **기존 시스템**: src/ 폴더에 있는 모놀리식 구조
- **새 시스템**: domain/, application/, infrastructure/ 계층으로 분리된 클린 아키텍처
- **브릿지**: bridge.py를 통한 점진적 전환 지원

## 통합된 컴포넌트
### 1. Position 도메인 (완료)
- `domain/trading/models/position.py`: 포지션 도메인 모델
- `domain/trading/rules/position_rules.py`: 포지션 비즈니스 규칙
- `application/services/position_service.py`: 포지션 관리 서비스
- `infrastructure/exchanges/binance/binance_adapter.py`: 바이낸스 어댑터
- `infrastructure/persistence/database/repositories/position_repository.py`: DB 리포지토리

## main.py와 통합하기

### 1. 초기화 코드 수정
```python
# main.py의 초기화 부분에 추가
from bridge import bridge

# 바이낸스 클라이언트 초기화 후
bridge.set_binance_client(client)

# 새 시스템 사용하려면 (선택적)
# bridge.use_new_system = True
```

### 2. PositionStateManager 대체
기존 코드:
```python
from src.trading.position_state_manager import position_state_manager

# 사용
position = position_state_manager.get_current_position("SOLUSDT")
```

새 코드:
```python
from bridge import bridge

# 브릿지를 통해 가져오기 (자동으로 적절한 시스템 선택)
position_manager = bridge.get_position_manager()
position = position_manager.get_current_position("SOLUSDT")
```

### 3. 점진적 전환 전략

#### Phase 1: 읽기 전용 테스트 (현재)
```python
# 새 시스템으로 읽기만 테스트
if DEBUG_MODE:
    bridge.use_new_system = True
    new_position = bridge.get_position_manager().get_current_position("SOLUSDT")
    bridge.use_new_system = False  # 다시 기존 시스템으로
    
    # 결과 비교
    legacy_position = position_state_manager.get_current_position("SOLUSDT")
    compare_results(new_position, legacy_position)
```

#### Phase 2: A/B 테스트
```python
# 특정 조건에서만 새 시스템 사용
if should_use_new_system():  # 예: 10% 트래픽
    bridge.use_new_system = True
```

#### Phase 3: 전체 전환
```python
# 설정 파일에서 제어
USE_NEW_SYSTEM = config.get('use_new_system', False)
bridge.use_new_system = USE_NEW_SYSTEM
```

## 새 시스템의 장점

### 1. 테스트 가능성
```python
# 단위 테스트가 쉬워짐
def test_position_size_calculation():
    service = PositionService(
        exchange_client=MockExchange(),
        position_repository=MockRepository()
    )
    
    size, _ = service.calculate_position_size(
        capital=Decimal("1000"),
        capital_percent=Decimal("20"),
        current_price=Decimal("100")
    )
    
    assert size == Decimal("2.0")
```

### 2. 비즈니스 규칙 분리
```python
# 규칙을 쉽게 변경 가능
custom_rules = PositionSizeRules(
    default_capital_percent=Decimal("10"),  # 더 보수적
    max_capital_percent=Decimal("50")       # 제한 완화
)

service = PositionService(size_rules=custom_rules)
```

### 3. 의존성 주입
```python
# 다른 거래소로 쉽게 전환
from infrastructure.exchanges.bybit import BybitAdapter

service = PositionService(
    exchange_client=BybitAdapter(bybit_client),
    position_repository=position_repository
)
```

## 디버깅 및 모니터링

### 로그 확인
```python
# 브릿지 로그
INFO:SystemBridge:Using new PositionService  # 새 시스템 사용 중
INFO:SystemBridge:Using legacy position_state_manager  # 기존 시스템 사용 중
```

### 성능 비교
```python
import time

# 기존 시스템
start = time.time()
legacy_result = position_state_manager.get_current_position("SOLUSDT")
legacy_time = time.time() - start

# 새 시스템
bridge.use_new_system = True
start = time.time()
new_result = bridge.get_position_manager().get_current_position("SOLUSDT")
new_time = time.time() - start

print(f"Legacy: {legacy_time:.3f}s, New: {new_time:.3f}s")
```

## 주의사항

1. **데이터 일관성**: 새 시스템과 기존 시스템이 같은 DB를 사용하므로 스키마 변경에 주의
2. **트랜잭션**: 두 시스템이 동시에 쓰기 작업을 하지 않도록 주의
3. **캐싱**: 새 시스템은 캐싱을 사용하지 않으므로 성능 차이 있을 수 있음

## 다음 단계

1. **TradeExecutor 마이그레이션**: 거래 실행 로직을 TradingService로 이동
2. **Agent 시스템 분리**: AI 에이전트를 인프라 계층으로 이동
3. **이벤트 기반 아키텍처**: 도메인 이벤트 도입으로 느슨한 결합

## 롤백 계획

문제 발생 시:
```python
# 즉시 기존 시스템으로 롤백
bridge.use_new_system = False

# 또는 환경 변수로 제어
export USE_NEW_SYSTEM=false
```

---

마이그레이션 관련 질문이나 이슈는 GitHub Issues에 등록해주세요.