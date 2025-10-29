# 🏛️ 델파이 트레이딩 시스템 (Project Delphi)

<div align="center">
  
[![Version](https://img.shields.io/badge/version-3.0-blue.svg)](https://github.com/yourusername/delphi-trader)
[![Python](https://img.shields.io/badge/python-3.8+-yellow.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Completion](https://img.shields.io/badge/completion-85%25-orange.svg)]()

**5명의 AI 전문가가 협업하여 24/7 자율 거래를 수행하는 차세대 암호화폐 트레이딩 시스템**

[설치 가이드](#-설치) • [시작하기](#-빠른-시작) • [문서](#-문서) • [기여하기](#-기여)

</div>

---

## 📌 소개

델파이는 고대 그리스 델파이 신전의 현인들처럼, 5명의 전문 AI 에이전트가 각자의 전문 분야에서 분석을 수행하고 협업하여 최적의 거래 결정을 내리는 자율 트레이딩 시스템입니다.

### 왜 델파이인가?
- **멀티 에이전트 아키텍처**: 단일 AI의 한계를 극복한 집단 지성
- **24/7 자율 거래**: 인간의 개입 없이 완전 자동화된 거래
- **적응형 리스크 관리**: 시장 상황에 따른 동적 포지션 관리
- **투명한 의사결정**: 모든 거래 결정의 근거를 추적 가능

---

## 🤖 AI 에이전트 소개

| 에이전트 | 그리스 이름 | 역할 | 주요 기능 |
|---------|------------|------|-----------|
| **차티스트** | 아르키메데스 | 기술적 분석 전문가 | • 4개 타임프레임 차트 분석<br>• 3개 시나리오 제시<br>• 진입/손절/익절 가격 제공 |
| **저널리스트** | 헤로도토스 | 뉴스/센티먼트 분석가 | • 실시간 뉴스 수집<br>• 팩트 기반 보고<br>• 시장 영향도 평가 |
| **퀀트** | 피타고라스 | 정량적 분석가 | • 멀티 타임프레임 지표<br>• 시나리오 기술적 검증<br>• 과거 패턴 매칭 |
| **스토익** | 제논 | 리스크 관리자 | • 적응형 레버리지 (5-20x)<br>• 포지션 크기 결정<br>• 손실 한도 관리 |
| **신디사이저** | 솔론 | 최종 의사결정자 | • 모든 분석 종합<br>• 거래 실행 결정<br>• 트리거 설정 |

---

## 🚀 주요 기능

### 핵심 기능
- ✅ **시나리오 기반 분석**: 복잡한 시장을 3가지 시나리오로 단순화
- ✅ **실시간 포지션 관리**: OCO 주문으로 자동 손절/익절
- ✅ **거래 연속성**: Trading Context로 일관된 거래 전략 유지
- ✅ **동적 리스크 조정**: 시장 변동성에 따른 레버리지 자동 조정
- ✅ **트리거 시스템**: 가격/변동성/거래량 기반 자동 재분석

### 모니터링 & 알림
- 📊 1분 단위 시스템 헬스체크
- 💬 Discord 실시간 알림
- 📈 일일/주간 성과 리포트
- 🚨 긴급 상황 자동 대응

---

## 📦 시스템 요구사항

- **OS**: Windows 10/11, Linux, macOS
- **Python**: 3.8 이상
- **RAM**: 최소 4GB (권장 8GB)
- **Storage**: 최소 10GB 여유 공간
- **API**: Binance Futures API 키
- **AI**: Google Gemini API 키

---

## 🛠 설치

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/delphi-trader.git
cd delphi-trader
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv new_venv
# Windows
new_venv\Scripts\activate
# Linux/Mac
source new_venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
```bash
cp config/.env.example config/.env
# .env 파일을 편집하여 API 키 입력
```

### 5. 트레이딩뷰 쿠키 설정 (차트 캡처용)
```bash
python scripts/setup_cookies.py
```

자세한 설치 가이드는 [설치 및 실행 가이드](./설치_및_실행_가이드.md)를 참조하세요.

---

## 🚦 빠른 시작

### 1. 단일 분석 실행
```bash
python src/main.py
```

### 2. 자동 스케줄링 설정 (15분마다)
```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts/setup_windows_scheduler.ps1

# Linux/Mac
python src/scheduler.py
```

### 3. 실시간 모니터링 (1분마다)
```bash
python src/monitoring/heartbeat_checker.py --mode continuous --interval 60
```

---

## 📁 프로젝트 구조

```
delphi-trader/
├── src/                    # 핵심 소스 코드
│   ├── agents/            # AI 에이전트 (5명)
│   ├── trading/           # 거래 실행 모듈
│   ├── monitoring/        # 모니터링 시스템
│   ├── data/              # 데이터 수집/관리
│   └── utils/             # 유틸리티 함수
├── prompts/               # AI 프롬프트 템플릿
├── config/                # 설정 파일
├── data/                  # 데이터 저장소
│   ├── screenshots/       # 차트 캡처
│   ├── database/          # SQLite DB
│   └── triggers.json      # 활성 트리거
├── logs/                  # 로그 파일
├── scripts/               # 유틸리티 스크립트
└── docs/                  # 문서
    ├── backup/            # 구버전 문서
    └── research/          # 연구 자료
```

---

## 📊 현재 상태 (v3.0)

### 완료된 기능 (Phase 1-4) ✅
- 시나리오 기반 차티스트 구현
- 팩트 중심 저널리스트 개편
- 퀀트 v3 멀티 타임프레임 분석
- 스토익 적응형 리스크 관리

### 진행 중 (Phase 5) 🚧
- 신디사이저 이미지 직접 분석
- 향상된 패턴 인식

### 알려진 이슈 ⚠️
1. **가짜 학습 시스템**: 에이전트 가중치가 랜덤값 사용 (수정 예정)
2. **15분 지연 트리거**: 실시간 반응 불가 (개선 예정)

---

## 📖 문서

### 필수 문서 (읽기 순서대로)
1. 🚀 [빠른 시작 가이드](./QUICK_START_GUIDE.md) - 처음 시작하는 분들을 위한 가이드
2. 📊 [시스템 전체 개요](./SYSTEM_OVERVIEW.md) - 시스템 이해를 위한 핵심 문서
3. 🔧 [기술 상세](./TECHNICAL_DETAILS.md) - 개발자를 위한 기술적 세부사항
4. 🗺️ [개발 로드맵](./ROADMAP.md) - 현재 진행상황과 향후 계획

### 보조 문서
- 🏗 [시스템 아키텍처](./시스템_아키텍처.md) - 시스템 구조도
- 📚 [설치 및 실행 가이드](./설치_및_실행_가이드.md) - 상세 설치 방법
- 🤖 [AI 관찰 노트](./AI_ASSISTANT_OBSERVATIONS.md) - AI 어시스턴트의 분석

---

## 🎯 로드맵

### 2025 Q1
- 🔴 가짜 학습 시스템 → 실제 학습 시스템
- 🔴 실시간 트리거 구현
- 🟡 백테스팅 시스템 구축

### 2025 Q2
- 🟡 멀티 자산 지원 (BTC, ETH)
- 🟢 웹 대시보드 개발
- 🟢 고급 리스크 관리

### 2025 하반기
- 🔵 머신러닝 모델 통합
- 🔵 분산 시스템 아키텍처
- 🔵 오픈소스 릴리즈

---

## 🤝 기여

델파이 프로젝트에 기여를 환영합니다!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

개발 가이드라인은 [DEV_GUIDELINES.md](./DEV_GUIDELINES.md)를 참조하세요.

---

## ⚠️ 주의사항

- 이 시스템은 교육 및 연구 목적으로 개발되었습니다
- 실제 거래에 사용 시 손실 위험이 있습니다
- 투자 결정은 본인의 책임입니다
- API 키는 절대 공유하지 마세요

---

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](../LICENSE) 파일을 참조하세요.

---

## 💬 연락처

- 이슈 트래커: [GitHub Issues](https://github.com/yourusername/delphi-trader/issues)
- 디스커션: [GitHub Discussions](https://github.com/yourusername/delphi-trader/discussions)

---

<div align="center">
  
**델파이와 함께 AI 기반 자율 거래의 미래를 경험하세요! 🚀**

*"많은 현인의 지혜가 모이면, 최고의 결정이 탄생한다" - 고대 그리스 격언*

</div>