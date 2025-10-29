# AWS EC2 배포 가이드

델파이 트레이더 프로젝트를 AWS EC2에 배포하기 위한 단계별 가이드입니다.

## 📋 사전 준비

### 1. AWS EC2 인스턴스 생성
- **OS**: Ubuntu 22.04 LTS 또는 Amazon Linux 2023
- **인스턴스 타입**: t2.medium 이상 권장 (메모리 4GB+)
- **스토리지**: 20GB 이상

### 2. 보안 그룹 설정
EC2 인스턴스의 보안 그룹에서 다음 인바운드 규칙 추가:

| 포트 | 프로토콜 | 설명 |
|------|----------|------|
| 8000 | TCP | 대시보드 HTTP 접속 |
| 8001 | TCP | 웹소켓 연결 |
| 22 | TCP | SSH 접속 |

## 🚀 배포 단계

### 1. EC2 접속 및 기본 패키지 설치
```bash
# EC2 인스턴스 접속
ssh -i your-key.pem ubuntu@your-ec2-ip

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python 및 필수 패키지 설치
sudo apt install -y python3.11 python3.11-venv python3-pip git
```

### 2. 프로젝트 클론
```bash
# 프로젝트 디렉토리로 이동
cd ~

# 저장소 클론
git clone your-repository-url delphi-trader
cd delphi-trader
```

### 3. 가상환경 생성 및 의존성 설치
```bash
# 가상환경 생성
python3.11 -m venv new_venv

# 가상환경 활성화
source new_venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 4. 환경변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
nano .env
```

**.env 파일 설정 예시** (EC2용):
```bash
# Binance API
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_api_secret

# Gemini API
GEMINI_API_KEY=your_actual_gemini_key

# OpenAI API (선택)
OPENAI_API_KEY=your_actual_openai_key

# Discord Webhook
DISCORD_WEBHOOK_URL=your_actual_webhook_url

# Dashboard WebSocket (EC2 공인 IP 또는 도메인)
DASHBOARD_WS_URL=ws://your-ec2-public-ip:8001/ws
```

**중요**: `DASHBOARD_WS_URL`을 EC2의 공인 IP 주소로 설정해야 합니다!

### 5. 디렉토리 자동 생성 확인
필요한 디렉토리는 자동으로 생성됩니다:
- `data/logs/` - 로그 파일 저장
- `data/database/` - SQLite DB 저장
- `data/screenshots/` - 차트 캡처 이미지 저장

수동으로 확인하려면:
```bash
ls -la data/
```

### 6. 대시보드 실행
```bash
# 대시보드 백그라운드 실행
cd ~/delphi-trader/src/dashboard
nohup ../../new_venv/bin/python app.py > dashboard.log 2>&1 &

# 실행 확인
ps aux | grep app.py
tail -f dashboard.log
```

### 7. 브라우저 접속
```
http://your-ec2-public-ip:8000
```

## 🔄 시스템 실행

### 대시보드에서 실행
1. 브라우저에서 대시보드 접속
2. "시작" 버튼 클릭 (비밀번호: admin)
3. 실시간 분석 모니터링

### 스케줄러 실행 (1시간마다 자동 분석)
```bash
cd ~/delphi-trader
source new_venv/bin/activate
python src/scheduler.py
```

## 🛡️ 프로덕션 권장사항

### 1. 방화벽 설정
```bash
# UFW 활성화
sudo ufw enable

# 필수 포트만 허용
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
```

### 2. Systemd 서비스 등록 (자동 재시작)

**대시보드 서비스** (`/etc/systemd/system/delphi-dashboard.service`):
```ini
[Unit]
Description=Delphi Trader Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/delphi-trader/src/dashboard
Environment="PATH=/home/ubuntu/delphi-trader/new_venv/bin"
ExecStart=/home/ubuntu/delphi-trader/new_venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**스케줄러 서비스** (`/etc/systemd/system/delphi-scheduler.service`):
```ini
[Unit]
Description=Delphi Trader Scheduler
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/delphi-trader
Environment="PATH=/home/ubuntu/delphi-trader/new_venv/bin"
ExecStart=/home/ubuntu/delphi-trader/new_venv/bin/python src/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**서비스 활성화**:
```bash
# 서비스 등록
sudo systemctl daemon-reload

# 서비스 시작
sudo systemctl start delphi-dashboard
sudo systemctl start delphi-scheduler

# 부팅 시 자동 시작
sudo systemctl enable delphi-dashboard
sudo systemctl enable delphi-scheduler

# 상태 확인
sudo systemctl status delphi-dashboard
sudo systemctl status delphi-scheduler
```

### 3. Nginx 리버스 프록시 (선택)
도메인 사용 시 Nginx로 80포트 → 8000포트 리버스 프록시 설정

```bash
sudo apt install -y nginx

# Nginx 설정
sudo nano /etc/nginx/sites-available/delphi
```

설정 예시:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# 설정 활성화
sudo ln -s /etc/nginx/sites-available/delphi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 🔍 문제 해결

### 로그 확인
```bash
# 대시보드 로그
sudo journalctl -u delphi-dashboard -f

# 스케줄러 로그
sudo journalctl -u delphi-scheduler -f

# 애플리케이션 로그
tail -f ~/delphi-trader/logs/delphi.log
```

### 포트 확인
```bash
# 포트 사용 확인
sudo netstat -tlnp | grep -E '8000|8001'

# 또는
sudo lsof -i :8000
sudo lsof -i :8001
```

### 서비스 재시작
```bash
sudo systemctl restart delphi-dashboard
sudo systemctl restart delphi-scheduler
```

## 📊 모니터링

### 리소스 사용량
```bash
# CPU/메모리 확인
htop

# 디스크 사용량
df -h
```

### 데이터베이스 확인
```bash
# SQLite DB 크기 확인
ls -lh ~/delphi-trader/data/database/delphi_trades.db

# DB 쿼리 (선택)
sqlite3 ~/delphi-trader/data/database/delphi_trades.db "SELECT COUNT(*) FROM trades;"
```

## 🔐 보안 체크리스트

- [x] `.env` 파일에 실제 API 키 입력
- [x] 보안 그룹에서 불필요한 포트 차단
- [x] SSH 키 기반 인증 사용 (비밀번호 비활성화)
- [x] 정기적인 시스템 업데이트
- [x] 로그 모니터링 및 알림 설정

---

**버전**: 1.0.0  
**최종 수정**: 2024-01-28  
**문의**: 프로젝트 GitHub Issues
