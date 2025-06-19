# 루트 Dockerfile 수정 - 환경변수 처리 개선
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치 (기존과 동일)
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates cron tzdata \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 타임존 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 모든 소스 코드 복사
COPY trend-collector/ ./trend-collector/
COPY trend-analyzer/ ./trend-analyzer/
COPY library-searcher/ ./library-searcher/
COPY scheduler/ ./scheduler/

# Firebase 설정 파일 복사
COPY csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json

# 환경변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul

# 로그 디렉토리 생성
RUN mkdir -p /var/log /app/logs

# 환경변수 검증 스크립트 생성
RUN echo '#!/bin/bash' > /app/check_env.sh && \
    echo 'echo "🔍 환경변수 검증 중..."' >> /app/check_env.sh && \
    echo '' >> /app/check_env.sh && \
    echo '# 필수 환경변수 체크' >> /app/check_env.sh && \
    echo 'MISSING_VARS=""' >> /app/check_env.sh && \
    echo '' >> /app/check_env.sh && \
    echo 'if [ -z "$GEMINI_API_KEY" ]; then' >> /app/check_env.sh && \
    echo '    echo "❌ GEMINI_API_KEY가 설정되지 않았습니다"' >> /app/check_env.sh && \
    echo '    MISSING_VARS="$MISSING_VARS GEMINI_API_KEY"' >> /app/check_env.sh && \
    echo 'fi' >> /app/check_env.sh && \
    echo '' >> /app/check_env.sh && \
    echo 'if [ -z "$NAVER_CLIENT_ID" ]; then' >> /app/check_env.sh && \
    echo '    echo "❌ NAVER_CLIENT_ID가 설정되지 않았습니다"' >> /app/check_env.sh && \
    echo '    MISSING_VARS="$MISSING_VARS NAVER_CLIENT_ID"' >> /app/check_env.sh && \
    echo 'fi' >> /app/check_env.sh && \
    echo '' >> /app/check_env.sh && \
    echo 'if [ -z "$NAVER_CLIENT_SECRET" ]; then' >> /app/check_env.sh && \
    echo '    echo "❌ NAVER_CLIENT_SECRET가 설정되지 않았습니다"' >> /app/check_env.sh && \
    echo '    MISSING_VARS="$MISSING_VARS NAVER_CLIENT_SECRET"' >> /app/check_env.sh && \
    echo 'fi' >> /app/check_env.sh && \
    echo '' >> /app/check_env.sh && \
    echo 'if [ -n "$MISSING_VARS" ]; then' >> /app/check_env.sh && \
    echo '    echo ""' >> /app/check_env.sh && \
    echo '    echo "💡 다음 환경변수들을 설정해주세요:"' >> /app/check_env.sh && \
    echo '    for var in $MISSING_VARS; do' >> /app/check_env.sh && \
    echo '        echo "  export $var=\"your_${var,,}\""' >> /app/check_env.sh && \
    echo '    done' >> /app/check_env.sh && \
    echo '    echo ""' >> /app/check_env.sh && \
    echo '    exit 1' >> /app/check_env.sh && \
    echo 'fi' >> /app/check_env.sh && \
    echo '' >> /app/check_env.sh && \
    echo 'echo "✅ 모든 환경변수가 설정되었습니다"' >> /app/check_env.sh && \
    chmod +x /app/check_env.sh

# 통합 파이프라인 실행 스크립트 생성 (환경변수 검증 포함)
RUN echo '#!/bin/bash' > /app/run_pipeline.sh && \
    echo 'set -e' >> /app/run_pipeline.sh && \
    echo 'set -o pipefail' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 환경변수 검증' >> /app/run_pipeline.sh && \
    echo '/app/check_env.sh' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 로그 파일 설정' >> /app/run_pipeline.sh && \
    echo 'DATE=$(date "+%y%m%d")' >> /app/run_pipeline.sh && \
    echo 'LOG_FILE="/var/log/pipeline_${DATE}.log"' >> /app/run_pipeline.sh && \
    echo 'touch "$LOG_FILE"' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 로그 함수' >> /app/run_pipeline.sh && \
    echo 'log() {' >> /app/run_pipeline.sh && \
    echo '    local message="[$(date "+%Y-%m-%d %H:%M:%S")] $1"' >> /app/run_pipeline.sh && \
    echo '    echo "$message"' >> /app/run_pipeline.sh && \
    echo '    echo "$message" >> "$LOG_FILE"' >> /app/run_pipeline.sh && \
    echo '}' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'DATE=$(date "+%y%m%d")' >> /app/run_pipeline.sh && \
    echo 'log "🚀 통합 파이프라인 시작 (날짜: $DATE)"' >> /app/run_pipeline.sh && \
    echo 'log "=================================================================="' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 1단계: 키워드 수집' >> /app/run_pipeline.sh && \
    echo 'log "📡 1단계: 트렌드 키워드 수집 시작..."' >> /app/run_pipeline.sh && \
    echo 'python3 trend-collector/keyword_collector.py' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'if [ $? -eq 0 ]; then' >> /app/run_pipeline.sh && \
    echo '    log "✅ 1단계 완료: 키워드 수집"' >> /app/run_pipeline.sh && \
    echo 'else' >> /app/run_pipeline.sh && \
    echo '    log "❌ 1단계 실패: 키워드 수집"' >> /app/run_pipeline.sh && \
    echo '    exit 1' >> /app/run_pipeline.sh && \
    echo 'fi' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'sleep 10' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 2단계: 뉴스 수집' >> /app/run_pipeline.sh && \
    echo 'log "📰 2단계: 네이버 뉴스 수집 시작..."' >> /app/run_pipeline.sh && \
    echo 'python3 trend-collector/naver_news_collector.py \' >> /app/run_pipeline.sh && \
    echo '    --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json \' >> /app/run_pipeline.sh && \
    echo '    --max_articles 5' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'if [ $? -eq 0 ]; then' >> /app/run_pipeline.sh && \
    echo '    log "✅ 2단계 완료: 뉴스 수집"' >> /app/run_pipeline.sh && \
    echo 'else' >> /app/run_pipeline.sh && \
    echo '    log "❌ 2단계 실패: 뉴스 수집"' >> /app/run_pipeline.sh && \
    echo '    exit 1' >> /app/run_pipeline.sh && \
    echo 'fi' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'sleep 10' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 3단계: 트렌드 분석' >> /app/run_pipeline.sh && \
    echo 'log "🤖 3단계: Gemini 트렌드 분석 시작..."' >> /app/run_pipeline.sh && \
    echo 'python3 trend-analyzer/trend_analyzer.py \' >> /app/run_pipeline.sh && \
    echo '    --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'if [ $? -eq 0 ]; then' >> /app/run_pipeline.sh && \
    echo '    log "✅ 3단계 완료: 트렌드 분석"' >> /app/run_pipeline.sh && \
    echo 'else' >> /app/run_pipeline.sh && \
    echo '    log "❌ 3단계 실패: 트렌드 분석"' >> /app/run_pipeline.sh && \
    echo '    exit 1' >> /app/run_pipeline.sh && \
    echo 'fi' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'sleep 10' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 4단계: 도서 검색 및 추천' >> /app/run_pipeline.sh && \
    echo 'log "📚 4단계: 도서 검색 및 추천 시작..."' >> /app/run_pipeline.sh && \
    echo 'python3 library-searcher/search_book.py \' >> /app/run_pipeline.sh && \
    echo '    --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json \' >> /app/run_pipeline.sh && \
    echo '    --books_per_keyword 10 \' >> /app/run_pipeline.sh && \
    echo '    --final_books_per_trend 5' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo 'if [ $? -eq 0 ]; then' >> /app/run_pipeline.sh && \
    echo '    log "✅ 4단계 완료: 도서 검색 및 추천"' >> /app/run_pipeline.sh && \
    echo 'else' >> /app/run_pipeline.sh && \
    echo '    log "❌ 4단계 실패: 도서 검색 및 추천"' >> /app/run_pipeline.sh && \
    echo '    exit 1' >> /app/run_pipeline.sh && \
    echo 'fi' >> /app/run_pipeline.sh && \
    echo '' >> /app/run_pipeline.sh && \
    echo '# 완료' >> /app/run_pipeline.sh && \
    echo 'log "🎉 통합 파이프라인 완료!"' >> /app/run_pipeline.sh && \
    echo 'log "📊 결과 요약:"' >> /app/run_pipeline.sh && \
    echo 'log "   📅 처리 날짜: $DATE"' >> /app/run_pipeline.sh && \
    echo 'log "   🕐 완료 시간: $(date "+%Y-%m-%d %H:%M:%S")"' >> /app/run_pipeline.sh && \
    echo 'log "✨ 모든 작업이 성공적으로 완료되었습니다!"' >> /app/run_pipeline.sh && \
    chmod +x /app/run_pipeline.sh

# cron 작업 등록 - 
RUN echo "# 매일 한국시간 오전 3시(2:00)에 파이프라인 실행" > /etc/cron.d/daily-pipeline && \
    echo "# TZ=Asia/Seoul 설정으로 cron도 한국 시간 기준" >> /etc/cron.d/daily-pipeline && \
    echo "0 3 * * * root cd /app && /app/run_pipeline_with_env.sh >> /var/log/pipeline.log 2>&1" >> /etc/cron.d/daily-pipeline && \
    echo "" >> /etc/cron.d/daily-pipeline && \
    chmod 0644 /etc/cron.d/daily-pipeline

# 환경변수를 포함한 래퍼 스크립트 생성
RUN echo '#!/bin/bash' > /app/run_pipeline_with_env.sh && \
    echo '# 컨테이너 실행 시 환경변수를 파일에서 로드' >> /app/run_pipeline_with_env.sh && \
    echo 'if [ -f /app/.env ]; then' >> /app/run_pipeline_with_env.sh && \
    echo '    source /app/.env' >> /app/run_pipeline_with_env.sh && \
    echo 'fi' >> /app/run_pipeline_with_env.sh && \
    echo '' >> /app/run_pipeline_with_env.sh && \
    echo '# 파이프라인 실행' >> /app/run_pipeline_with_env.sh && \
    echo 'exec /app/run_pipeline.sh' >> /app/run_pipeline_with_env.sh && \
    chmod +x /app/run_pipeline_with_env.sh

# 시작 스크립트 (cron 서비스 시작 + 대기)
RUN echo '#!/bin/bash' > /app/start_service.sh && \
    echo 'set -e' >> /app/start_service.sh && \
    echo '' >> /app/start_service.sh && \
    echo 'log() {' >> /app/start_service.sh && \
    echo '    echo "[$(date "+%Y-%m-%d %H:%M:%S")] $1"' >> /app/start_service.sh && \
    echo '}' >> /app/start_service.sh && \
    echo '' >> /app/start_service.sh && \
    echo '# 환경변수 검증' >> /app/start_service.sh && \
    echo '/app/check_env.sh' >> /app/start_service.sh && \
    echo '' >> /app/start_service.sh && \
    echo '# 실행 모드 확인' >> /app/start_service.sh && \
    echo 'MODE=${PIPELINE_MODE:-cron}' >> /app/start_service.sh && \
    echo '' >> /app/start_service.sh && \
    echo 'if [ "$MODE" = "immediate" ]; then' >> /app/start_service.sh && \
    echo '    log "🚀 즉시 실행 모드"' >> /app/start_service.sh && \
    echo '    exec /app/run_pipeline.sh' >> /app/start_service.sh && \
    echo 'else' >> /app/start_service.sh && \
    echo '    log "⏰ 스케줄 모드 - 매일 3:00에 실행"' >> /app/start_service.sh && \
    echo '    log "🕐 현재 시간: $(date)"' >> /app/start_service.sh && \
    echo '    log "🌏 타임존: $TZ"' >> /app/start_service.sh && \
    echo '    ' >> /app/start_service.sh && \
    echo '    # 환경변수를 파일로 저장 (cron에서 사용)' >> /app/start_service.sh && \
    echo '    log "💾 환경변수 저장 중..."' >> /app/start_service.sh && \
    echo '    cat > /app/.env << EOF' >> /app/start_service.sh && \
    echo 'export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' >> /app/start_service.sh && \
    echo 'export GEMINI_API_KEY="$GEMINI_API_KEY"' >> /app/start_service.sh && \
    echo 'export NAVER_CLIENT_ID="$NAVER_CLIENT_ID"' >> /app/start_service.sh && \
    echo 'export NAVER_CLIENT_SECRET="$NAVER_CLIENT_SECRET"' >> /app/start_service.sh && \
    echo 'export PYTHONPATH=/app' >> /app/start_service.sh && \
    echo 'export PYTHONUNBUFFERED=1' >> /app/start_service.sh && \
    echo 'export TZ=Asia/Seoul' >> /app/start_service.sh && \
    echo 'EOF' >> /app/start_service.sh && \
    echo '    ' >> /app/start_service.sh && \
    echo '    log "📋 크론 작업:"' >> /app/start_service.sh && \
    echo '    crontab /etc/cron.d/daily-pipeline' >> /app/start_service.sh && \
    echo '    crontab -l' >> /app/start_service.sh && \
    echo '    ' >> /app/start_service.sh && \
    echo '    # cron 서비스 시작' >> /app/start_service.sh && \
    echo '    service cron start' >> /app/start_service.sh && \
    echo '    log "✅ cron 서비스 시작됨"' >> /app/start_service.sh && \
    echo '    ' >> /app/start_service.sh && \
    echo '    # 로그 파일 생성' >> /app/start_service.sh && \
    echo '    touch /var/log/pipeline.log' >> /app/start_service.sh && \
    echo '    log "📁 로그 파일 생성: /var/log/pipeline.log"' >> /app/start_service.sh && \
    echo '    ' >> /app/start_service.sh && \
    echo '    # 무한 대기 (컨테이너 유지)' >> /app/start_service.sh && \
    echo '    log "💤 스케줄 대기 중..."' >> /app/start_service.sh && \
    echo '    tail -f /dev/null' >> /app/start_service.sh && \
    echo 'fi' >> /app/start_service.sh && \
    chmod +x /app/start_service.sh

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/check_env.sh && test -f /app/run_pipeline.sh || exit 1

# 기본 실행 명령
CMD ["/app/start_service.sh"]