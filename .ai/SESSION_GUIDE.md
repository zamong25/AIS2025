# 🤖 AI 세션 가이드 - 델파이 트레이더

> 이 문서는 AI(Claude)가 세션 간 일관성을 유지하기 위한 핵심 가이드입니다.

## 🚨 세션 시작 시 필수 확인 사항

### 1. 필수 문서 읽기 (순서대로)
```bash
1. cat .ai/CRITICAL_INFO.md      # 실행 환경, 주의사항
2. cat .ai/CURRENT_STATE.yaml    # 현재 프로젝트 상태
3. cat .ai/WORK_LOG.yaml         # 이전 작업 내역
4. cat CLAUDE.md                 # 코딩 가이드라인
```

### 2. 현재 상태 파악
- **현재 Phase**: 12 (문서화) - 11/12 완료
- **프로젝트 구조**: 클린 아키텍처 97% 완료
- **실행 경로**: `legacy/src/main.py` (변경됨!)
- **가상환경**: `new_venv` 사용 필수

## 📁 프로젝트 구조 이해

### 현재 구조
```
delphi-trader/
├── .ai/                    # AI 작업 공간 (세션 정보)
├── domain/                 # 새 시스템 - 도메인 모델
├── application/            # 새 시스템 - 서비스 레이어
├── infrastructure/         # 새 시스템 - 외부 연동
├── legacy/src/             # 기존 시스템 (실제 운영 중)
├── bridge.py               # 새/구 시스템 연결
├── new_venv/               # 가상환경
└── tests/                  # 테스트 코드
```

### 중요 변경사항
- ❌ `src/main.py` (이전 경로)
- ✅ `legacy/src/main.py` (현재 경로)
- ✅ `USE_NEW_SYSTEM=true` 환경변수로 새 시스템 사용

## 🎯 현재 목표

### 전체 목표
1. **클린한 코드**: Clean Architecture 패턴
2. **클린 프로젝트**: 체계적 폴더 구조
3. **일관성 있는 작업**: 모든 변경사항 추적
4. **일관성 있는 프로젝트**: 코딩 규칙 통일

### 현재 작업 (Phase 8: 문서화)
- [ ] AI 세션 연속성 문서
- [ ] 실행 가이드
- [ ] 사용자 문서 (README)
- [ ] 개발자 문서
- [ ] 운영 문서

## 💻 코드 작업 시 규칙

### 1. 경로 관련
```python
# 잘못된 예
from utils.time_manager import TimeManager  # ❌

# 올바른 예 (legacy/src에서 실행 시)
from utils.time_manager import TimeManager  # ✅
```

### 2. 실행 명령
```bash
# 잘못된 예
python src/main.py                          # ❌
./new_venv/Scripts/python.exe src/main.py   # ❌

# 올바른 예
cd legacy/src
../../new_venv/Scripts/python.exe main.py   # ✅
```

### 3. 테스트 실행
```bash
# 프로젝트 루트에서
./new_venv/Scripts/pytest.exe tests/ -v
```

## 📝 작업 추적

### 세션 시작 시
1. TodoWrite로 현재 작업 확인
2. CURRENT_STATE.yaml 읽기
3. 이전 세션 작업 확인 (WORK_LOG.yaml)

### 작업 중
- 모든 중요 결정은 WORK_LOG에 기록
- 발견한 문제는 ISSUES.yaml에 추가
- 진행상황은 TodoWrite로 업데이트

### 세션 종료 시
1. WORK_LOG.yaml에 세션 추가
2. CURRENT_STATE.yaml 업데이트
3. 다음 작업 명확히 기록

## ⚠️ 주의사항

### 1. 가상환경
- **항상** `new_venv` 사용
- `python` 대신 `./new_venv/Scripts/python.exe`

### 2. 인코딩
- Windows에서 UTF-8 문제 주의
- 유니코드 문자 대신 ASCII 사용 권장

### 3. 경로
- main.py는 `legacy/src/`에 있음
- 실행 시 해당 디렉토리에서 실행

### 4. 환경변수
- `.env` 파일 필수
- `USE_NEW_SYSTEM=true`로 새 시스템 테스트

## 🔄 일관성 유지 방법

### 1. 코딩 스타일
- Black으로 포맷팅
- Flake8로 린트
- 타입 힌트 사용

### 2. 테스트
- 새 기능은 테스트 필수
- pytest 사용
- 커버리지 25% 이상 유지

### 3. 문서화
- 모든 변경사항 문서화
- docstring 작성
- README 업데이트

## 🚀 다음 AI 세션을 위한 체크리스트

- [ ] .ai/CRITICAL_INFO.md 읽었나?
- [ ] CURRENT_STATE.yaml 확인했나?
- [ ] WORK_LOG.yaml 마지막 세션 확인했나?
- [ ] 현재 Phase와 작업 확인했나?
- [ ] 실행 경로 변경 인지했나? (legacy/src/)
- [ ] 가상환경 경로 확인했나? (new_venv)

---

**"일관성은 반복에서 나온다. 매 세션 시작 시 이 문서를 확인하라."**