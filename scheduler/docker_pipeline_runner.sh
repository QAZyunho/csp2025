#!/bin/bash

# Docker 컨테이너 기반 파이프라인 실행 스크립트
# 파일 위치: scheduler/docker_pipeline_runner.sh
# 새벽 4시에 실행되어 각 단계를 별도의 Docker 컨테이너로 순차 실행

set -e  # 오류 발생 시 스크립트 중단
set -o pipefail  # 파이프라인에서 오류 발생 시 감지

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 오류 처리 함수
error_exit() {
    log "❌ ERROR: $1"
    cleanup_containers
    exit 1
}

# 환경변수 확인
check_env() {
    log "🔍 환경변수 확인 중..."
    
    if [ -z "$FIREBASE_CONFIG_PATH" ]; then
        FIREBASE_CONFIG_PATH="/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json"
        log "⚠️ FIREBASE_CONFIG_PATH 기본값 설정: $FIREBASE_CONFIG_PATH"
    fi
    
    if [ -z "$GEMINI_API_KEY" ]; then
        error_exit "GEMINI_API_KEY 환경변수가 설정되지 않았습니다"
    fi
    
    if [ -z "$NAVER_CLIENT_ID" ] || [ -z "$NAVER_CLIENT_SECRET" ]; then
        error_exit "네이버 API 키가 설정되지 않았습니다"
    fi
    
    # Firebase 설정 파일 확인
    if [ ! -f "$FIREBASE_CONFIG_PATH" ]; then
        error_exit "Firebase 설정 파일이 없습니다: $FIREBASE_CONFIG_PATH"
    fi
    
    log "✅ 환경변수 확인 완료"
}

# Docker 네트워크 확인/생성
setup_network() {
    local NETWORK_NAME="cs-project-network"
    
    log "🌐 Docker 네트워크 설정 중..."
    
    if ! docker network ls | grep -q "$NETWORK_NAME"; then
        if docker network create "$NETWORK_NAME"; then
            log "✅ Docker 네트워크 생성: $NETWORK_NAME"
        else
            log "⚠️ 네트워크 생성 실패, 기존 네트워크 사용: $NETWORK_NAME"
        fi
    else
        log "✅ Docker 네트워크 확인: $NETWORK_NAME"
    fi
}

# Docker 이미지 빌드
build_images() {
    local BASE_TAG="cs-project-2025"
    local BUILD_CONTEXT="/app"
    
    log "🔨 Docker 이미지 빌드 중..."
    
    # 이미지 목록 정의
    declare -A IMAGES=(
        ["$BASE_TAG-keyword-collector"]="dockerfiles/Dockerfile.keyword-collector"
        ["$BASE_TAG-news-collector"]="dockerfiles/Dockerfile.news-collector" 
        ["$BASE_TAG-trend-analyzer"]="dockerfiles/Dockerfile.trend-analyzer"
        ["$BASE_TAG-library-searcher"]="dockerfiles/Dockerfile.library-searcher"
    )
    
    for IMAGE_NAME in "${!IMAGES[@]}"; do
        DOCKERFILE="${IMAGES[$IMAGE_NAME]}"
        
        # 이미지 존재 확인
        if [[ -z $(docker images -q "$IMAGE_NAME" 2>/dev/null) ]]; then
            log "🔨 이미지 빌드: $IMAGE_NAME"
            
            if docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$BUILD_CONTEXT"; then
                log "✅ 이미지 빌드 완료: $IMAGE_NAME"
            else
                error_exit "이미지 빌드 실패: $IMAGE_NAME"
            fi
        else
            log "✅ 이미지 존재 확인: $IMAGE_NAME"
        fi
    done
}

# Docker 컨테이너로 단계 실행 (개선된 버전)
run_docker_step() {
    local STEP_NAME="$1"
    local IMAGE_NAME="$2"
    local CONTAINER_NAME="$3"
    shift 3
    local COMMAND=("$@")
    
    log "🐳 $STEP_NAME 시작..."
    log "   📦 이미지: $IMAGE_NAME"
    log "   🏷️ 컨테이너: $CONTAINER_NAME"
    log "   🔧 명령어: ${COMMAND[*]}"
    
    # 기존 컨테이너 정리 (같은 이름이 있을 경우)
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    
    # Docker run 명령 구성
    local DOCKER_CMD=(
        docker run --rm
        --network cs-project-network
        --name "$CONTAINER_NAME"
        -e PYTHONUNBUFFERED=1
        -e PYTHONPATH=/app
        -v "$FIREBASE_CONFIG_PATH:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro"
    )
    
    # 단계별 추가 환경변수
    case "$STEP_NAME" in
        *"키워드"*)
            DOCKER_CMD+=(-e "GEMINI_API_KEY=$GEMINI_API_KEY")
            ;;
        *"뉴스"*)
            DOCKER_CMD+=(-e "NAVER_CLIENT_ID=$NAVER_CLIENT_ID")
            DOCKER_CMD+=(-e "NAVER_CLIENT_SECRET=$NAVER_CLIENT_SECRET")
            ;;
        *"분석"*)
            DOCKER_CMD+=(-e "GEMINI_API_KEY=$GEMINI_API_KEY")
            ;;
        *"도서"*)
            DOCKER_CMD+=(-e "GEMINI_API_KEY=$GEMINI_API_KEY")
            ;;
    esac
    
    # 이미지와 명령 추가
    DOCKER_CMD+=("$IMAGE_NAME")
    DOCKER_CMD+=("${COMMAND[@]}")
    
    # 컨테이너 실행
    local START_TIME=$(date +%s)
    
    log "🚀 실행 명령: ${DOCKER_CMD[*]}"
    
    if "${DOCKER_CMD[@]}"; then
        local END_TIME=$(date +%s)
        local DURATION=$((END_TIME - START_TIME))
        log "✅ $STEP_NAME 완료 (소요시간: ${DURATION}초)"
        return 0
    else
        local RETURN_CODE=$?
        log "❌ $STEP_NAME 실패 (종료코드: $RETURN_CODE)"
        
        # 컨테이너 로그 확인 시도
        if docker ps -a | grep -q "$CONTAINER_NAME"; then
            log "📋 컨테이너 로그:"
            docker logs "$CONTAINER_NAME" 2>&1 | tail -20 | while read line; do
                log "   $line"
            done
        fi
        
        return $RETURN_CODE
    fi
}

# API 서버 상태 확인
check_api_health() {
    log "🏥 추천 API 서버 상태 확인..."
    
    local MAX_RETRIES=3
    local RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if timeout 10 docker run --rm --network cs-project-network curlimages/curl:latest \
           curl -f -s http://recommendation-api:5001/ > /dev/null 2>&1; then
            log "✅ 추천 API 서버 정상 동작 중"
            return 0
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            log "⚠️ API 서버 응답 없음 (시도 $RETRY_COUNT/$MAX_RETRIES)"
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                sleep 5
            fi
        fi
    done
    
    log "⚠️ 추천 API 서버 응답 없음 - 파이프라인은 계속 진행"
}

# 파이프라인 실행
run_pipeline() {
    local DATE=$(date '+%y%m%d')
    local BASE_TAG="cs-project-2025"
    
    log "🚀 Docker 컨테이너 기반 파이프라인 시작 (날짜: $DATE)"
    log "=================================================================="
    
    # 1단계: 키워드 수집
    log ""
    log "📡 1단계: 트렌드 키워드 수집 시작..."
    if ! run_docker_step \
        "1단계: 트렌드 키워드 수집" \
        "$BASE_TAG-keyword-collector" \
        "pipeline-keyword-collector-$DATE" \
        python trend-collector/keyword_collector.py \
        --gemini_api_key "$GEMINI_API_KEY" \
        --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json; then
        error_exit "키워드 수집 실패"
    fi
    
    sleep 15  # 단계간 대기
    
    # 2단계: 뉴스 수집
    log ""
    log "📰 2단계: 네이버 뉴스 수집 시작..."
    if ! run_docker_step \
        "2단계: 네이버 뉴스 수집" \
        "$BASE_TAG-news-collector" \
        "pipeline-news-collector-$DATE" \
        python trend-collector/naver_news_collector.py \
        --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json \
        --max_articles 5; then
        error_exit "뉴스 수집 실패"
    fi
    
    sleep 15
    
    # 3단계: 트렌드 분석
    log ""
    log "🤖 3단계: Gemini 트렌드 분석 시작..."
    if ! run_docker_step \
        "3단계: Gemini 트렌드 분석" \
        "$BASE_TAG-trend-analyzer" \
        "pipeline-trend-analyzer-$DATE" \
        python trend-analyzer/trend_analyzer.py \
        --gemini_api_key "$GEMINI_API_KEY" \
        --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json; then
        error_exit "트렌드 분석 실패"
    fi
    
    sleep 15
    
    # 4단계: 도서 검색 및 추천
    log ""
    log "📚 4단계: 도서 검색 및 추천 시작..."
    if ! run_docker_step \
        "4단계: 도서 검색 및 추천" \
        "$BASE_TAG-library-searcher" \
        "pipeline-library-searcher-$DATE" \
        python library-searcher/search_book.py \
        --gemini_api_key "$GEMINI_API_KEY" \
        --firebase_config /app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json \
        --books_per_keyword 10 \
        --final_books_per_trend 5; then
        error_exit "도서 추천 실패"
    fi
    
    # 파이프라인 완료
    log ""
    log "🎉 Docker 파이프라인 완료!"
    log "📊 결과 요약:"
    log "   📅 처리 날짜: $DATE"
    log "   🕐 완료 시간: $(date '+%Y-%m-%d %H:%M:%S')"
    log "   🐳 실행 방식: Docker 컨테이너 기반"
    log "   📁 Firebase 저장 경로:"
    log "     - keywords/$DATE"
    log "     - news/$DATE"
    log "     - trend/$DATE"
    log "     - source/$DATE"
    
    log "🔔 파이프라인 성공 완료 - 추천 API 서버에서 새로운 데이터 사용 가능"
}

# 컨테이너 정리
cleanup_containers() {
    log "🧹 파이프라인 컨테이너 정리 중..."
    
    local DATE=$(date '+%y%m%d')
    
    # 현재 날짜의 파이프라인 컨테이너 정리
    local CONTAINERS=$(docker ps -a --filter "name=pipeline-*-$DATE" -q)
    if [ -n "$CONTAINERS" ]; then
        docker rm -f $CONTAINERS 2>/dev/null || true
        log "   🗑️ 파이프라인 컨테이너 정리 완료"
    fi
    
    # 오래된 파이프라인 컨테이너 정리 (7일 이상)
    docker container prune -f --filter "until=168h" 2>/dev/null || true
    
    log "✅ 컨테이너 정리 완료"
}

# 디버그 정보 출력
print_debug_info() {
    log "🔍 디버그 정보:"
    log "   🐳 Docker 버전: $(docker --version 2>/dev/null || echo 'Docker 없음')"
    log "   📁 현재 디렉토리: $(pwd)"
    log "   📄 Firebase 파일: $(ls -la $FIREBASE_CONFIG_PATH 2>/dev/null || echo '파일 없음')"
    log "   🌐 네트워크: $(docker network ls | grep cs-project || echo '네트워크 없음')"
    log "   📦 이미지: $(docker images | grep cs-project | wc -l)개"
}

# 메인 실행
main() {
    log "🌅 Docker 파이프라인 시작"
    
    # 디버그 정보 출력
    print_debug_info
    
    # 환경변수 확인
    check_env
    
    # Docker 네트워크 설정
    setup_network
    
    # Docker 이미지 빌드
    build_images

    
    # 파이프라인 실행
    run_pipeline
    
    # 컨테이너 정리
    cleanup_containers
    
    log "✨ 모든 작업이 성공적으로 완료되었습니다!"
}

# 스크립트 실행
main "$@"