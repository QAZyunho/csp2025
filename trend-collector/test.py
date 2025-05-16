import requests
import xml.etree.ElementTree as ET
import pandas as pd
import logging
import time

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_trends_from_rss(geo='KR'):
    """
    Google Trends RSS 피드에서 모든 인기 검색어를 가져옵니다.
    
    Args:
        geo: 국가 코드 (예: 'KR' - 한국, 'US' - 미국)
        
    Returns:
        list: 인기 검색어 목록
    """
    url = f"https://trends.google.co.kr/trending/rss?geo={geo}"
    
    try:
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"{geo} - Error: {response.status_code}")
            return []
        
        # XML 파싱
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error(f"{geo} - XML 파싱 오류: {e}")
            # 잘못된 XML 문자 처리
            content = response.content.decode('utf-8', errors='ignore')
            root = ET.fromstring(content.encode('utf-8'))
        
        # 트렌드 추출
        trends = []
        
        # RSS 항목 찾기
        channel = root.find('channel')
        if channel is None:
            logger.error(f"{geo} - 'channel' 요소를 찾을 수 없습니다.")
            return []
            
        items = channel.findall('item')
        logger.debug(f"{geo} - 총 {len(items)}개의 항목을 찾았습니다.")
        
        for idx, item in enumerate(items):
            try:
                title_elem = item.find('title')
                link_elem = item.find('link')
                description_elem = item.find('description')
                pub_date_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else 'No Title'
                link = link_elem.text if link_elem is not None else 'No Link'
                description = description_elem.text if description_elem is not None else 'No Description'
                pub_date = pub_date_elem.text if pub_date_elem is not None else 'No Date'
                
                # 트래픽 정보 찾기 (네임스페이스가 있을 수 있음)
                traffic = None
                for elem in item:
                    if 'approxTraffic' in elem.tag:
                        traffic = elem.text
                        break
                
                trends.append({
                    'index': idx,
                    'title': title,
                    'link': link,
                    'description': description,
                    'published_date': pub_date,
                    'traffic': traffic,
                    'country': geo  # 국가 코드 추가
                })
            except Exception as e:
                logger.error(f"{geo} - 항목 {idx} 처리 중 오류: {e}")
        
        logger.debug(f"{geo} - 총 {len(trends)}개의 트렌드를 추출했습니다.")
        return trends
    
    except Exception as e:
        logger.error(f"{geo} - 전체 처리 중 오류: {e}")
        return []

def get_trends_from_multiple_countries(country_codes):
    """
    여러 국가의 Google Trends 데이터를 가져옵니다.
    
    Args:
        country_codes: 국가 코드 목록 (예: ['KR', 'US', 'JP'])
        
    Returns:
        dict: 국가별 트렌드 목록
    """
    all_trends = {}
    
    for country in country_codes:
        print(f"\n{get_country_name(country)} ({country}) 인기 검색어 가져오는 중...")
        trends = get_all_trends_from_rss(geo=country)
        all_trends[country] = trends
        
        print(f"{get_country_name(country)} ({country}) - 총 {len(trends)}개의 트렌드를 가져왔습니다.")
        
        # API 호출 사이에 약간의 지연 추가 (Google 차단 방지)
        time.sleep(1)
    
    return all_trends

def get_country_name(country_code):
    """
    국가 코드에서 국가 이름을 반환합니다.
    """
    country_names = {
        'KR': '한국',
        'US': '미국',
        'JP': '일본',
        'GB': '영국',
        'DE': '독일',
        'FR': '프랑스',
        'CA': '캐나다',
        'IN': '인도',
        'AU': '호주',
        'BR': '브라질',
        'IT': '이탈리아',
        'ES': '스페인',
        'RU': '러시아',
        'MX': '멕시코',
        'ID': '인도네시아',
        'SG': '싱가포르',
        'HK': '홍콩',
        'TW': '대만',
        'CH': '스위스',
        'SE': '스웨덴',
        'NL': '네덜란드',
        'TR': '터키',
        'PL': '폴란드'
    }
    
    return country_names.get(country_code, country_code)

def print_country_trends(trends_by_country):
    """
    국가별 트렌드를 출력합니다.
    """
    total_trends = 0
    
    for country, trends in trends_by_country.items():
        total_trends += len(trends)
        
        print(f"\n=== {get_country_name(country)} ({country}) 인기 검색어 ===")
        if not trends:
            print(f"  데이터를 가져오지 못했습니다.")
            continue
            
        for idx, trend in enumerate(trends):
            print(f"  {idx+1}. {trend['title']}")
            if 'traffic' in trend and trend['traffic']:
                print(f"     트래픽: {trend['traffic']}")

def main():
    # 국가 코드 목록
    # 주요 국가들만 포함 (워낙 많은 국가가 있으므로)
    country_codes = [
        'KR',  # 한국
        'US',  # 미국
    ]
    
    print(f"총 {len(country_codes)}개 국가의 인기 검색어를 가져옵니다...\n")
    
    # 여러 국가의 트렌드 가져오기
    trends_by_country = get_trends_from_multiple_countries(country_codes)
    
    # 결과 출력
    print("\n모든 국가의 인기 검색어:")
    print_country_trends(trends_by_country)
    
    # 총계 출력
    all_trends_count = sum(len(trends) for trends in trends_by_country.values())
    print(f"\n총 {len(trends_by_country)}개 국가에서 {all_trends_count}개의 인기 검색어를 수집했습니다.")

if __name__ == "__main__":
    main()