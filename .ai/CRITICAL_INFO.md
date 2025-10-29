# 🚨 필수 정보 - 반드시 먼저 읽기

## 🔧 실행 환경
- **가상환경**: `new_venv` (반드시 사용!)
- **Python 실행**: `./new_venv/Scripts/python.exe`
- **모듈 설치**: `./new_venv/Scripts/pip.exe install -r requirements.txt`

## 📁 프로젝트 구조
```
delphi-trader/
├── new_venv/          # 가상환경 (모든 모듈 설치됨)
├── legacy/src/        # 레거시 메인 시스템
├── domain/            # 새 도메인 모델
├── application/       # 새 애플리케이션 서비스
├── infrastructure/    # 새 인프라
├── bridge.py          # 레거시-새시스템 연결
└── .ai/               # AI 작업 공간
```

## 🚀 실행 명령어

### 메인 시스템 실행 (배치 파일 - 권장)
```bash
cd C:\Users\PCW\Desktop\delphi-trader
run_delphi.bat
```

### 메인 시스템 실행 (수동)
```bash
cd legacy/src
../../new_venv/Scripts/python.exe main.py
```

### 대시보드 실행
```bash
cd legacy/src/dashboard
../../../new_venv/Scripts/python.exe app.py
```

### 테스트 실행
```bash
# 프로젝트 루트에서
./new_venv/Scripts/python.exe .ai/workspace/test_name.py
```

## ⚙️ 환경 변수 (.env)
```
USE_NEW_DASHBOARD=true    # 새 대시보드 시스템 사용
USE_NEW_BINANCE=true      # 새 바이낸스 연결 사용
DISCORD_WEBHOOK_URL=...   # Discord 알림
```

## 🔑 중요 파일 위치
- **설정**: `config/trading_config.yaml`
- **프롬프트**: `prompts/` 폴더
- **데이터베이스**: `data/database/delphi_trades.db`
- **로그**: `logs/` 폴더

## ⚠️ 주의사항
1. **절대 `python` 명령 사용 금지** → `./new_venv/Scripts/python.exe` 사용
2. **인코딩 문제** → UTF-8 설정 또는 영문 출력 사용
3. **경로 문제** → 항상 프로젝트 루트 기준 상대 경로 사용
4. **API 키** → 현재 설정 없음, Demo 모드로 작동

## 📝 현재 상태 (2024-01-21)
- 현재 계획: 90% 완료
- 추가 계획: Phase 6-8 대기
- 주요 이슈: 
  - PositionService 메서드명 불일치
  - 테스트 코드 부재
  - 일부 하드코딩 잔존

## 🔄 작업 흐름
1. 세션 시작 시 이 파일 먼저 읽기
2. `.ai/SESSION_GUIDE.md` 읽기 (AI 세션 가이드)
3. `.ai/CURRENT_STATE.yaml` 확인
4. `.ai/WORK_LOG.yaml` 확인
5. 작업 시작

## 💡 자주 하는 실수
- ❌ `python` 대신 `python3` 사용
- ❌ 가상환경 활성화 없이 실행
- ❌ 잘못된 경로에서 실행
- ❌ 환경 변수 미설정

## ✅ 올바른 예시
```bash
# 항상 이렇게 실행
./new_venv/Scripts/python.exe script.py

# 절대 이렇게 하지 말 것
python script.py
python3 script.py
```