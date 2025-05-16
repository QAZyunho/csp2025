from fastapi import FastAPI, Query
from pytrends.request import TrendReq
import pandas as pd
import datetime
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Trend Collector API")

# PyTrends 설정 - 한국어, 한국 시간대(UTC+9)
pytrends = TrendReq(hl='ko-KR', tz=540)

@app.get("/")
def index():
    """서비스 상태 확인"""
    return {
        "status": "running",
        "service": "Trend Collector API",
        "endpoints": [
            {"path": "/api/v1/trending", "method": "GET", "description": "인기 검색어 조회"},
            {"path": "/api/v1/trends/{keyword}", "method": "GET", "description": "특정 키워드 트렌드 조회"}
        ]
    }

@app.get("/api/v1/trending")
def get_trending_topics():
    """인기 검색어 상위 10개 조회"""
    try:
        # 인기 검색어 가져오기 (국가별 - 한국)
        trending_searches = pytrends.trending_searches(pn='south_korea')
        trending_list = trending_searches[0].tolist()[:10]  # 상위 10개
        
        response = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "trending_topics": trending_list
        }
        
        return response
    
    except Exception as e:
        logger.error(f"인기 검색어 조회 오류: {str(e)}")
        return {"error": str(e)}

@app.get("/api/v1/top_charts/{year}")
def get_top_charts(year: int):
    """특정 연도의 인기 검색어 차트 조회"""
    try:
        # 현재 연도를 가져옴
        current_year = datetime.datetime.now().year
        
        # 입력된 연도가 현재 연도보다 크면 작년 데이터를 가져옴 (Google은 현재 연도 차트를 제공하지 않음)
        if year >= current_year:
            year = current_year - 1
            
        # Top Charts 가져오기
        top_charts = pytrends.top_charts(year, hl='ko', tz=540, geo='GLOBAL')
        
        # 데이터 처리
        if top_charts is not None and not top_charts.empty:
            # DataFrame을 dict로 변환
            chart_data = top_charts.to_dict('records')
            
            response = {
                "year": year,
                "country": "Korea",
                "top_charts": chart_data
            }
        else:
            response = {
                "year": year,
                "country": "Korea",
                "top_charts": [],
                "message": "No data available for this year or region"
            }
        
        return response
    
    except Exception as e:
        logger.error(f"Top Charts 조회 오류: {str(e)}")
        return {"error": str(e)}
   
@app.get("/api/v1/realtime_trending")
def get_realtime_trending():
    """실시간 인기 검색어 조회"""
    try:
        # 실시간 인기 검색어 가져오기 (국가별 - 한국)
        realtime_trends = pytrends.realtime_trending_searches(pn='US')
        
        # 결과 포맷팅
        trends_list = []
        if not realtime_trends.empty:
            for _, row in realtime_trends.iterrows():
                trend_data = {
                    "title": row.get('title', ''),
                    "entity_names": row.get('entityNames', []),
                    "articles": row.get('articles', [])
                }
                trends_list.append(trend_data)
        
        response = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "realtime_trends": trends_list[:10]  # 상위 10개
        }
        
        return response
    
    except Exception as e:
        logger.error(f"실시간 인기 검색어 조회 오류: {str(e)}")
        return {"error": str(e)}

@app.get("/api/v1/trends/{keyword}")
def get_trend_data(keyword: str, timeframe: str = "now 7-d"):
    """특정 키워드의 트렌드 데이터 조회"""
    try:
        # 트렌드 데이터 수집
        pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo='KR')
        
        # 시간별 관심도
        interest_over_time_df = pytrends.interest_over_time()
        
        # 데이터프레임을 딕셔너리로 변환
        if not interest_over_time_df.empty:
            interest_data = {}
            for date, row in interest_over_time_df.iterrows():
                date_str = date.strftime('%Y-%m-%d')
                interest_data[date_str] = int(row[keyword])
        else:
            interest_data = {}
        
        # 연관 쿼리
        related_queries = pytrends.related_queries()
        rising_queries = []
        top_queries = []
        
        if keyword in related_queries and related_queries[keyword]:
            if 'rising' in related_queries[keyword] and not related_queries[keyword]['rising'] is None:
                rising_queries = related_queries[keyword]['rising'].head(5).to_dict('records')
            if 'top' in related_queries[keyword] and not related_queries[keyword]['top'] is None:
                top_queries = related_queries[keyword]['top'].head(5).to_dict('records')
        
        # 결과 조합
        result = {
            "keyword": keyword,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interest_over_time": interest_data,
            "related_queries": {
                "rising": rising_queries,
                "top": top_queries
            }
        }
        
        return result
    
    except Exception as e:
        logger.error(f"트렌드 데이터 조회 오류: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 3001))
    uvicorn.run(app, host="0.0.0.0", port=port)