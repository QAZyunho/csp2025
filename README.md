# C&S Project 2025 - Team Q

🔥 트렌드 기반 도서 추천 서비스
일간 검색량을 기반으로 식별한 사회적으로 인기있는 주제(트렌드 토픽)를 AI로 분석하여 해당 주제가 왜 주목받고 있는지를 파악하고, 해당 주제와 관련된 온/오프라인 자료를 연결하는 지능형 추천 서비스입니다.

## 🎯 프로젝트 개요

### 목적 (Why?)

도서관을 단순히 서적을 읽고 공부하는 공간이 아니라, 최신 트렌드와 연결된 깊이 있는 지식을 탐색할 수 있는 지능형 공간으로 만드는 것을 목표로 합니다.

### 방법 (How?)

🔍 트렌드 수집: Google Trends, 뉴스 기사에서 실시간 트렌드 데이터 수집
🤖 AI 분석: Gemini AI를 활용하여 각 주제별로 간결한 요약 및 도서 검색 키워드 생성
📚 도서 매칭: 국립중앙도서관 Open API를 통해 관련 도서 및 문헌 자료 매칭
✨ 개인화 추천: 사용자 피드백 기반 맞춤형 추천 시스템 제공
🔄 자동화: Docker 컨테이너 기반 일일 자동 파이프라인 운영

### 대상 사용자

📖 트렌드 및 관련 자료 탐색을 원하는 도서관 방문자
💻 전자도서관 이용자
🔬 최신 주제에 관심있는 연구자 및 학습자
📊 트렌드 기반 학습을 원하는 일반 사용자

### 🏗️ 시스템 아키텍처

📡 트렌드 수집 → 🤖 AI 분석 → 📚 도서 검색 → ✨ 개인화 추천 → 🌐 웹 서비스
↓ ↓ ↓ ↓ ↓
Google Trends Gemini AI 국립중앙도서관 사용자 피드백 React 웹앱
네이버 뉴스 트렌드 분석 Open API 학습 시스템 Flask API

## 📂 Directory Structure

```
/
├── docs/                        # 📋 프로젝트 문서 및 발표자료
├── trend-collector/             # 📡 트렌드 데이터 수집
│   ├── keyword_collector.py     # Google Trends 키워드 수집
│   ├── naver_news_collector.py  # 네이버 뉴스 수집
│   └── requirements.txt
├── trend-analyzer/              # 🤖 트렌드 분석 및 요약
│   ├── trend_analyzer.py        # Gemini AI 트렌드 분석
│   └── requirements.txt
├── library-searcher/            # 📚 도서관 자료 검색
│   ├── search_book.py           # 국립중앙도서관 API 도서 검색
│   └── requirements.txt
├── recommendation-system/       # ✨ 개인화 추천 시스템
│   ├── api_server.py            # Flask API 서버
│   ├── recommender.py           # 추천 엔진
│   ├── frontend/                # React 웹 인터페이스
│   │   ├── index.html
│   │   ├── script.js
│   │   └── style.css
│   └── requirements.txt
├── scheduler/                   # ⏰ 자동화 스케줄러
│   ├── docker_pipeline_orchestrator.py  # Docker 파이프라인 오케스트레이터
│   └── docker_pipeline_runner.sh        # 파이프라인 실행 스크립트
├── dockerfiles/                 # 🐳 Docker 설정
│   ├── Dockerfile.keyword-collector
│   ├── Dockerfile.news-collector
│   ├── Dockerfile.trend-analyzer
│   ├── Dockerfile.library-searcher
│   ├── Dockerfile.recommendation-api
│   ├── Dockerfile.scheduler
│   └── Dockerfile.pipeline-all-in-one
├── docker-compose.yml           # 🐳 Docker Compose 설정
├── requirements.txt             # 📦 통합 의존성
├── README.md
└── Usage.md
```

## 🚀 Quick Start

### 1. 환경 설정

```
bash
## 저장소 클론
git clone <repository-url>
cd csp2025

# 환경변수 설정 (.env 파일 생성)
cp .env.example .env
# .env 파일에서 API 키들을 설정하세요:
# - GEMINI_API_KEY=your_gemini_api_key
# - NAVER_CLIENT_ID=your_naver_client_id
# - NAVER_CLIENT_SECRET=your_naver_client_secret
```

### 2. Docker Compose로 실행 (권장)

```
bash
# 전체 시스템 실행
docker compose up

# 백그라운드 실행
docker compose up -d

# 특정 서비스만 실행
docker compose up recommendation-api
```

### 3. 개별 컴포넌트 실행

```
bash
# 1️⃣ 트렌드 키워드 수집
python trend-collector/keyword_collector.py \
    --gemini_api_key YOUR_GEMINI_API_KEY \
    --firebase_config firebase-config.json

# 2️⃣ 뉴스 수집
python trend-collector/naver_news_collector.py \
    --firebase_config firebase-config.json

# 3️⃣ 트렌드 분석
python trend-analyzer/trend_analyzer.py \
    --gemini_api_key YOUR_GEMINI_API_KEY \
    --firebase_config firebase-config.json

# 4️⃣ 도서 검색 및 추천
python library-searcher/search_book.py \
    --gemini_api_key YOUR_GEMINI_API_KEY \
    --firebase_config firebase-config.json

# 5️⃣ 추천 API 서버 실행
cd recommendation-system
python api_server.py
```

## 🌐 접속 정보

📱 웹 애플리케이션: http://localhost:3001

🔌 추천 API: http://localhost:5001

📊 API 상태 확인: http://localhost:5001/

## 🔧 주요 기능

### 📡 트렌드 수집

- Google Trends: RSS 피드 및 자동 다운로드를 통한 실시간 트렌드 수집
- 네이버 뉴스: API를 통한 트렌드별 최신 뉴스 기사 수집
- 사용자 선호도: 기존 사용자 선호 키워드와 트렌드 결합

### 🤖 AI 분석

- Gemini 1.5 Flash: 트렌드별 뉴스 분석 및 요약 생성
- 도서 키워드 생성: 각 트렌드에 최적화된 도서 검색 키워드 자동 생성
- 관련성 검증: AI 기반 도서-트렌드 관련성 검증 및 필터링

### 📚 도서 검색

- 국립중앙도서관 API: 공식 도서 데이터베이스 연동
- 스마트 필터링: 도서 유형별 우선순위 적용 (도서 > 기타 자료)
- 중복 제거: 제목-저자 기반 지능형 중복 제거

### ✨ 개인화 추천

- 사용자 프로필: 연령대, 독서 빈도, 선호 키워드 관리
- 피드백 학습: 5점 평가 시스템 기반 선호도 학습
- 맞춤형 플레이리스트: 선호 주제 + 새로운 트렌드 조합 추천
- 페이지네이션: 키워드별 도서 목록 페이지 단위 제공

### 🔄 자동화

- 일일 파이프라인: 매일 자동으로 최신 트렌드 수집 및 분석
- Docker 컨테이너: 각 단계별 독립적인 컨테이너 실행
- 오류 복구: 단계별 실패 시 재시도 및 로깅
- 리소스 관리: 컨테이너 정리 및 리소스 최적화

## 🛠️ 기술 스택

### Backend

- Python 3.11: 메인 개발 언어
- 🌶️ Flask: REST API 서버
- 🤖 Gemini AI: 트렌드 분석 및 도서 추천
- 🔥 Firebase Firestore: NoSQL 데이터베이스
- 🕷️ Selenium: 웹 자동화 (Google Trends)
- 📊 Pandas: 데이터 처리
  Frontend
  ⚛️ React (Vanilla JS): 사용자 인터페이스
  🎨 Bootstrap 5: UI 컴포넌트
  📱 반응형 디자인: 모바일/데스크톱 최적화
  Infrastructure
  🐳 Docker: 컨테이너화
  🐙 Docker Compose: 다중 컨테이너 관리
  ⏰ Cron: 스케줄링
  🌐 Nginx: 웹 서버 (프로덕션)
  External APIs
  📈 Google Trends: 트렌드 데이터
  📰 네이버 뉴스 API: 뉴스 기사
  📚 국립중앙도서관 API: 도서 정보
  🔥 Firebase Admin SDK: 데이터베이스 연동
  📊 데이터 플로우
  mermaid
  graph TD
  A[Google Trends] --> B[키워드 수집]
  C[사용자 선호도] --> B
  B --> D[Firebase: keywords]
  D --> E[네이버 뉴스 수집]
  E --> F[Firebase: news]
  F --> G[Gemini AI 분석]
  G --> H[Firebase: trend]
  H --> I[도서 검색]
  I --> J[Firebase: source]
  J --> K[추천 엔진]
  L[사용자 피드백] --> K
  K --> M[웹 인터페이스]
  🔐 환경변수 설정
  bash

# 필수 API 키

GEMINI_API_KEY=your_gemini_api_key_here
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# Firebase 설정

FIREBASE_CONFIG_PATH=/path/to/firebase-config.json

# 파이프라인 설정 (선택사항)

PIPELINE_MODE=cron # 또는 immediate
📋 API 엔드포인트
사용자 관리
GET /api/users - 전체 사용자 목록
GET /api/users/{user_id} - 특정 사용자 프로필
POST /api/users - 새 사용자 생성
트렌드 및 추천
GET /api/trends/latest - 최신 트렌드 목록
GET /api/trends/dates - 사용 가능한 트렌드 날짜
GET /api/trends/by_date/{date} - 특정 날짜 트렌드
GET /api/books/by_keyword/{user_id} - 키워드별 도서 추천
GET /api/recommendations/general/{user_id} - 일반 추천
피드백
POST /api/feedback - 사용자 피드백 제출
🔄 자동화 파이프라인
일일 실행 스케줄
bash

# 매일 한국시간 오후 3시(15:00)에 실행

40 12 \* \* \* root cd /app && /app/run_pipeline_with_env.sh
파이프라인 단계
🔍 키워드 수집 (30분): Google Trends + 사용자 선호도
📰 뉴스 수집 (15분): 네이버 뉴스 API
🤖 AI 분석 (20분): Gemini 트렌드 분석
📚 도서 검색 (40분): 국립중앙도서관 API + AI 필터링
실행 방법
bash

# 즉시 실행

docker run -e PIPELINE_MODE=immediate cs-project-pipeline

# 스케줄 모드

docker run -e PIPELINE_MODE=cron cs-project-pipeline
🧪 테스트
bash

# 의존성 설치

pip install -r requirements.txt

# 개별 모듈 테스트

python -m pytest tests/

# API 서버 테스트

curl http://localhost:5001/api/trends/latest
📈 모니터링
로그 확인
bash

# 파이프라인 로그

docker logs <container_name>

# API 서버 로그

docker logs recommendation-api

# 전체 시스템 로그

docker compose logs -f
헬스체크
bash

# API 서버 상태

curl http://localhost:5001/

# 데이터베이스 연결 확인

docker exec recommendation-api python -c "from recommender import BookRecommender; r = BookRecommender('firebase-config.json'); print('DB:', len(r.books_df))"
🔧 Build & Deploy
컨테이너 빌드
bash

# 개별 컴포넌트 빌드

docker build --tag cs-project .

# 전체 시스템 빌드

docker compose build

# 특정 서비스 빌드

docker compose build recommendation-api
프로덕션 배포
bash

# 프로덕션 모드 실행

docker compose -f docker-compose.prod.yml up -d

# 서비스 스케일링

docker compose up --scale recommendation-api=3
🛡️ 보안 고려사항
🔐 API 키는 환경변수로만 관리
🔥 Firebase 보안 규칙 적용
🌐 CORS 설정을 통한 도메인 제한
📝 사용자 입력 데이터 검증
🔒 HTTPS 사용 권장 (프로덕션)
🐛 문제 해결
일반적인 문제들
Firebase 연결 오류
bash

# 설정 파일 확인

ls -la firebase-config.json

# 권한 확인

export GOOGLE_APPLICATION_CREDENTIALS=firebase-config.json
API 키 오류
bash

# 환경변수 확인

echo $GEMINI_API_KEY
echo $NAVER_CLIENT_ID
Docker 관련 문제
bash

# 컨테이너 정리

docker system prune -f

# 이미지 재빌드

docker compose build --no-cache
📚 참고 자료
Google Trends API
네이버 개발자 센터
국립중앙도서관 Open API
Gemini AI
Firebase Firestore
👥 팀 정보
Team Q - C&S Project 2025

🎯 목표: 트렌드와 지식을 연결하는 지능형 추천 시스템
🔄 접근법: AI 기반 실시간 분석 및 개인화
🌟 특징: 완전 자동화된 일일 업데이트 파이프라인
📄 라이선스
이 프로젝트는 교육 목적으로 개발되었습니다.

📞 지원
문제가 발생하거나 질문이 있으시면 GitHub Issues를 통해 문의해주세요.

🔥 실시간 트렌드와 함께하는 스마트한 독서 여행을 시작하세요! 📚✨
