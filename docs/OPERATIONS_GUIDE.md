# 델파이 트레이더 운영 가이드

## 목차
1. [시스템 요구사항](#시스템-요구사항)
2. [설치 및 초기 설정](#설치-및-초기-설정)
3. [일일 운영 절차](#일일-운영-절차)
4. [모니터링](#모니터링)
5. [백업 및 복구](#백업-및-복구)
6. [문제 해결](#문제-해결)
7. [성능 관리](#성능-관리)
8. [보안 관리](#보안-관리)
9. [업데이트 절차](#업데이트-절차)

## 시스템 요구사항

### 하드웨어
- **CPU**: 2코어 이상
- **RAM**: 4GB 이상 (권장: 8GB)
- **저장공간**: 10GB 이상
- **네트워크**: 안정적인 인터넷 연결 (최소 10Mbps)

### 소프트웨어
- **OS**: Windows 10+, Ubuntu 20.04+, macOS 10.15+
- **Python**: 3.10 이상
- **데이터베이스**: SQLite (내장)

### 외부 서비스
- Binance API 계정
- Google Gemini API 키
- Discord Webhook (선택사항)

## 설치 및 초기 설정

### 1. 시스템 준비
```bash
# Python 버전 확인
python --version  # 3.10 이상

# Git 설치 확인
git --version

# 디스크 공간 확인
df -h  # Linux/Mac
dir  # Windows
```

### 2. 프로젝트 설치
```bash
# 1. 클론
git clone https://github.com/your-repo/delphi-trader.git
cd delphi-trader

# 2. 가상환경 (이미 있음)
.\new_venv\Scripts\activate  # Windows
source new_venv/bin/activate  # Linux/Mac

# 3. 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 설정
```bash
# .env 파일 생성
cp .env.example .env

# 편집기로 .env 수정
# 필수 설정:
# - BINANCE_API_KEY
# - BINANCE_API_SECRET
# - GEMINI_API_KEY
# - DISCORD_WEBHOOK_URL (선택)
```

### 4. 초기 테스트
```bash
# 시스템 테스트
python test_run.py

# 연결 테스트
python -c "from infrastructure.exchanges.binance_adapter import BinanceAdapter; print('OK')"
```

## 일일 운영 절차

### 1. 시작 전 체크리스트
- [ ] 시스템 리소스 확인 (CPU, 메모리)
- [ ] 인터넷 연결 상태 확인
- [ ] 로그 파일 크기 확인
- [ ] 이전 거래 결과 확인

### 2. 시스템 시작
```bash
# 방법 1: 배치 파일 (Windows)
run_delphi.bat

# 방법 2: 직접 실행
cd legacy\src
..\..\new_venv\Scripts\python.exe main.py

# 방법 3: 백그라운드 실행 (Linux)
nohup python main.py > /dev/null 2>&1 &
```

### 3. 정상 작동 확인
```bash
# 로그 확인
tail -f logs/delphi_orchestrator.log

# 프로세스 확인
ps aux | grep python  # Linux
tasklist | findstr python  # Windows

# API 상태 확인
curl http://localhost:5000/health
```

### 4. 일일 점검 사항
- 거래 실행 여부
- 에러 로그 확인
- 포지션 상태 확인
- 자본금 변동 확인

## 모니터링

### 1. 실시간 모니터링
```bash
# 대시보드 실행
cd legacy\src\dashboard
..\..\..\new_venv\Scripts\python.exe app.py

# 브라우저: http://localhost:5000
```

### 2. 로그 모니터링
```bash
# 실시간 로그
tail -f logs/*.log

# 에러 검색
grep -i error logs/*.log | tail -50

# 특정 날짜 로그
grep "2025-01-21" logs/delphi_orchestrator.log
```

### 3. 성능 메트릭
```python
# 모니터링 스크립트
python scripts/monitor_performance.py

# 출력 예시:
# CPU Usage: 15%
# Memory Usage: 1.2GB
# API Latency: 45ms
# Trade Success Rate: 95%
```

### 4. 알림 설정
```yaml
# config/alerts.yaml
alerts:
  - type: "error_rate"
    threshold: 0.05  # 5% 이상
    action: "discord_notify"
  
  - type: "position_drawdown"
    threshold: 0.10  # 10% 이상
    action: "emergency_close"
```

## 백업 및 복구

### 1. 자동 백업
```bash
# 백업 스크립트 (scripts/backup.sh)
#!/bin/bash
BACKUP_DIR="/backup/delphi/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# 데이터베이스 백업
cp data/database/*.db $BACKUP_DIR/

# 설정 백업
cp -r config/ $BACKUP_DIR/

# 거래 컨텍스트 백업
cp data/*.json $BACKUP_DIR/

# 압축
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
```

### 2. 수동 백업
```bash
# 중요 파일 백업
python scripts/manual_backup.py

# 클라우드 업로드 (선택)
aws s3 cp backup/ s3://your-bucket/delphi-backup/ --recursive
```

### 3. 복구 절차
```bash
# 1. 시스템 중지
pkill -f main.py

# 2. 백업 복원
tar -xzf backup_20250121.tar.gz
cp -r backup_20250121/* .

# 3. 데이터베이스 검증
python scripts/verify_database.py

# 4. 시스템 재시작
python main.py
```

## 문제 해결

### 1. 일반적인 문제

#### 시스템이 시작되지 않음
```bash
# 포트 충돌 확인
netstat -an | grep 5000

# 프로세스 종료
kill -9 $(ps aux | grep 'main.py' | awk '{print $2}')

# 로그 확인
tail -100 logs/error.log
```

#### API 연결 실패
```bash
# API 키 확인
grep API_KEY .env

# 네트워크 테스트
ping api.binance.com
curl https://api.binance.com/api/v3/ping

# 방화벽 확인
sudo ufw status  # Linux
```

#### 메모리 부족
```bash
# 메모리 사용량 확인
free -h  # Linux
wmic OS get TotalVisibleMemorySize /Value  # Windows

# 임시 파일 정리
rm -rf data/temp/*
rm -rf logs/*.log.old

# 캐시 정리
python scripts/clear_cache.py
```

### 2. 긴급 대응

#### 비정상 거래 감지
```python
# 긴급 중지 스크립트
python scripts/emergency_stop.py

# 모든 포지션 청산
python scripts/close_all_positions.py --confirm
```

#### 데이터 손상
```bash
# 데이터베이스 복구
python scripts/repair_database.py

# 백업에서 복원
python scripts/restore_from_backup.py --date 20250120
```

## 성능 관리

### 1. 리소스 최적화
```yaml
# config/performance.yaml
performance:
  max_memory: 2048  # MB
  api_rate_limit: 10  # requests/second
  cache_size: 100  # MB
  log_rotation: daily
  log_retention: 7  # days
```

### 2. 로그 관리
```bash
# 로그 로테이션 설정 (logrotate)
/path/to/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### 3. 데이터베이스 최적화
```sql
-- 인덱스 생성
CREATE INDEX idx_trades_timestamp ON trades(timestamp);
CREATE INDEX idx_positions_status ON positions(status);

-- 정기 정리
DELETE FROM trades WHERE timestamp < datetime('now', '-30 days');
VACUUM;
```

## 보안 관리

### 1. API 키 보안
```bash
# 권한 제한
chmod 600 .env

# 환경변수 암호화
python scripts/encrypt_env.py

# API 키 로테이션 (월 1회)
python scripts/rotate_api_keys.py
```

### 2. 접근 제어
```nginx
# nginx 설정 (대시보드)
location / {
    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # IP 화이트리스트
    allow 192.168.1.0/24;
    deny all;
}
```

### 3. 감사 로그
```python
# 감사 로그 활성화
AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH=/secure/audit/delphi.audit
```

## 업데이트 절차

### 1. 업데이트 전 준비
```bash
# 1. 백업
./scripts/backup.sh

# 2. 변경사항 확인
git fetch
git log HEAD..origin/main --oneline

# 3. 테스트 환경 확인
python -m pytest tests/
```

### 2. 업데이트 실행
```bash
# 1. 시스템 중지
./scripts/stop_gracefully.sh

# 2. 코드 업데이트
git pull origin main

# 3. 의존성 업데이트
pip install -r requirements.txt --upgrade

# 4. 마이그레이션
python scripts/migrate.py

# 5. 시스템 재시작
./run_delphi.bat
```

### 3. 업데이트 후 확인
- [ ] 시스템 정상 시작
- [ ] API 연결 정상
- [ ] 기존 설정 유지
- [ ] 신규 기능 작동

## 운영 체크리스트

### 일일
- [ ] 시스템 상태 확인
- [ ] 거래 결과 검토
- [ ] 에러 로그 확인
- [ ] 리소스 사용량 확인

### 주간
- [ ] 성과 리포트 생성
- [ ] 로그 파일 정리
- [ ] 데이터베이스 백업
- [ ] 시스템 업데이트 확인

### 월간
- [ ] 전체 백업
- [ ] API 키 로테이션
- [ ] 성능 분석
- [ ] 보안 점검

## 비상 연락처

### 시스템 관리자
- 주 담당자: [이름] ([연락처])
- 부 담당자: [이름] ([연락처])

### 외부 지원
- Binance Support: https://www.binance.com/en/support
- Discord Server: [초대 링크]

---

**운영 중 문제 발생 시 즉시 시스템을 중지하고 관리자에게 연락하세요.**