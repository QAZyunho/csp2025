# Usage

## Build

> The commands below **cannot be modified**. Be sure to implement the Dockerfile so that it can run.

```bash
docker build --tag cs-project .
```

> If you need more than one `Dockerfile`, you can add the command below.

```bash
# 웹 UI + 추천 시스템 빌드
docker build --tag cs-project-web -f recommendation-system/frontend.Dockerfile recommendation-system/

# 추천 API 서버 빌드
docker build --tag cs-project-api -f recommendation-system/backend.Dockerfile recommendation-system/
```

## Run

### 파이프라인 실행 (메인 - cs-project)

고정 명령어로 빌드된 `cs-project` 이미지는 **데이터 수집 파이프라인 전용**입니다.

#### 즉시 실행 (일회성 데이터 수집)

```bash
docker run --rm \
  -e PIPELINE_MODE=immediate \
  -e GEMINI_API_KEY=your_gemini_api_key \
  -e NAVER_CLIENT_ID=your_naver_client_id \
  -e NAVER_CLIENT_SECRET=your_naver_client_secret \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

#### 스케줄 실행 (매일 자동 데이터 수집)

```bash
docker run -d --name cs-pipeline-scheduler \
  -e PIPELINE_MODE=cron \
  -e GEMINI_API_KEY=your_gemini_api_key \
  -e NAVER_CLIENT_ID=your_naver_client_id \
  -e NAVER_CLIENT_SECRET=your_naver_client_secret \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

### 웹 시스템 실행 (추가 빌드 필요)

#### Docker Compose 방식 (권장)

```bash
# 전체 시스템 실행 (웹 UI + API 서버)
docker compose up

# 백그라운드 실행
docker compose up -d

# 특정 서비스만 실행
docker compose up recommendation-api
docker compose up web-ui
```

#### 개별 컨테이너 방식

```bash
# 1. 추천 API 서버 실행
docker run -d --name cs-api \
  -p 5001:5001 \
  -v ./recommendation-system/csproject2025-cfcb7-firebase-adminsdk-fbsvc-f15f257ae3.json:/app/firebase-config.json:ro \
  cs-project-api

# 2. 웹 UI 실행 (API 서버 실행 후)
docker run -d --name cs-web \
  -p 8080:80 \
  --link cs-api:recommendation-api \
  cs-project-web
```

## Control

### 파이프라인 제어

#### 데이터 수집 파이프라인 상태 확인

```bash
# 스케줄러 로그 확인
docker logs -f cs-pipeline-scheduler

# 파이프라인 로그 파일 확인
docker exec cs-pipeline-scheduler tail -f /var/log/pipeline.log

# 크론 작업 상태 확인
docker exec cs-pipeline-scheduler crontab -l
docker exec cs-pipeline-scheduler service cron status
```

#### 수동 파이프라인 실행

```bash
# 즉시 실행 (기존 스케줄러와 별도)
docker run --name cs-pipeline-manual \
  -e PIPELINE_MODE=immediate \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e NAVER_CLIENT_ID=$NAVER_CLIENT_ID \
  -e NAVER_CLIENT_SECRET=$NAVER_CLIENT_SECRET \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project

# 완료 후 컨테이너 정리
docker rm cs-pipeline-manual
```

### 웹 시스템 제어

#### 시스템 접속

- **웹 애플리케이션**: http://localhost:8080
- **추천 API**: http://localhost:5001
- **API 상태 확인**: http://localhost:5001/

#### 사용자 워크플로우

1. **사용자 설정**

   - 웹 인터페이스의 "사용자 설정" 탭 접속
   - 기존 사용자 선택 또는 신규 사용자 생성
   - 프로필 로드

2. **트렌드 탐색**

   - "최신 트렌드" 탭에서 날짜별 트렌드 확인
   - 관심 있는 트렌드 클릭하여 관련 도서 조회
   - 도서에 대한 피드백(별점) 제공

3. **맞춤 추천 받기**
   - "맞춤 추천" 탭에서 개인화된 도서 추천 확인
   - 선호 주제와 새로운 트렌드 조합 탐색
   - 페이지 단위로 도서 목록 탐색

### 통합 운영 시나리오

#### 1단계: 데이터 수집 파이프라인 시작

```bash
# 매일 자동 데이터 수집을 위한 스케줄러 시작
docker run -d --name cs-pipeline-scheduler \
  -e PIPELINE_MODE=cron \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e NAVER_CLIENT_ID=$NAVER_CLIENT_ID \
  -e NAVER_CLIENT_SECRET=$NAVER_CLIENT_SECRET \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

#### 2단계: 웹 시스템 시작

```bash
# Docker Compose로 웹 시스템 시작
docker compose up -d
```

#### 3단계: 초기 데이터 생성 (선택사항)

```bash
# 첫 번째 데이터를 바로 생성하고 싶다면
docker run --rm \
  -e PIPELINE_MODE=immediate \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e NAVER_CLIENT_ID=$NAVER_CLIENT_ID \
  -e NAVER_CLIENT_SECRET=$NAVER_CLIENT_SECRET \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

## 모니터링 및 관리

### 로그 확인

```bash
# 파이프라인 로그
docker logs -f cs-pipeline-scheduler

# 웹 시스템 로그
docker compose logs -f
docker compose logs recommendation-api
docker compose logs web-ui

# 파이프라인 내부 로그 파일
docker exec cs-pipeline-scheduler tail -f /var/log/pipeline.log
```

### 헬스체크

```bash

```
