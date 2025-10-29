#!/bin/bash
# SQLite 데이터베이스 브라우저 뷰어 실행 스크립트

echo "🗄️  델파이 트레이더 DB 뷰어 시작 중..."
echo ""
echo "데이터베이스: data/database/delphi_trades.db"
echo ""

cd "$(dirname "$0")/.."

# datasette 실행 (포트 8001)
../new_venv/Scripts/datasette serve data/database/delphi_trades.db \
    --host 0.0.0.0 \
    --port 8001 \
    --metadata scripts/db_metadata.json \
    --open

echo ""
echo "✅ DB 뷰어가 시작되었습니다!"
echo "🌐 브라우저에서 http://localhost:8001 으로 접속하세요"
echo ""
echo "종료하려면 Ctrl+C 를 누르세요"
