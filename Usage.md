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
  --env-file .env \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

#### 스케줄 실행 (매일 자동 데이터 수집)

```bash
docker run -d --name cs-pipeline-scheduler \
  --env-file .env \
  -e PIPELINE_MODE=cron \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

### 웹 시스템 실행 (추가 빌드 필요)

#### Docker Compose 방식 (권장)

```bash
# 전체 시스템 실행 (웹 UI + API 서버)
docker compose -f recommendation-system/docker-compose.yml up

# 백그라운드 실행
docker compose -f recommendation-system/docker-compose.yml up -d

# 특정 서비스만 실행
docker compose -f recommendation-system/docker-compose.yml up backend
docker compose -f recommendation-system/docker-compose.yml up frontend
```

#### 개별 컨테이너 방식

```bash
# 1. 추천 API 서버 실행
docker run -d --name cs-api \
  -p 5001:5001 \
  -v ./recommendation-system/csproject2025-cfcb7-firebase-adminsdk-fbsvc-f15f257ae3.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-f15f257ae3.json:ro \
  cs-project-api

# 2. 웹 UI 실행 (API 서버 실행 후)
docker run -d --name cs-web \
  -p 8080:80 \
  --link cs-api:backend \
  cs-project-web
```

## Control

### 파이프라인 제어

#### 데이터 수집 파이프라인 상태 확인

```bash
# 스케줄러 로그 확인
docker logs -f cs-pipeline-scheduler

# 파이프라인 로그 파일 확인 (컨테이너 내부)
docker exec cs-pipeline-scheduler tail -f /var/log/pipeline.log

# 크론 작업 상태 확인
docker exec cs-pipeline-scheduler crontab -l
docker exec cs-pipeline-scheduler service cron status
```

#### 수동 파이프라인 실행

```bash
# 즉시 실행 (기존 스케줄러와 별도)
docker run --rm \
  --name cs-pipeline-manual \
  --env-file .env \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
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

## 환경변수 설정

### .env 파일 구성

프로젝트 루트에 `.env` 파일을 생성하고 다음과 같이 설정:

```bash
# CS Project 환경변수 설정 파일

# 🤖 Gemini API 설정
GEMINI_API_KEY=${YOUR_GEMINI_API_KEY}

# 🌐 Google Cloud API 설정
GOOGLE_CLOUD_API_KEY=${YOUR_GOOGLE_CLOUD_API_KEY}

# 📰 네이버 검색 API 설정
NAVER_CLIENT_ID=${YOUR_NAVER_CLIENT_ID}
NAVER_CLIENT_SECRE=${YOUR_NAVER_CLIENT_SECRE}

# 📚 국립중앙도서관 API 설정
NATIONAL_LIBRARY_API_KEY=${YOUR_NATIONAL_LIBRARY_API_KEY}

# 🔥 Firebase 설정
FIREBASE_CONFIG_PATH=${YOUR_FIREBASE_CONFIG_PATH}

# ⚙️ 파이프라인 설정
PIPELINE_MODE=immediate

# 🐳 Docker 관련 설정
PYTHONPATH=/app
PYTHONUNBUFFERED=1
TZ=Asia/Seoul
```

### 통합 운영 시나리오

#### 1단계: 환경 준비

```bash
# .env 파일이 있는지 확인
ls -la .env

# Firebase 설정 파일 확인
ls -la csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json

# 모든 이미지 빌드
docker build --tag cs-project .
docker build --tag cs-project-web -f recommendation-system/frontend.Dockerfile recommendation-system/
docker build --tag cs-project-api -f recommendation-system/backend.Dockerfile recommendation-system/
```

#### 2단계: 데이터 수집 파이프라인 시작

```bash
# 매일 자동 데이터 수집을 위한 스케줄러 시작
docker run -d --name cs-pipeline-scheduler \
  --env-file .env \
  -e PIPELINE_MODE=cron \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

#### 3단계: 웹 시스템 시작

```bash
# Docker Compose로 웹 시스템 시작
cd recommendation-system
docker compose up -d
cd ..
```

#### 4단계: 초기 데이터 생성 (선택사항)

```bash
# 첫 번째 데이터를 바로 생성하고 싶다면
docker run --rm \
  --env-file .env \
  -v ./csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json:ro \
  cs-project
```

## 파이프라인 상세 과정

CS Project 파이프라인은 4단계로 구성됩니다:

### 1단계: 트렌드 키워드 수집

- Google Trends RSS 피드에서 실시간 트렌드 수집
- 사용자 선호 키워드와 결합
- Gemini AI로 키워드 정제 및 그룹핑
- Firebase `keywords` 컬렉션에 저장

### 2단계: 네이버 뉴스 수집

- 수집된 키워드로 네이버 뉴스 API 검색
- 키워드당 최대 5개 관련 기사 수집
- Firebase `news` 컬렉션에 저장

### 3단계: Gemini 트렌드 분석

- 수집된 뉴스 기사를 Gemini AI로 분석
- 각 키워드별 요약 및 도서 검색 키워드 생성
- Firebase `trend` 컬렉션에 저장

### 4단계: 도서 검색 및 추천

- 국립중앙도서관 API로 관련 도서 검색
- Gemini AI로 관련성 높은 도서 선별
- Firebase `source` 컬렉션에 최종 추천 도서 저장

## 모니터링 및 관리

### 로그 확인

```bash
# 파이프라인 로그
docker logs -f cs-pipeline-scheduler

# 웹 시스템 로그
cd recommendation-system
docker compose logs -f
docker compose logs backend
docker compose logs frontend
cd ..

# 파이프라인 내부 로그 파일
docker exec cs-pipeline-scheduler tail -f /var/log/pipeline.log
```

### 헬스체크

```bash
# API 서버 상태 확인
curl http://localhost:5001/

# 웹 서버 상태 확인
curl http://localhost:8080/

# Firebase 데이터 확인 (파이프라인 로그에서)
docker logs cs-pipeline-scheduler | grep "Firebase"
```

### 컨테이너 관리

```bash
# 실행 중인 컨테이너 확인
docker ps

# 모든 CS Project 컨테이너 중지
docker stop cs-pipeline-scheduler cs-api cs-web

# 컨테이너 제거
docker rm cs-pipeline-scheduler cs-api cs-web

# Docker Compose 서비스 중지
cd recommendation-system
docker compose down
cd ..
```

### 데이터 백업 및 복구

```bash
# Firebase 데이터는 자동으로 클라우드에 저장됨
# 로컬 백업이 필요한 경우 Firebase Admin SDK 사용

# 설정 파일 백업
cp .env .env.backup
cp csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json firebase-config.backup.json
```

## 트러블슈팅

### 자주 발생하는 문제

1. **API 키 오류**

   ```bash
   # .env 파일 확인
   cat .env | grep API_KEY
   ```

2. **Firebase 연결 실패**

   ```bash
   # Firebase 설정 파일 확인
   ls -la csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json
   ```

3. **포트 충돌**

   ```bash
   # 사용 중인 포트 확인
   netstat -tulpn | grep :5001
   netstat -tulpn | grep :8080
   ```

4. **메모리 부족**
   ```bash
   # Docker 메모리 사용량 확인
   docker stats
   ```

### 완전 초기화

```bash
# 모든 CS Project 컨테이너 정지 및 제거
docker stop $(docker ps -q --filter "name=cs-")
docker rm $(docker ps -aq --filter "name=cs-")

# 이미지 제거 (선택사항)
docker rmi cs-project cs-project-web cs-project-api

# 재빌드
docker build --tag cs-project .
docker build --tag cs-project-web -f recommendation-system/frontend.Dockerfile recommendation-system/
docker build --tag cs-project-api -f recommendation-system/backend.Dockerfile recommendation-system/
```
