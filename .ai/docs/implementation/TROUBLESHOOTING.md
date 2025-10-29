# 트러블 슈팅 문서

## 현재 시스템 문제점 (2025-01-13 업데이트)

### ✅ 해결된 문제들 (2025-01-13)

1. **이중화된 데이터베이스 시스템** - 해결됨
   - enhanced_trade_db 관련 코드 모두 제거
   - 시나리오 기반 DB로 단일화

2. **레거시 Cross Validator 시스템** - 해결됨
   - cross_validator.py 파일 삭제
   - 시스템에서 가중치 개념 제거

3. **구버전 quant.py** - 해결됨
   - quant.py 삭제 (quant_v3만 사용)
   - main.py에서 조건부 import로 수정

4. **enhanced_daily_analyzer.py** - 해결됨
   - 파일 삭제
   - 주간 분석으로 통합

### 🟡 남은 개선 사항

### 1. 대시보드 랜덤 데이터
- **문제**: 대시보드가 실제 데이터 대신 랜덤값 사용
- **영향**: 정확한 성과 확인 불가
- **해결 필요**: 실제 데이터 연동

### ✅ 추가로 해결된 문제들 (2025-01-13)

5. **exploration_trade 필드** - 해결됨
   - trade_database.py에서 관련 코드 모두 제거
   - ALTER TABLE 문 주석 처리
   - 관련 로직 제거

6. **빈 except 블록** - 해결됨
   - oco_order_manager.py: Discord 알림 실패 로깅 추가
   - websocket_monitor.py: 콜백 및 알림 오류 로깅 추가
   - 적절한 에러 메시지로 디버깅 용이성 향상

7. **position_decision 논리 오류** - 해결됨
   - **문제**: 포지션이 있는데도 position_decision이 "NEW_ENTRY"로 설정됨
   - **증상**: has_position: true인데 position_decision: "NEW_ENTRY"
   - **영향**: 이미 포지션이 있는데 새로운 진입 신호가 발생
   - **해결**: synthesizer_v2.txt에 명확한 규칙 및 예시 추가

8. **ADJUST_STOP 시 익절가 사라짐** - 해결됨
   - **문제**: 손절가 조정 시 모든 주문이 취소되어 익절가가 사라짐
   - **원인**: _cancel_all_open_orders() 사용
   - **해결**: 
     - _cancel_stop_orders_only() 함수 추가
     - _cancel_take_profit_orders_only() 함수 추가
     - 선택적 주문 취소로 변경

9. **update_exit_decision 메서드 없음** - 해결됨
   - **문제**: TradingContextManager에 update_exit_decision 메서드가 없음
   - **해결**: 해당 호출 제거하고 로깅으로 대체

10. **거래 실행 상태 처리 누락** - 해결됨 (2025-01-13)
   - **문제**: main.py의 _execute_trade에서 'adjusted', 'both_adjusted' 등 상태 미처리
   - **증상**: "거래 실행 완료 - 실패: 알 수 없는 오류" 로그 출력
   - **원인**: ADJUST_STOP, ADJUST_TARGETS, ADJUST_BOTH, ADJUST_POSITION 액션의 반환 상태 미처리
   - **해결**: 
     - 'adjusted', 'both_adjusted', 'position_adjusted' 상태 처리 추가
     - 'disabled', 'blocked' 상태도 경고로 처리
     - 상태값을 로그에 포함시켜 디버깅 용이하게 개선

11. **trade_direction 키 에러** - 해결됨 (2025-01-13)
   - **문제**: "거래 실행 중 예외 발생: 'trade_direction'" 에러
   - **원인**: 신디사이저 v2 프롬프트에 trade_direction 필드 없음
   - **해결**: 
     - trade_direction이 없을 경우 action에서 유추하는 로직 추가
     - BUY → LONG, SELL → SHORT로 매핑

12. **PENDING 거래 경고** - 해결됨 (2025-01-13)
   - **문제**: "중복 진입 감지: 4개의 PENDING 거래" 경고
   - **원인**: 
     - 포지션 진입 시 PENDING 상태로 DB에 저장하지 않음
     - 포지션 종료 시에만 거래 기록 저장
   - **해결**:
     - 포지션 진입 시 즉시 PENDING 상태로 DB 저장
     - 포지션 종료 시 PENDING → 완료 상태로 업데이트
     - 7일 이상 오래된 PENDING 거래 자동 정리 기능 추가
     - TradeDatabase에 필요한 메서드 추가 (get_trade_by_id, update_trade, cleanup_old_pending_trades)

---

## 현재 시스템 문제점 (2025-01-19 업데이트)

### 🔴 심각한 문제들

1. **숏 포지션만 진입하는 극심한 편향**
   - **현황**: 최근 16개 거래 중 15개가 SHORT (93.8%)
   - **원인**: 
     - 차티스트가 하락 시나리오에 높은 확률 부여 경향
     - 스토익이 하락장에서 SHORT에 추가 레버리지 부여
     - 신디사이저 프롬프트에 LONG/SHORT 균형 지침 부재
   - **영향**: 상승장에서 수익 기회 상실

2. **승률 0% - 모든 거래 손실**
   - **현황**: 16개 거래 모두 손실, 평균 -0.16%
   - **원인**:
     - 모든 거래가 MANUAL_EXIT (손절/익절 미도달)
     - 진입 타이밍과 청산 타이밍 모두 부적절
   - **영향**: 지속적인 자본 손실

3. **가짜 학습 시스템**
   - **현황**: agent_weight_manager가 랜덤값 사용 (현재 비활성화)
   - **영향**: 시스템이 경험에서 학습하지 못함

### 🟡 중요한 문제들

4. **익절가 설정 문제**
   - **현황**: ADJUST_STOP 시 손절가만 조정되고 익절가는 그대로
   - **원인**: 설계상 ADJUST_STOP은 손절가만 조정
   - **해결**: ADJUST_BOTH 액션 사용 필요

5. **트리거 시스템 비효율**
   - **현황**: 15분 주기로만 체크, 급격한 변화 놓침
   - **문제점**:
     - 트리거 발동 시 모든 트리거 삭제
     - 가격 허용 오차 0.1%로 너무 타이트
   - **영향**: 재진입 기회 상실

6. **디스코드 알림 정보 부족**
   - **현황**: 포지션 정보 미표시
   - **필요**: 현재 포지션, 진입가, 손익, 손절/익절가 표시

### 🟢 개선 필요 사항

7. **시장 분류 시스템 부재**
   - market_classifier.py 파일 없음
   - 모든 시장 상황에 동일한 전략 적용

8. **에이전트 점수 불균형**
   - 저널리스트(6.9), 스토익(5.0) 점수가 매우 낮음
   - 신디사이저가 낮은 점수도 동등하게 반영할 가능성

9. **포지션 조정 기능 비활성화**
   - ADJUST_POSITION 기능이 환경변수로 비활성화
   - 손실 포지션을 조기에 정리하지 못함