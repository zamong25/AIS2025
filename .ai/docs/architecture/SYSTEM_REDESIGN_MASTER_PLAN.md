# 델파이 트레이더 시스템 재설계 마스터 플랜
> 작성일: 2024-01-20  
> 목적: AI 주도 개발을 위한 완전한 시스템 재설계  
> 철학: "의도를 코드화하고, 복잡성을 단순화하라"

## 📋 목차
1. [핵심 설계 원칙](#핵심-설계-원칙)
2. [새로운 프로젝트 구조](#새로운-프로젝트-구조)
3. [AI 연속성 시스템](#ai-연속성-시스템)
4. [코드 표준 및 규칙](#코드-표준-및-규칙)
5. [마이그레이션 전략](#마이그레이션-전략)
6. [실행 로드맵](#실행-로드맵)

---

## 🎯 핵심 설계 원칙

### 1. 의도 주도 설계 (Intent-Driven Design)
```
의도(자연어) → 명세(구조화) → 구현(코드) → 검증(테스트)
```

### 2. 단일 책임 원칙 (Single Responsibility)
- 한 함수 = 한 가지 일
- 한 파일 = 한 가지 개념
- 한 폴더 = 한 가지 도메인

### 3. AI 우선 문서화 (AI-First Documentation)
- 코드보다 의도가 중요
- 구현보다 설계가 중요
- 방법보다 이유가 중요

### 4. 제로 하드코딩 (Zero Hardcoding)
- 모든 값은 설정 파일에서
- 모든 규칙은 명시적으로
- 모든 의존성은 주입으로

---

## 🏗️ 새로운 프로젝트 구조

```
delphi-trader/
│
├── 🧠 .ai/                          # AI 메타 레이어 (최우선)
│   ├── README.md                    # "5분 안에 모든 것을 이해하기"
│   ├── CURRENT_STATE.yaml           # 현재 상태 (자동 갱신)
│   ├── WORK_LOG.yaml               # 작업 이력 (세션별)
│   ├── intentions/                  # 시스템 의도
│   │   ├── trading/                # 거래 관련 의도
│   │   ├── agents/                 # 에이전트 관련 의도
│   │   └── monitoring/             # 모니터링 관련 의도
│   └── workspace/                   # AI 작업 공간
│       └── .gitignore              # 임시 파일 제외
│
├── 📐 intentions/                   # 비즈니스 의도 (자연어)
│   ├── WHAT_WE_WANT.md             # 시스템이 해야 할 일
│   ├── HOW_IT_WORKS.md             # 작동 방식
│   ├── CONSTRAINTS.md              # 제약 사항
│   └── features/                   # 기능별 의도
│       ├── auto_trading.md         # 자동 거래 의도
│       ├── risk_management.md      # 리스크 관리 의도
│       └── ai_agents.md            # AI 에이전트 의도
│
├── ⚙️ config/                       # 설정 (하드코딩 제로)
│   ├── schema/                     # 설정 스키마 (검증용)
│   ├── base/                       # 기본 설정
│   │   ├── app.yaml               # 애플리케이션
│   │   ├── trading.yaml           # 거래
│   │   ├── agents.yaml            # 에이전트
│   │   └── monitoring.yaml        # 모니터링
│   ├── environments/               # 환경별 설정
│   │   ├── development.yaml       # 개발
│   │   ├── staging.yaml           # 스테이징
│   │   └── production.yaml        # 운영
│   └── secrets/                    # 비밀 설정 (git 제외)
│       └── .gitignore
│
├── 🎯 domain/                       # 핵심 도메인 (순수 Python)
│   ├── trading/                    # 거래 도메인
│   │   ├── models/                # 도메인 모델
│   │   │   ├── position.py        # Position 클래스
│   │   │   ├── order.py           # Order 클래스
│   │   │   └── trade.py           # Trade 클래스
│   │   ├── rules/                 # 비즈니스 규칙
│   │   │   ├── entry_rules.py     # 진입 규칙
│   │   │   ├── exit_rules.py      # 청산 규칙
│   │   │   └── risk_rules.py      # 리스크 규칙
│   │   └── calculations/          # 계산 로직
│   │       ├── pnl.py             # 손익 계산
│   │       ├── position_size.py   # 포지션 크기
│   │       └── risk_metrics.py    # 리스크 지표
│   │
│   └── analysis/                   # 분석 도메인
│       ├── models/
│       ├── indicators/            # 기술적 지표
│       └── scenarios/             # 시나리오 분석
│
├── 🔧 application/                  # 애플리케이션 계층
│   ├── services/                   # 비즈니스 서비스
│   │   ├── trading_service.py     # 거래 서비스
│   │   ├── analysis_service.py    # 분석 서비스
│   │   └── monitoring_service.py  # 모니터링 서비스
│   │
│   ├── workflows/                  # 비즈니스 워크플로우
│   │   ├── trading_workflow.py    # 거래 워크플로우
│   │   └── analysis_workflow.py   # 분석 워크플로우
│   │
│   └── interfaces/                 # 인터페이스 정의
│       ├── i_exchange.py          # 거래소 인터페이스
│       ├── i_agent.py             # AI 에이전트 인터페이스
│       └── i_notifier.py          # 알림 인터페이스
│
├── 🏭 infrastructure/              # 인프라 구현
│   ├── exchanges/                  # 거래소 연동
│   │   └── binance/               # 바이낸스
│   │       ├── client.py
│   │       └── adapter.py         # 인터페이스 구현
│   │
│   ├── agents/                     # AI 에이전트
│   │   ├── base_agent.py          # 기본 에이전트
│   │   ├── chartist/              # 차티스트
│   │   ├── journalist/            # 저널리스트
│   │   ├── quant/                 # 퀀트
│   │   ├── stoic/                 # 스토익
│   │   └── synthesizer/           # 신디사이저
│   │
│   ├── persistence/                # 데이터 영속성
│   │   ├── database/              # 데이터베이스
│   │   │   ├── repositories/      # 리포지토리
│   │   │   └── migrations/        # 마이그레이션
│   │   └── cache/                 # 캐시
│   │
│   └── notifications/              # 알림 시스템
│       └── discord/               # 디스코드
│
├── 🚀 presentation/                # 표현 계층
│   ├── cli/                       # CLI 인터페이스
│   ├── api/                       # REST API
│   └── scheduler/                 # 스케줄러
│
├── 🧪 tests/                       # 테스트 (구조 미러링)
│   ├── unit/                      # 단위 테스트
│   ├── integration/               # 통합 테스트
│   ├── e2e/                       # E2E 테스트
│   └── fixtures/                  # 테스트 데이터
│
├── 📊 monitoring/                  # 모니터링
│   ├── logs/                      # 로그
│   ├── metrics/                   # 메트릭
│   └── alerts/                    # 알림 규칙
│
├── 🛠️ tools/                       # 도구
│   ├── setup/                     # 설치 스크립트
│   ├── migration/                 # 마이그레이션 도구
│   └── analysis/                  # 분석 도구
│
├── 📚 docs/                        # 문서
│   ├── architecture/              # 아키텍처
│   ├── api/                       # API 문서
│   ├── guides/                    # 가이드
│   └── decisions/                 # 아키텍처 결정
│
└── 🗄️ legacy/                      # 기존 코드 (점진적 제거)
    └── src/                       # 현재 src 폴더 이동

```

---

## 🔄 AI 연속성 시스템

### 1. 상태 관리 (.ai/CURRENT_STATE.yaml)
```yaml
system:
  version: "2.0.0"
  phase: "migration"
  health: "operational"

current_work:
  sprint: 1
  focus: "infrastructure_setup"
  progress: 25

active_issues:
  - id: "ISSUE-001"
    type: "bug"
    description: "포지션 캐싱 문제"
    status: "in_progress"
    location: "legacy/src/trading/position_state_manager.py"

completed_today:
  - "프로젝트 구조 생성"
  - "설정 스키마 정의"

next_tasks:
  - priority: "high"
    task: "도메인 모델 구현"
  - priority: "medium"
    task: "리포지토리 패턴 적용"

ai_notes:
  - "하드코딩된 값 300개 발견"
  - "함수 평균 길이 150줄"
```

### 2. 작업 로그 (.ai/WORK_LOG.yaml)
```yaml
sessions:
  - id: "2024-01-20-001"
    start: "14:00"
    end: "17:00"
    tasks_completed:
      - "폴더 구조 생성"
      - "도메인 모델 설계"
    files_created:
      - "domain/trading/models/position.py"
    files_modified:
      - ".ai/CURRENT_STATE.yaml"
    insights:
      - "TradeExecutor가 15개의 책임을 가짐"
```

### 3. Claude.md 개선안
```markdown
# Claude 작업 가이드

## 🎯 작업 시작 전 필수 확인
1. `.ai/CURRENT_STATE.yaml` 읽기
2. `.ai/WORK_LOG.yaml`에서 마지막 세션 확인
3. `intentions/` 폴더에서 관련 의도 확인

## 📝 코딩 규칙
### 함수 작성
- 최대 30줄 (예외: 복잡한 알고리즘은 50줄까지)
- 한 가지 일만 수행
- 명확한 이름 사용

### 예시
```python
# ❌ 나쁜 예
def process_trade(data):
    # 검증도 하고
    # 계산도 하고
    # DB 저장도 하고
    # 알림도 보내고
    # ... 200줄

# ✅ 좋은 예
def validate_trade_data(data: Dict) -> bool:
    """거래 데이터 검증"""
    return all([
        data.get('symbol'),
        data.get('quantity') > 0,
        data.get('price') > 0
    ])

def calculate_trade_metrics(trade: Trade) -> TradeMetrics:
    """거래 지표 계산"""
    return TradeMetrics(
        pnl=calculate_pnl(trade),
        roi=calculate_roi(trade)
    )
```

## 🔧 작업 규칙
1. **의도 먼저**: 코드 작성 전 intentions/ 업데이트
2. **설정 우선**: 하드코딩 대신 config/ 사용
3. **테스트 필수**: 기능 추가 시 테스트 동반
4. **문서 동기화**: 코드 변경 시 문서 업데이트

## 🚫 금지 사항
1. 한 번에 여러 책임 가진 함수 작성
2. 하드코딩된 값 사용
3. 테스트 없는 리팩토링
4. 문서 업데이트 없는 구조 변경
5. 이모지 사용 (인코딩 문제)

## 📊 작업 완료 시
1. `.ai/CURRENT_STATE.yaml` 업데이트
2. `.ai/WORK_LOG.yaml`에 세션 기록
3. 다음 작업자를 위한 메모 남기기
```

---

## 🎨 코드 표준 및 규칙

### 1. 명명 규칙
```python
# 클래스: PascalCase
class PositionManager:
    pass

# 함수/변수: snake_case
def calculate_position_size():
    current_price = 100.0

# 상수: UPPER_SNAKE_CASE
MAX_POSITION_SIZE = 10000
DEFAULT_LEVERAGE = 10

# 인터페이스: I prefix
class IExchangeClient:
    pass
```

### 2. 함수 설계 원칙
```python
# 1. 단일 책임
def get_current_price(symbol: str) -> float:
    """현재가 조회 - 이것만 함"""
    return exchange.get_ticker(symbol)['price']

# 2. 순수 함수 선호
def calculate_position_size(
    capital: float,
    risk_percent: float,
    stop_distance: float
) -> float:
    """외부 의존성 없는 순수 계산"""
    return (capital * risk_percent / 100) / stop_distance

# 3. 명시적 의존성
class TradingService:
    def __init__(
        self,
        exchange: IExchangeClient,
        notifier: INotifier,
        config: TradingConfig
    ):
        self.exchange = exchange
        self.notifier = notifier
        self.config = config
```

### 3. 설정 관리
```yaml
# config/base/trading.yaml
trading:
  symbols:
    - symbol: "SOLUSDT"
      precision:
        price: 2
        quantity: 3
      limits:
        min_quantity: 0.01
        max_quantity: 10000
  
  risk_management:
    max_position_size_percent: 10
    default_leverage: 10
    stop_loss:
      atr_multiplier: 1.5
      max_percent: 2.0
```

---

## 🚀 마이그레이션 전략

### Phase 1: 기반 구축 (Week 1)
```bash
# Day 1-2: 구조 생성
- 새 폴더 구조 생성
- 기존 코드를 legacy/로 이동
- .ai/ 시스템 구축

# Day 3-4: 설정 추출
- 모든 하드코딩 값을 config/로 이동
- 설정 스키마 정의
- 환경별 설정 분리

# Day 5-7: 도메인 모델
- 핵심 도메인 모델 구현
- 비즈니스 규칙 추출
- 순수 함수로 계산 로직 분리
```

### Phase 2: 인터페이스 정의 (Week 2)
```python
# application/interfaces/i_exchange.py
from abc import ABC, abstractmethod
from typing import Dict, List
from domain.trading.models import Order, Position

class IExchangeClient(ABC):
    @abstractmethod
    def place_order(self, order: Order) -> Dict:
        """주문 실행"""
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Position:
        """포지션 조회"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        pass
```

### Phase 3: 서비스 계층 구현 (Week 3-4)
```python
# application/services/trading_service.py
class TradingService:
    """거래 오케스트레이션"""
    
    def __init__(self, exchange: IExchangeClient, ...):
        self.exchange = exchange
        
    def execute_trade(self, signal: TradeSignal) -> TradeResult:
        # 1. 검증
        if not self._validate_signal(signal):
            return TradeResult.invalid()
        
        # 2. 포지션 크기 계산
        size = self._calculate_position_size(signal)
        
        # 3. 주문 생성
        order = self._create_order(signal, size)
        
        # 4. 주문 실행
        result = self.exchange.place_order(order)
        
        # 5. 결과 처리
        return self._process_result(result)
```

### Phase 4: 점진적 통합 (Week 5-8)
```python
# infrastructure/adapters/legacy_adapter.py
class LegacyTradingAdapter(ITradingService):
    """기존 시스템 어댑터"""
    
    def __init__(self):
        # 기존 코드 임포트
        from legacy.src.trading.trade_executor import TradeExecutor
        self._legacy = TradeExecutor()
    
    def execute_trade(self, command: TradeCommand) -> TradeResult:
        # 새 형식 → 기존 형식
        legacy_format = self._to_legacy_format(command)
        
        # 기존 시스템 호출
        result = self._legacy.execute_trade(legacy_format)
        
        # 기존 형식 → 새 형식
        return self._from_legacy_format(result)
```

---

## 📅 실행 로드맵

### Month 1: 기반 구축
- Week 1: 프로젝트 구조 및 설정
- Week 2: 도메인 모델 및 인터페이스
- Week 3-4: 서비스 계층 구현

### Month 2: 핵심 마이그레이션
- Week 5-6: 거래 시스템 마이그레이션
- Week 7-8: AI 에이전트 시스템 마이그레이션

### Month 3: 완성 및 최적화
- Week 9-10: 모니터링 및 알림 시스템
- Week 11-12: 테스트 및 문서화

### 성공 지표
- [ ] 함수 평균 길이 < 30줄
- [ ] 테스트 커버리지 > 80%
- [ ] 하드코딩 값 = 0
- [ ] AI 세션 시작 시간 < 5분
- [ ] 새 기능 추가 시간 50% 감소

---

## 🎯 다음 단계

1. **즉시 실행**
   ```bash
   # 1. 백업
   cp -r . ../delphi-trader-backup-$(date +%Y%m%d)
   
   # 2. 구조 생성
   python tools/setup/create_new_structure.py
   
   # 3. AI 시스템 초기화
   python .ai/scripts/initialize_ai_system.py
   ```

2. **첫 번째 마이그레이션**
   - Position 모델 구현
   - PositionManager 서비스 구현
   - 캐싱 문제 해결

3. **지속적 개선**
   - 매일 1-2개 모듈 마이그레이션
   - 주간 리뷰 및 조정
   - 월간 성과 측정

---

이 계획은 살아있는 문서입니다. 진행하면서 계속 업데이트하세요.