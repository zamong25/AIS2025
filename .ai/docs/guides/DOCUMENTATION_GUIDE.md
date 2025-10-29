# 📚 델파이 문서 가이드

> 작성일: 2025-01-12

## 문서 구조 및 읽는 순서

### 🎯 목적별 가이드

#### "델파이가 뭔지 빠르게 알고 싶어요"
1. **[QUICK_START_GUIDE.md](./QUICK_START_GUIDE.md)** - 1분 요약부터 시작

#### "시스템을 전체적으로 이해하고 싶어요"
1. **[QUICK_START_GUIDE.md](./QUICK_START_GUIDE.md)** - 개요 파악
2. **[SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)** - 전체 구조 이해
3. **[시스템_아키텍처.md](./시스템_아키텍처.md)** - 구조도 확인

#### "개발/유지보수를 해야 해요"
1. **[SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)** - 시스템 이해
2. **[TECHNICAL_DETAILS.md](./TECHNICAL_DETAILS.md)** - 기술적 세부사항
3. **[ROADMAP.md](./ROADMAP.md)** - 현재 이슈와 TODO

#### "설치하고 실행하고 싶어요"
1. **[QUICK_START_GUIDE.md](./QUICK_START_GUIDE.md)** - 빠른 설치
2. **[설치_및_실행_가이드.md](./설치_및_실행_가이드.md)** - 상세 가이드

---

## 📁 현재 문서 구조

```
docs/
├── 📄 핵심 문서 (4개)
│   ├── QUICK_START_GUIDE.md      # 🚀 빠른 시작 (신규)
│   ├── SYSTEM_OVERVIEW.md        # 📊 전체 개요 (통합본)
│   ├── TECHNICAL_DETAILS.md      # 🔧 기술 상세 (통합본)
│   └── ROADMAP.md               # 🗺️ 로드맵 (통합본)
│
├── 📄 보조 문서 (4개)
│   ├── README.md                # 프로젝트 소개
│   ├── 시스템_아키텍처.md        # 구조도
│   ├── 설치_및_실행_가이드.md     # 상세 설치
│   └── AI_ASSISTANT_OBSERVATIONS.md  # AI 분석
│
├── 📁 backup/                   # 이전 버전 문서들
│   └── (통합 전 원본 문서 14개)
│
└── 📁 research/                 # 연구 자료
    └── (참고 논문 및 분석 2개)
```

---

## 🔄 문서 정리 내역 (2025-01-12)

### 통합된 문서들
| 새 문서 | ← 통합된 기존 문서들 |
|--------|-------------------|
| **SYSTEM_OVERVIEW.md** | ← SYSTEM_ANALYSIS_2025.md<br>← 시스템_아키텍처.md (일부)<br>← README.md (일부) |
| **TECHNICAL_DETAILS.md** | ← TECHNICAL_INSIGHTS.md<br>← IMPLEMENTATION_DETAILS.md<br>← PHASE_PROGRESS.md (기술 부분) |
| **ROADMAP.md** | ← TODO_AND_ROADMAP.md<br>← FUTURE_IMPROVEMENTS_PLAN.md<br>← DEV_GUIDELINES.md (일부) |
| **QUICK_START_GUIDE.md** | ← README.md (설치 부분)<br>← 설치_및_실행_가이드.md (요약) |

### 제거된 중복 내용
- Phase 진행 상황 (4개 문서에 중복 → ROADMAP.md로 통합)
- 가짜 학습 시스템 설명 (3개 문서에 중복 → TECHNICAL_DETAILS.md로 통합)
- 에이전트 설명 (3개 문서에 중복 → SYSTEM_OVERVIEW.md로 통합)
- 설치 가이드 (2개 문서에 중복 → QUICK_START_GUIDE.md로 정리)

### 개선 사항
- ✅ 문서 수 감소: 14개 → 8개 (43% 감소)
- ✅ 중복 제거: 주요 내용이 한 곳에만 존재
- ✅ 일관성: 모든 문서 날짜를 2025-01-12로 통일
- ✅ 접근성: 목적별 읽기 순서 제공

---

## 💡 문서 관리 원칙

1. **Single Source of Truth**: 각 정보는 한 곳에만
2. **목적 중심**: 독자가 누구인지 명확히
3. **최신성**: 코드 변경 시 문서도 함께 업데이트
4. **간결성**: 핵심만 담고 나머지는 참조

---

*문서에 대한 제안이나 수정사항은 PR로 제출해주세요.*