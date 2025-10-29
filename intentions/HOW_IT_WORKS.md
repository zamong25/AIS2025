# 델파이 트레이더 - 작동 원리

## 🔄 전체 작동 흐름

```
[스케줄러] → [시장 데이터 수집] → [5개 AI 에이전트 분석] → [신디사이저 종합]
     ↓                                                            ↓
[트리거 설정] ← [HOLD 결정]                    [거래 실행] ← [BUY/SELL 결정]
     ↓                                              ↓
[트리거 감시] → [트리거 발동] → [빠른 재평가]      [포지션 모니터링]
                                                    ↓
                                              [청산 실행]
```

## 📅 정기 실행 (15분마다)

### 1. 데이터 수집
```python
# 수집하는 데이터
- 현재가, 거래량
- 5분/15분/1시간/4시간/1일 캔들
- 기술적 지표 (RSI, MACD, 볼린저밴드 등)
- 최근 뉴스 (API로 수집)
- 시장 심리 지표
```

### 2. AI 에이전트 분석
각 에이전트가 독립적으로 분석하여 리포트 생성:

#### 차티스트 (기술적 분석)
```json
{
  "trend": "상승",
  "support": 100.5,
  "resistance": 105.0,
  "patterns": ["상승 삼각형", "골든크로스"],
  "signal": "BUY",
  "confidence": 75
}
```

#### 저널리스트 (펀더멘털 분석)
```json
{
  "sentiment": "긍정적",
  "major_news": ["대형 파트너십 발표"],
  "market_mood": 7,
  "signal": "BUY",
  "confidence": 65
}
```

#### 퀀트 (통계적 분석)
```json
{
  "statistical_edge": 1.3,
  "similar_patterns_winrate": 68,
  "optimal_position_size": 8.5,
  "signal": "BUY",
  "confidence": 70
}
```

#### 스토익 (리스크 평가)
```json
{
  "risk_score": 3,
  "max_position_allowed": 10,
  "stop_loss_required": 98.0,
  "approval": "YES"
}
```

### 3. 신디사이저 최종 결정

#### 결정 프로세스
```python
def synthesize_decision(reports):
    # 1. 모든 신호 수집
    signals = extract_signals(reports)
    
    # 2. 가중 평균 신뢰도 계산
    weighted_confidence = calculate_weighted_confidence(signals)
    
    # 3. 리스크 체크
    if not stoic_approves(reports['stoic']):
        return "HOLD"
    
    # 4. 최종 결정
    if weighted_confidence > 70:
        return "BUY" or "SELL"
    elif 50 < weighted_confidence <= 70:
        return "HOLD_WITH_TRIGGERS"
    else:
        return "HOLD"
```

## 🎯 거래 실행

### BUY/SELL 결정 시
1. **포지션 크기 계산**
   ```
   포지션 크기 = (총 자본 × 리스크%) / 손절 거리
   ```

2. **주문 실행**
   - Market 주문 또는 Limit 주문
   - 동시에 손절/익절 주문 설정 (OCO)

3. **기록 저장**
   - 진입 시점의 모든 데이터 저장
   - 거래 근거 상세 기록

### HOLD 결정 시
1. **멀티 시나리오 트리거 생성**
   ```python
   triggers = [
       {"scenario": "상승", "price": 102.0, "probability": 45},
       {"scenario": "하락", "price": 98.0, "probability": 35},
       {"scenario": "박스권", "price_range": [99.0, 101.0], "probability": 20}
   ]
   ```

2. **트리거 모니터링**
   - 실시간 가격 감시
   - 트리거 조건 충족 시 알림

## 📊 포지션 관리

### 진입 후 모니터링
```python
every_15_minutes:
    - 현재 손익 계산
    - MDD/MFE 추적
    - 시장 상황 재평가
    - 손절/익절 조정 검토
```

### 청산 조건
1. **손절가 도달**: 즉시 청산
2. **익절가 도달**: 단계적 청산
3. **시간 기반**: 48시간 이상 정체 시
4. **신호 변경**: 반대 신호 강하게 발생

## 🔔 트리거 시스템

### 트리거 종류
1. **가격 트리거**: 특정 가격 돌파
2. **시간 트리거**: 특정 시간대
3. **조건 트리거**: 복합 조건 충족
4. **긴급 트리거**: 급격한 변동

### 트리거 발동 시
```python
def on_trigger_activated(trigger):
    # 1. 빠른 재평가 (10초 이내)
    quick_analysis = quick_reassess(trigger, current_market)
    
    # 2. 진입 결정
    if quick_analysis.confidence > 80:
        execute_trade(quick_analysis)
    else:
        set_closer_trigger()  # 더 가까운 트리거 설정
```

## 💾 데이터 관리

### 실시간 데이터
- Redis 캐시에 최근 데이터 유지
- 5초마다 가격 업데이트

### 이력 데이터
- SQLite에 모든 거래 기록
- 일별 시장 데이터 압축 저장
- 분석 결과 30일 보관

### 학습 데이터
- 거래 결과와 시장 상황 매칭
- 성공/실패 패턴 분석
- 전략 개선에 활용

## 🛡️ 안전 장치

### 1. 포지션 제한
- 동시 포지션 1개만
- 최대 자본 10% 제한
- 일일 거래 횟수 제한

### 2. 긴급 정지
- 일일 손실 5% 초과 시
- 연속 3회 손실 시
- 시스템 오류 감지 시

### 3. 복구 메커니즘
- 자동 재시작
- 포지션 상태 복구
- 미체결 주문 정리

---

**"단순하지만 견고하게, 자동이지만 안전하게"**