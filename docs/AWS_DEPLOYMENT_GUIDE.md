# 델파이 트레이더 AWS 배포 가이드

> 프로덕션 환경(AWS EC2)에 델파이 트레이딩 시스템을 배포하는 가이드입니다.

## 📋 목차

1. [사전 준비](#사전-준비)
2. [EC2 인스턴스 설정](#ec2-인스턴스-설정)
3. [시스템 설치](#시스템-설치)
4. [환경 변수 설정](#환경-변수-설정)
5. [보안 설정](#보안-설정)
6. [서비스 등록](#서비스-등록)
7. [Nginx 리버스 프록시 설정](#nginx-리버스-프록시-설정)
8. [SSL 인증서 설정](#ssl-인증서-설정)
9. [모니터링 및 로그](#모니터링-및-로그)
10. [백업 및 복구](#백업-및-복구)
11. [트러블슈팅](#트러블슈팅)

## 사전 준비

### 필요한 계정
- AWS 계정
- Binance Futures 계정 (API 키 발급 필요)
- Google Cloud (Gemini API 키 발급 필요)
- Discord 서버 (알림 수신용 웹훅 URL)

### 로컬 환경
- Git
- SSH 클라이언트
- 텍스트 에디터

## EC2 인스턴스 설정

### 1. EC2 인스턴스 생성

**권장 사양:**
- **인스턴스 타입**: t3.medium (2 vCPU, 4GB RAM) 이상
- **OS**: Ubuntu 22.04 LTS
- **스토리지**: 30GB EBS (gp3)
- **리전**: ap-northeast-2 (서울)

**보안 그룹 설정:**
```
인바운드 규칙:
- SSH (22): 내 IP 주소만 허용
- HTTP (80): 0.0.0.0/0 (나중에 HTTPS로 리다이렉트)
- HTTPS (443): 0.0.0.0/0
- Custom TCP (8000): 내 IP 주소만 허용 (대시보드, 선택사항)
```

### 2. Elastic IP 할당

고정 IP 주소 할당:
```bash
# AWS 콘솔에서:
# EC2 → Elastic IPs → Allocate Elastic IP address → 인스턴스에 연결
```

### 3. SSH 접속

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@your-elastic-ip
```

## 시스템 설치

### 1. 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. 필수 패키지 설치

```bash
# Python 3.11 설치
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 기타 필수 도구
sudo apt install -y git build-essential nginx certbot python3-certbot-nginx htop
```

### 3. 프로젝트 클론

```bash
cd /home/ubuntu
git clone https://github.com/your-username/delphi-trader.git
cd delphi-trader
```

### 4. Python 가상 환경 설정

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 환경 변수 설정

### 1. .env 파일 생성

```bash
cp .env.example .env
nano .env
```

### 2. 필수 환경 변수 입력

```env
# 대시보드 제어 패널 비밀번호 (강력한 비밀번호로 변경!)
DASHBOARD_CONTROL_PASSWORD=your_strong_password_here

# 바이낸스 API (반드시 실제 값으로 변경)
BINANCE_API_KEY=your_real_binance_api_key
BINANCE_SECRET_KEY=your_real_binance_secret_key

# Gemini API
GEMINI_API_KEY=your_real_gemini_api_key

# 디스코드 웹훅
DISCORD_WEBHOOK_URL=your_real_discord_webhook_url

# 프로덕션 모드
PRODUCTION_MODE=true

# JWT 시크릿 (강력한 무작위 문자열로 변경!)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# 로그 레벨
LOG_LEVEL=INFO
```

**보안 주의사항:**
- `.env` 파일 권한 설정: `chmod 600 .env`
- 절대 Git에 커밋하지 마세요
- API 키는 읽기 전용(Read-Only) 권한으로 제한 권장

## 보안 설정

### 1. 방화벽 설정 (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Fail2ban 설치 (SSH 브루트포스 방어)

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. 사용자 권한 설정

```bash
# 프로젝트 디렉토리 소유권 설정
sudo chown -R ubuntu:ubuntu /home/ubuntu/delphi-trader

# 로그 디렉토리 생성 및 권한 설정
mkdir -p data/logs data/database
chmod 755 data
chmod 755 data/logs data/database
```

## 서비스 등록

### 1. Systemd 서비스 파일 생성

**메인 트레이딩 시스템 서비스:**

```bash
sudo nano /etc/systemd/system/delphi-trader.service
```

```ini
[Unit]
Description=Delphi Trading System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/delphi-trader/src
Environment="PATH=/home/ubuntu/delphi-trader/venv/bin"
ExecStart=/home/ubuntu/delphi-trader/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/delphi-trader/data/logs/system.log
StandardError=append:/home/ubuntu/delphi-trader/data/logs/system.log

[Install]
WantedBy=multi-user.target
```

**대시보드 서비스:**

```bash
sudo nano /etc/systemd/system/delphi-dashboard.service
```

```ini
[Unit]
Description=Delphi Trading Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/delphi-trader/src/dashboard
Environment="PATH=/home/ubuntu/delphi-trader/venv/bin"
ExecStart=/home/ubuntu/delphi-trader/venv/bin/python app.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/delphi-trader/data/logs/dashboard.log
StandardError=append:/home/ubuntu/delphi-trader/data/logs/dashboard.log

[Install]
WantedBy=multi-user.target
```

### 2. 서비스 활성화

```bash
# 서비스 등록
sudo systemctl daemon-reload

# 부팅 시 자동 시작 설정
sudo systemctl enable delphi-trader
sudo systemctl enable delphi-dashboard

# 서비스 시작
sudo systemctl start delphi-trader
sudo systemctl start delphi-dashboard

# 상태 확인
sudo systemctl status delphi-trader
sudo systemctl status delphi-dashboard
```

### 3. 서비스 관리 명령어

```bash
# 시작
sudo systemctl start delphi-trader
sudo systemctl start delphi-dashboard

# 정지
sudo systemctl stop delphi-trader
sudo systemctl stop delphi-dashboard

# 재시작
sudo systemctl restart delphi-trader
sudo systemctl restart delphi-dashboard

# 로그 확인
sudo journalctl -u delphi-trader -f
sudo journalctl -u delphi-dashboard -f
```

## Nginx 리버스 프록시 설정

### 1. Nginx 설정 파일 생성

```bash
sudo nano /etc/nginx/sites-available/delphi-trader
```

```nginx
# WebSocket 업그레이드를 위한 맵 설정
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    server_name your-domain.com;  # 실제 도메인으로 변경

    # 보안 헤더
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 정적 파일 캐싱
    location /static {
        alias /home/ubuntu/delphi-trader/src/dashboard/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # WebSocket 프록시
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 타임아웃
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # API 및 대시보드 프록시
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 타임아웃 설정
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 로그 파일
    access_log /var/log/nginx/delphi-trader-access.log;
    error_log /var/log/nginx/delphi-trader-error.log;
}
```

### 2. Nginx 설정 활성화

```bash
# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/delphi-trader /etc/nginx/sites-enabled/

# 기본 사이트 비활성화
sudo rm /etc/nginx/sites-enabled/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

## SSL 인증서 설정

### 1. Certbot으로 Let's Encrypt 인증서 발급

```bash
# 인증서 자동 발급 및 Nginx 설정 업데이트
sudo certbot --nginx -d your-domain.com

# 인증서 자동 갱신 테스트
sudo certbot renew --dry-run
```

### 2. 자동 갱신 설정 확인

```bash
# Certbot 타이머 상태 확인 (자동 갱신)
sudo systemctl status certbot.timer
```

## 모니터링 및 로그

### 1. 로그 확인

```bash
# 시스템 로그
tail -f /home/ubuntu/delphi-trader/data/logs/system.log

# 대시보드 로그
tail -f /home/ubuntu/delphi-trader/data/logs/dashboard.log

# Nginx 로그
sudo tail -f /var/log/nginx/delphi-trader-access.log
sudo tail -f /var/log/nginx/delphi-trader-error.log

# Systemd 저널
sudo journalctl -u delphi-trader -f
sudo journalctl -u delphi-dashboard -f
```

### 2. 시스템 리소스 모니터링

```bash
# CPU, 메모리 실시간 모니터링
htop

# 디스크 사용량
df -h

# 프로세스 확인
ps aux | grep python
```

### 3. 로그 로테이션 설정

```bash
sudo nano /etc/logrotate.d/delphi-trader
```

```
/home/ubuntu/delphi-trader/data/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
    postrotate
        systemctl reload delphi-trader > /dev/null 2>&1
        systemctl reload delphi-dashboard > /dev/null 2>&1
    endscript
}
```

## 백업 및 복구

### 1. 자동 백업 스크립트

```bash
nano ~/backup-delphi.sh
```

```bash
#!/bin/bash

# 백업 디렉토리
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="/home/ubuntu/delphi-trader"

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

# 데이터베이스 백업
cp "$PROJECT_DIR/data/database/delphi_trades.db" "$BACKUP_DIR/delphi_trades_$DATE.db"

# 로그 백업 (최근 7일)
tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" "$PROJECT_DIR/data/logs"

# 설정 파일 백업
cp "$PROJECT_DIR/.env" "$BACKUP_DIR/env_$DATE.backup"
cp "$PROJECT_DIR/config/config.yaml" "$BACKUP_DIR/config_$DATE.yaml"

# 30일 이상 된 백업 삭제
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.backup" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
chmod +x ~/backup-delphi.sh
```

### 2. Cron으로 자동 백업 설정

```bash
crontab -e
```

```cron
# 매일 새벽 3시에 백업 실행
0 3 * * * /home/ubuntu/backup-delphi.sh >> /home/ubuntu/backup.log 2>&1
```

### 3. S3 백업 (선택사항)

```bash
# AWS CLI 설치
sudo apt install -y awscli

# AWS 자격 증명 설정
aws configure

# S3 백업 스크립트
aws s3 sync /home/ubuntu/backups s3://your-bucket-name/delphi-trader-backups/
```

## 트러블슈팅

### 1. 서비스가 시작되지 않을 때

```bash
# 상세 에러 로그 확인
sudo journalctl -u delphi-trader -n 50 --no-pager

# 설정 파일 확인
cat /etc/systemd/system/delphi-trader.service

# 권한 확인
ls -la /home/ubuntu/delphi-trader/src/main.py
```

### 2. 대시보드 접속이 안 될 때

```bash
# 포트 사용 확인
sudo netstat -tulpn | grep 8000

# Nginx 상태 확인
sudo systemctl status nginx

# Nginx 설정 테스트
sudo nginx -t

# 방화벽 규칙 확인
sudo ufw status
```

### 3. WebSocket 연결 실패

```bash
# Nginx 에러 로그 확인
sudo tail -100 /var/log/nginx/delphi-trader-error.log

# WebSocket 프록시 설정 확인
sudo nano /etc/nginx/sites-available/delphi-trader
```

### 4. 메모리 부족

```bash
# 메모리 사용량 확인
free -h

# 스왑 파일 생성 (4GB)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 부팅 시 자동 마운트
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 5. 디스크 공간 부족

```bash
# 디스크 사용량 확인
df -h

# 대용량 파일 찾기
sudo du -h /home/ubuntu/delphi-trader | sort -hr | head -20

# 오래된 로그 삭제
find /home/ubuntu/delphi-trader/data/logs -name "*.log" -mtime +30 -delete
```

## 성능 최적화

### 1. Python 프로세스 우선순위 조정

```bash
# nice 값 설정 (-20 ~ 19, 낮을수록 높은 우선순위)
sudo renice -n -5 -p $(pgrep -f "python main.py")
```

### 2. 데이터베이스 최적화

```bash
# 데이터베이스 VACUUM (정기적 실행 권장)
sqlite3 /home/ubuntu/delphi-trader/data/database/delphi_trades.db "VACUUM;"
```

### 3. Nginx 성능 튜닝

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
client_max_body_size 20M;
```

## 보안 체크리스트

- [ ] 강력한 비밀번호 설정 (DASHBOARD_CONTROL_PASSWORD, JWT_SECRET_KEY)
- [ ] SSH 키 기반 인증 사용 (비밀번호 로그인 비활성화)
- [ ] 방화벽(UFW) 활성화 및 최소 포트만 개방
- [ ] Fail2ban 설치 및 활성화
- [ ] SSL/TLS 인증서 설정 (HTTPS)
- [ ] .env 파일 권한 600 설정
- [ ] 정기적인 시스템 업데이트
- [ ] 로그 정기적 검토
- [ ] 백업 자동화 및 복구 테스트
- [ ] Binance API 키 권한 최소화 (읽기 전용 또는 필요한 권한만)

## 유용한 명령어 모음

```bash
# 전체 서비스 재시작
sudo systemctl restart delphi-trader delphi-dashboard nginx

# 실시간 로그 모니터링 (모든 서비스)
sudo journalctl -f

# Git 최신 코드 pull 및 재시작
cd /home/ubuntu/delphi-trader
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart delphi-trader delphi-dashboard

# 데이터베이스 백업 즉시 실행
~/backup-delphi.sh

# 시스템 리소스 요약
top -bn1 | head -20
df -h
free -h
```

## 지원 및 문의

문제가 발생하면:
1. 로그 파일 확인
2. GitHub Issues에 오류 내용과 로그 첨부
3. Discord 커뮤니티 문의

---

**배포 성공을 기원합니다! 🚀**
