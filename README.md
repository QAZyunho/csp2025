<<<<<<< HEAD

# csp2025

=======

# C&S Project 2025 - Team Q

### 트렌드 기반 도서 추천 서비스

일간 검색량을 기반으로 식별한 사회적으로 인기있는 주제(트렌드 토픽)를 빠르게 요약하여 해당 주제가 왜 주목받고 있는지를 분석하고, 해당 주제와 관련된 온/오프라인 자료를 연결하는 서비스입니다.

## 프로젝트 개요

### 목적 (Why?)

도서관을 단순히 서적을 읽고 공부하는 공간이 아니라 인기 있는 주제에 대해 깊이 있는 지식을 탐색할 수 있는 공간으로 만드는 것을 목표로 합니다.

### 방법 (How?)

- Google Trends, 뉴스 기사, 커뮤니티 게시글에서 트렌드 주제 데이터 수집
- 언어 모델(Gemini)을 활용하여 각 주제별로 간결한 요약 생성
- 국립중앙도서관 Open API를 통해 관련 도서 및 문헌 자료 매칭
- 사용자 맞춤형 추천 시스템 제공

### 대상 사용자

- 트렌드 및 관련 자료 탐색을 원하는 도서관 방문자
- 전자도서관 이용자
- 최신 주제에 관심있는 연구자 및 학습자

## Directory Structure

The directory structure below must be followed, and must be periodically updated in order to be recognized for contributions in external activities such as presentations.

```
/
├── docs/                    # 프로젝트 문서 및 발표자료
├── trend-collector/        # 트렌드 데이터 수집
│   ├── keyword_collector.py
│   ├── naver_news_collector.py
│   └── requirements.txt
├── trend-analyzer/         # 트렌드 분석 및 요약
│   ├── trend_analyzer.py
│   └── requirements.txt
├── library-searcher/       # 도서관 자료 검색
│   ├── search_book.py
│   └── requirements.txt
├── recommendation-system/  # 개인화 추천 시스템
│   ├── api_server.py
│   ├── recommender.py
│   ├── test_category.py
│   └── requirements.txt
├── Dockerfile
├── README.md
└── Usage.md
```

## Guidelines

docker compose -f docker-compose.yml up recommendation-api
python recommendation-system/user_feedback.py

Team members are responsible for taking on tasks appropriate to their roles and submitting them periodically to the appropriate repositories. At this time, please be aware of the following precautions.

- Prohibition of account sharing: The act of pushing someone else's work to your ID is prohibited. **You can only upload your own results with your GitHub account.**
- Periodic upload recommended: Even if the results such as code are incomplete, **please continue to push the progress so that other team members and evaluators can observe and give feedback.** The act of pushing completed results at once is recognized only as a contribution for that date, and efforts in the process are difficult to be recognized.
- Documentation recommended: Documentation in the `docs` directory provided by default will be credited to the author. In addition, even if presentation materials such as PPT are uploaded in binary format, if the contents are listed in the `docs` directory, contributions can be recognized by quoting them.
- Create a `Dockerfile (Containerfile)`: Project artifacts should be able to be packaged into one (or more) container image with the following command: `docker build --tag cs-project-2025-team-xxx .`
  - Build arguments and environment variable dependencies should not be present.
  - **Execution: Execution and usage for containerized images must be documented in `Usage.md` file.**

## Q&A

Please use the `Issues` function to raise inquiries.

> > > > > > > 94b5acf15c0e946733edf55d3ced73e60ccc6420
