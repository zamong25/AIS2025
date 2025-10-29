@echo off
echo [%date% %time%] 델파이 트레이딩 시스템 실행 시작 >> logs\scheduler.log

cd /d C:\Users\PCW\Desktop\delphi-trader

:: Python 가상환경 활성화 (있다면)
:: call venv\Scripts\activate

:: 메인 스크립트 실행
python src\main.py >> logs\scheduler.log 2>&1

echo [%date% %time%] 델파이 트레이딩 시스템 실행 완료 >> logs\scheduler.log
echo ======================================== >> logs\scheduler.log