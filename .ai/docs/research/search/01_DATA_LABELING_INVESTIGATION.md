# 델파이 시스템 데이터 라벨링 및 DB 저장 현황 조사

## 1. DB 스키마 분석

### 1.1 trade_records 테이블 주요 컬럼
```sql
-- 기본 거래 정보
trade_id, asset, entry_price, exit_price, direction, leverage, 
position_size_percent, entry_time, exit_time, outcome, rr_ratio, 
pnl_percent, market_conditions, agent_scores, stop_loss_price, 
take_profit_price, max_drawdown_percent

-- Phase 3 추가 컬럼들
strategy_mode, timeframe_alignment, conflict_narrative, 
volatility_at_entry, market_regime, exploration_trade, 
adaptive_thresholds, auto_lesson

-- ATR 기반 리스크 관리 컬럼들
time_to_stop_minutes, stop_loss_type, position_management_quality,
atr_at_entry, stop_distance_percent
```

### 1.2 market_classifications 테이블
```sql
trade_id, trend_type, volatility_level, volume_profile,
chartist_score, journalist_score
```

## 2. 실제 데이터 저장 현황

### 2.1 ✅ 정상적으로 저장되는 데이터

1. **기본 거래 정보** (save_trade_record)
   - trade_id, asset, prices, direction, leverage 등
   - outcome: "TP_HIT", "SL_HIT", "TIME_EXIT", "MANUAL_EXIT", "WIN", "LOSS"로 세분화
   - market_conditions, agent_scores는 JSON 형태로 저장

2. **시장 분류 정보** (market_classifications)
   - _classify_market_conditions()에서 자동 분류하여 저장
   - trend_type: UPTREND/DOWNTREND/SIDEWAYS
   - volatility_level: HIGH/MEDIUM/LOW
   - volume_profile: HIGH/NORMAL/LOW

3. **거래 완료 후 라벨링** (label_completed_trade)
   - time_to_stop_minutes: 거래 시간 계산
   - stop_loss_type: NOISE/QUICK/NORMAL/LATE
   - position_management_quality: GOOD/POOR
   - stop_distance_percent: 계산 저장

4. **향상된 거래 기록** (save_enhanced_record)
   - strategy_mode, timeframe_alignment
   - conflict_narrative, volatility_at_entry
   - market_regime: HIGH_VOLATILITY/LOW_VOLATILITY/STRONG_TREND/RANGE_BOUND/NORMAL
   - auto_lesson: 자동 생성된 교훈

### 2.2 ❌ 누락되거나 잘못된 데이터

1. **MDD (Maximum Drawdown)**
   - DB 스키마에는 max_drawdown_percent 컬럼 존재
   - 실제로는 항상 0 또는 하드코딩된 값으로 저장
   - 실시간 MDD 추적 로직 없음

2. **에이전트 개별 신호**
   - chartist_signal, journalist_signal 등의 컬럼이 DB에 없음
   - agent_scores에 점수만 저장, 실제 신호 내용은 누락
   - save_trade_with_metadata()에서 metadata 수집하지만 활용 안 됨

3. **exploration_trade**
   - DB 컬럼은 있지만 더 이상 사용하지 않음
   - main.py에서 'exploration_mode' 주석 처리됨
   - EnhancedTradeDatabase에서만 부분적으로 사용

4. **adaptive_thresholds**
   - DB에 저장하지만 빈 딕셔너리 {} 로 저장
   - 퀀트 에이전트의 적응형 임계값 연동 안 됨

5. **ATR 정보**
   - atr_at_entry는 None으로 저장
   - 실제 ATR 데이터 수집 로직 없음

### 2.3 🔄 불일치하는 데이터

1. **strategy_mode**
   - 현재 시스템: conflict_context.strategy.mode에서 가져옴
   - 실제 값: SHORT_TERM, SWING, POSITION 등
   - 문제: 신디사이저의 전략 결정과 연동 불완전

2. **position_size_percent**
   - DB 저장 시: execution_plan에서 가져옴
   - 포지션 청산 시: 기본값 5%로 하드코딩
   - 실제 사용된 포지션 크기와 불일치 가능

3. **agent_scores**
   - 저장 형식 불일치: quantitative_scorecard vs 실제 구조
   - journalist_score가 overall_contextual_bias.score로 접근

## 3. 주요 문제점 및 개선 필요사항

### 3.1 긴급 수정 필요
1. **MDD 추적 구현**
   - 포지션 모니터링 중 실시간 MDD 계산
   - 거래 종료 시 정확한 max_drawdown_percent 저장

2. **에이전트 신호 저장**
   - agent_signals 테이블 생성 또는 JSON 필드 확장
   - 각 에이전트의 실제 분석 내용 저장

3. **ATR 데이터 연동**
   - market_data에서 ATR 값 추출
   - atr_at_entry 필드에 실제 값 저장

### 3.2 중요 개선사항
1. **adaptive_thresholds 연동**
   - 퀀트 에이전트의 동적 임계값 저장
   - 거래 결정에 사용된 실제 임계값 기록

2. **position_size_percent 일관성**
   - 실제 사용된 포지션 크기 정확히 기록
   - 청산 시에도 정확한 값 사용

3. **exploration_trade 정리**
   - 사용하지 않는 필드 제거 또는
   - 새로운 의미로 재정의 (예: experimental_trade)

### 3.3 데이터 품질 향상
1. **거래 시간대 정보 추가**
   - 뉴욕/런던/아시아 세션 구분
   - 거래 시간대별 성과 분석 가능

2. **상세 비용 정보**
   - 슬리피지, 수수료 개별 저장
   - 실제 거래 비용 분석 강화

3. **포지션 진행 중 이벤트**
   - 부분 청산, 추가 진입 등 기록
   - 포지션 수명주기 완전 추적

## 4. 결론

현재 델파이 시스템은 기본적인 거래 데이터는 잘 저장하고 있으나, 고급 분석에 필요한 상세 데이터(MDD, 에이전트 신호, ATR 등)의 수집과 저장이 미흡합니다. 특히 실시간 추적이 필요한 데이터(MDD, 포지션 상태 변화)와 에이전트별 상세 분석 내용의 보존이 시급히 개선되어야 합니다.