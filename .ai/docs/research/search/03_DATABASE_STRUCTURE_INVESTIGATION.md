# 델파이 시스템 데이터베이스 구조 상세 분석

> 작성일: 2025-01-12  
> 조사자: Claude AI Assistant

## 요약

델파이 시스템은 3개의 SQLite 데이터베이스를 사용하며, 총 8개 테이블에 거래 데이터와 분석 결과를 체계적으로 저장합니다.

---

## 1. 데이터베이스 파일 구조

### 1.1 파일 위치 및 용도
```
data/
├── database/
│   ├── delphi_trades.db    # 메인 거래 데이터베이스 (핵심)
│   └── dashboard.db         # 대시보드용 세션 및 성과 데이터
└── trade_memory.db          # 현재 사용 안 함 (레거시)
```

---

## 2. delphi_trades.db - 메인 거래 데이터베이스

### 2.1 trade_records 테이블 (핵심 거래 기록)

| 컬럼명 | 타입 | 설명 | 업데이트 시점 |
|--------|------|------|--------------|
| **trade_id** | TEXT (PK) | 고유 거래 ID (예: DELPHI_20250710_010055) | 진입 시 |
| **asset** | TEXT | 거래 자산 (SOLUSDT) | 진입 시 |
| **entry_price** | REAL | 진입 가격 | 진입 시 |
| **exit_price** | REAL | 청산 가격 | 청산 시 |
| **direction** | TEXT | 방향 (LONG/SHORT) | 진입 시 |
| **leverage** | REAL | 레버리지 (5-20) | 진입 시 |
| **position_size_percent** | REAL | 포지션 크기 (%) | 진입 시 |
| **entry_time** | TEXT | 진입 시간 (ISO format) | 진입 시 |
| **exit_time** | TEXT | 청산 시간 | 청산 시 |
| **outcome** | TEXT | 결과 (아래 참조) | 청산 시 |
| **rr_ratio** | REAL | Risk/Reward 비율 | 청산 시 |
| **pnl_percent** | REAL | 손익률 | 청산 시 |
| **market_conditions** | TEXT | 시장 상황 (JSON) | 진입 시 |
| **agent_scores** | TEXT | 에이전트 점수 (JSON) | 진입 시 |
| **stop_loss_price** | REAL | 손절가 | 진입 시 |
| **take_profit_price** | REAL | 익절가 | 진입 시 |
| **max_drawdown_percent** | REAL | 최대 낙폭 | 청산 시 |
| **created_at** | TEXT | DB 저장 시간 | 진입 시 |
| **strategy_mode** | TEXT | 전략 모드 (SHORT_TERM/SWING/POSITION) | 진입 시 |
| **timeframe_alignment** | TEXT | 주도 시간대 | 진입 시 |
| **conflict_narrative** | TEXT | 갈등 설명 | 진입 시 |
| **volatility_at_entry** | REAL | 진입 시 변동성 | 진입 시 |
| **market_regime** | TEXT | 시장 체제 | 진입 시 |
| **exploration_trade** | BOOLEAN | 탐험 거래 여부 | 진입 시 |
| **adaptive_thresholds** | TEXT | 적응형 임계값 (JSON) | 진입 시 |
| **auto_lesson** | TEXT | 자동 생성 교훈 | 청산 시 |
| **time_to_stop_minutes** | INTEGER | 손절까지 시간 | 청산 시 |
| **stop_loss_type** | TEXT | 손절 유형 (NOISE/QUICK/NORMAL/LATE) | 청산 시 |
| **position_management_quality** | TEXT | 포지션 관리 품질 (GOOD/POOR) | 청산 시 |
| **atr_at_entry** | REAL | 진입 시 ATR | 진입 시 |
| **stop_distance_percent** | REAL | 손절 거리 (%) | 청산 시 |
| **updated_at** | TEXT | 업데이트 시간 | 청산 시 |

#### outcome 필드 값:
- `PENDING`: 진행 중
- `TP_HIT`: 익절가 도달
- `SL_HIT`: 손절가 도달
- `TIME_EXIT`: 시간 초과 청산
- `MANUAL_EXIT`: 수동 청산
- `WIN`: 수익 (TP 미도달)
- `LOSS`: 손실 (SL 미도달)

### 2.2 market_classifications 테이블 (시장 분류)

| 컬럼명 | 타입 | 설명 | 저장 시점 |
|--------|------|------|-----------|
| **id** | INTEGER (PK) | 자동 증가 ID | - |
| **trade_id** | TEXT (FK) | trade_records 참조 | 진입 시 |
| **trend_type** | TEXT | 추세 (UPTREND/DOWNTREND/SIDEWAYS) | 진입 시 |
| **volatility_level** | TEXT | 변동성 (HIGH/MEDIUM/LOW) | 진입 시 |
| **volume_profile** | TEXT | 거래량 (HIGH/NORMAL/LOW) | 진입 시 |
| **chartist_score** | INTEGER | 차티스트 점수 (0-100) | 진입 시 |
| **journalist_score** | INTEGER | 저널리스트 점수 (0-10) | 진입 시 |

### 2.3 trade_analyses 테이블 (거래 분석)

| 컬럼명 | 타입 | 설명 | 저장 시점 |
|--------|------|------|-----------|
| **id** | INTEGER (PK) | 자동 증가 ID | - |
| **trade_id** | TEXT | trade_records 참조 | 분석 시 |
| **analysis_type** | TEXT | 분석 유형 | 분석 시 |
| **key_factors** | TEXT | 주요 요인 (JSON) | 분석 시 |
| **agent_accuracy** | TEXT | 에이전트 정확도 (JSON) | 분석 시 |
| **market_factor_impact** | TEXT | 시장 요인 영향 (JSON) | 분석 시 |
| **lessons_learned** | TEXT | 학습된 교훈 (JSON) | 분석 시 |
| **confidence_score** | REAL | 신뢰도 (0-100) | 분석 시 |
| **timestamp** | TEXT | 분석 시간 | 분석 시 |
| **created_at** | TEXT | 생성 시간 | 분석 시 |

### 2.4 scenario_outcomes 테이블 (시나리오 결과)

| 컬럼명 | 타입 | 설명 | 저장 시점 |
|--------|------|------|-----------|
| **id** | INTEGER (PK) | 자동 증가 ID | - |
| **trade_id** | TEXT (FK) | trade_records 참조 | 청산 시 |
| **scenario_type** | TEXT | 시나리오 (상승/하락/박스권) | 청산 시 |
| **scenario_confidence** | INTEGER | 신뢰도 (%) | 청산 시 |
| **actual_outcome** | TEXT | 실제 결과 | 청산 시 |
| **predicted_entry** | REAL | 예측 진입가 | 청산 시 |
| **predicted_target** | REAL | 예측 목표가 | 청산 시 |
| **predicted_stop** | REAL | 예측 손절가 | 청산 시 |
| **actual_entry** | REAL | 실제 진입가 | 청산 시 |
| **actual_exit** | REAL | 실제 청산가 | 청산 시 |
| **success** | BOOLEAN | 성공 여부 | 청산 시 |
| **created_at** | TEXT | 생성 시간 | 청산 시 |

### 2.5 indicator_snapshots 테이블 (지표 스냅샷)

| 컬럼명 | 타입 | 설명 | 저장 시점 |
|--------|------|------|-----------|
| **id** | INTEGER (PK) | 자동 증가 ID | - |
| **trade_id** | TEXT (FK) | trade_records 참조 | 진입 시 |
| **timeframe** | TEXT | 시간대 (5m/15m/1h) | 진입 시 |
| **rsi_value** | REAL | RSI 값 (0-100) | 진입 시 |
| **rsi_change** | REAL | RSI 변화량 | 진입 시 |
| **macd_histogram** | REAL | MACD 히스토그램 | 진입 시 |
| **macd_signal_cross** | TEXT | MACD 교차 | 진입 시 |
| **volume_ratio** | REAL | 거래량 비율 | 진입 시 |
| **ema_alignment** | TEXT | EMA 정렬 | 진입 시 |
| **bollinger_position** | TEXT | 볼린저 위치 | 진입 시 |
| **created_at** | TEXT | 생성 시간 | 진입 시 |

### 2.6 인덱스 및 뷰

#### 인덱스:
- `idx_indicator_patterns`: (timeframe, rsi_value, volume_ratio) - 패턴 검색 최적화

#### 뷰:
- `scenario_success_rates`: 시나리오별 성공률 집계 뷰

---

## 3. dashboard.db - 대시보드 데이터베이스

### 3.1 dashboard_sessions 테이블 (세션 관리)

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| **id** | INTEGER (PK) | 자동 증가 ID |
| **username** | VARCHAR | 사용자명 |
| **session_token** | VARCHAR | 세션 토큰 |
| **created_at** | DATETIME | 생성 시간 |
| **last_active** | DATETIME | 마지막 활동 |
| **is_active** | BOOLEAN | 활성 상태 |

### 3.2 performance_metrics 테이블 (성과 지표)

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| **id** | INTEGER (PK) | 자동 증가 ID |
| **timestamp** | DATETIME | 측정 시간 |
| **ai_pnl** | FLOAT | AI 손익 |
| **buyhold_pnl** | FLOAT | Buy & Hold 손익 |
| **benchmark_pnl** | FLOAT | 벤치마크 손익 |
| **sharpe_ratio** | FLOAT | 샤프 비율 |
| **max_drawdown** | FLOAT | 최대 낙폭 |
| **win_rate** | FLOAT | 승률 |
| **total_trades** | INTEGER | 총 거래 수 |

---

## 4. 데이터 흐름과 관계

### 4.1 거래 생명주기별 데이터 저장

```
1. 거래 진입
   ├── trade_records (기본 정보)
   ├── market_classifications (시장 분류)
   └── indicator_snapshots (지표 스냅샷)

2. 거래 진행
   └── (실시간 추적, DB 업데이트 없음)

3. 거래 청산
   ├── trade_records (UPDATE: 결과, 손익)
   ├── scenario_outcomes (시나리오 평가)
   └── trade_analyses (선택적 AI 분석)

4. 사후 분석
   └── dashboard.db → performance_metrics
```

### 4.2 테이블 간 관계

```
trade_records (1) ─┬─ (1) market_classifications
                   ├─ (0..1) trade_analyses
                   ├─ (0..1) scenario_outcomes
                   └─ (0..N) indicator_snapshots
```

---

## 5. 주요 쿼리 패턴

### 5.1 유사 거래 검색
```sql
SELECT tr.*, mc.trend_type, mc.volatility_level
FROM trade_records tr
JOIN market_classifications mc ON tr.trade_id = mc.trade_id
WHERE mc.trend_type = ?
AND ABS(mc.chartist_score - ?) <= 15
AND ABS(mc.journalist_score - ?) <= 2
ORDER BY tr.created_at DESC
LIMIT ?
```

### 5.2 시나리오 성공률
```sql
SELECT 
    scenario_type,
    COUNT(*) as total,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
    AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 as success_rate
FROM scenario_outcomes
GROUP BY scenario_type
```

### 5.3 성과 통계
```sql
SELECT 
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl_percent > 0 THEN 1 ELSE 0 END) as wins,
    AVG(pnl_percent) as avg_pnl,
    MAX(pnl_percent) as best_trade,
    MIN(pnl_percent) as worst_trade
FROM trade_records
WHERE exit_time IS NOT NULL
```

---

## 6. 데이터 무결성 및 제약사항

### 6.1 제약사항
- trade_id는 UNIQUE (중복 불가)
- 외래키 제약으로 참조 무결성 보장
- NOT NULL 제약으로 필수 필드 보장

### 6.2 데이터 검증
- 진입가/청산가는 양수여야 함
- 레버리지는 1-125 범위
- 날짜는 ISO 형식
- JSON 필드는 유효한 JSON

---

## 7. 성능 고려사항

### 7.1 인덱스 최적화
- 자주 검색되는 컬럼에 인덱스 생성
- 복합 인덱스로 패턴 검색 최적화

### 7.2 데이터 증가 관리
- 일일 약 10-20개 거래 기록
- 연간 약 5,000개 레코드 예상
- SQLite는 충분히 처리 가능

---

## 8. 결론

델파이의 데이터베이스 구조는 **체계적이고 확장 가능**하게 설계되었습니다. 거래의 전체 생명주기를 추적하며, 분석과 학습에 필요한 모든 데이터를 저장합니다.

주요 특징:
- ✅ 정규화된 테이블 구조
- ✅ 명확한 관계 정의
- ✅ 확장 가능한 JSON 필드
- ✅ 성능 최적화 인덱스

개선 제안:
- 파티셔닝 고려 (데이터 증가 시)
- 아카이빙 전략 수립
- 실시간 집계 테이블 추가