#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""마이그레이션 실행 스크립트 (자동 실행)"""

import subprocess
import sys

print("=== 안전한 마이그레이션 실행 ===\n")
print("[정보] 기존 시스템에 영향 없이 새 구조를 생성합니다.")

# 스크립트 실행 (y 자동 입력)
process = subprocess.Popen(
    [sys.executable, '.ai/scripts/create_new_structure_safe.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# 'y' 입력 전송
output, _ = process.communicate(input='y\n')

print(output)