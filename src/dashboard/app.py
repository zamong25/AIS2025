"""
델파이 트레이딩 시스템 - 프로페셔널 대시보드
실시간 성과 분석 및 모니터링 웹 애플리케이션
"""

import os
import sys
import asyncio
import json
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import requests

# FastAPI와 관련 라이브러리
from fastapi import FastAPI, Request, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn

# 보안 관련
import bcrypt
import jwt
from passlib.context import CryptContext

# 데이터베이스
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# 프로젝트 루트 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 델파이 시스템 모듈
from trading.trade_executor import TradeExecutor
from monitoring.websocket_monitor import WebSocketMonitor
from data.trade_database import get_trade_history
from dashboard.system_controller import get_system_controller
# from utils.testnet_validator import TestnetValidator  # 레거시 기능 제거됨

# FastAPI 앱 초기화
app = FastAPI(title="Delphi Trading Dashboard", version="1.0.0")

# 정적 파일 및 템플릿 설정
dashboard_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(dashboard_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(dashboard_dir, "templates"))

# 보안 설정
SECRET_KEY = "delphi-trading-system-secret-key-2024"
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# 사용자 인증 정보 (나중에 DB로 이동 가능)
USERS_DB = {
    "ais2025": {
        "username": "ais2025",
        "hashed_password": pwd_context.hash("ais2025"),
        "role": "admin"
    }
}

# 시스템 제어 패널 비밀번호 (환경 변수에서 로드, 없으면 기본값)
CONTROL_PANEL_PASSWORD = os.getenv("DASHBOARD_CONTROL_PASSWORD", "ais202512")

# 시스템 컨트롤러 인스턴스
system_controller = get_system_controller()

# 데이터베이스 설정 (대시보드용)
DATABASE_URL = f"sqlite:///{project_root}/data/database/dashboard.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DashboardSession(Base):
    """대시보드 세션 관리"""
    __tablename__ = "dashboard_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    session_token = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class PerformanceMetric(Base):
    """성과 지표 저장"""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ai_pnl = Column(Float, default=0.0)
    buyhold_pnl = Column(Float, default=0.0)
    benchmark_pnl = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)

class AIAnalysis(Base):
    """AI 에이전트 분석 히스토리"""
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    agent_name = Column(String, index=True)  # chartist, journalist, quant, stoic, synthesizer
    analysis_data = Column(String)  # JSON 문자열로 저장
    reasoning = Column(String)  # AI의 추론 과정
    score = Column(Float)
    confidence = Column(Float)
    recommendation = Column(String)  # LONG, SHORT, NEUTRAL

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# 전역 변수
websocket_connections: List[WebSocket] = []

# 데이터 영속성 경로
LOGS_FILE = os.path.join(project_root, "data", "logs", "dashboard_logs.json")
AGENT_ANALYSIS_FILE = os.path.join(project_root, "data", "logs", "agent_analysis.json")
MOCK_DATA_FILE = os.path.join(project_root, "data", "mock_dashboard.json")

# data/logs 디렉토리 자동 생성 (EC2 배포용)
logs_dir = os.path.dirname(LOGS_FILE)
os.makedirs(logs_dir, exist_ok=True)

# 로그 및 분석 데이터 저장
dashboard_logs = []
agent_analyses = []

# 시스템 프로세스 관리
system_process = None

def load_persisted_data():
    """저장된 로그와 분석 데이터 로드"""
    global dashboard_logs, agent_analyses

    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                dashboard_logs = json.load(f)
                print(f"[OK] Loaded {len(dashboard_logs)} logs")
    except Exception as e:
        print(f"[WARN] Failed to load logs: {e}")
        dashboard_logs = []

    try:
        if os.path.exists(AGENT_ANALYSIS_FILE):
            with open(AGENT_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                agent_analyses = json.load(f)
                print(f"[OK] Loaded {len(agent_analyses)} agent analyses")
    except Exception as e:
        print(f"[WARN] Failed to load agent analyses: {e}")
        agent_analyses = []

def save_log(log_data: Dict):
    """로그 저장"""
    global dashboard_logs
    dashboard_logs.append(log_data)

    # 최근 1000개만 유지
    if len(dashboard_logs) > 1000:
        dashboard_logs = dashboard_logs[-1000:]

    # 파일 저장
    try:
        with open(LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(dashboard_logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save logs: {e}")

def save_agent_analysis(analysis_data: Dict):
    """에이전트 분석 저장"""
    global agent_analyses
    agent_analyses.append(analysis_data)

    # 최근 100개만 유지
    if len(agent_analyses) > 100:
        agent_analyses = agent_analyses[-100:]

    # 파일 저장
    try:
        with open(AGENT_ANALYSIS_FILE, 'w', encoding='utf-8') as f:
            json.dump(agent_analyses, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save agent analysis: {e}")

current_system_status = {
    "mode": "TESTNET",
    "status": "RUNNING",
    "uptime": "0h 0m",
    "health": 100,
    "position": None,
    "agents": {
        "chartist": {"score": 50, "accuracy": 0, "confidence": 0},
        "journalist": {"score": 50, "accuracy": 0, "confidence": 0},
        "quant": {"score": 50, "accuracy": 0, "confidence": 0},
        "stoic": {"score": 50, "accuracy": 0, "confidence": 0}
    },
    "consensus": {"direction": "NEUTRAL", "confidence": "LOW", "score": 50},
    "performance": {
        "ai_return": 0.0,
        "buyhold_return": 0.0,
        "benchmark_return": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0
    },
    "trading_stats": {
        "win_rate": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "avg_profit": 0.0,
        "avg_loss": 0.0,
        "profit_factor": 0.0,
        "max_consecutive_losses": 0
    }
}

# 의존성 함수들
def get_db():
    """데이터베이스 세션 생성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """JWT 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """JWT 토큰 검증 - Authorization 헤더 또는 쿠키에서 토큰 읽기"""
    token = None

    # 1. Authorization 헤더에서 토큰 읽기 시도
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials

    # 2. 헤더에 없으면 쿠키에서 읽기
    if not token:
        token = request.cookies.get("access_token")

    # 3. 토큰이 없으면 401
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # 4. 토큰 검증
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# 라우트 정의
@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """대시보드 홈페이지 (로그인 전)"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request):
    """로그인 처리"""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    if username not in USERS_DB:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    user = USERS_DB[username]
    if not verify_password(password, user["hashed_password"]):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": username})
    
    # 리다이렉트 응답에 쿠키 설정
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False)
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_main(request: Request):
    """메인 대시보드"""
    # 쿠키에서 토큰 확인
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username not in USERS_DB:
            return RedirectResponse(url="/")
    except jwt.PyJWTError:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": username,
        "system_status": current_system_status
    })

@app.get("/api/status")
async def get_system_status(username: str = Depends(verify_token)):
    """시스템 상태 API"""
    return current_system_status

@app.get("/api/performance")
async def get_performance_data(username: str = Depends(verify_token), db: Session = Depends(get_db)):
    """성과 데이터 API"""
    # 최근 30일 성과 데이터 조회
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    metrics = db.query(PerformanceMetric).filter(
        PerformanceMetric.timestamp >= thirty_days_ago
    ).order_by(PerformanceMetric.timestamp.desc()).limit(100).all()
    
    if not metrics:
        # 기본 데이터 반환
        return {
            "dates": [],
            "ai_returns": [],
            "buyhold_returns": [],
            "benchmark_returns": []
        }
    
    return {
        "dates": [metric.timestamp.isoformat() for metric in reversed(metrics)],
        "ai_returns": [metric.ai_pnl for metric in reversed(metrics)],
        "buyhold_returns": [metric.buyhold_pnl for metric in reversed(metrics)],
        "benchmark_returns": [metric.benchmark_pnl for metric in reversed(metrics)]
    }

@app.get("/api/trades")
async def get_trade_history_api(username: str = Depends(verify_token)):
    """거래 히스토리 API"""
    try:
        trades = get_trade_history(limit=50)
        return {"trades": trades}
    except Exception as e:
        return {"trades": [], "error": str(e)}

# Phase 3: 대시보드 확장 API 추가
@app.get("/api/agent-accuracy")
async def get_agent_accuracy(username: str = Depends(verify_token)):
    """에이전트별 정확도 추이 API"""
    try:
        from monitoring.daily_reporter import DailyPerformanceReporter
        
        # 최근 30일간 일일 리포트 조회
        reporter = DailyPerformanceReporter()
        
        # 샘플 데이터 (실제로는 저장된 리포트에서 조회)
        dates = []
        chartist_accuracy = []
        journalist_accuracy = []
        quant_accuracy = []
        stoic_accuracy = []
        
        from datetime import datetime, timedelta
        
        for i in range(30):
            date = datetime.now() - timedelta(days=29-i)
            dates.append(date.strftime('%Y-%m-%d'))
            
            # 임시 데이터 (실제로는 저장된 accuracy 데이터)
            import random
            chartist_accuracy.append(45 + random.random() * 20)
            journalist_accuracy.append(40 + random.random() * 25)
            quant_accuracy.append(50 + random.random() * 15)
            stoic_accuracy.append(55 + random.random() * 10)
        
        return {
            "dates": dates,
            "chartist": chartist_accuracy,
            "journalist": journalist_accuracy,
            "quant": quant_accuracy,
            "stoic": stoic_accuracy
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/market-events")
async def get_market_events(username: str = Depends(verify_token)):
    """시장 이벤트 히스토리 API"""
    try:
        from monitoring.market_event_tracker import market_event_tracker
        
        # 최근 24시간 이벤트 조회
        events = market_event_tracker.get_recent_events(hours=24)
        
        return {"events": events}
    except Exception as e:
        return {"events": [], "error": str(e)}

@app.get("/api/trigger-history")
async def get_trigger_history(username: str = Depends(verify_token)):
    """트리거 발동 히스토리 API"""
    try:
        # 트리거 이력 조회 (임시 구현)
        trigger_history = [
            {
                "timestamp": "2025-07-02T15:30:00Z",
                "trigger_type": "price",
                "trigger_id": "price_20250702_1530",
                "symbol": "SOLUSDT",
                "details": "가격이 $150.50에 도달하여 트리거 발동",
                "result": "재분석 완료"
            },
            {
                "timestamp": "2025-07-02T12:15:00Z",
                "trigger_type": "volatility",
                "trigger_id": "volatility_20250702_1215", 
                "symbol": "SOLUSDT",
                "details": "변동성이 5.2% 증가하여 트리거 발동",
                "result": "시장 상황 변화 없음"
            }
        ]
        
        return {"triggers": trigger_history}
    except Exception as e:
        return {"triggers": [], "error": str(e)}

@app.get("/api/market-regime")
async def get_market_regime(username: str = Depends(verify_token)):
    """시장 체제별 성과 분석 API"""
    try:
        # 시장 체제별 성과 (임시 데이터)
        regime_performance = {
            "trending": {
                "total_trades": 45,
                "win_rate": 62.5,
                "avg_return": 2.8,
                "best_agent": "chartist"
            },
            "ranging": {
                "total_trades": 28,
                "win_rate": 48.3,
                "avg_return": 0.8,
                "best_agent": "quant"
            },
            "volatile": {
                "total_trades": 33,
                "win_rate": 55.2,
                "avg_return": 1.9,
                "best_agent": "stoic"
            }
        }
        
        return {"regimes": regime_performance}
    except Exception as e:
        return {"regimes": {}, "error": str(e)}

@app.get("/api/mock-data")
async def get_mock_data():
    """목업 대시보드 데이터 전체 반환 (시연용 - 인증 불필요)"""
    try:
        if os.path.exists(MOCK_DATA_FILE):
            with open(MOCK_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"error": "목업 데이터 파일 없음"}
    except Exception as e:
        logger.error(f"목업 데이터 로드 실패: {e}")
        return {"error": str(e)}

@app.get("/api/metrics")
async def get_metrics():
    """메트릭스 데이터 반환 (시연용 - 인증 불필요)"""
    try:
        if os.path.exists(MOCK_DATA_FILE):
            with open(MOCK_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    "metrics": data.get("metrics", {}),
                    "current_position": data.get("current_position", "HOLD")
                }
        return {"metrics": {}, "current_position": "HOLD"}
    except Exception as e:
        logger.error(f"메트릭스 로드 실패: {e}")
        return {"metrics": {}, "current_position": "HOLD", "error": str(e)}

@app.get("/api/realtime-analyses")
async def get_realtime_analyses():
    """실시간 분석 데이터 반환 (실제 데이터 사용)"""
    try:
        # 실제 agent_analysis.json에서 최신 5개 가져오기
        if os.path.exists(AGENT_ANALYSIS_FILE):
            with open(AGENT_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 최신 5개만 실시간으로 표시
                recent = data[-5:] if len(data) >= 5 else data
                return {"analyses": recent}
        return {"analyses": []}
    except Exception as e:
        logger.error(f"실시간 분석 로드 실패: {e}")
        return {"analyses": [], "error": str(e)}

@app.get("/api/analysis-history")
async def get_analysis_history():
    """에이전트 분석 히스토리 불러오기 (실제 데이터 사용)"""
    try:
        # 실제 agent_analysis.json에서 최신 5개 제외한 나머지 가져오기
        if os.path.exists(AGENT_ANALYSIS_FILE):
            with open(AGENT_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 최신 5개는 실시간에 표시되므로 나머지를 히스토리로
                if len(data) > 5:
                    history = data[:-5]  # 최신 5개 제외
                    # 최대 100개만 표시
                    history = history[-100:] if len(history) > 100 else history
                    return {"history": history}
                else:
                    return {"history": []}
        return {"history": []}
    except Exception as e:
        logger.error(f"분석 히스토리 로드 실패: {e}")
        return {"history": [], "error": str(e)}

@app.post("/api/toggle-mode")
async def toggle_mode(request: Request, username: str = Depends(verify_token)):
    """테스트넷/메인넷 모드 전환"""
    data = await request.json()
    new_mode = data.get("mode", "TESTNET")

    if new_mode not in ["TESTNET", "MAINNET"]:
        raise HTTPException(status_code=400, detail="Invalid mode")

    current_system_status["mode"] = new_mode

    # 웹소켓으로 모든 클라이언트에 업데이트 전송
    await broadcast_system_update()

    return {"status": "success", "new_mode": new_mode}

# ========== 시스템 제어 API ==========

@app.post("/api/unlock")
async def unlock_control_panel(request: Request, username: str = Depends(verify_token)):
    """제어 패널 잠금 해제 - 비밀번호 검증"""
    try:
        body = await request.json()
        password = (body.get("password") or "").strip()

        if password != CONTROL_PANEL_PASSWORD:
            return {
                "success": False,
                "message": "비밀번호가 올바르지 않습니다."
            }

        return {
            "success": True,
            "message": "제어 패널 잠금이 해제되었습니다."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"오류 발생: {str(e)}"
        }

@app.post("/api/system/start")
async def start_system():
    """트레이딩 시스템 시작"""
    global system_process
    try:
        if system_process and system_process.poll() is None:
            return {"success": False, "message": "시스템이 이미 실행 중입니다"}

        # main.py 실행 (크로스 플랫폼 지원)
        main_path = os.path.join(project_root, "src", "main.py")

        # 플랫폼별 Python 실행 파일 경로
        import platform
        if platform.system() == "Windows":
            python_exe = os.path.join(project_root, "new_venv", "Scripts", "python.exe")
        else:
            python_exe = os.path.join(project_root, "new_venv", "bin", "python")

        system_process = subprocess.Popen(
            [python_exe, main_path],
            cwd=os.path.join(project_root, "src"),
            stdout=None,
            stderr=None
        )

        await broadcast_message({
            "type": "system_status",
            "status": "running"
        })

        return {"success": True, "message": "시스템이 시작되었습니다"}
    except Exception as e:
        return {"success": False, "message": f"시작 실패: {str(e)}"}

@app.post("/api/system/stop")
async def stop_system():
    """트레이딩 시스템 정지"""
    global system_process
    try:
        if not system_process or system_process.poll() is not None:
            return {"success": False, "message": "시스템이 실행 중이 아닙니다"}

        system_process.terminate()
        system_process.wait(timeout=10)
        system_process = None

        await broadcast_message({
            "type": "system_status",
            "status": "stopped"
        })

        return {"success": True, "message": "시스템이 정지되었습니다"}
    except Exception as e:
        return {"success": False, "message": f"정지 실패: {str(e)}"}

@app.get("/api/system/status")
async def get_system_status():
    """시스템 상태 확인 (시연용 - 항상 running)"""
    # 시연용: 항상 RUNNING 상태로 표시
    return {"status": "running"}

@app.get("/api/solana-price")
async def get_solana_price():
    """바이낸스에서 SOL/USDT 가격 조회"""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "SOLUSDT"},
            timeout=5
        )
        data = response.json()
        price = float(data.get("price", 0))
        return {
            "success": True,
            "symbol": "SOL/USDT",
            "price": round(price, 2)
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"가격 조회 실패: {str(e)}",
            "price": 0
        }

@app.get("/api/logs")
async def get_logs(limit: int = 100):
    """저장된 로그 조회"""
    try:
        return {
            "success": True,
            "logs": dashboard_logs[-limit:],
            "total": len(dashboard_logs)
        }
    except Exception as e:
        return {
            "success": False,
            "logs": [],
            "error": str(e)
        }

@app.get("/api/agent-history")
async def get_agent_history(limit: int = 50):
    """저장된 에이전트 분석 조회"""
    try:
        return {
            "success": True,
            "analyses": agent_analyses[-limit:],
            "total": len(agent_analyses)
        }
    except Exception as e:
        return {
            "success": False,
            "analyses": [],
            "error": str(e)
        }

async def start_trading_system(username: str = Depends(verify_token)):
    """트레이딩 시스템 시작"""
    result = system_controller.start()

    if result["success"]:
        # 시스템 상태 업데이트
        current_system_status["status"] = "RUNNING"
        await broadcast_message({
            "type": "system_status",
            "status": "RUNNING",
            "message": result["message"],
            "pid": result.get("pid")
        })

    return result

@app.post("/api/system/restart")
async def restart_trading_system(username: str = Depends(verify_token)):
    """트레이딩 시스템 재시작"""
    # 재시작 전 알림
    await broadcast_message({
        "type": "system_status",
        "status": "RESTARTING",
        "message": "시스템을 재시작하는 중입니다..."
    })

    result = system_controller.restart()

    if result["success"]:
        # 시스템 상태 업데이트
        current_system_status["status"] = "RUNNING"
        await broadcast_message({
            "type": "system_status",
            "status": "RUNNING",
            "message": "시스템이 재시작되었습니다.",
            "pid": result.get("pid")
        })
    else:
        current_system_status["status"] = "ERROR"
        await broadcast_message({
            "type": "system_status",
            "status": "ERROR",
            "message": result["message"]
        })

    return result

@app.get("/api/system/detail-status")
async def get_detailed_system_status(username: str = Depends(verify_token)):
    """상세 시스템 상태 조회"""
    controller_status = system_controller.get_status()

    return {
        "running": controller_status["running"],
        "pid": controller_status["pid"],
        "uptime": controller_status["uptime"],
        "cpu_percent": controller_status["cpu_percent"],
        "memory_mb": controller_status["memory_mb"],
        "mode": current_system_status.get("mode", "MAINNET"),
        "health": current_system_status.get("health", 100),
        "position": current_system_status.get("position"),
        "performance": current_system_status.get("performance")
    }

@app.get("/api/system/logs")
async def get_system_logs(
    username: str = Depends(verify_token),
    lines: int = 100
):
    """시스템 로그 조회"""
    logs = system_controller.get_log_tail(lines=lines)
    return {
        "logs": logs,
        "lines": lines
    }

@app.get("/api/analysis/history")
async def get_analysis_history(
    username: str = Depends(verify_token),
    limit: int = 50,
    agent: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """AI 에이전트 분석 히스토리 조회"""
    try:
        # 쿼리 생성
        query = db.query(AIAnalysis).order_by(AIAnalysis.timestamp.desc())

        # 특정 에이전트 필터링
        if agent:
            query = query.filter(AIAnalysis.agent_name == agent)

        # 제한 적용
        analyses = query.limit(limit).all()

        # 결과 포맷팅
        results = []
        for analysis in analyses:
            try:
                analysis_data = json.loads(analysis.analysis_data) if analysis.analysis_data else {}
            except:
                analysis_data = {}

            results.append({
                "id": analysis.id,
                "timestamp": analysis.timestamp.isoformat() if analysis.timestamp else None,
                "agent": analysis.agent_name,
                "analysis": {
                    "data": analysis_data,
                    "reasoning": analysis.reasoning,
                    "score": analysis.score,
                    "confidence": analysis.confidence,
                    "recommendation": analysis.recommendation
                }
            })

        return {
            "success": True,
            "analyses": results,
            "total": len(results)
        }

    except Exception as e:
        return {
            "success": False,
            "analyses": [],
            "error": str(e)
        }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 데이터 웹소켓"""
    await websocket.accept()
    websocket_connections.append(websocket)

    try:
        while True:
            # 클라이언트 또는 main.py로부터 메시지 수신
            data = await websocket.receive_text()

            # JSON 파싱 시도
            try:
                message = json.loads(data)
                msg_type = message.get("type")

                # 로그 메시지 저장
                if msg_type == "log":
                    save_log(message)
                    await broadcast_message(message)

                # 새 실행 시작 알림
                elif msg_type == "run_start":
                    # 프론트엔드로 즉시 브로드캐스트 (기존 실시간 카드를 히스토리로 이동)
                    await broadcast_message(message)
                    logger.info(f"[RUN_START] 새 실행 시작: {message.get('run_id')}")

                # 에이전트 분석 저장 및 브로드캐스트
                elif msg_type == "agent_analysis":
                    # summary 자동 생성 (프론트 호환성)
                    analysis = message.get("analysis", {})
                    if "summary" not in analysis:
                        agent_name = message.get("agent", "")

                        # 에이전트별 요약 생성
                        if agent_name == "차티스트":
                            # 차티스트: timeframe_analysis 또는 scenario_analysis
                            timeframes = analysis.get("timeframe_analysis", {})
                            if timeframes and "1H" in timeframes:
                                main_trend = timeframes.get("1H", {}).get("trend", "중립")
                                analysis["summary"] = f"1시간봉 {main_trend} 추세"
                            else:
                                scenarios = analysis.get("scenario_analysis", [])
                                if scenarios:
                                    top = scenarios[0]
                                    scenario = top.get("scenario", "중립")
                                    prob = top.get("probability", 0)
                                    analysis["summary"] = f"{scenario} 시나리오 {prob}%"
                                else:
                                    analysis["summary"] = "차트 분석 완료"

                        elif agent_name == "저널리스트":
                            # 저널리스트: sentiment 또는 뉴스 개수
                            sentiment = analysis.get("sentiment_summary", {}).get("overall", "")
                            if sentiment:
                                analysis["summary"] = f"시장 심리: {sentiment}"
                            else:
                                short_news = analysis.get("short_term_news", [])
                                long_news = analysis.get("long_term_news", [])
                                total = len(short_news) + len(long_news)
                                if total > 0:
                                    analysis["summary"] = f"뉴스 {total}건 분석"
                                else:
                                    analysis["summary"] = "뉴스 분석 완료"

                        elif agent_name == "퀀트":
                            # 퀀트: integrated_analysis.synthesis 우선
                            integrated = analysis.get("integrated_analysis", {})
                            synthesis = integrated.get("synthesis", "")
                            if synthesis and len(synthesis) > 50:
                                analysis["summary"] = synthesis[:47] + "..."
                            elif synthesis:
                                analysis["summary"] = synthesis
                            else:
                                # 대체: recommendation 확인
                                recommendation = analysis.get("recommendation", {}).get("action", "")
                                if recommendation:
                                    analysis["summary"] = f"거래 신호: {recommendation}"
                                else:
                                    analysis["summary"] = "정량 분석 완료"

                        elif agent_name == "스토익":
                            # 스토익: scenario_strategies
                            scenarios = analysis.get("scenario_strategies", [])
                            if scenarios:
                                top = scenarios[0]
                                scenario = top.get("scenario", "")
                                prob = top.get("probability", 0)
                                rec = top.get("recommendation", "")
                                if rec:
                                    analysis["summary"] = f"{scenario} {prob}% - {rec}"
                                else:
                                    analysis["summary"] = f"{scenario} {prob}%"
                            else:
                                analysis["summary"] = "전략 분석 완료"

                        elif agent_name == "신디사이저":
                            # 신디사이저: final_decision
                            decision = analysis.get("final_decision", {})
                            action = decision.get("action", "")
                            confidence = decision.get("confidence", "")
                            if action and confidence:
                                analysis["summary"] = f"최종 결정: {action} (신뢰도: {confidence})"
                            elif action:
                                analysis["summary"] = f"최종 결정: {action}"
                            else:
                                analysis["summary"] = "종합 분석 완료"

                        else:
                            analysis["summary"] = "분석 완료"

                    save_agent_analysis(message)
                    await broadcast_message(message)

            except json.JSONDecodeError:
                pass  # keep-alive 메시지 무시

    except WebSocketDisconnect:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

async def broadcast_system_update():
    """모든 웹소켓 클라이언트에 시스템 업데이트 전송"""
    if websocket_connections:
        status_raw = current_system_status.get("status", "STOPPED")
        status = status_raw.lower()  # RUNNING/STOPPED/ERROR → running/stopped/error

        message = json.dumps({
            "type": "system_status",
            "status": status
        })

        disconnected = []
        for connection in websocket_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)

        # 끊어진 연결 제거
        for connection in disconnected:
            if connection in websocket_connections:
                websocket_connections.remove(connection)

async def broadcast_message(message_data: Dict):
    """특정 메시지를 모든 웹소켓 클라이언트에 전송"""
    if websocket_connections:
        message = json.dumps(message_data)

        disconnected = []
        for connection in websocket_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)

        # 끊어진 연결 제거
        for connection in disconnected:
            if connection in websocket_connections:
                websocket_connections.remove(connection)

async def broadcast_agent_analysis(agent_name: str, analysis: Dict):
    """AI 에이전트 분석 결과 브로드캐스트"""
    await broadcast_message({
        "type": "agent_analysis",
        "agent": agent_name,
        "analysis": analysis,
        "timestamp": datetime.now().isoformat()
    })

async def broadcast_log(message: str, level: str = "info"):
    """로그 메시지 브로드캐스트"""
    await broadcast_message({
        "type": "log",
        "message": message,
        "level": level,
        "timestamp": datetime.now().isoformat()
    })

async def broadcast_metrics(metrics: Dict):
    """성능 지표 브로드캐스트"""
    await broadcast_message({
        "type": "metrics",
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    })

async def update_system_status():
    """시스템 상태 주기적 업데이트"""
    while True:
        try:
            # 여기서 실제 시스템 상태를 조회하고 업데이트
            # 예: trade_executor, websocket_monitor 등의 상태 확인
            
            # 시뮬레이션 데이터 (실제로는 시스템에서 조회)
            import random
            current_system_status["agents"]["chartist"]["score"] = random.randint(70, 90)
            current_system_status["agents"]["journalist"]["score"] = random.randint(60, 80)
            current_system_status["agents"]["quant"]["score"] = random.randint(65, 85)
            current_system_status["agents"]["stoic"]["score"] = random.randint(75, 95)
            
            # 컨센서스 계산
            avg_score = sum(agent["score"] for agent in current_system_status["agents"].values()) / 4
            current_system_status["consensus"]["score"] = avg_score
            
            if avg_score > 70:
                current_system_status["consensus"]["direction"] = "BULLISH"
                current_system_status["consensus"]["confidence"] = "HIGH"
            elif avg_score < 30:
                current_system_status["consensus"]["direction"] = "BEARISH"
                current_system_status["consensus"]["confidence"] = "HIGH"
            else:
                current_system_status["consensus"]["direction"] = "NEUTRAL"
                current_system_status["consensus"]["confidence"] = "MEDIUM"
            
            # 웹소켓으로 업데이트 전송
            await broadcast_system_update()
            
        except Exception as e:
            print(f"Error updating system status: {e}")
        
        # 5초마다 업데이트
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작시 백그라운드 태스크 시작"""
    asyncio.create_task(update_system_status())

if __name__ == "__main__":
    print(f"[BOOT] Starting server from: {__file__}")

    # 저장된 데이터 로드
    print("[DATA] Loading persisted data...")
    load_persisted_data()

    uvicorn.run(
        app,  # app 객체를 직접 전달
        host="0.0.0.0",
        port=8001,
        reload=False,  # 객체 전달 시에는 reload 비활성화
        log_level="info"
    )