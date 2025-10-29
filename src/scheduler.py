"""
델파이 트레이딩 시스템 - 자동 실행 스케줄러
15분마다 main.py를 실행
"""

import schedule
import time
import subprocess
import logging
from datetime import datetime
import os
import sys

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('DelphiScheduler')

def run_delphi_system():
    """델파이 시스템 실행"""
    try:
        logger.info("=" * 60)
        logger.info(f"델파이 트레이딩 시스템 실행 시작: {datetime.now()}")
        
        # main.py 실행
        result = subprocess.run(
            [sys.executable, 'src/main.py'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        if result.returncode == 0:
            logger.info("✅ 델파이 시스템 실행 성공")
            logger.debug(f"출력: {result.stdout}")
        else:
            logger.error(f"❌ 델파이 시스템 실행 실패: {result.stderr}")
            
    except Exception as e:
        logger.error(f"❌ 실행 중 오류 발생: {e}")
    finally:
        logger.info(f"델파이 트레이딩 시스템 실행 완료: {datetime.now()}")
        logger.info("=" * 60)

def main():
    """스케줄러 메인 함수"""
    logger.info("🚀 델파이 자동 실행 스케줄러 시작")
    logger.info("15분마다 자동으로 실행됩니다. (Ctrl+C로 종료)")
    
    # 시작하자마자 한 번 실행
    run_delphi_system()
    
    # 1시간마다 실행 스케줄 설정
    schedule.every(60).minutes.do(run_delphi_system)
    
    # 다음 실행 시간 표시
    def show_next_run():
        jobs = schedule.get_jobs()
        if jobs:
            next_run = jobs[0].next_run
            logger.info(f"⏰ 다음 실행 예정 시간: {next_run}")
    
    # 무한 루프로 스케줄 실행
    while True:
        try:
            schedule.run_pending()
            show_next_run()
            time.sleep(60)  # 1분마다 체크
        except KeyboardInterrupt:
            logger.info("🛑 스케줄러 종료")
            break
        except Exception as e:
            logger.error(f"스케줄러 오류: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()