# 델파이 트레이더 - AI 작업 가이드

## 🚀 빠른 시작 (5분 이내)

### 1. 시스템 이해
- **무엇**: 5개 AI 에이전트 기반 암호화폐 자동 거래 시스템
- **목표**: 시장 분석 → 거래 결정 → 자동 실행
- **현재 상태**: 레거시 코드 리팩토링 중 (Phase 1)

### 2. 현재 문제
- 포지션 캐싱 버그 (시스템이 없는 포지션을 있다고 표시)
- 함수들이 너무 길고 복잡 (평균 150줄)
- 하드코딩된 값 300개 이상
- 테스트 커버리지 0%

### 3. 작업 시작
```bash
# 1. 현재 상태 확인
cat .ai/CURRENT_STATE.yaml

# 2. 마지막 작업 확인
cat .ai/WORK_LOG.yaml

# 3. 오늘 작업 시작
# next_tasks에서 작업 선택 후 진행
```

### 4. 핵심 파일 위치
- **설계 문서**: `docs/SYSTEM_REDESIGN_MASTER_PLAN.md`
- **현재 코드**: `legacy/src/` (기존 코드)
- **새 코드**: `domain/`, `application/`, `infrastructure/`
- **설정**: `config/`
- **의도**: `intentions/`

### 5. 작업 규칙
- 코드 작성 전 의도 문서화
- 하드코딩 절대 금지
- 함수는 30줄 이하
- 테스트 필수
- 작업 후 상태 업데이트

## 📁 폴더 구조

```
.ai/                    # AI 전용 메타 정보
├── README.md          # 이 파일
├── CURRENT_STATE.yaml # 현재 상태
├── WORK_LOG.yaml     # 작업 이력
├── intentions/       # 시스템 의도 문서
└── workspace/        # 임시 작업 공간
```

## 🎯 현재 목표

1. **단기 (1주)**: 기본 구조 구축 및 설정 추출
2. **중기 (1개월)**: 핵심 모듈 마이그레이션
3. **장기 (3개월)**: 완전한 리팩토링 및 테스트 커버리지 80%

## 💡 유용한 명령어

```bash
# 하드코딩 찾기
grep -r "= ['\"].*['\"]" legacy/src/

# 긴 함수 찾기
find legacy/src -name "*.py" -exec wc -l {} + | sort -n | tail -20

# 테스트 실행
pytest tests/

# 설정 검증
python tools/validate_config.py
```

## 🚨 주의사항

1. **절대 하지 말 것**
   - legacy/ 코드 직접 수정 (어댑터 패턴 사용)
   - 테스트 없는 리팩토링
   - 한 번에 큰 변경

2. **항상 해야 할 것**
   - 작업 전 상태 확인
   - 작업 후 로그 업데이트
   - 의도 먼저, 코드 나중에

## 📞 도움말

문제가 있으면:
1. `docs/SYSTEM_REDESIGN_MASTER_PLAN.md` 참조
2. `.ai/intentions/` 에서 관련 의도 확인
3. `WORK_LOG.yaml`에서 비슷한 작업 찾기

---

**"의도를 명확히, 코드는 단순히"**