-- 델파이 트레이딩 시스템 v2 스키마
-- 시나리오 기반 학습 시스템을 위한 DB 확장
-- Created: 2025-01-13

-- 1. 기존 테이블 확장
-- SQLite는 한 번에 하나의 컬럼만 추가 가능
ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS selected_scenario TEXT;
ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS scenario_confidence REAL;
ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS max_favorable_excursion REAL;
ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS max_adverse_excursion REAL;

-- 2. 시나리오 추적 테이블
CREATE TABLE IF NOT EXISTS scenario_tracking (
    trade_id TEXT PRIMARY KEY,
    chartist_scenarios TEXT,     -- JSON: 3개 시나리오 전체
    selected_scenario TEXT,      -- 선택된 시나리오
    selection_reason TEXT,       -- Synthesizer의 선택 이유
    invalidation_price REAL,     -- 무효화 가격
    target_prices TEXT,          -- JSON: 목표가들
    actual_outcome TEXT,         -- 실제 발생한 시나리오
    accuracy_score REAL,         -- 예측 정확도
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 포지션 스냅샷 테이블 (15분마다 기록)
CREATE TABLE IF NOT EXISTS position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT,
    timestamp TEXT,
    current_price REAL,
    pnl_percent REAL,
    current_mdd REAL,
    current_mfe REAL,
    scenario_status TEXT,        -- on_track/warning/invalidated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 포지션 스냅샷에 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_trade_time ON position_snapshots(trade_id, timestamp);

-- 4. 시장 컨텍스트 테이블
CREATE TABLE IF NOT EXISTS market_context (
    trade_id TEXT PRIMARY KEY,
    -- 객관적 지표
    atr_value REAL,
    atr_percentile REAL,
    volume_ratio REAL,
    -- 트렌드 지표
    trend_strength INTEGER,      -- -4 to 4
    ma20_slope REAL,
    price_vs_ma20 REAL,
    -- 구조적 위치
    distance_from_high20 REAL,
    distance_from_low20 REAL,
    structural_position TEXT,    -- breakout/breakdown/middle/support
    -- 시간 정보
    hour_of_day INTEGER,
    day_of_week INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 주간 성과 리포트 테이블 (선택적)
CREATE TABLE IF NOT EXISTS weekly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number TEXT,            -- 예: '2025-W03'
    total_trades INTEGER,
    win_rate REAL,
    avg_mdd REAL,
    best_scenario TEXT,
    worst_scenario TEXT,
    report_data TEXT,            -- JSON: 전체 리포트 데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 시나리오 추적에 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_scenario_type ON scenario_tracking(selected_scenario);
CREATE INDEX IF NOT EXISTS idx_scenario_outcome ON scenario_tracking(actual_outcome);

-- 시장 컨텍스트에 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_trend_strength ON market_context(trend_strength);
CREATE INDEX IF NOT EXISTS idx_structural_pos ON market_context(structural_position);