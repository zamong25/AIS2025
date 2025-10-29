# 🚀 델파이 트레이딩 시스템 빠른 시작 가이드

> 최종 업데이트: 2025-01-12  
> 시스템 버전: 3.0

이 가이드는 델파이 시스템을 처음 접하는 개발자가 빠르게 시스템을 이해하고 실행할 수 있도록 작성되었습니다.

---

## 📌 시스템 개요 (1분 요약)

**델파이(Delphi)**는 5명의 전문 AI 에이전트가 협업하여 **Solana(SOL) 선물 거래**를 자동으로 수행하는 시스템입니다.

### 핵심 특징
- ✅ **24/7 자동 거래**: 15분마다 시장 분석 및 거래 결정
- ✅ **멀티 AI 협업**: 각 분야 전문 AI가 의견을 제시하고 종합
- ✅ **적응형 리스크 관리**: 시장 상황에 따라 레버리지 자동 조정 (5-20x)
- ✅ **완전 자동화**: 진입부터 청산까지 인간 개입 없이 실행

### ⚠️ 알려진 주요 이슈
- **가짜 학습 시스템**: 현재 AI 가중치가 랜덤값 사용 (실제 학습 안 함)
- **15분 지연 트리거**: 실시간 반응 불가

---

## 🤖 AI 에이전트 소개

| 에이전트 | 역할 | 사용 프롬프트 |
|---------|------|--------------|
| **차티스트** | 차트 패턴 분석 | `chartist_final.txt` |
| **저널리스트** | 뉴스/이벤트 분석 | `journalist_final.txt` |
| **퀀트** | 기술적 지표 분석 | `quant_v3.txt` |
| **스토익** | 리스크 관리 | `stoic_v2.txt` |
| **신디사이저** | 최종 의사결정 | `synthesizer_v2.txt` |

---

## 🛠 필수 준비사항

### 1. API 키
- **Binance API**: 선물 거래 권한 필요
- **Google Gemini API**: AI 분석용
- **Discord Webhook**: 알림용

### 2. 시스템 요구사항
- Python 3.8+
- Windows/Linux/Mac
- 4GB+ RAM

---

## ⚡ 30초 설치

```bash
# 1. 클론
git clone https://github.com/yourusername/delphi-trader.git
cd delphi-trader

# 2. 가상환경
python -m venv new_venv
new_venv\Scripts\activate  # Windows
# source new_venv/bin/activate  # Mac/Linux

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp config/.env.example config/.env
# .env 파일 편집하여 API 키 입력

# 5. 쿠키 설정 (차트 캡처용)
python scripts/setup_cookies.py
```

---

## 🏃 실행 방법

### 1회성 분석 실행
```bash
python src/main.py
```

### 자동 스케줄링 (15분마다)
```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts/setup_windows_scheduler.ps1

# Linux/Mac
python src/scheduler.py
```

### 실시간 모니터링
```bash
python src/monitoring/heartbeat_checker.py --mode continuous
```

---

## 📊 시스템 작동 방식

```
1. 차트 캡처 (5분/15분/1시간/1일)
   ↓
2. 5명의 AI가 각자 분석
   ↓
3. 신디사이저가 종합하여 결정
   ↓
4. 거래 실행 (진입/홀드/청산)
   ↓
5. OCO 주문으로 자동 손절/익절
```

---

## 📁 핵심 파일 위치

```
delphi-trader/
├── src/
│   ├── main.py              # 진입점
│   ├── agents/              # AI 에이전트들
│   └── trading/             # 거래 실행
├── prompts/                 # AI 프롬프트
├── config/.env              # API 키 설정
├── data/
│   ├── active_trading_context.json  # 현재 포지션
│   └── history/             # 과거 거래
└── logs/delphi.log          # 실행 로그
```

---

## 🚨 문제 해결

### API 키 오류
```
ERROR: Client error: (401)
```
→ `.env` 파일의 API 키 확인

### 차트 캡처 실패
```
ERROR: 차트 캡처 실패
```
→ `python scripts/setup_cookies.py` 재실행

### Discord 알림 안 옴
→ `.env`의 `DISCORD_WEBHOOK_URL` 확인

---

## 🔍 더 알아보기

- **시스템 전체 분석**: [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- **기술적 상세**: [TECHNICAL_DETAILS.md](./TECHNICAL_DETAILS.md)
- **개발 로드맵**: [ROADMAP.md](./ROADMAP.md)

---

## ⚠️ 주의사항

1. **실제 자금으로 시작하지 마세요** - 테스트넷에서 충분히 검증
2. **가짜 학습 시스템** - AI가 실제로 학습하지 않음
3. **24/7 모니터링 필요** - 예상치 못한 상황 대비

---

*질문이나 문제가 있으면 [GitHub Issues](https://github.com/yourusername/delphi-trader/issues)에 남겨주세요.*