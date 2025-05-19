#!/usr/bin/env python3
# 국립중앙도서관 API 키워드 검색 프로그램 (직접 URL 사용 버전)

import requests
import sys
import os
import re

def direct_url_search(keyword=None):
    """
    직접 URL을 사용하여 검색을 수행합니다.
    브라우저에서 동작하는 것과 동일한 URL 사용
    """
    try:
        # 기본 URL (브라우저에서 동작하는 URL)
        if keyword:
            # 키워드가 제공된 경우 URL 인코딩하여 URL 구성
            import urllib.parse
            encoded_keyword = urllib.parse.quote(keyword)
            url = f"https://www.nl.go.kr/NL/search/openApi/search.do?key=0dfddd5045ff123245cc00ab9034d122d6b6c1e6fba60c838f7304b8f98a69c1&apiType=xml&srchTarget=total&kwd={encoded_keyword}&pageSize=10&pageNum=1"

        
        print(f"\n요청 URL: {url}")
        
        # 브라우저 User-Agent 사용
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # GET 요청 - 직접 URL 사용
        print("\n요청 전송 중...")
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"상태 코드: {response.status_code}")
        print(f"응답 인코딩: {response.encoding}")
        
        # 인코딩 설정
        response.encoding = 'utf-8'
        
        # 응답 텍스트 파일로 저장
        result_file = "direct_url_result.xml"
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        print(f"\n검색 결과가 '{result_file}' 파일에 저장되었습니다.")
        print("파일 크기:", os.path.getsize(result_file), "바이트")
        
        # 결과의 일부 출력 및 분석
        extract_and_print_results(response.text)
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")

def extract_and_print_results(xml_text):
    """
    XML 응답에서 주요 내용을 추출하여 출력
    """
    print("\n===== 검색 결과 =====")
    
    # 전체 응답 첫 부분 출력
    print("\n응답 시작 부분:")
    print(xml_text[:200] + "...\n")
    
    # 총 검색 결과 수 추출
    total_match = re.search(r'<total>(\d+)</total>', xml_text)
    if total_match:
        total = total_match.group(1)
        print(f"총 검색 결과: {total}건")
    
    # CDATA 태그 찾기
    cdata_tags = re.findall(r'<!\[CDATA\[(.*?)\]\]>', xml_text)
    print(f"\nCDATA 태그 내용 ({len(cdata_tags)}개 발견):")
    for i, content in enumerate(cdata_tags[:10], 1):  # 처음 10개만 출력
        print(f"{i}. {content}")
    
    # 아이템 정보 추출 시도
    print("\n도서 정보 추출 시도:")
    items = []
    item_pattern = r'<item>(.*?)</item>'
    
    for i, item_match in enumerate(re.finditer(item_pattern, xml_text, re.DOTALL), 1):
        if i > 5:  # 처음 5개만 처리
            break
            
        item_text = item_match.group(1)
        book = {}
        
        # 제목 추출 (CDATA 처리)
        title_match = re.search(r'<title_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</title_info>', item_text, re.DOTALL)
        if title_match:
            title = title_match.group(1) or title_match.group(2)
            book['title'] = title.strip()
        
        # 저자 추출 (CDATA 처리)
        author_match = re.search(r'<author_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</author_info>', item_text, re.DOTALL)
        if author_match:
            author = author_match.group(1) or author_match.group(2)
            book['author'] = author.strip()
        
        items.append(book)
    
    # 추출된 정보 출력
    if items:
        for i, book in enumerate(items, 1):
            print(f"\n[도서 {i}]")
            print(f"제목: {book.get('title', '정보 없음')}")
            print(f"저자: {book.get('author', '정보 없음')}")
    else:
        print("도서 정보를 추출할 수 없습니다.")
    
    print("\n전체 XML 내용을 직접 확인하려면 'direct_url_result.xml' 파일을 열어보세요.")

def main():
    print("국립중앙도서관 API 키워드 검색 프로그램 (직접 URL 사용 버전)")
    
    # 기본 "토지" 검색
    print("\n기본 '토지' 검색을 실행합니다...")
    direct_url_search()
    
    # 사용자 검색
    while True:
        print("\n-----------------------------------")
        keyword = input("\n검색할 키워드를 입력하세요 (종료: q): ")
        
        if keyword.lower() == 'q':
            print("프로그램을 종료합니다.")
            break
            
        if not keyword.strip():
            print("검색어를 입력해주세요.")
            continue
        
        direct_url_search(keyword)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n프로그램 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)