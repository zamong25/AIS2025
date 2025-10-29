"""
델파이 트레이딩 시스템 제어 모듈
main.py 프로세스 시작/정지/재시작 관리
"""

import os
import sys
import signal
import subprocess
import time
import psutil
from typing import Optional, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SystemController:
    """시스템 프로세스 제어 클래스"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.start_time: Optional[datetime] = None
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.main_py_path = os.path.join(self.project_root, "src", "main.py")
        self.python_path = os.path.join(self.project_root, "new_venv", "Scripts", "python.exe")
        self.log_file = os.path.join(self.project_root, "data", "logs", "system.log")

    def is_running(self) -> bool:
        """시스템 실행 중 여부 확인"""
        if self.pid is None:
            return False

        try:
            process = psutil.Process(self.pid)
            # 프로세스가 존재하고 python 프로세스인지 확인
            return process.is_running() and "python" in process.name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self.pid = None
            self.process = None
            return False

    def get_status(self) -> Dict:
        """시스템 상태 조회"""
        status = {
            "running": self.is_running(),
            "pid": self.pid,
            "uptime": None,
            "cpu_percent": 0.0,
            "memory_mb": 0.0
        }

        if self.is_running() and self.start_time:
            # 가동 시간 계산
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            status["uptime"] = f"{hours}h {minutes}m"

            try:
                process = psutil.Process(self.pid)
                status["cpu_percent"] = process.cpu_percent(interval=0.1)
                status["memory_mb"] = process.memory_info().rss / 1024 / 1024
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return status

    def start(self) -> Dict:
        """시스템 시작"""
        if self.is_running():
            return {
                "success": False,
                "message": "시스템이 이미 실행 중입니다.",
                "pid": self.pid
            }

        try:
            # 로그 디렉토리 확인
            log_dir = os.path.dirname(self.log_file)
            os.makedirs(log_dir, exist_ok=True)

            # 로그 파일 열기
            log_f = open(self.log_file, "a", encoding="utf-8")

            # 프로세스 시작
            self.process = subprocess.Popen(
                [self.python_path, self.main_py_path],
                cwd=os.path.join(self.project_root, "src"),
                stdout=log_f,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )

            self.pid = self.process.pid
            self.start_time = datetime.now()

            # 프로세스가 정상 시작되었는지 확인 (1초 대기)
            time.sleep(1)
            if not self.is_running():
                return {
                    "success": False,
                    "message": "시스템 시작 실패 (프로세스가 즉시 종료됨)",
                    "pid": None
                }

            logger.info(f"시스템 시작 성공: PID={self.pid}")
            return {
                "success": True,
                "message": "시스템이 성공적으로 시작되었습니다.",
                "pid": self.pid,
                "start_time": self.start_time.isoformat()
            }

        except Exception as e:
            logger.error(f"시스템 시작 실패: {e}")
            return {
                "success": False,
                "message": f"시스템 시작 실패: {str(e)}",
                "pid": None
            }

    def stop(self, force: bool = False) -> Dict:
        """시스템 정지"""
        if not self.is_running():
            return {
                "success": False,
                "message": "시스템이 실행 중이 아닙니다."
            }

        try:
            process = psutil.Process(self.pid)

            if force:
                # 강제 종료
                process.kill()
                message = "시스템이 강제 종료되었습니다."
            else:
                # 정상 종료
                if sys.platform == "win32":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
                message = "시스템 종료 신호를 전송했습니다."

            # 종료 대기 (최대 10초)
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                if not force:
                    # 정상 종료 실패 시 강제 종료
                    logger.warning("정상 종료 실패, 강제 종료 시도")
                    process.kill()
                    message = "정상 종료 실패하여 강제 종료했습니다."

            self.pid = None
            self.process = None
            self.start_time = None

            logger.info(f"시스템 정지 성공: {message}")
            return {
                "success": True,
                "message": message
            }

        except Exception as e:
            logger.error(f"시스템 정지 실패: {e}")
            return {
                "success": False,
                "message": f"시스템 정지 실패: {str(e)}"
            }

    def restart(self) -> Dict:
        """시스템 재시작"""
        # 먼저 정지
        if self.is_running():
            stop_result = self.stop()
            if not stop_result["success"]:
                return stop_result

            # 정지 후 2초 대기
            time.sleep(2)

        # 다시 시작
        return self.start()

    def get_log_tail(self, lines: int = 100) -> str:
        """최근 로그 조회"""
        try:
            if not os.path.exists(self.log_file):
                return "로그 파일이 존재하지 않습니다."

            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return "".join(recent_lines)

        except Exception as e:
            logger.error(f"로그 조회 실패: {e}")
            return f"로그 조회 실패: {str(e)}"


# 싱글톤 인스턴스
_system_controller = None

def get_system_controller() -> SystemController:
    """시스템 컨트롤러 싱글톤 인스턴스 반환"""
    global _system_controller
    if _system_controller is None:
        _system_controller = SystemController()
    return _system_controller
