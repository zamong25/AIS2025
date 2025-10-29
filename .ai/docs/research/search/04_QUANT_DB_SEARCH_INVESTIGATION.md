# 퀀트 에이전트의 DB 검색 메커니즘 조사 보고서

> 작성일: 2025-01-12  
> 조사자: Claude AI Assistant

## 요약

퀀트 에이전트의 DB 검색 기능은 **문서 작성 당시에는 하드코딩된 문제가 있었으나, 현재는 관련 파일이 삭제된 상태**입니다. `src/utils/quant_db_search.py` 파일이 더 이상 존재하지 않으며, 이 기능은 시스템에서 제거되었습니다.

---

## 1. DB 검색 구현 현황

### 1.1 주요 함수: `_query_historical_data()` (현재 삭제됨)
**위치**: `src/agents/quant.py:169-213` (파일이 더 이상 존재하지 않음)

```python
def _query_historical_data(self, chartist_json: dict, journalist_json: dict) -> Optional[dict]:
    """과거 거래 데이터 조회"""
    
    # 문제: 하드코딩된 가짜 데이터
    current_conditions = {
        'atr_1h': 1.0,  # 실제로는 current_market_data에서 가져와야 함
        'current_price': 150.0,
        'volume_ratio': 1.0
    }
    
    # 현재 에이전트 점수
    current_scores = {
        'chartist_score': chartist_json.get('quantitative_scorecard', {}).get('overall_bias_score', 50),
        'journalist_score': journalist_json.get('quantitative_scorecard', {}).get('overall_contextual_bias', {}).get('score', 5)
    }
    
    # 유사한 거래 검색
    similar_trades = trade_db.find_similar_trades(current_conditions, current_scores, limit=10)
```

### 1.2 핵심 문제점

**🔴 하드코딩된 조건**
- ATR: 항상 1.0 (실제 변동성 무시)
- 가격: 항상 150.0 (실제 가격 무시)
- 거래량 비율: 항상 1.0 (실제 거래량 무시)

이는 실제 시장 상황과 전혀 무관한 검색 결과를 만듭니다.

---

## 2. DB 검색 프로세스

### 2.1 검색 기준

#### A. 추세 분류
```python
# 차티스트 점수 기반 분류
if current_chartist >= 65:
    trend_type = "UPTREND"
elif current_chartist <= 35:
    trend_type = "DOWNTREND"
else:
    trend_type = "SIDEWAYS"
```

#### B. 유사도 범위
- 차티스트 점수: ±15점
- 저널리스트 점수: ±2점

### 2.2 실제 SQL 쿼리
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

### 2.3 검색 결과 처리
```python
# 통계 정보 생성
if similar_trades:
    # 방향별 통계
    long_trades = [t for t in similar_trades if t['direction'] == 'LONG']
    short_trades = [t for t in similar_trades if t['direction'] == 'SHORT']
    
    # 승률, 평균 수익률 계산
    long_win_rate = sum(1 for t in long_trades if t['pnl_percent'] > 0) / len(long_trades) * 100
    long_avg_return = sum(t['pnl_percent'] for t in long_trades) / len(long_trades)
```

---

## 3. 프롬프트 분석

### 3.1 quant_v3.txt의 DB 검색 지시사항

프롬프트는 명확하게 DB 검색 결과를 활용하도록 지시합니다:

```json
"db_analysis": {
    "similar_patterns_found": 15,
    "pattern_outcomes": {
        "long_trades": {
            "count": 10,
            "win_rate": 70.0,
            "avg_return": 3.2,
            "max_return": 8.5,
            "max_loss": -2.1,
            "avg_duration_hours": 3.5
        },
        "short_trades": {
            "count": 5,
            "win_rate": 40.0,
            "avg_return": -0.8
        }
    },
    "recommendation": "과거 유사 패턴에서 LONG의 승률이 70%로 높음"
}
```

### 3.2 프롬프트와 구현의 불일치

- **프롬프트**: 실제 시장 데이터 기반 검색 기대
- **구현**: 하드코딩된 가짜 조건으로 검색
- **결과**: 무의미한 통계 정보 생성

---

## 4. 실제 작동 여부 검증

### 4.1 ✅ 작동하는 부분
1. **DB 연결**: SQLite 연결 정상
2. **SQL 실행**: 쿼리 실행 및 결과 반환
3. **통계 계산**: 검색된 거래의 통계 생성
4. **JSON 출력**: 형식에 맞는 결과 반환

### 4.2 ❌ 작동하지 않는 부분
1. **실제 시장 데이터 사용**: 하드코딩된 값 사용
2. **의미 있는 검색**: 현재 상황과 무관한 결과
3. **패턴 학습**: 개별 거래 패턴 분석 없음
4. **구체적 활용**: 통계만 제공, 구체적 전략 없음

---

## 5. 개선 방안

### 5.1 즉시 수정 가능한 부분

```python
# 현재 (문제)
current_conditions = {
    'atr_1h': 1.0,  # 하드코딩
    'current_price': 150.0,
    'volume_ratio': 1.0
}

# 개선안
current_conditions = {
    'atr_1h': current_market_data.get('atr_14', 0),
    'current_price': current_market_data.get('current_price', 0),
    'volume_ratio': current_market_data.get('volume_vs_24h_avg_ratio', 1.0)
}
```

### 5.2 추가 개선 사항

#### A. 더 정교한 검색 조건
```python
# 변동성 수준 추가
volatility_level = classify_volatility(current_market_data['atr_14'])

# 거래량 프로파일 추가
volume_profile = classify_volume(current_market_data['volume_24h'])

# 시간대 패턴 추가
hour_of_day = datetime.now().hour
```

#### B. 향상된 패턴 매칭
```sql
-- 더 복잡한 유사도 검색
SELECT * FROM trade_records
WHERE 
    ABS(volatility_at_entry - ?) < 0.5
    AND timeframe_alignment = ?
    AND HOUR(entry_time) BETWEEN ? AND ?
    AND market_regime = ?
```

#### C. 검색 결과의 구체적 활용
```python
def extract_trading_patterns(similar_trades):
    """유사 거래에서 구체적 패턴 추출"""
    patterns = {
        'entry_conditions': analyze_entry_patterns(similar_trades),
        'exit_conditions': analyze_exit_patterns(similar_trades),
        'risk_parameters': analyze_risk_patterns(similar_trades),
        'timing_patterns': analyze_timing_patterns(similar_trades)
    }
    return patterns
```

---

## 6. 영향도 분석

### 6.1 현재 상태의 영향
- **낮은 영향**: 하드코딩된 검색이므로 일관된 결과
- **무의미한 참조**: 실제 시장과 무관한 통계
- **잠재력 낭비**: DB에 축적된 데이터 미활용

### 6.2 개선 시 기대 효과
- **맞춤형 전략**: 현재 상황에 맞는 과거 사례 참조
- **학습 효과**: 성공/실패 패턴 활용
- **적응형 거래**: 시장 상황별 최적 전략 적용

---

## 7. 구현 우선순위

### 7.1 단기 (1주일)
1. **하드코딩 제거**: 실제 시장 데이터 연결
2. **기본 검증**: 검색 결과의 관련성 테스트

### 7.2 중기 (1개월)
1. **검색 조건 확대**: 변동성, 거래량, 시간대 추가
2. **패턴 추출**: 구체적 거래 패턴 분석

### 7.3 장기 (3개월)
1. **머신러닝 통합**: 유사도 계산 고도화
2. **실시간 학습**: 새로운 거래 결과 즉시 반영

---

## 8. 결론

퀀트 에이전트의 DB 검색은 **"껍데기는 있지만 알맹이가 없는"** 상태입니다.

### 핵심 발견:
1. **인프라는 완성**: DB, SQL, 통계 계산 모두 작동
2. **데이터 연결 문제**: 하드코딩으로 실제 데이터 미사용
3. **즉시 개선 가능**: 간단한 코드 수정으로 큰 개선 가능

### 권장사항:
가장 시급한 것은 `current_conditions`의 하드코딩을 제거하고 실제 시장 데이터를 연결하는 것입니다. 이는 몇 줄의 코드 수정으로 가능하며, 즉각적인 개선 효과를 가져올 수 있습니다.

현재는 "과거를 보지만 현재를 모르는" 시스템입니다. 실제 시장 데이터와 연결하면 진정한 의미의 패턴 매칭이 가능해집니다.