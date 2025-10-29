# 델파이 트레이더 개발자 가이드

## 목차
1. [아키텍처 개요](#아키텍처-개요)
2. [개발 환경 설정](#개발-환경-설정)
3. [코드 구조](#코드-구조)
4. [핵심 컴포넌트](#핵심-컴포넌트)
5. [개발 워크플로우](#개발-워크플로우)
6. [테스트 가이드](#테스트-가이드)
7. [디버깅 가이드](#디버깅-가이드)
8. [성능 최적화](#성능-최적화)
9. [배포 가이드](#배포-가이드)

## 아키텍처 개요

델파이 트레이더는 Clean Architecture 원칙을 따르는 계층형 구조입니다.

### 계층 구조
```
┌─────────────────────────────────────────────────────┐
│                 Presentation Layer                   │
│   • CLI Commands (main.py)                          │
│   • Web Dashboard (FastAPI)                         │
│   • API Endpoints                                  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                Application Layer                     │
│   • Services (PositionService, TradingService)      │
│   • Use Cases (Execute Trade, Analyze Market)       │
│   • Event Bus & Task Queue                         │
│   • DTOs & Mappers                                 │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                   Domain Layer                       │
│   • Entities (Position, Trade, Trigger)            │
│   • Value Objects (Price, Quantity)                │
│   • Domain Services                                │
│   • Domain Events                                  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│               Infrastructure Layer                   │
│   • External APIs (Binance, Gemini)                │
│   • Database (SQLite)                              │
│   • Message Queue                                  │
│   • File System                                    │
└─────────────────────────────────────────────────────┘
```

### 의존성 규칙
- 내부 계층은 외부 계층을 알지 못함
- 의존성은 항상 안쪽을 향함
- 인터페이스를 통한 의존성 역전

## 개발 환경 설정

### 1. 필수 도구
```bash
# Python 3.10+
python --version

# Git
git --version

# 가상환경
python -m venv new_venv
.\new_venv\Scripts\activate  # Windows
```

### 2. 개발 도구 설치
```bash
# 개발 의존성 설치
pip install -r requirements-dev.txt

# 도구 포함 내용:
# - pytest: 테스트 프레임워크
# - black: 코드 포맷터
# - flake8: 린터
# - mypy: 타입 체커
# - coverage: 커버리지 측정
```

### 3. IDE 설정 (VS Code)
```json
// .vscode/settings.json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "editor.formatOnSave": true
}
```

## 코드 구조

### Domain Layer (`domain/`)
```
domain/
├── trading/
│   ├── models/
│   │   ├── position.py      # Position 엔티티
│   │   ├── trade.py         # Trade 엔티티
│   │   └── trigger.py       # Trigger 엔티티
│   ├── value_objects/
│   │   ├── price.py         # Price VO
│   │   └── quantity.py      # Quantity VO
│   └── services/
│       └── risk_calculator.py
```

### Application Layer (`application/`)
```
application/
├── services/
│   ├── position_service.py  # 포지션 관리
│   ├── trading_service.py   # 거래 실행
│   └── trigger_service.py   # 트리거 관리
├── events/
│   ├── event_bus.py        # 이벤트 버스
│   └── handlers/           # 이벤트 핸들러
├── queues/
│   └── task_queue.py       # 작업 큐
└── interfaces/
    └── exchange.py         # 거래소 인터페이스
```

### Infrastructure Layer (`infrastructure/`)
```
infrastructure/
├── exchanges/
│   └── binance_adapter.py  # 바이낸스 구현
├── ai/
│   └── gemini_client.py    # Gemini AI 클라이언트
├── persistence/
│   └── sqlite_adapter.py   # SQLite 어댑터
└── notifications/
    └── discord_adapter.py  # Discord 알림
```

## 핵심 컴포넌트

### 1. Position 도메인 모델
```python
# domain/trading/models/position.py
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class PositionDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class Position:
    symbol: str
    direction: PositionDirection
    entry_price: Decimal
    quantity: Decimal
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """손익 계산"""
        if self.direction == PositionDirection.LONG:
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity
```

### 2. Position Service
```python
# application/services/position_service.py
class PositionService:
    def __init__(self, exchange: IExchangeClient, db: IDatabase):
        self.exchange = exchange
        self.db = db
    
    async def open_position(self, request: OpenPositionRequest) -> Position:
        """포지션 오픈"""
        # 1. 검증
        self._validate_request(request)
        
        # 2. 거래소에 주문
        order = await self.exchange.place_order(...)
        
        # 3. 포지션 생성
        position = Position(...)
        
        # 4. DB 저장
        await self.db.save_position(position)
        
        return position
```

### 3. 이벤트 버스
```python
# application/events/event_bus.py
class EventBus:
    async def publish(self, event: Event) -> None:
        """이벤트 발행"""
        handlers = self._handlers.get(event.event_type, [])
        await asyncio.gather(*[h(event) for h in handlers])
```

## 개발 워크플로우

### 1. 새 기능 개발
```bash
# 1. 새 브랜치 생성
git checkout -b feature/new-indicator

# 2. 도메인 모델 작성
# domain/trading/indicators/rsi.py

# 3. 서비스 구현
# application/services/indicator_service.py

# 4. 테스트 작성
# tests/unit/domain/indicators/test_rsi.py

# 5. 통합
# infrastructure/adapters/indicator_adapter.py
```

### 2. 코드 스타일
```bash
# 포맷팅
black .

# 린팅
flake8 .

# 타입 체크
mypy .
```

### 3. 커밋 규칙
```bash
# 형식: <type>: <subject>
# 예시:
git commit -m "feat: RSI 지표 추가"
git commit -m "fix: 포지션 계산 버그 수정"
git commit -m "docs: API 문서 업데이트"
git commit -m "test: RSI 테스트 추가"
```

## 테스트 가이드

### 1. 단위 테스트
```python
# tests/unit/domain/test_position.py
import pytest
from decimal import Decimal
from domain.trading.models import Position, PositionDirection

class TestPosition:
    def test_calculate_pnl_long(self):
        position = Position(
            symbol="SOLUSDT",
            direction=PositionDirection.LONG,
            entry_price=Decimal("100"),
            quantity=Decimal("10")
        )
        
        pnl = position.calculate_pnl(Decimal("110"))
        assert pnl == Decimal("100")
```

### 2. 통합 테스트
```python
# tests/integration/test_trading_flow.py
@pytest.mark.asyncio
async def test_complete_trading_flow():
    # Given: 테스트 환경 설정
    service = TradingService(mock_exchange, mock_db)
    
    # When: 거래 실행
    result = await service.execute_trade(...)
    
    # Then: 결과 검증
    assert result.status == "SUCCESS"
```

### 3. 테스트 실행
```bash
# 전체 테스트
pytest

# 특정 테스트
pytest tests/unit/domain/test_position.py

# 커버리지
pytest --cov=domain --cov=application

# 상세 리포트
pytest --cov --cov-report=html
```

## 디버깅 가이드

### 1. 로깅 설정
```python
# utils/logging_config.py
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
```

### 2. 디버그 모드
```bash
# 환경변수 설정
export DEBUG=true
export LOG_LEVEL=DEBUG

# 실행
python main.py --debug
```

### 3. 일반적인 문제 해결

#### 모듈 임포트 에러
```bash
# PYTHONPATH 확인
echo $PYTHONPATH

# 설정
export PYTHONPATH="${PYTHONPATH}:/path/to/delphi-trader"
```

#### 메모리 누수
```python
# 메모리 프로파일링
from memory_profiler import profile

@profile
def memory_intensive_function():
    # 코드
```

## 성능 최적화

### 1. 프로파일링
```bash
# cProfile 사용
python -m cProfile -o profile.stats main.py

# 결과 분석
python -m pstats profile.stats
```

### 2. 최적화 전략
- 캐싱 활용 (functools.lru_cache)
- 비동기 처리 (asyncio)
- 데이터베이스 쿼리 최적화
- 불필요한 API 호출 제거

### 3. 성능 모니터링
```python
# utils/performance.py
import time
from functools import wraps

def measure_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper
```

## 배포 가이드

### 1. 환경 준비
```bash
# 프로덕션 환경변수
cp .env.example .env.production
# 편집기로 .env.production 수정
```

### 2. 의존성 고정
```bash
# requirements.txt 생성
pip freeze > requirements.txt
```

### 3. 배포 스크립트
```bash
#!/bin/bash
# deploy.sh

# 1. 코드 업데이트
git pull origin main

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 마이그레이션
python -m alembic upgrade head

# 4. 테스트
pytest tests/

# 5. 서비스 재시작
systemctl restart delphi-trader
```

### 4. 모니터링
```bash
# 로그 확인
tail -f logs/delphi.log

# 시스템 상태
systemctl status delphi-trader

# 리소스 사용량
htop
```

## 추가 리소스

### 문서
- [API 레퍼런스](./API_REFERENCE.md)
- [아키텍처 상세](./ARCHITECTURE.md)
- [트러블슈팅](./TROUBLESHOOTING.md)

### 도구
- [Postman Collection](./postman/)
- [Docker Compose](./docker/)
- [CI/CD 설정](./.github/workflows/)

---

**질문이나 기여는 GitHub Issues를 통해 제출해주세요.**