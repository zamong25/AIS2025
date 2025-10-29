# 마이그레이션 가이드

## [목표] 목표
기존 시스템을 중단 없이 새 구조로 점진적 마이그레이션

## [순서] 마이그레이션 순서

### Phase 1: 도메인 모델 (현재)
1. Position, Order, Trade 등 핵심 모델 정의
2. 비즈니스 규칙을 순수 함수로 추출
3. 기존 코드에서 도메인 모델 참조 시작

### Phase 2: 인프라 어댑터
1. 바이낸스 API 어댑터 구현
2. DB 리포지토리 패턴 구현
3. 기존 코드를 어댑터 사용하도록 변경

### Phase 3: 애플리케이션 서비스
1. TradingService, AnalysisService 구현
2. 기존 main.py를 서비스 호출로 변경
3. 의존성 주입 도입

### Phase 4: 프레젠테이션
1. 새로운 CLI 구현
2. 스케줄러를 이벤트 기반으로 변경
3. 기존 시스템 제거

## [사용법] 브릿지 사용법

```python
from bridge import bridge

# 기존 시스템 사용 (기본값)
position_manager = bridge.get_position_manager()

# 새 시스템으로 전환 (준비되면)
bridge.use_new_system = True
position_manager = bridge.get_position_manager()
```

## [주의] 주의사항
1. 한 번에 하나의 컴포넌트만 마이그레이션
2. 각 단계마다 충분한 테스트
3. 롤백 가능하도록 구현
4. 기존 데이터와의 호환성 유지
