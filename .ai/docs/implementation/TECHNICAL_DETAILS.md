# 🔧 델파이 시스템 기술 상세

> 최종 업데이트: 2025-01-12  
> 대상: 시스템 개발/유지보수 담당자

## 📋 목차
1. [핵심 기술 구현](#핵심-기술-구현)
2. [중요 코드 패턴](#중요-코드-패턴)
3. [데이터 구조](#데이터-구조)
4. [성능 최적화](#성능-최적화)
5. [보안 구현](#보안-구현)
6. [알려진 기술적 이슈](#알려진-기술적-이슈)

---

## 핵심 기술 구현

### 1. 가짜 학습 시스템 (⚠️ 치명적 문제)

#### 현재 구현 (문제)
```python
# 삭제된 agent_weight_manager.py의 코드
def adjust_weights(self):
    for agent in self.agents:
        # 실제 성과와 무관한 랜덤 조정
        success_rate = 0.5 + (random.random() - 0.5) * 0.2
        self.weights[agent] *= (1 + success_rate * 0.1)
```

#### 필요한 구현
```python
class RealLearningSystem:
    def calculate_agent_contribution(self, trade_result, agent_reports):
        """각 에이전트의 실제 기여도 계산"""
        contributions = {}
        
        # 차티스트: 시나리오 정확도
        actual_movement = trade_result['price_change']
        predicted_scenario = agent_reports['chartist']['winning_scenario']
        accuracy = self.calculate_scenario_accuracy(actual_movement, predicted_scenario)
        contributions['chartist'] = accuracy
        
        # 퀀트: 지지도와 실제 결과 일치도
        quant_support = agent_reports['quant']['support_level']
        contributions['quant'] = self.calculate_support_accuracy(quant_support, trade_result)
        
        return contributions
```

### 2. 시나리오 기반 분석 시스템

#### 차티스트 구현
```python
# src/agents/chartist.py
def analyze_scenarios(self, chart_data):
    scenarios = []
    
    # 3가지 시나리오 생성
    for scenario_type in ['bullish', 'bearish', 'sideways']:
        scenario = {
            'type': scenario_type,
            'probability': self.calculate_probability(chart_data, scenario_type),
            'entry_price': self.find_entry_point(chart_data, scenario_type),
            'target_price': self.calculate_target(chart_data, scenario_type),
            'stop_loss': self.calculate_stop_loss(chart_data, scenario_type)
        }
        scenarios.append(scenario)
    
    # 확률 정규화 (합계 100%)
    total_prob = sum(s['probability'] for s in scenarios)
    for s in scenarios:
        s['probability'] = (s['probability'] / total_prob) * 100
    
    return scenarios
```

### 3. Trading Context 시스템

#### 포지션 생명주기 관리
```python
# src/data/trading_context.py
@dataclass
class TradingThesis:
    """거래 진입 시점의 가설과 계획"""
    trade_id: str
    entry_time: str
    direction: str  # LONG/SHORT
    
    # 진입 정보
    entry_price: float
    entry_reason: str
    
    # 핵심 시나리오
    primary_scenario: str
    target_price: float
    stop_loss: float
    
    # 무효화 조건
    invalidation_condition: str
    invalidation_price: float
```

### 4. Position State Manager (Single Source of Truth)

#### 상태 우선순위
```python
def get_current_position(self, symbol: str = "SOLUSDT") -> Optional[Dict]:
    """
    현재 포지션 상태를 반환 (진실의 단일 소스)
    
    우선순위:
    1. 바이낸스 API (실제 포지션)
    2. Trading Context (의도와 계획)
    3. DB (거래 기록)
    """
    
    # 1. 바이낸스에서 실제 포지션 조회
    binance_position = self._get_binance_position(symbol)
    
    if not binance_position:
        # 포지션이 없으면 정리 작업
        self._cleanup_stale_data()
        return None
```

### 5. OCO 주문 시스템

#### 자동 리스크 관리
```python
# src/trading/oco_order_manager.py
def place_oco_order(self, position_info: Dict) -> Dict:
    """
    OCO (One-Cancels-Other) 주문 실행
    - 익절 주문과 손절 주문을 동시에 설정
    - 한쪽이 체결되면 다른 쪽은 자동 취소
    """
    
    # 정밀도 조정 (SOL의 경우 특별 처리)
    if symbol == "SOLUSDT":
        quantity = round(quantity, 2)  # 소수점 2자리
```

---

## 중요 코드 패턴

### 1. 비동기 처리 제안
```python
# 현재: 동기 처리
results = []
for agent in agents:
    results.append(agent.analyze())

# 개선: 비동기 처리
async def run_analysis():
    tasks = [agent.analyze_async() for agent in agents]
    results = await asyncio.gather(*tasks)
    return results
```

### 2. 에러 처리 패턴
```python
# 표준 에러 처리
try:
    result = binance_api.get_position()
except BinanceAPIException as e:
    if e.code == -2019:  # Margin insufficient
        logger.error("마진 부족")
        return self._handle_insufficient_margin()
    else:
        raise
```

### 3. 캐싱 패턴
```python
# 멀티 타임프레임 데이터 캐싱
class MultiTimeframeCache:
    def __init__(self):
        self.cache = TTLCache(maxsize=100, ttl=60)  # 1분 캐시
    
    @cached(cache)
    def get_indicators(self, symbol, timeframe):
        return calculate_indicators(symbol, timeframe)
```

---

## 데이터 구조

### 1. 에이전트 보고서 형식
```json
{
  "chartist": {
    "scenarios": [
      {
        "type": "bullish",
        "probability": 45,
        "entry_price": 150.5,
        "target_price": 155.0,
        "stop_loss": 148.0
      }
    ],
    "winning_scenario": "bullish"
  },
  "quant": {
    "support_level": "strong",
    "indicators": {
      "rsi": {"5m": 45, "15m": 52, "1h": 58},
      "macd": {"signal": "bullish_divergence"}
    }
  }
}
```

### 2. Trading Context 저장 형식
```json
{
  "thesis": {
    "trade_id": "DELPHI_20250112_143021",
    "entry_time": "2025-01-12T14:30:21",
    "direction": "LONG",
    "entry_price": 150.5,
    "primary_scenario": "돌파 후 상승",
    "target_price": 155.0,
    "stop_loss": 148.0
  },
  "history": [
    {
      "update_time": "2025-01-12T14:45:00",
      "price_at_update": 151.2,
      "scenario_progress": "ON_TRACK",
      "progress_percentage": 14.0
    }
  ]
}
```

### 3. 데이터베이스 스키마
```sql
-- trades 테이블
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity REAL NOT NULL,
    leverage INTEGER NOT NULL,
    pnl REAL,
    pnl_percent REAL,
    status TEXT NOT NULL,
    entry_reason TEXT,
    exit_reason TEXT
);

-- agent_scores 테이블
CREATE TABLE agent_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    chartist_score REAL,
    journalist_score REAL,
    quant_score REAL,
    stoic_score REAL,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);
```

---

## 성능 최적화

### 1. API 호출 최적화
```python
# 배치 API 호출
def get_multiple_symbols_data(symbols):
    # 나쁜 예: 개별 호출
    # for symbol in symbols:
    #     data[symbol] = client.futures_ticker(symbol=symbol)
    
    # 좋은 예: 배치 호출
    return client.futures_ticker()  # 모든 심볼 한번에
```

### 2. 데이터 캐싱 전략
- **가격 데이터**: 5초 캐시
- **지표 데이터**: 60초 캐시
- **뉴스 데이터**: 5분 캐시
- **차트 이미지**: 15분 캐시

### 3. 메모리 관리
```python
# 대용량 데이터 처리 시
def process_large_dataset(data):
    # 청크 단위로 처리
    chunk_size = 1000
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        process_chunk(chunk)
        
        # 명시적 가비지 컬렉션
        if i % 10000 == 0:
            gc.collect()
```

---

## 보안 구현

### 1. API 키 관리
```python
# .env 파일
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here

# 코드에서 사용
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
```

### 2. 거래 검증
```python
def validate_trade(self, trade_params):
    """거래 실행 전 다중 검증"""
    checks = [
        self.check_position_size_limit(),     # 30% 제한
        self.check_daily_loss_limit(),        # 5% 제한
        self.check_leverage_limit(),          # 20x 제한
        self.check_market_conditions()        # 비정상 시장 체크
    ]
    return all(checks)
```

### 3. 에러 복구
```python
class AutoRecovery:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5
    
    def execute_with_retry(self, func, *args):
        for attempt in range(self.max_retries):
            try:
                return func(*args)
            except RecoverableError as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise
```

---

## 알려진 기술적 이슈

### 1. 트리거 시스템 비효율성
```python
# 현재: 15분마다 체크
scheduler.every(15).minutes.do(check_triggers)

# 필요: 실시간 체크
async def monitor_triggers():
    websocket_monitor.add_price_callback(check_price_trigger)
    await websocket_monitor.start_monitoring(['SOLUSDT'])
```

### 2. Discord 알림 타임아웃
```python
# 문제: 10초 타임아웃으로 실패
# 해결: 타임아웃 연장 및 재시도
response = requests.post(
    webhook_url, 
    json=data, 
    timeout=30,  # 30초로 연장
    retry=3      # 3회 재시도
)
```

### 3. 차트 캡처 안정성
```python
# XPath 동적 변경 대응
def find_symbol_input():
    selectors = [
        '//*[@id="header-toolbar-symbol-search"]/div/input',
        '//input[@class="search-ZXK7YV7S"]',
        '//input[contains(@placeholder, "Symbol")]'
    ]
    
    for selector in selectors:
        try:
            element = driver.find_element(By.XPATH, selector)
            if element:
                return element
        except:
            continue
```

---

## 개발 팁

### 1. 로깅 레벨
- **DEBUG**: 개발 중 상세 정보
- **INFO**: 일반 실행 정보
- **WARNING**: 주의가 필요한 상황
- **ERROR**: 에러 발생
- **CRITICAL**: 시스템 중단 위험

### 2. 테스트 우선순위
1. 거래 실행 로직
2. 리스크 관리 시스템
3. API 연동
4. 에이전트 분석
5. UI/알림

### 3. 디버깅 도구
```python
# 실시간 로그 모니터링
tail -f logs/delphi.log | grep ERROR

# 포지션 상태 확인
python -c "from src.trading.position_state_manager import *; print(get_current_position())"

# API 연결 테스트
python scripts/test_api_connection.py
```

---

*이 문서는 시스템의 기술적 세부사항을 다룹니다. 전체적인 이해는 [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)를 참조하세요.*