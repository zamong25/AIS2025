# 디버그 추적 문서

## SmartScheduler 디버그 포인트

### 파일: src/utils/smart_scheduler.py

1. **초기화 로그** (라인 26)
   - `self.logger.info(f"SmartScheduler 초기화: 최소 간격 {min_interval_minutes}분")`
   - 용도: 스케줄러가 올바른 간격으로 초기화되었는지 확인

2. **히스토리 파일 생성** (라인 38)
   - `self.logger.info(f"AI 호출 히스토리 파일 생성: {self.call_history_file}")`
   - 용도: 히스토리 파일이 정상적으로 생성되었는지 확인

3. **첫 호출 감지** (라인 56)
   - `self.logger.info("첫 AI 호출 - 실행 허용")`
   - 용도: 첫 번째 AI 호출인지 확인

4. **쿨다운 체크** (라인 64-75)
   - 실행 허용: `self.logger.info(f"마지막 호출로부터 {time_since_last.total_seconds()/60:.1f}분 경과 - 실행 허용")`
   - 실행 거부: `self.logger.warning(f"마지막 호출로부터 {time_since_last.total_seconds()/60:.1f}분만 경과 - {remaining:.1f}분 더 대기 필요")`
   - 용도: 쿨다운 로직이 정상 작동하는지 확인

5. **AI 호출 기록** (라인 108)
   - `self.logger.info(f"AI 호출 기록: {call_type} {trigger_id}")`
   - 용도: 모든 AI 호출이 정상적으로 기록되는지 확인

6. **히스토리 정리** (라인 100)
   - `self.logger.debug("히스토리 100개 초과 - 오래된 기록 삭제")`
   - 용도: 메모리 관리가 정상 작동하는지 확인

7. **통계 조회** (라인 144)
   - `self.logger.debug(f"최근 {hours}시간 AI 호출 통계: {stats['total_calls']}회")`
   - 용도: 통계 집계가 정확한지 확인

8. **에러 처리** (라인 40, 111, 153, 178, 194, 206, 217)
   - 각종 에러 상황에서 로그 기록
   - 용도: 문제 발생 시 원인 파악

### 디버그 레벨
- `INFO`: 정상 동작 확인
- `WARNING`: 쿨다운으로 인한 호출 거부
- `ERROR`: 실패 상황
- `DEBUG`: 상세 동작 추적

### 디버그 활성화 방법
```python
import logging
logging.getLogger('utils.smart_scheduler').setLevel(logging.DEBUG)
```

---

## PositionTriggerManager 디버그 포인트

### 파일: src/agents/position_trigger_manager.py

1. **트리거 생성 시작** (라인 28)
   - `self.logger.info(f"포지션 트리거 생성 시작: {trade_id}, 진입가: {entry_price}, ATR: {atr}")`
   - 용도: 트리거 생성 파라미터 확인

2. **트리거 생성 완료** (라인 109-112)
   - `self.logger.info(f"[포지션 트리거 생성 완료 메시지]")`
   - 용도: 생성된 트리거 요약 정보 확인

---

## TriggerManager 디버그 포인트

### 파일: src/agents/trigger_manager.py

1. **HOLD 트리거 삭제** (라인 74)
   - `self.logger.info(f"HOLD 트리거 삭제, {len(position_triggers)}개 포지션 트리거 유지")`
   - 용도: 트리거 분리가 정상 작동하는지 확인

2. **포지션 트리거 삭제** (라인 81)
   - `self.logger.info(f"포지션 트리거 삭제, {len(hold_triggers)}개 HOLD 트리거 유지")`
   - 용도: 트리거 분리가 정상 작동하는지 확인

3. **포지션 트리거 추가** (라인 98)
   - `self.logger.info(f"{len(new_triggers)}개 포지션 트리거 추가됨")`
   - 용도: 트리거 추가가 정상적으로 이루어지는지 확인

---

## PriceHistory 디버그 포인트

### 파일: src/monitoring/price_history.py

1. **초기화** (라인 24)
   - `self.logger.info(f"PriceHistory 초기화: 최대 {max_size}개 가격 저장")`
   - 용도: 순환 버퍼 크기 확인

2. **새 심볼 추가** (라인 49)
   - `self.logger.debug(f"새 심볼 히스토리 생성: {symbol}")`
   - 용도: 새로운 심볼 추적 시작 확인

3. **가격 히스토리 크기** (라인 54-56)
   - `self.logger.debug(f"{symbol} 가격 히스토리: {len(self.symbol_histories[symbol])}개 저장됨")`
   - 용도: 10개마다 히스토리 크기 확인

4. **과거 가격 조회** (라인 89-93)
   - 성공: `self.logger.debug(f"{symbol} {minutes_ago}분 전 가격: {closest_price:.2f} (실제 {closest_time_diff/60:.1f}분 전 데이터)")`
   - 실패: `self.logger.debug(f"{symbol} {minutes_ago}분 전 가격 없음")`
   - 용도: 과거 가격 조회 정확성 확인

5. **변화율 계산** (라인 110-113)
   - `self.logger.debug(f"{symbol} {minutes}분간 변화율: {change_rate:.2f}% ({past_price:.2f} -> {current_price:.2f})")`
   - 용도: 변화율 계산 로직 검증

6. **가격 범위** (라인 151-156)
   - `self.logger.debug(f"{symbol} 최근 {minutes}분 범위: 최고 {result['high']:.2f}, 최저 {result['low']:.2f}, 데이터 {result['count']}개")`
   - 용도: 가격 범위 집계 확인

---

## SmartPositionMonitor 디버그 포인트

### 파일: src/monitoring/position_monitor.py

1. **초기화** (라인 25)
   - `self.logger.info("SmartPositionMonitor 초기화 완료")`
   - 용도: 모니터 초기화 확인

2. **긴급 상황 감지** (라인 46)
   - `self.logger.critical(f"긴급 상황 감지: {emergency_check['reason']}")`
   - 용도: 긴급 상황 발생 추적

3. **트리거 조건 충족** (라인 56-59)
   - `self.logger.info(f"트리거 조건 충족: {trigger['trigger_id']} (타입: {trigger['condition_type']})")`
   - 용도: 어떤 트리거가 발동했는지 확인

4. **최고 우선순위 트리거** (라인 69-72)
   - `self.logger.info(f"최고 우선순위 트리거: {highest_priority['trigger_id']} (긴급도: {highest_priority.get('urgency', 'low')})")`
   - 용도: 우선순위 선택 로직 확인

5. **긴급 쿨다운** (라인 112)
   - `self.logger.debug(f"긴급 알림 쿨다운 중: {remaining:.1f}분 남음")`
   - 용도: 쿨다운 작동 확인

6. **극단적 손실** (라인 122)
   - `self.logger.error(f"극단적 손실 감지: {pnl_percent:.2f}%")`
   - 용도: 손실 임계값 도달 추적

7. **플래시 크래시** (라인 135)
   - `self.logger.error(f"플래시 크래시 감지: {rapid_change:.2f}% 급변")`
   - 용도: 급격한 가격 변동 감지

8. **거래량 폭발** (라인 147)
   - `self.logger.error(f"거래량 폭발 감지: {volume_ratio:.1f}배")`
   - 용도: 비정상적 거래량 감지

9. **각 트리거 타입별 발동** (라인 168, 175, 189, 201)
   - MDD: `self.logger.debug(f"MDD 트리거: PnL {pnl:.2f}% <= {threshold}%")`
   - 이익: `self.logger.debug(f"이익 트리거: PnL {pnl:.2f}% >= {threshold}%")`
   - 시간: `self.logger.debug(f"시간 트리거: {hours_held:.1f}시간 경과, 움직임 {price_change:.2f}% < {min_movement}%")`
   - 변동성: `self.logger.debug(f"변동성 트리거: {vol_ratio:.2f}x >= {threshold_mult}x")`
   - 용도: 각 트리거 타입별 조건 충족 확인

10. **스마트 분석 조건** (라인 230, 238, 246)
    - AI 호출 초과: `self.logger.debug(f"시간당 AI 호출 초과: {stats['total_calls']}회")`
    - 시장 변화: `self.logger.info(f"시장 조건 변화 감지: {market_condition}")`
    - PnL 변화: `self.logger.info(f"의미있는 PnL 변화: {pnl:.2f}%")`
    - 용도: 스마트 분석 트리거 이유 추적

11. **쿨다운 설정/제거** (라인 295, 307)
    - 설정: `self.logger.info(f"긴급 알림 쿨다운 설정: {trade_id} - {minutes}분")`
    - 제거: `self.logger.info(f"긴급 쿨다운 제거: {trade_id}")`
    - 용도: 쿨다운 관리 추적

---

## HeartbeatChecker 포지션 모니터링 통합 디버그 포인트

### 파일: src/monitoring/heartbeat_checker.py

1. **포지션 모니터링 초기화** (라인 54-60)
   - 포지션 모니터링 시스템 컴포넌트 초기화
   - 용도: 초기화 상태 확인

2. **포지션 트리거 체크** (라인 469-499)
   - 포지션이 있을 때 포지션 트리거 체크 로직
   - `self.logger.info(f"HOLD 트리거 발동! {triggered['trigger_id']} - {triggered['rationale']}")`
   - 용도: 포지션 트리거와 HOLD 트리거 분리 확인

3. **긴급 상황 처리** (라인 864-888)
   - `self.logger.critical(f"포지션 긴급 상황 발생: {reason}")`
   - `self.logger.info("긴급 포지션 청산 완료")`
   - `self.logger.error(f"긴급 청산 실패: {close_result}")`
   - 용도: 포지션 긴급 상황 처리 추적

4. **포지션 재분석** (라인 890-928)
   - `self.logger.info(f"재분석 쿨다운 중 - {reason}")`
   - `self.logger.info(f"포지션 재분석 시작: {reason}")`
   - `self.logger.info("포지션 재분석 완료")`
   - `self.logger.warning("포지션 재분석 실패")`
   - 용도: AI 재분석 요청 및 스케줄링 추적

5. **트리거 타입 분리** (라인 472-473, 549-550)
   - 포지션 트리거 필터링: `position_triggers = [t for t in triggers if t.get('trigger_type') == 'position']`
   - HOLD 트리거 필터링: `hold_triggers = [t for t in self.trigger_manager.load_triggers() if t.get('trigger_type') != 'position']`
   - 용도: 트리거 타입별 분리 동작 확인

---

## 주문 관리 시스템 디버그 포인트 (2025-01-13 추가)

### 파일: src/trading/trade_executor.py

#### 1. 선택적 주문 취소 기능

**`_cancel_stop_orders_only()` (라인 ~450)**
- **주요 로그**:
  - `✅ 손절 주문 취소됨: {order['type']} @ ${order.get('stopPrice', 'N/A')}`
  - `⚠️ 손절 주문 취소 실패: {e}`
  - `❌ 손절 주문 조회 중 오류: {e}`
- **반환값**: 취소된 주문 수 (int)
- **주의사항**: STOP_MARKET 타입만 취소

**`_cancel_take_profit_orders_only()` (라인 ~480)**
- **주요 로그**:
  - `✅ 익절 주문 취소됨: {order['type']} @ ${order.get('price', 'N/A')}`
  - `⚠️ 익절 주문 취소 실패: {e}`
  - `❌ 익절 주문 조회 중 오류: {e}`
- **반환값**: 취소된 주문 수 (int)
- **주의사항**: LIMIT 타입만 취소

#### 2. 손절가/익절가 조정 기능

**`_adjust_stop_loss()` (라인 ~1450)**
- **주요 로그**:
  - `📋 {cancelled}개의 손절 주문 취소됨 (익절 주문은 유지)`
  - `✅ 손절가 조정 완료: ${new_stop_loss}`
  - `📝 손절가 조정 사유: {rationale}`
  - `❌ 조정할 포지션이 없습니다`
  - `❌ 유효하지 않은 손절가`

**`_adjust_take_profit()` (라인 ~1500)**
- **주요 로그**:
  - `📋 {cancelled}개의 익절 주문 취소됨 (손절 주문은 유지)`
  - `🎯 1차 익절 조정: ${new_tp1} (50%)`
  - `🎯 2차 익절 조정: ${new_tp2} (50%)`
  - `📝 익절가 조정 사유: {rationale}`
  - `❌ 유효하지 않은 익절가`

#### 3. 신디사이저 결정 처리

**`execute_trade_playbook()` (라인 ~380)**
- **새로운 액션 타입**:
  - `ADJUST_TARGETS`: 익절가만 조정
  - `ADJUST_BOTH`: 손절가와 익절가 모두 조정
- **주요 로그**:
  - `📊 신디사이저 결정: ADJUST_TARGETS - 익절가 조정`
  - `📊 신디사이저 결정: ADJUST_BOTH - 손절가와 익절가 모두 조정`

### 디버그 방법

#### 1. 주문 상태 확인
```python
# 현재 열린 주문 확인
open_orders = self.client.futures_get_open_orders(symbol=symbol)
for order in open_orders:
    logging.debug(f"주문 타입: {order['type']}, 가격: {order.get('price', order.get('stopPrice'))}")
```

#### 2. 선택적 취소 검증
```python
# 취소 전 주문 수
before_count = len(self.client.futures_get_open_orders(symbol=symbol))
# 취소 실행
cancelled = self._cancel_stop_orders_only(symbol)
# 취소 후 주문 수
after_count = len(self.client.futures_get_open_orders(symbol=symbol))
# 검증
assert before_count - after_count == cancelled
```

#### 3. 포지션 상태 추적
- 조정 전/후 포지션 정보 로깅
- 주문 타입별 분류 확인
- 가격 정밀도 검증 (SOL: 소수점 2자리)

### 주의사항

1. **주문 타입 구분**
   - `STOP_MARKET`: 손절 주문
   - `LIMIT`: 익절 주문
   - 타입이 다른 경우 로그 확인 필요

2. **타이밍 이슈**
   - 주문 취소 후 0.5초 대기
   - 바이난스 API 응답 지연 고려

3. **에러 처리**
   - 이미 체결된 주문 취소 시도
   - 네트워크 오류로 인한 실패
   - 주문 ID 불일치

### 트러블슈팅

#### 문제: 익절가가 여전히 사라짐
**원인**: `_cancel_all_open_orders()` 호출
**해결**: 해당 함수 호출 위치 확인 및 선택적 취소 함수로 대체

#### 문제: 주문 타입 인식 실패
**원인**: 바이난스 API 응답 형식 변경
**해결**: API 응답 로깅하여 실제 타입 필드 확인

#### 문제: 부분 체결된 주문 처리
**원인**: 익절 주문이 일부만 체결된 상태
**해결**: 남은 수량 확인 후 조정

### 모니터링 포인트

1. **주문 취소 성공률**
   - 시도한 취소 vs 실제 취소된 주문
   - 실패 원인 분석

2. **조정 빈도**
   - 너무 자주 조정하면 수수료 증가
   - 적절한 조정 주기 모니터링

3. **가격 정밀도**
   - SOL: 반드시 소수점 2자리
   - 다른 심볼 추가 시 정밀도 확인

---

## 2025-01-13 시스템 실행 오류 해결

### 발생한 문제들
1. **trade_database.py IndentationError**
   - 위치: 518, 528, 886, 968번 줄
   - 원인: 중첩된 try-except 블록에서 들여쓰기 불일치
   - 해결: 올바른 들여쓰기로 수정 및 finally 블록 추가

2. **.env 파일 경고**
   - 증상: "WARNING: Environment file not found: .env"
   - 원인: .env 파일이 없음
   - 영향: 시스템은 정상 작동하지만 경고 메시지 출력

### 문제 발생 원인 분석
1. **들여쓰기 오류의 근본 원인**:
   - 코드 병합 과정에서 들여쓰기가 일관되지 않게 적용됨
   - Python의 엄격한 들여쓰기 규칙으로 인해 실행 불가
   - 특히 중첩된 try-except 구조에서 finally 블록 누락

2. **코드 구조 문제**:
   ```python
   # 문제가 된 패턴
   conn = self._get_connection()
   try:
       # 코드...
       return result
   # finally 블록이 없어서 오류 발생
   except Exception as e:
       # 에러 처리
   ```

### 해결 방법
1. 모든 중첩된 try 블록에 finally 추가:
   ```python
   conn = self._get_connection()
   try:
       # 코드...
       return result
   finally:
       conn.close()
   ```

2. 들여쓰기 일관성 확보 (4 스페이스 사용)

### 주요 디버그 포인트
- `src/data/trade_database.py:518-568` - get_outcome_statistics 메서드
- `src/data/trade_database.py:813-893` - save_enhanced_record 메서드  
- `src/data/trade_database.py:931-972` - find_similar_enhanced_trades 메서드
- `src/data/trade_database.py:974-992` - get_trade_by_id 메서드

### 향후 주의사항
1. 코드 수정 시 들여쓰기 일관성 유지
2. 중첩된 try 블록 사용 시 반드시 finally 추가
3. DB 연결 관리 패턴 통일화 필요

---

## 2025-01-13 LIMIT 주문 OCO 자동 생성 기능 추가

### 구현 내용
1. **문제**: LIMIT 주문 사용 시 익절/손절 주문이 설정되지 않음
2. **원인**: LIMIT 주문은 대기 상태가 되며, 체결 후에도 OCO 생성 로직이 없었음
3. **해결**: monitor_position에서 LIMIT 주문 체결을 감지하고 자동으로 OCO 생성

### 추가된 코드 위치
- `src/trading/trade_executor.py:397-398` - pending_order_id, oco_created 필드 추가
- `src/trading/trade_executor.py:1007-1014` - LIMIT 주문 체결 확인 로직
- `src/trading/trade_executor.py:1901-2003` - 헬퍼 함수들 추가
  - `_check_order_filled()`: 주문 체결 여부 확인
  - `_create_oco_for_filled_limit()`: OCO 주문 생성
  - `_get_actual_fill_price()`: 실제 체결가 조회

### 주요 디버그 포인트
1. **LIMIT 주문 체결 확인** (라인 1010-1011)
   - `🔍 LIMIT 주문 체결 확인 중... Order ID: {pending_order_id}`
   - 1분마다 체크, pending이고 oco_created=False일 때만

2. **체결 확인 및 OCO 생성** (라인 1013-1014)
   - `✅ LIMIT 주문 체결 확인! OCO 주문 생성 시작...`
   - 체결 시 즉시 OCO 생성 시도

3. **실제 체결가 확인** (라인 1935)
   - `📊 LIMIT 주문 체결가: ${actual_entry_price:.2f} (예상: ${expected_price:.2f})`
   - 슬리피지 확인 가능

4. **OCO 생성 완료** (라인 1956)
   - `✅ LIMIT 주문 체결 후 OCO 주문 생성 완료`
   - Discord 알림 발송

### 모니터링 포인트
1. **API 호출 빈도**: 1분마다 pending 주문만 체크하므로 부하 최소
2. **중복 생성 방지**: oco_created 플래그로 관리
3. **체결가 정확도**: avgPrice와 price 중 적절한 값 선택

### 테스트 방법
```python
# 로그 레벨 설정으로 상세 확인
import logging
logging.getLogger('trading.trade_executor').setLevel(logging.DEBUG)

# LIMIT 주문 테스트
# 1. 신디사이저가 order_type: "LIMIT" 생성
# 2. monitor_position이 체결 감지
# 3. OCO 주문 자동 생성 확인
```

### 주의사항
1. **부분 체결**: 현재는 완전 체결(FILLED)만 처리
2. **취소된 주문**: CANCELED 상태는 무시됨
3. **네트워크 오류**: 다음 주기에 재시도됨

---

## 2025-01-15 로그 오류 수정 관련 디버그 포인트

### 1. PENDING 거래 DB 오류 관련
**파일**: `src/data/trade_database.py`
- **위치**: `save_trade()` 메서드 (새로 추가 예정)
- **목적**: TradeDatabase에 없는 save_trade 메서드 호출 오류 해결
- **디버그 코드**:
  ```python
  def save_trade(self, trade_data: Dict) -> bool:
      """add_trade_record의 호환성 래퍼"""
      try:
          logging.debug(f"[DEBUG] save_trade 호출됨: {trade_data.get('trade_id', 'NO_ID')}")
          # trade_data를 TradeRecord 형식으로 변환
          trade_record = self._convert_to_trade_record(trade_data)
          result = self.add_trade_record(trade_record)
          logging.debug(f"[DEBUG] save_trade 결과: {result}")
          return result
      except Exception as e:
          logging.error(f"[DEBUG] 거래 저장 실패: {e}", exc_info=True)
          return False
  ```

### 2. DB 연결 재시도 로직
**파일**: `src/data/trade_database.py`
- **위치**: `_get_connection()` 메서드 (기 구현됨)
- **목적**: SQLite 동시 접근 오류 추적
- **디버그 개선사항**:
  ```python
  def _get_connection(self, timeout: float = 10.0) -> sqlite3.Connection:
      retry_count = 0
      max_retries = 3
      
      while retry_count < max_retries:
          try:
              logging.debug(f"[DEBUG] DB 연결 시도 {retry_count + 1}/{max_retries}")
              conn = sqlite3.connect(self.db_path, timeout=timeout)
              conn.row_factory = sqlite3.Row
              logging.debug("[DEBUG] DB 연결 성공")
              return conn
          except sqlite3.OperationalError as e:
              retry_count += 1
              if retry_count >= max_retries:
                  logging.error(f"[DEBUG] DB 연결 최종 실패: {e}")
                  raise
              
              wait_time = retry_count * 0.5
              logging.warning(f"[DEBUG] DB 연결 재시도 대기 {wait_time}초")
              time.sleep(wait_time)
  ```

### 3. 수동 포지션 감지 개선
**파일**: `src/trading/trade_history_sync.py`
- **위치**: `_detect_manual_positions()` 메서드
- **목적**: 오탐지 원인 추적 및 24시간 필터 적용
- **디버그 코드**:
  ```python
  def _detect_manual_positions(self, trades: List[Dict], pending_trades: List[Dict]) -> List[Dict]:
      logging.debug(f"[DEBUG] 수동 포지션 감지 시작: {len(trades)}개 거래 분석")
      manual_positions = []
      current_time = datetime.now().timestamp() * 1000
      
      # 포지션 그룹화
      position_groups = self._group_trades_by_position(trades)
      logging.debug(f"[DEBUG] {len(position_groups)}개 포지션 그룹 생성됨")
      
      # PENDING 거래의 시간 목록
      pending_times = [
          int(datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00')).timestamp() * 1000)
          for t in pending_trades
      ]
      
      for pos_key, position in position_groups.items():
          # 시스템 거래와 매칭되지 않는 포지션
          is_manual = True
          for pending_time in pending_times:
              if abs(position['start_time'] - pending_time) < 5 * 60 * 1000:  # 5분 오차
                  is_manual = False
                  break
          
          if is_manual and not position.get('is_closed', False):
              # 24시간 이내 포지션만
              position_age_hours = (current_time - position['start_time']) / (1000 * 3600)
              logging.debug(f"[DEBUG] 포지션 {pos_key}: 나이={position_age_hours:.1f}시간, 닫힘={position.get('is_closed')}")
              
              if position_age_hours <= 24:
                  logging.debug(f"[DEBUG] 수동 포지션 감지됨: {pos_key}")
                  # 포지션 정보 추가
                  entry_trades = position['entry_trades']
                  total_qty = sum(float(t['qty']) for t in entry_trades)
                  if total_qty > 0:
                      avg_entry_price = sum(float(t['price']) * float(t['qty']) for t in entry_trades) / total_qty
                  else:
                      avg_entry_price = 0.0
                      logging.warning(f"[DEBUG] 수량이 0인 포지션 발견")
                  
                  manual_positions.append({
                      'direction': position['direction'],
                      'entry_time': datetime.fromtimestamp(position['start_time'] / 1000).isoformat(),
                      'entry_price': avg_entry_price,
                      'quantity': total_qty,
                      'is_closed': False
                  })
              else:
                  logging.debug(f"[DEBUG] 오래된 포지션 무시: {pos_key} ({position_age_hours:.1f}시간)")
      
      logging.debug(f"[DEBUG] 총 {len(manual_positions)}개 수동 포지션 감지됨")
      return manual_positions
  ```

### 4. 트리거 체크 로직
**파일**: `src/monitoring/heartbeat_checker.py`
- **위치**: `_check_triggers()` 메서드
- **목적**: 트리거 발동 조건 추적 및 중복 로깅 방지
- **디버그 코드**:
  ```python
  def _check_triggers(self):
      try:
          current_price = get_current_price(self.target_asset)
          logging.debug(f"[DEBUG] 트리거 체크 시작: 현재가={current_price}")
          
          triggers = self.trigger_manager.load_triggers()
          logging.debug(f"[DEBUG] 활성 트리거 수: {len(triggers)}")
          
          # HOLD 트리거와 포지션 트리거 분리
          hold_triggers = [t for t in triggers if t.get('trigger_type') != 'position']
          position_triggers = [t for t in triggers if t.get('trigger_type') == 'position']
          
          logging.debug(f"[DEBUG] HOLD 트리거: {len(hold_triggers)}개, 포지션 트리거: {len(position_triggers)}개")
          
          # 트리거 체크 로직...
      except Exception as e:
          logging.error(f"[DEBUG] 트리거 체크 실패: {e}", exc_info=True)
  ```

### 5. cleanup_old_pending_trades 호출 개선
**파일**: `src/main.py`
- **위치**: `__init__` 메서드 (라인 71-79)
- **목적**: import 오류 해결 및 메서드 호출 정상화
- **디버그 코드**:
  ```python
  # 오래된 PENDING 거래 정리 (시작 시 실행)
  try:
      from data.trade_database import TradeDatabase
      trade_db = TradeDatabase()
      logging.debug("[DEBUG] PENDING 거래 정리 시작")
      deleted_count = trade_db.cleanup_old_pending_trades(days=7)
      if deleted_count > 0:
          self.logger.info(f"[DEBUG] 시작 시 {deleted_count}개의 오래된 PENDING 거래 정리 완료")
      else:
          logging.debug("[DEBUG] 정리할 PENDING 거래 없음")
  except AttributeError as e:
      self.logger.warning(f"[DEBUG] cleanup_old_pending_trades 메서드 없음: {e}")
  except Exception as e:
      self.logger.warning(f"[DEBUG] PENDING 거래 정리 실패: {e}", exc_info=True)
  ```

## 디버그 레벨 설정

### 개발 환경 (상세 디버그)
```python
# .env 파일
LOG_LEVEL=DEBUG

# 또는 코드에서
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### 운영 환경 (중요 정보만)
```python
# .env 파일
LOG_LEVEL=INFO
```

## 디버그 로그 분석 명령어

### 1. 특정 디버그 포인트 검색
```bash
# save_trade 관련 디버그
grep "\[DEBUG\].*save_trade" logs/delphi.log

# DB 연결 관련
grep "\[DEBUG\].*DB 연결" logs/delphi.log

# 수동 포지션 관련
grep "\[DEBUG\].*수동 포지션" logs/delphi.log
```

### 2. 시간대별 디버그 로그
```bash
# 특정 시간대 디버그 로그
grep "\[DEBUG\]" logs/delphi.log | grep "2025-01-15 14:"
```

### 3. 오류 추적
```bash
# 디버그 관련 오류
grep -A 5 -B 5 "\[DEBUG\].*실패" logs/delphi.log

# save_trade 오류
grep -A 10 "'TradeDatabase' object has no attribute 'save_trade'" logs/delphi.log
```

### 4. 중복 로깅 확인
```bash
# 동일 메시지 중복 확인
grep "수동 포지션 감지됨" logs/delphi.log | uniq -c | sort -nr
```

## 테스트 스크립트

### 1. save_trade 메서드 테스트
```python
# temporary/test_save_trade.py
import sys
sys.path.append('/mnt/c/Users/PCW/Desktop/delphi-trader/src')

from data.trade_database import TradeDatabase
from datetime import datetime

db = TradeDatabase()

# 테스트 데이터
test_trade = {
    'trade_id': f'TEST_{datetime.now().timestamp()}',
    'symbol': 'SOLUSDT',
    'direction': 'LONG',
    'entry_price': 100.0,
    'entry_time': datetime.now().isoformat(),
    'position_size': 0.5,
    'leverage': 10,
    'outcome': 'PENDING'
}

print("테스트 시작: save_trade 메서드")
try:
    result = db.save_trade(test_trade)
    print(f"결과: {'성공' if result else '실패'}")
except AttributeError as e:
    print(f"오류: {e}")
    print("save_trade 메서드가 없습니다. 구현 필요!")
except Exception as e:
    print(f"예상치 못한 오류: {e}")
```

### 2. 수동 포지션 오탐지 테스트
```python
# temporary/test_manual_position.py
import sys
sys.path.append('/mnt/c/Users/PCW/Desktop/delphi-trader/src')

from trading.trade_history_sync import TradeHistorySync
from binance.client import Client
import os

# 환경 변수에서 API 키 로드
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

if not api_key or not api_secret:
    print("API 키가 설정되지 않았습니다.")
    exit(1)

client = Client(api_key, api_secret)
sync = TradeHistorySync(client)

print("최근 24시간 거래 동기화 테스트")
result = sync.sync_recent_trades("SOLUSDT", hours=24)

print(f"\n동기화 결과:")
print(f"- 발견된 거래: {result.get('trades_found', 0)}개")
print(f"- PENDING 거래: {result.get('pending_trades', 0)}개")
print(f"- 매칭된 거래: {result.get('matched_trades', 0)}개")

if 'manual_positions' in result:
    print(f"\n수동 포지션 감지: {len(result['manual_positions'])}개")
    for pos in result['manual_positions']:
        print(f"  - {pos['direction']} @ ${pos['entry_price']:.2f} ({pos['entry_time']})")
else:
    print("\n수동 포지션 없음")
```

## 주의사항

1. **운영 환경 디버그 레벨**
   - 운영 환경에서는 DEBUG 레벨을 사용하지 않음
   - 필요시에만 일시적으로 활성화

2. **민감 정보 로깅 금지**
   - API 키, 비밀번호 등은 절대 로깅하지 않음
   - 개인정보나 거래 세부사항은 최소화

3. **성능 영향 최소화**
   - 디버그 로그는 조건부로만 출력
   - 대용량 데이터는 요약해서 로깅

4. **정기적인 정리**
   - 문제 해결 후 불필요한 디버그 코드 제거
   - 로그 파일 크기 관리

---

## Synthesizer 멀티 시나리오 트리거 디버그 포인트

### 파일: src/agents/synthesizer.py

1. **키 레벨 추출 및 변환** (라인 429-460)
   - `self.logger.info(f"[SYNTH] 키 레벨: {key_levels}")`
   - 용도: 키 레벨이 올바르게 추출되고 리스트로 변환되었는지 확인
   
2. **안전한 숫자 추출** (_safe_extract_numeric, 라인 676-689)
   - 다양한 타입 처리: None, float, int, string, list
   - 용도: 예상치 못한 데이터 타입도 안전하게 처리되는지 확인

3. **안전한 리스트 변환** (_safe_get_list, 라인 691-700)
   - 입력: None, list, float/int/string
   - 출력: 항상 유효한 숫자만 포함하는 리스트
   - 용도: resistance/support 레벨이 다양한 형태로 들어와도 안전하게 처리

4. **트리거 생성 로그** (라인 479-561)
   - 상승 트리거: `[SYNTH] 상승 트리거 생성: LONG @ ${trigger_price:.2f}`
   - 하락 트리거: `[SYNTH] 하락 트리거 생성: ${trigger_price:.2f}`
   - 박스권 트리거: `[SYNTH] 박스권 트리거 생성: ${lower_range:.2f} ~ ${upper_range:.2f}`
   - 용도: 각 시나리오별 트리거가 정상 생성되는지 확인

5. **에러 처리** (라인 564-566)
   - `[ERROR] 멀티 시나리오 트리거 생성 실패: {e}`
   - 용도: 어떤 예외가 발생했는지 정확히 파악

### 디버그 활성화 방법
```python
# 특정 트리거 생성 문제 추적
import logging
logging.getLogger('agents.synthesizer').setLevel(logging.DEBUG)
```

### 주의사항
1. **다양한 데이터 형식 대응**
   - resistance/support가 float로 올 수 있음
   - 빈 리스트나 None도 처리 가능
   - weak_resistance/weak_support도 안전하게 처리

2. **방어적 프로그래밍**
   - 모든 리스트 접근 전 길이 확인
   - 타입 체크 후 적절한 변환
   - 예외 발생 시 기본값 반환

---

## ExecutionLock 디버그 포인트

### 파일: src/utils/execution_lock.py

1. **잠금 획득 시도** (라인 82-114)
   - `[SAFETY] 잠금 타임아웃 - 기존: {locked_by}`
   - `[SAFETY] 동시 실행 방지 - {locked_by} 실행 중, {remaining:.0f}초 남음`
   - `[SAFETY] 실행 잠금 획득 - {process_name}`
   - 용도: 잠금 경합 상황과 타임아웃 처리 확인

2. **잠금 해제** (라인 153-177)
   - `[SAFETY] 실행 잠금 해제 - {process_name}`
   - `[WARN] 다른 프로세스의 잠금 - 현재: {process_name}, 잠금: {locked_by}`
   - 용도: 잠금 소유권 확인 및 정상 해제 추적

3. **파일 시스템 작업** (라인 72-100)
   - Windows 파일 삭제 재시도 로직
   - 지수 백오프: 0.1초, 0.2초, 0.4초, 0.8초, 1.6초
   - 최종 실패 시 파일 내용 비우기 시도
   - 용도: Windows 파일 잠금 문제 해결 과정 추적

4. **만료된 잠금 자동 정리** (라인 197-199)
   - `만료된 잠금 자동 정리: {locked_by}`
   - 용도: 5분 타임아웃 후 자동 정리 확인

5. **컨텍스트 매니저 사용** (라인 207-225)
   - with 문 사용 시 자동 잠금 획득/해제
   - 예외 발생 시에도 잠금 해제 보장
   - 용도: 안전한 리소스 관리 확인

### 사용 예시
```python
# 기본 사용
from utils.execution_lock import execution_lock

if execution_lock.acquire('15min_analysis'):
    try:
        # 작업 수행
        pass
    finally:
        execution_lock.release('15min_analysis')

# 컨텍스트 매니저 사용 (권장)
with execution_lock.lock('intelligent_trigger'):
    # 작업 수행
    pass  # 자동으로 잠금 해제됨

# 현재 잠금 상태 확인
locked_by = execution_lock.is_locked()
if locked_by:
    print(f"현재 {locked_by}가 실행 중")

# 긴급 상황 시 강제 해제
execution_lock.force_unlock()
```

### 주의사항
1. **프로세스 이름 일관성**: acquire와 release에 동일한 프로세스 이름 사용
2. **타임아웃 설정**: 기본 5분, 필요시 조정 가능
3. **파일 경로**: data/.execution_lock 파일 권한 확인 필요
4. **동시성**: 멀티 스레드 환경에서도 안전하게 작동

## 업데이트 이력

- 2025-01-15: 로그 오류 수정 관련 디버그 포인트 추가
  - save_trade 메서드 호환성 래퍼
  - 수동 포지션 24시간 필터
  - cleanup_old_pending_trades 호출 개선
  - 테스트 스크립트 추가

- 2025-01-20: WAL 체크포인트 구현으로 거래 DB 저장/조회 문제 해결
  - _force_wal_checkpoint 메서드 추가
  - save_trade_record에 체크포인트 호출 추가
  - get_trade_by_id 메서드 추가 (재시도 로직 포함)
  - WAL 모드 최적화 설정 추가

- 2025-01-20: 멀티 시나리오 트리거 타입 오류 수정
  - synthesizer.py generate_multi_scenario_triggers 메서드 개선
  - _safe_extract_numeric, _safe_get_list 헬퍼 메서드 추가
  - resistance/support 레벨이 float, list, empty 등 다양한 형태 처리
  - 방어적 프로그래밍으로 모든 데이터 형식 안전하게 처리

- 2025-01-20: ExecutionLock 파일 잠금 문제 해결
  - 컨텍스트 매니저 패턴 구현 (__enter__, __exit__)
  - 스레드 안전성을 위한 threading.Lock 추가
  - 시간 기반 잠금 만료 (5분) 자동 처리
  - Windows 파일 시스템 호환성 개선
  - 재시도 로직 (지수 백오프) 추가
  - 파일 핸들 자동 해제 보장

- 2025-01-20: Synthesizer 코드 품질 개선 및 버그 수정
  - 누락된 헬퍼 메서드 추가:
    - _safe_get_list(): 다양한 타입을 안전하게 리스트로 변환
    - _safe_extract_numeric(): 다양한 타입을 안전하게 숫자로 변환
  - 트리거 생성 로직 리팩토링:
    - _create_trigger() 헬퍼 메서드로 중복 코드 제거
    - 4개의 중복 트리거 생성 블록을 통합
  - 로깅 개선:
    - 중복 로그 제거 (시나리오 확률 한 번만 출력)
    - 에러 발생 시 상세 컨텍스트 추가 (exc_info=True)
    - 디버그 레벨 로그 추가
  - 에러 처리 강화:
    - generate_multi_scenario_triggers 예외 시 입력값 로깅
    - 타입 안전성 강화로 AttributeError 방지