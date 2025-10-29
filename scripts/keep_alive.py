"""
시스템 상태 체크 및 자동 복구 스크립트
델파이 시스템이 중단되었을 때 자동으로 재시작
"""

import psutil
import subprocess
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    filename='logs/keep_alive.log'
)

def is_delphi_running():
    """델파이 프로세스가 실행 중인지 확인"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any('main.py' in arg for arg in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def start_delphi():
    """델파이 시스템 시작"""
    try:
        subprocess.Popen(['python', 'src/main.py'])
        logging.info("✅ 델파이 시스템 시작됨")
    except Exception as e:
        logging.error(f"❌ 시작 실패: {e}")

def main():
    """메인 모니터링 루프"""
    logging.info("🔍 델파이 시스템 모니터링 시작")
    
    while True:
        try:
            if not is_delphi_running():
                logging.warning("⚠️ 델파이 시스템이 실행되지 않음. 재시작 중...")
                start_delphi()
                time.sleep(60)  # 시작 후 1분 대기
            
            time.sleep(300)  # 5분마다 체크
            
        except KeyboardInterrupt:
            logging.info("모니터링 종료")
            break
        except Exception as e:
            logging.error(f"모니터링 오류: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()