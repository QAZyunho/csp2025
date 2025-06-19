# CS Project 2025 - Team Q

🔥 **트렌드 기반 도서 추천 서비스**

실시간 검색 트렌드를 AI로 분석하여 관련 도서를 추천하는 지능형 추천 시스템입니다.

## 🎯 프로젝트 개요

### 왜 만들었나요? (Why)

도서관을 단순한 독서 공간이 아닌, **최신 트렌드와 연결된 깊이 있는 지식을 탐색할 수 있는 지능형 공간**으로 만들고자 합니다.

### 어떻게 동작하나요? (How)

```
🔍 트렌드 수집 → 🤖 AI 분석 → 📚 도서 매칭 → ✨ 개인화 추천 → 🌐 웹 서비스
```

1. **트렌드 수집**: Google Trends + 네이버 뉴스에서 실시간 키워드 수집
2. **AI 분석**: Gemini AI로 트렌드 요약 및 도서 검색 키워드 생성
3. **도서 매칭**: 국립중앙도서관 API를 통한 관련 도서 발굴
4. **개인화 추천**: 사용자 피드백 학습 기반 맞춤형 추천
5. **자동화**: Docker 기반 일일 자동 파이프라인 운영

### 누구를 위한 서비스인가요?

- 📖 트렌드와 관련된 자료를 찾는 도서관 이용자
- 💻 전자도서관 사용자
- 🔬 최신 주제에 관심있는 연구자
- 📊 트렌드 기반 학습을 원하는 일반인

## 🏗️ 시스템 아키텍처

```
📡 Trend Collector    🤖 Trend Analyzer    📚 Library Searcher    ✨ Recommendation System
      ↓                     ↓                      ↓                        ↓
Google Trends RSS      Gemini 1.5 Flash     국립중앙도서관 API        사용자 피드백 학습
네이버 뉴스 API       트렌드 요약 생성       도서 검색 & 필터링         React 웹 인터페이스
      ↓                     ↓                      ↓                        ↓
🔥 Firebase Firestore (csproject2025 Database)
```

## 📂 프로젝트 구조

```
cs-project-2025/
├── 📋 docs/                              # 프로젝트 문서
├── 📦 trend-collector/                   # 트렌드 데이터 수집
│   ├── keyword_collector.py              # Google Trends 키워드 수집
│   └── naver_news_collector.py           # 네이버 뉴스 수집
├── 🤖 trend-analyzer/                    # AI 트렌드 분석
│   └── trend_analyzer.py                 # Gemini AI 분석 엔진
├── 📚 library-searcher/                  # 도서관 자료 검색
│   └── search_book.py                     # 국립중앙도서관 API 도서 검색
├── ✨ recommendation-system/              # 추천 시스템 & 웹 인터페이스
│   ├── api_server.py                      # Flask API 서버
│   ├── recommender.py                     # 추천 엔진
│   └── frontend/                          # React 웹 UI
│       ├── index.html
│       ├── script.js
│       └── style.css
├── ⏰ scheduler/                          # 자동화 스케줄러
│   ├── docker_pipeline_orchestrator.py   # Docker 파이프라인 오케스트레이터
│   └── docker_pipeline_runner.sh         # 파이프라인 실행 스크립트
├── 🐳 dockerfiles/                       # Docker 설정
├── 🐳 docker-compose.yml                 # 서비스 오케스트레이션
├── 📦 requirements.txt                    # 통합 의존성
├── 🔐 setup_env.sh                       # 환경변수 설정 스크립트
└── 📄 csproject2025-cfcb7-firebase-adminsdk-*.json  # Firebase 설정
```

## 🛡️ 보안 고려사항

- 🔐 API 키는 환경변수로 관리
- 🔥 Firebase 보안 규칙 적용
- 🌐 CORS 설정을 통한 도메인 제한
- 📝 사용자 입력 데이터 검증
- 🔒 HTTPS 사용 권장 (프로덕션)

## 📚 참고 자료

- [Google Trends API 문서](https://trends.google.com/trends/)
- [네이버 개발자 센터](https://developers.naver.com/)
- [국립중앙도서관 Open API](https://www.nl.go.kr/seoji/contents/S80100000000.do)
- [Gemini AI 가이드](https://ai.google.dev/)
- [Firebase Firestore 문서](https://firebase.google.com/docs/firestore)

## 👥 팀 정보

**Team Q - CS Project 2025**

- 🎯 **목표**: 트렌드와 지식을 연결하는 지능형 추천 시스템
- 🔄 **접근법**: AI 기반 실시간 분석 및 개인화
- 🌟 **특징**: 완전 자동화된 일일 업데이트 파이프라인

## 📄 라이선스

이 프로젝트는 교육 목적으로 개발되었습니다.

## 📞 지원

문제가 발생하거나 질문이 있으시면 GitHub Issues를 통해 문의해주세요.
