#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
델파이 트레이더 - 새 프로젝트 구조 생성 스크립트
이 스크립트를 실행하면 클린 아키텍처 기반의 새 폴더 구조가 생성됩니다.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


def create_directory_structure():
    """새로운 프로젝트 구조 생성"""
    
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
        "tests/unit/domain",
        "tests/unit/application",
        "tests/integration",
        "tests/e2e",
        "tests/fixtures",
        
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
        
        # 레거시
        "legacy",
    ]
    
    print("🏗️  새 프로젝트 구조 생성 중...")
    
    for directory in directories:
        dir_path = root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # __init__.py 생성 (Python 패키지)
        if not any(part.startswith('.') for part in directory.split('/')):
            init_file = dir_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""{}"""\n'.format(directory.replace('/', '.')))
    
    print("✅ 디렉토리 구조 생성 완료")


def create_base_files():
    """기본 파일들 생성"""
    
    files = {
        # 루트 설정 파일
        ".gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# 프로젝트
.ai/workspace/*
!.ai/workspace/.gitignore
config/secrets/*
!config/secrets/.gitignore
monitoring/logs/*
!monitoring/logs/.gitignore
legacy/
*.db
*.log

# 테스트
.coverage
htmlcov/
.pytest_cache/
""",
        
        # 작업 공간 gitignore
        ".ai/workspace/.gitignore": """# AI 작업 공간
*
!.gitignore
""",
        
        # 비밀 설정 gitignore
        "config/secrets/.gitignore": """# 비밀 설정
*
!.gitignore
!.env.example
""",
        
        # 환경 변수 예시
        "config/secrets/.env.example": """# 바이낸스 API
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Discord
DISCORD_WEBHOOK_URL=your_webhook_url_here

# Gemini AI
GEMINI_API_KEY=your_gemini_key_here

# 환경
ENVIRONMENT=development
""",
        
        # 기본 설정
        "config/base/app.yaml": """app:
  name: "Delphi Trader"
  version: "2.0.0"
  environment: "${ENVIRONMENT}"
  
logging:
  level: "INFO"
  format: "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
  file: "monitoring/logs/delphi.log"
  max_size: "100MB"
  backup_count: 7
""",
        
        "config/base/trading.yaml": """trading:
  symbol: "SOLUSDT"
  base_currency: "USDT"
  
  risk_management:
    max_position_size_percent: 10
    max_daily_loss_percent: 5
    max_monthly_loss_percent: 10
    default_leverage: 10
    max_leverage: 20
    
  position:
    min_size: 0.01
    max_concurrent: 1
    
  timing:
    analysis_interval: 900  # 15분 (초)
    min_trade_interval: 1800  # 30분 (초)
    position_timeout: 172800  # 48시간 (초)
""",
        
        # 도메인 모델 예시
        "domain/trading/models/position.py": '''"""거래 포지션 도메인 모델"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional


@dataclass
class Position:
    """포지션 정보"""
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
        if self.direction == "LONG":
            return (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - current_price) * self.quantity
    
    def calculate_pnl_percent(self, current_price: Decimal) -> Decimal:
        """현재가 기준 손익률 계산"""
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.margin_required) * 100
''',
        
        # 인터페이스 예시
        "application/interfaces/i_exchange.py": '''"""거래소 인터페이스"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from domain.trading.models import Position, Order


class IExchangeClient(ABC):
    """거래소 클라이언트 인터페이스"""
    
    @abstractmethod
    def get_balance(self, currency: str) -> float:
        """잔고 조회"""
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """포지션 조회"""
        pass
    
    @abstractmethod
    def place_order(self, order: Order) -> Dict:
        """주문 실행"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """현재가 조회"""
        pass
''',
        
        # README
        "README.md": """# 델파이 트레이더 v2.0

## 🚀 빠른 시작

1. 환경 설정
   ```bash
   cp config/secrets/.env.example config/secrets/.env
   # .env 파일에 API 키 입력
   ```

2. 의존성 설치
   ```bash
   pip install -r requirements.txt
   ```

3. 실행
   ```bash
   python -m presentation.cli.main
   ```

## 📁 프로젝트 구조

- `.ai/` - AI 작업 관리
- `intentions/` - 비즈니스 의도 문서
- `domain/` - 핵심 비즈니스 로직
- `application/` - 애플리케이션 서비스
- `infrastructure/` - 외부 시스템 연동
- `presentation/` - 사용자 인터페이스

## 📖 문서

- [시스템 재설계 계획](docs/SYSTEM_REDESIGN_MASTER_PLAN.md)
- [AI 작업 가이드](.ai/README.md)
- [의도 문서](intentions/README.md)

## 🧪 테스트

```bash
# 단위 테스트
pytest tests/unit/

# 통합 테스트
pytest tests/integration/

# 전체 테스트
pytest
```

## 🔧 개발

1. 의도 먼저 작성 (`intentions/`)
2. 도메인 모델 구현 (`domain/`)
3. 서비스 구현 (`application/`)
4. 인프라 연결 (`infrastructure/`)
5. 테스트 작성 (`tests/`)

---

**"명확한 의도, 깨끗한 코드, 안정적인 수익"**
""",
    }
    
    print("\n📄 기본 파일 생성 중...")
    
    for file_path, content in files.items():
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"   ✓ {file_path}")
    
    print("✅ 기본 파일 생성 완료")


def backup_legacy_code():
    """기존 코드를 legacy 폴더로 이동"""
    
    src_path = Path("src")
    if src_path.exists():
        legacy_path = Path("legacy/src")
        
        print("\n📦 기존 코드 백업 중...")
        
        # 백업 생성
        backup_name = f"legacy/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(src_path, backup_name)
        print(f"   ✓ 백업 생성: {backup_name}")
        
        # legacy로 이동
        if legacy_path.exists():
            shutil.rmtree(legacy_path)
        shutil.move(src_path, legacy_path)
        print(f"   ✓ 이동 완료: src/ → legacy/src/")
        
        print("✅ 레거시 코드 백업 완료")
    else:
        print("\n⚠️  src/ 폴더가 없습니다. 백업 건너뛰기")


def main():
    """메인 실행 함수"""
    
    print("🎯 델파이 트레이더 v2.0 구조 생성 시작\n")
    
    # 확인
    response = input("⚠️  이 작업은 프로젝트 구조를 변경합니다. 계속하시겠습니까? (y/N): ")
    if response.lower() != 'y':
        print("❌ 취소되었습니다.")
        return
    
    # 실행
    create_directory_structure()
    create_base_files()
    backup_legacy_code()
    
    print("\n✨ 새 프로젝트 구조 생성 완료!")
    print("\n다음 단계:")
    print("1. config/secrets/.env 파일에 API 키 설정")
    print("2. .ai/CURRENT_STATE.yaml 확인 및 업데이트")
    print("3. legacy/src/에서 필요한 코드 점진적 마이그레이션")
    print("\n행운을 빕니다! 🚀")


if __name__ == "__main__":
    main()