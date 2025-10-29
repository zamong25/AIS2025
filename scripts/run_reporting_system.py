#!/usr/bin/env python3
"""
리포팅 시스템 실행 스크립트
독립적으로 실행 가능한 래퍼 스크립트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# reporting_main 모듈 import 및 실행
from reporting_main import main
import asyncio

if __name__ == "__main__":
    # 실행
    sys.exit(asyncio.run(main()))