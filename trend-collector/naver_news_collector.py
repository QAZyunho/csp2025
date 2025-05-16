import urllib.request
import json
import pandas as pd
import argparse

def print_news_titles(keywords, client_id, client_secret, max_articles=5):
    """
    키워드 리스트로 뉴스를 검색하고 제목만 출력합니다.
    
    Args:
        keywords (list): 검색할 키워드 리스트
        client_id (str): 네이버 API 클라이언트 ID
        client_secret (str): 네이버 API 클라이언트 시크릿
        max_articles (int): 키워드당 최대 뉴스 개수
    """
    print(f"검색할 키워드 수: {len(keywords)}")
    
    all_titles = []
    
    for idx, keyword in enumerate(keywords):
        try:
            # URL 인코딩
            encText = urllib.parse.quote(keyword)
            url = f"https://openapi.naver.com/v1/search/news?query={encText}&display={max_articles}&start=1&sort=date"
            
            # 요청 객체 생성
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            # API 호출
            response = urllib.request.urlopen(request)
            
            rescode = response.getcode()
            if rescode == 200:
                response_body = response.read()
                news_data = json.loads(response_body.decode('utf-8'))
                
                # 반환된 뉴스 항목이 있는지 확인
                if "items" in news_data and len(news_data["items"]) > 0:
                    for item in news_data["items"]:
                        # HTML 태그 제거
                        title = item["title"].replace("<b>", "").replace("</b>", "")
                        all_titles.append((keyword, title))
                
                print(f"[{idx+1}/{len(keywords)}] '{keyword}' 검색: {len(news_data.get('items', []))}개 기사")
            else:
                print(f"[{idx+1}/{len(keywords)}] '{keyword}' 검색 실패: 오류 코드 {rescode}")
                
        except Exception as e:
            print(f"[{idx+1}/{len(keywords)}] '{keyword}' 검색 중 오류: {str(e)}")
    
    # 찾은 모든 기사 제목 출력
    if all_titles:
        print("\n===== 찾은 뉴스 기사 제목 =====")
        for i, (keyword, title) in enumerate(all_titles):
            print(f"{i+1}. [{keyword}] {title}")
        
        print(f"\n총 {len(all_titles)}개의 뉴스 기사를 찾았습니다.")
    else:
        print("찾은 뉴스 기사가 없습니다.")

def main():
    parser = argparse.ArgumentParser(description="네이버 뉴스 API로 기사 제목만 출력")
    parser.add_argument("--keywords", type=str, default="prioritized_keywords.csv", 
                       help="키워드 CSV 파일 경로 (기본값: prioritized_keywords.csv)")
    parser.add_argument("--max_keywords", type=int, default=50, 
                       help="검색할 최대 키워드 수 (기본값: 50)")
    parser.add_argument("--max_articles", type=int, default=5, 
                       help="키워드당 최대 뉴스 개수 (기본값: 5)")
    
    args = parser.parse_args()
    
    try:
        # 키워드 파일 로드
        keywords_df = pd.read_csv(args.keywords)
        if "rank" in keywords_df.columns and "keyword" in keywords_df.columns:
            keywords_df = keywords_df.sort_values("rank")
            keyword_column = "keyword"
        else:
            # 열 이름이 다를 경우 첫 번째 열 사용
            keyword_column = keywords_df.columns[0]
        
        keywords = keywords_df[keyword_column].tolist()[:args.max_keywords]
        client_id = "RPUhkWY7UVq81hlMiHNL"
        client_secret = "u5HUugAYuv"
        # 뉴스 제목 출력
        print_news_titles(keywords, client_id, client_secret, args.max_articles)
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    main()