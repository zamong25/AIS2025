#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
델파이 트레이더 - 안전한 새 프로젝트 구조 생성 스크립트
기존 시스템에 영향을 주지 않고 새 구조를 생성합니다.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


def create_directory_structure():
    """새로운 프로젝트 구조 생성 (기존 src는 유지)"""
    
    # 프로젝트 루트
    root = Path.cwd()
    
    # 생성할 디렉토리 구조
    directories = [
        # AI 메타 레이어
        ".ai/intentions",
        ".ai/workspace",
        ".ai/scripts",
        
        # 의도 문서
        "intentions/features",
        "intentions/domains",
        "intentions/workflows",
        
        # 설정
        "config/base",
        "config/environments",
        "config/secrets",
        "config/schema",
        
        # 도메인 계층
        "domain/trading/models",
        "domain/trading/rules",
        "domain/trading/calculations",
        "domain/analysis/models",
        "domain/analysis/indicators",
        "domain/analysis/scenarios",
        
        # 애플리케이션 계층
        "application/services",
        "application/workflows",
        "application/interfaces",
        
        # 인프라 계층
        "infrastructure/exchanges/binance",
        "infrastructure/agents/chartist",
        "infrastructure/agents/journalist",
        "infrastructure/agents/quant",
        "infrastructure/agents/stoic",
        "infrastructure/agents/synthesizer",
        "infrastructure/persistence/database/repositories",
        "infrastructure/persistence/database/migrations",
        "infrastructure/persistence/cache",
        "infrastructure/notifications/discord",
        
        # 프레젠테이션 계층
        "presentation/cli",
        "presentation/api",
        "presentation/scheduler",
        
        # 테스트
        "tests_v2/unit/domain",
        "tests_v2/unit/application",
        "tests_v2/integration",
        "tests_v2/e2e",
        "tests_v2/fixtures",
        
        # 모니터링
        "monitoring/logs",
        "monitoring/metrics",
        "monitoring/alerts",
        
        # 도구
        "tools/setup",
        "tools/migration",
        "tools/analysis",
        
        # 문서
        "docs/architecture",
        "docs/api",
        "docs/guides",
        "docs/decisions",
    ]
    
    print("[생성중]  새 프로젝트 구조 생성 중...")
    print("   (기존 src 폴더는 그대로 유지됩니다)")
    
    for directory in directories:
        dir_path = root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # __init__.py 생성 (Python 패키지)
        if not any(part.startswith('.') for part in directory.split('/')) and not directory.startswith('tests_v2'):
            init_file = dir_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""{}"""\n'.format(directory.replace('/', '.')))
    
    print("[완료] 디렉토리 구조 생성 완료")


def create_base_files():
    """기본 파일들 생성"""
    
    files = {
        # 기존 시스템과의 브릿지 파일
        "bridge.py": '''"""
기존 시스템과 새 시스템을 연결하는 브릿지 모듈
점진적 마이그레이션을 위한 어댑터 패턴 구현
"""

import sys
import os

# 기존 src 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 새 구조 경로도 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'domain'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'application'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'infrastructure'))


class SystemBridge:
    """기존 시스템과 새 시스템을 연결"""
    
    def __init__(self):
        self.use_new_system = False  # 기본값: 기존 시스템 사용
        
    def get_position_manager(self):
        """포지션 매니저 반환"""
        if self.use_new_system:
            # 새 시스템 (나중에 구현)
            from domain.trading.services import PositionService
            return PositionService()
        else:
            # 기존 시스템
            from src.trading.position_state_manager import position_state_manager
            return position_state_manager
            
    def get_trade_executor(self):
        """거래 실행자 반환"""
        if self.use_new_system:
            # 새 시스템 (나중에 구현)
            from application.services import TradingService
            return TradingService()
        else:
            # 기존 시스템
            from src.trading.trade_executor import TradeExecutor
            return TradeExecutor
            

# 전역 브릿지 인스턴스
bridge = SystemBridge()
''',
        
        # 설정 스키마
        "config/schema/trading.yaml": """# 거래 설정 스키마
type: object
properties:
  symbol:
    type: string
    pattern: "^[A-Z]+USDT$"
    default: "SOLUSDT"
  
  risk_management:
    type: object
    properties:
      max_position_size_percent:
        type: number
        minimum: 1
        maximum: 100
        default: 10
      max_daily_loss_percent:
        type: number
        minimum: 1
        maximum: 20
        default: 5
      default_leverage:
        type: integer
        minimum: 1
        maximum: 20
        default: 10
        
required: ["symbol", "risk_management"]
""",

        # 도메인 모델 예시
        "domain/trading/models/position.py": '''"""거래 포지션 도메인 모델"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional


@dataclass
class Position:
    """포지션 정보 (불변 객체)"""
    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_price: Decimal
    quantity: Decimal
    leverage: int
    entry_time: datetime
    
    # 선택적 필드
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    trade_id: Optional[str] = None
    
    def __post_init__(self):
        """타입 변환 및 검증"""
        self.entry_price = Decimal(str(self.entry_price))
        self.quantity = Decimal(str(self.quantity))
        
        if self.stop_loss:
            self.stop_loss = Decimal(str(self.stop_loss))
        if self.take_profit:
            self.take_profit = Decimal(str(self.take_profit))
            
        # 검증
        if self.leverage < 1 or self.leverage > 20:
            raise ValueError(f"Invalid leverage: {self.leverage}")
        if self.quantity <= 0:
            raise ValueError(f"Invalid quantity: {self.quantity}")
    
    @property
    def exposure(self) -> Decimal:
        """총 노출 금액"""
        return self.entry_price * self.quantity * self.leverage
    
    @property
    def margin_required(self) -> Decimal:
        """필요 증거금"""
        return self.exposure / self.leverage
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """현재가 기준 손익 계산"""
        current_price = Decimal(str(current_price))
        
        if self.direction == "LONG":
            return (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - current_price) * self.quantity
    
    def calculate_pnl_percent(self, current_price: Decimal) -> Decimal:
        """현재가 기준 손익률 계산"""
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.margin_required) * 100
''',

        # 마이그레이션 가이드
        "tools/migration/README.md": """# 마이그레이션 가이드

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
""",

        # 테스트 헬퍼
        "tests_v2/conftest.py": '''"""pytest 설정 및 공통 픽스처"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone


@pytest.fixture
def sample_position():
    """테스트용 포지션"""
    from domain.trading.models import Position
    
    return Position(
        symbol="SOLUSDT",
        direction="LONG",
        entry_price=Decimal("100.50"),
        quantity=Decimal("10"),
        leverage=10,
        entry_time=datetime.now(timezone.utc),
        stop_loss=Decimal("95.00"),
        take_profit=Decimal("110.00"),
        trade_id="TEST_001"
    )


@pytest.fixture
def mock_binance_client():
    """Mock 바이낸스 클라이언트"""
    class MockClient:
        def futures_position_information(self, symbol):
            return [{
                'symbol': symbol,
                'positionAmt': '10.000',
                'entryPrice': '100.50',
                'unRealizedProfit': '50.00',
                'markPrice': '105.50',
                'leverage': '10'
            }]
            
    return MockClient()
''',

        # .gitignore 업데이트
        ".gitignore_update": """
# 새 구조 관련 추가
.ai/workspace/*
!.ai/workspace/.gitignore
config/secrets/*
!config/secrets/.gitignore
!config/secrets/.env.example

# 테스트 커버리지
htmlcov/
.coverage
.pytest_cache/

# 마이그레이션 임시 파일
*.migration_backup
""",

        # AI 상태 업데이트
        ".ai/CURRENT_STATE_UPDATE.yaml": """# 마이그레이션 진행 상태 추가
migration:
  phase: 1_domain_models
  started_at: "{}"
  components:
    domain_models:
      status: in_progress
      progress: 10%
    infrastructure_adapters:
      status: pending
      progress: 0%
    application_services:
      status: pending
      progress: 0%
    presentation_layer:
      status: pending
      progress: 0%
  
  next_tasks:
    - "Position 도메인 모델 완성"
    - "Trade 도메인 모델 구현"
    - "비즈니스 규칙 추출"
    - "도메인 모델 테스트 작성"
""".format(datetime.now().isoformat()),
    }
    
    print("\n[생성중] 기본 파일 생성 중...")
    
    for file_path, content in files.items():
        # _update로 끝나는 파일은 기존 파일에 추가
        if file_path.endswith('_update'):
            continue
            
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"   [OK] {file_path}")
    
    print("[완료] 기본 파일 생성 완료")


def show_next_steps():
    """다음 단계 안내"""
    print("\n[***] 새 프로젝트 구조 생성 완료!")
    print("\n[중요] 중요: 기존 src/ 폴더는 그대로 유지됩니다")
    print("         새 구조와 병행 운영하며 점진적으로 마이그레이션합니다")
    
    print("\n다음 단계:")
    print("1. bridge.py를 통해 기존 시스템과 연결")
    print("2. domain/trading/models/에 핵심 모델 구현")
    print("3. tests_v2/에서 새 모델 테스트")
    print("4. 기존 코드에서 점진적으로 새 모델 사용")
    
    print("\n[가이드] 마이그레이션 가이드: tools/migration/README.md")
    print("[상태] 진행 상태 추적: .ai/CURRENT_STATE.yaml")
    
    print("\n[시작] 안전한 마이그레이션을 시작하세요!")


def main():
    """메인 실행 함수"""
    
    print("=== 델파이 트레이더 v2.0 안전한 구조 생성 ===\n")
    print("[주의] 이 스크립트는:")
    print("   - 기존 src/ 폴더를 그대로 유지합니다")
    print("   - 새로운 구조를 별도로 생성합니다")
    print("   - 시스템 운영에 영향을 주지 않습니다")
    
    # 확인
    response = input("\n계속하시겠습니까? (y/N): ")
    if response.lower() != 'y':
        print("[취소] 취소되었습니다.")
        return
    
    # 실행
    create_directory_structure()
    create_base_files()
    show_next_steps()


if __name__ == "__main__":
    main()