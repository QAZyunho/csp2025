#!/bin/bash

# 파이프라인 실행 스크립트
# cron으로 새벽 4시에 실행됨

set -e

echo "🌅 $(date): 새벽 4시 파이프라인 시작" >> /var/log/pipeline.log

# Python 경로 설정
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# 파이프라인 실행
cd /app
python scheduler/daily_pipeline.py

echo "✅ $(date): 파이프라인 완료" >> /var/log/pipeline.log