# 시나리오 학습 시스템 통합 가이드

## 1. DB 마이그레이션 실행

### 1.1 new_venv 환경 활성화
```bash
# Windows
cd C:\Users\PCW\Desktop\delphi-trader
new_venv\Scripts\activate

# WSL
source new_venv/bin/activate
```

### 1.2 마이그레이션 실행
```bash
python scripts/migrate_db_v2.py
```

## 2. main.py 수정

### 2.1 Import 추가 (파일 상단)
```python
# 기존 import들 아래에 추가
from integration.scenario_system_integration import scenario_integration
```

### 2.2 __init__ 메서드 수정
```python
def __init__(self):
    # 기존 코드...
    
    # 시나리오 학습 시스템 초기화 (추가)
    self.scenario_integration = scenario_integration
```

### 2.3 run_full_analysis 메서드 수정

#### A. 에이전트 분석 강화 (170번 줄 근처)
```python
# 4. 퀀트 분석
if results['reports']['chartist'] and results['reports']['journalist']:
    # 시나리오 기반 유사 거래 검색 (추가)
    results['reports'] = self.scenario_integration.enhance_agent_reports(
        results['reports'], 
        self.target_asset
    )
    
    results['reports']['quant'] = self._run_quant_analysis(
        results['reports']['chartist'], 
        results['reports']['journalist']
    )
```

#### B. 주간 리포트 생성 추가 (240번 줄 근처)
```python
# 매일 23시대에 실행되는 경우 일일 리포트 생성
if current_hour == 23:
    self.logger.info("📊 일일 성과 리포트 생성 중...")
    daily_result = generate_daily_report()
    if daily_result['success']:
        self.logger.info("✅ 일일 성과 리포트 생성 완료")
    
    # 주간 리포트 생성 추가 (일요일 23시)
    current_day = datetime.now().weekday()
    self.scenario_integration.generate_weekly_report_if_needed(current_hour, current_day)
```

### 2.4 _execute_trade 메서드 수정

거래 실행 성공 후에 추가 (자세한 위치는 코드 확인 필요):
```python
if execution_result and execution_result.get('status') == 'executed':
    self.logger.info(f"✅ [거래 실행] 완료 - 성공! Trade ID: {execution_result['trade_id']}")
    
    # 시나리오 데이터 수집 (추가)
    trade_id = execution_result['trade_id']
    self.scenario_integration.collect_trade_entry_data(trade_id, playbook, reports)
    
    # 기존 Phase 3 코드...
```

## 3. 포지션 모니터링 설정

### 3.1 scheduler.py 수정 (선택사항)

15분마다 MDD 업데이트를 위한 스케줄 추가:
```python
# 포지션 MDD 모니터링 (15분마다)
schedule.every(15).minutes.do(monitor_positions)

def monitor_positions():
    """포지션 MDD 모니터링"""
    from main import DelphiOrchestrator
    orchestrator = DelphiOrchestrator()
    orchestrator.monitor_positions()
```

### 3.2 또는 main.py에 메서드 추가
```python
def monitor_positions(self):
    """포지션 MDD 모니터링 (15분마다 실행)"""
    try:
        from trading.position_state_manager import position_state_manager
        from data.binance_connector import get_current_price
        
        # 열린 포지션 조회
        open_positions = position_state_manager.get_open_positions()
        
        for position in open_positions:
            trade_id = position.get('trade_id')
            if trade_id:
                current_price = get_current_price(self.target_asset)
                
                # MDD 업데이트
                self.scenario_integration.update_position_mdd(trade_id, current_price)
        
    except Exception as e:
        self.logger.error(f"포지션 모니터링 실패: {e}")
```

## 4. 거래 종료 처리

### 4.1 trade_executor.py 수정

거래 종료 처리 부분에 추가:
```python
from integration.scenario_system_integration import scenario_integration

# 거래 종료 후
scenario_integration.update_trade_exit_data(
    trade_id,
    'WIN' if pnl > 0 else 'LOSS',
    actual_scenario  # 실제 발생한 시나리오 (선택적)
)
```

## 5. 테스트 및 확인

### 5.1 통합 테스트
```bash
# 테스트 실행 (new_venv 환경에서)
python src/main.py
```

### 5.2 확인 사항
- [ ] DB 마이그레이션 성공 (새 테이블 생성 확인)
- [ ] 거래 진입 시 scenario_tracking에 데이터 저장
- [ ] 유사 거래 검색이 Quant 리포트에 표시
- [ ] 일요일 23시에 주간 리포트 생성
- [ ] 에러 없이 정상 작동

## 6. 모니터링

### 6.1 새 테이블 데이터 확인
```sql
-- SQLite로 확인
sqlite3 data/database/delphi_trades.db

-- 시나리오 추적 확인
SELECT * FROM scenario_tracking ORDER BY created_at DESC LIMIT 5;

-- MDD 스냅샷 확인  
SELECT * FROM position_snapshots ORDER BY created_at DESC LIMIT 10;

-- 시장 컨텍스트 확인
SELECT * FROM market_context ORDER BY created_at DESC LIMIT 5;
```

### 6.2 주간 리포트 확인
```bash
# 리포트 파일 확인
ls reports/weekly/
```

## 7. 문제 해결

### 7.1 마이그레이션 실패 시
```bash
# 백업에서 복원
cp data/database/delphi_trades.db.backup_YYYYMMDD_HHMMSS data/database/delphi_trades.db
```

### 7.2 통합 오류 시
- 로그 확인: `logs/` 디렉토리
- 임시로 통합 비활성화: import 라인 주석 처리

## 8. 점진적 적용 전략

1. **1단계**: DB 마이그레이션만 실행
2. **2단계**: 데이터 수집 기능만 활성화 (enhance_agent_reports 제외)
3. **3단계**: 유사 거래 검색 활성화
4. **4단계**: 주간 리포트 활성화

각 단계별로 1-2일 모니터링 후 다음 단계 진행을 권장합니다.