#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import urllib.parse
import json
import pandas as pd
import time
import datetime

def load_keywords_from_csv(file_path, max_keywords=20):
    """CSV 파일에서 키워드 로드"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        # 키워드 컬럼 찾기
        if 'keyword' in df.columns:
            keyword_col = 'keyword'
        else:
            keyword_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        keywords = df[keyword_col].astype(str).str.strip().tolist()[:max_keywords]
        print(f"로드된 키워드 수: {len(keywords)}개")
        return keywords
        
    except Exception as e:
        print(f"키워드 파일 로드 실패: {str(e)}")
        return []

def search_news_for_keyword(keyword, client_id, client_secret, max_articles=5):
    """특정 키워드로 네이버 뉴스 검색"""
    try:
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://openapi.naver.com/v1/search/news?query={encoded_keyword}&display={max_articles}&start=1&sort=date"
        
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", client_id)
        request.add_header("X-Naver-Client-Secret", client_secret)
        
        response = urllib.request.urlopen(request)
        
        if response.getcode() == 200:
            response_body = response.read()
            news_data = json.loads(response_body.decode('utf-8'))
            
            articles = []
            if "items" in news_data:
                for item in news_data["items"]:
                    title = item["title"].replace("<b>", "").replace("</b>", "")
                    description = item.get("description", "").replace("<b>", "").replace("</b>", "")
                    
                    articles.append({
                        'keyword': keyword,
                        'title': title,
                        'description': description,
                        'link': item.get("link", ""),
                        'pub_date': item.get("pubDate", ""),
                        'source': item.get("source", "")
                    })
            
            return articles
        else:
            print(f"'{keyword}' 검색 실패: HTTP {response.getcode()}")
            return []
            
    except Exception as e:
        print(f"'{keyword}' 뉴스 검색 오류: {str(e)}")
        return []

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="네이버 뉴스 수집기")
    parser.add_argument("--input", "-i", required=True, help="키워드 CSV 파일")
    parser.add_argument("--output", "-o", default=None, help="출력 파일명")
    parser.add_argument("--max_keywords", "-k", type=int, default=20, help="최대 키워드 수")
    parser.add_argument("--max_articles", "-a", type=int, default=5, help="키워드당 최대 기사 수")
    
    args = parser.parse_args()
    
    # 네이버 API 키
    client_id = "RPUhkWY7UVq81hlMiHNL"
    client_secret = "u5HUugAYuv"
    
    # 출력 파일명 설정
    if not args.output:
        timestamp = datetime.datetime.now().strftime("%y%m%d")
        args.output = f"news_{timestamp}.csv"
    
    print(f"입력: {args.input}")
    print(f"출력: {args.output}")
    print(f"최대 키워드: {args.max_keywords}개")
    print(f"키워드당 최대 기사: {args.max_articles}개")
    
    # 키워드 로드
    keywords = load_keywords_from_csv(args.input, args.max_keywords)
    if not keywords:
        print("키워드를 찾을 수 없습니다.")
        return
    
    # 뉴스 수집
    all_news = []
    for i, keyword in enumerate(keywords, 1):
        print(f"[{i}/{len(keywords)}] '{keyword}' 검색 중...")
        
        articles = search_news_for_keyword(keyword, client_id, client_secret, args.max_articles)
        if articles:
            all_news.extend(articles)
            print(f"  ✅ {len(articles)}개 기사 수집")
        else:
            print(f"  ⚠️  기사 없음")
        
        time.sleep(0.1)  # API 제한 방지
    
    # 결과 저장
    if all_news:
        df = pd.DataFrame(all_news)
        df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\n✅ {len(all_news)}개 기사를 '{args.output}'에 저장했습니다.")
    else:
        print("\n❌ 수집된 뉴스가 없습니다.")

if __name__ == "__main__":
    main()