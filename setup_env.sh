#!/bin/bash
# direct_setup_env.sh - API 키 직접 설정 스크립트
# Docker 컨테이너용 환경변수 자동 생성

set -e

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 CS Project - 환경변수 직접 설정${NC}"
echo "======================================"

# .env 파일 생성
cat > .env << 'EOF'
# CS Project 환경변수 설정 파일
# Docker 컨테이너용 - 자동 생성됨

# 🤖 Gemini API 설정
GEMINI_API_KEY=AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs

# 🌐 Google Cloud API 설정  
GOOGLE_CLOUD_API_KEY=AIzaSyDsiwihLcnZuccu_6XPno0R0BH-NbUxVCQ

# 📰 네이버 검색 API 설정
NAVER_CLIENT_ID=RPUhkWY7UVq81hlMiHNL
NAVER_CLIENT_SECRET=u5HUugAYuv

# 📚 국립중앙도서관 API 설정
NATIONAL_LIBRARY_API_KEY=0dfddd5045ff123245cc00ab9034d122d6b6c1e6fba60c838f7304b8f98a69c1

# 🔥 Firebase 설정
FIREBASE_CONFIG_PATH=./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json

# ⚙️ 파이프라인 설정
PIPELINE_MODE=immediate

# 🐳 Docker 관련 설정
PYTHONPATH=/app
PYTHONUNBUFFERED=1
TZ=Asia/Seoul
EOF

echo -e "${GREEN}✅ .env 파일이 생성되었습니다!${NC}"

# .gitignore 업데이트
if [ ! -f ".gitignore" ]; then
    touch ".gitignore"
fi

if ! grep -q "^\.env$" ".gitignore" 2>/dev/null; then
    echo ".env" >> ".gitignore"
    echo -e "${GREEN}✅ .env를 .gitignore에 추가했습니다${NC}"
fi