#!/bin/bash
set -e

echo "Starting Kilterboard API..."

# 데이터베이스가 없으면 다운로드
if [ ! -f "./kilter.db" ]; then
    echo "Database not found. Downloading..."
    echo "$KILTER_PASSWORD" | boardlib database kilter ./kilter.db --username "$KILTER_USERNAME"
    echo "Database downloaded!"
else
    echo "Database exists: $(ls -lh kilter.db)"
fi

echo "Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT
