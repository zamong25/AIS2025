# 거래 히스토리 폴더

이 폴더는 종료된 거래의 Trading Context를 보관합니다.

## 폴더 구조

```
history/
└── 2025/                    # 연도
    ├── 01/                  # 월
    │   ├── context_20250112_143021.json
    │   └── context_20250115_091533.json
    └── 07/                  # 7월
        ├── context_20250706_121126.json
        ├── context_20250707_004304.json
        └── ...
```

## 파일 명명 규칙

- 파일명: `context_YYYYMMDD_HHMMSS.json`
- 예시: `context_20250710_201558.json`

## 파일 내용

각 JSON 파일은 다음 정보를 포함합니다:

```json
{
  "thesis": {
    "trade_id": "DELPHI_20250709_160425",
    "entry_time": "2025-07-09T16:04:25",
    "direction": "LONG/SHORT",
    "entry_price": 150.5,
    "entry_reason": "AI의 거래 진입 이유",
    "primary_scenario": "예상 시나리오",
    "target_price": 155.0,
    "stop_loss": 148.0,
    "initial_confidence": 75,
    "initial_agent_scores": {...}
  },
  "history": [
    // 거래 중 발생한 업데이트 기록
  ]
}
```

## 활용 방법

1. **성과 분석**: 과거 거래의 성공/실패 패턴 분석
2. **학습 데이터**: AI 학습 시스템 구현 시 훈련 데이터로 활용
3. **감사 추적**: 각 거래의 전체 라이프사이클 추적

## 자동 생성

- 포지션이 종료되면 `PositionStateManager`가 자동으로 파일을 이 폴더로 이동
- 수동으로 파일을 수정하지 마세요

## 데이터 보존 정책

- 기본적으로 모든 거래 기록은 영구 보존
- 필요시 오래된 데이터는 압축하여 보관 가능