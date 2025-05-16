import requests
import pandas as pd
import time
from urllib.parse import quote

# CSV 파일 로드
def load_keywords_from_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        # CSV 파일 구조에 따라 키워드가 있는 열 이름을 지정하세요
        # 첫 번째 열 이름이 없는 경우 직접 접근
        if len(df.columns) == 1:
            keywords = df.iloc[:, 0].tolist()
        else:
            # 여러 열이 있는 경우 첫 번째 열 사용
            keywords = df[df.columns[0]].tolist()
        
        # NaN 값 제거 및 문자열로 변환
        keywords = [str(keyword) for keyword in keywords if pd.notna(keyword)]
        return keywords
    except Exception as e:
        print(f"CSV 파일 로드 중 오류 발생: {e}")
        return []

# NewsAPI를 사용하여 뉴스 가져오기
def get_news_for_keyword(keyword, api_key, language='ko'):
    # 키워드 URL 인코딩
    encoded_keyword = quote(keyword)
    
    url = (f'https://newsapi.org/v2/everything?'
           f'q={encoded_keyword}&'
           f'language={language}&'
           f'sortBy=publishedAt&'
           f'apiKey={api_key}')
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data.get('status') == 'ok':
            return data.get('articles', [])
        else:
            print(f"키워드 '{keyword}'에 대한 뉴스를 가져오는 데 실패했습니다: {data.get('message', '알 수 없는 오류')}")
            return []
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return []

# 메인 함수
def main():
    # 본인의 NewsAPI 키로 대체하세요
    api_key = "9a1225e79f9a47fcb59fccf946d9f992"
    csv_file_path = "google_trends_20250516_162603.csv"
    
    # CSV에서 키워드 로드
    keywords = load_keywords_from_csv(csv_file_path)
    print(f"CSV에서 {len(keywords)}개의 키워드를 로드했습니다.")
    
    # 각 키워드에 대한 뉴스 가져오기
    all_news = {}
    
    for keyword in keywords[:10]:  # API 사용량 제한을 위해 처음 10개만 테스트 (필요 시 변경하세요)
        print(f"'{keyword}' 키워드에 대한 뉴스를 가져오는 중...")
        articles = get_news_for_keyword(keyword, api_key)
        
        if articles:
            # 각 키워드별로 최대 5개의 기사만 저장
            all_news[keyword] = articles[:5]
            print(f"  - {len(articles[:5])}개의 기사를 찾았습니다.")
        else:
            print(f"  - 기사를 찾을 수 없습니다.")
        
        # API 요청 제한을 피하기 위한 지연
        time.sleep(1)
    
    # 결과 출력 및 저장
    for keyword, articles in all_news.items():
        print(f"\n키워드: {keyword} - {len(articles)}개의 기사")
        
        for i, article in enumerate(articles, 1):
            print(f"  {i}. {article.get('title', '제목 없음')}")
            print(f"     출처: {article.get('source', {}).get('name', '알 수 없음')}")
            print(f"     URL: {article.get('url', '링크 없음')}")
            print(f"     날짜: {article.get('publishedAt', '날짜 없음')}")
    
    # 결과를 파일로 저장 (선택 사항)
    # 모든 결과를 CSV 파일로 저장
    save_results_to_csv(all_news, "news_results.csv")

# 뉴스 결과를 CSV 파일로 저장
def save_results_to_csv(all_news, output_file):
    rows = []
    
    for keyword, articles in all_news.items():
        for article in articles:
            rows.append({
                '키워드': keyword,
                '제목': article.get('title', ''),
                '출처': article.get('source', {}).get('name', ''),
                'URL': article.get('url', ''),
                '발행일': article.get('publishedAt', ''),
                '내용': article.get('description', '')
            })
    
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n뉴스 결과가 '{output_file}' 파일에 저장되었습니다.")
    else:
        print("\n저장할 뉴스 결과가 없습니다.")

if __name__ == "__main__":
    main()