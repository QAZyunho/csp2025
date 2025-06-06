#!/usr/bin/env python3
# 국립중앙도서관 API 키워드 검색 프로그램 (prioritized keywords 기반)

import requests
import sys
import os
import re
import pandas as pd
import json
from datetime import datetime
import urllib.parse
import argparse

class BookRecommender:
    def __init__(self, api_key="0dfddd5045ff123245cc00ab9034d122d6b6c1e6fba60c838f7304b8f98a69c1"):
        self.api_key = api_key
        self.base_url = "https://www.nl.go.kr/NL/search/openApi/search.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def load_prioritized_keywords(self, csv_path=None, max_keywords=10):
        """우선순위가 높은 키워드들을 CSV에서 로드"""
        if not csv_path:
            print("❌ 키워드 CSV 파일 경로가 제공되지 않았습니다.")
            return []
        
        try:
            df = pd.read_csv(csv_path)
            
            # CSV 구조에 따라 키워드 컬럼 찾기
            if 'keyword' in df.columns:
                keywords = df.head(max_keywords)['keyword'].tolist()
            elif len(df.columns) >= 2:
                # rank, keyword 순서로 되어있는 경우
                keywords = df.head(max_keywords).iloc[:, 1].tolist()
            else:
                # 첫 번째 컬럼이 키워드인 경우
                keywords = df.head(max_keywords).iloc[:, 0].tolist()
                
            # NaN 값 제거 및 문자열 변환
            keywords = [str(kw).strip() for kw in keywords if pd.notna(kw) and str(kw).strip()]
            
            print(f"✅ {len(keywords)}개의 우선순위 키워드를 로드했습니다.")
            return keywords
            
        except FileNotFoundError:
            print(f"❌ 파일을 찾을 수 없습니다: {csv_path}")
            return []
        except Exception as e:
            print(f"❌ 키워드 로드 중 오류: {str(e)}")
            return []
    
    def search_books_by_keyword(self, keyword, max_results=5):
        """특정 키워드로 도서 검색"""
        try:
            # URL 인코딩
            encoded_keyword = urllib.parse.quote(keyword)
            url = f"{self.base_url}?key={self.api_key}&apiType=xml&srchTarget=total&kwd={encoded_keyword}&pageSize={max_results}&pageNum=1"
            
            print(f"🔍 '{keyword}' 검색 중...")
            
            # API 요청
            response = requests.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                books = self.parse_search_results(response.text, keyword)
                print(f"📚 '{keyword}': {len(books)}개 도서 발견")
                return books
            else:
                print(f"❌ '{keyword}' 검색 실패: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ '{keyword}' 검색 중 오류: {str(e)}")
            return []
    
    def parse_search_results(self, xml_text, keyword):
        """XML 검색 결과를 파싱하여 도서 정보 추출"""
        books = []
        
        try:
            # 총 검색 결과 수 추출
            total_match = re.search(r'<total>(\d+)</total>', xml_text)
            total_count = int(total_match.group(1)) if total_match else 0
            
            # 각 도서 항목 추출
            item_pattern = r'<item>(.*?)</item>'
            for i, item_match in enumerate(re.finditer(item_pattern, xml_text, re.DOTALL), 1):
                if i > 10:  # 최대 10개만 처리
                    break
                    
                item_text = item_match.group(1)
                book = self.extract_book_info(item_text)
                
                if book and book.get('title'):  # 제목이 있는 경우만 추가
                    book['keyword'] = keyword
                    book['total_results'] = total_count
                    books.append(book)
                    
        except Exception as e:
            print(f"XML 파싱 오류: {str(e)}")
            
        return books
    
    def extract_book_info(self, item_text):
        """개별 도서 항목에서 정보 추출"""
        book = {}
        
        # 정보 추출 패턴들 (도서관 정보 추가)
        patterns = {
            'title': r'<title_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</title_info>',
            'author': r'<author_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</author_info>',
            'publisher': r'<pub_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</pub_info>',
            'pub_year': r'<pub_year_info>(\d+)</pub_year_info>',
            'call_no': r'<call_no>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</call_no>',
            'type': r'<type_name>([^<]+)</type_name>',
            'isbn': r'<isbn>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</isbn>',
            # 도서관 정보 추가
            'library_location': r'<place_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</place_info>',
            'library_name': r'<manage_name>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</manage_name>'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, item_text, re.DOTALL)
            if match:
                # CDATA 또는 일반 텍스트 추출
                value = match.group(1) or match.group(2) if len(match.groups()) >= 2 else match.group(1)
                if value:
                    book[field] = value.strip()
        
        return book
    
    def process_all_keywords(self, keywords, max_books_per_keyword=3):
        """모든 키워드에 대해 도서 검색 수행"""
        all_recommendations = []
        
        print(f"\n🚀 {len(keywords)}개 키워드로 도서 검색을 시작합니다...\n")
        
        for i, keyword in enumerate(keywords, 1):
            print(f"[{i}/{len(keywords)}] ", end="")
            books = self.search_books_by_keyword(keyword, max_books_per_keyword)
            
            if books:
                all_recommendations.extend(books)
            else:
                print(f"⚠️  '{keyword}': 관련 도서를 찾지 못했습니다.")
            
            # API 호출 간격 조절 (너무 빠른 요청 방지)
            if i < len(keywords):
                import time
                time.sleep(0.5)
        
        return all_recommendations
    
    def save_recommendations(self, recommendations, output_dir=".", base_filename="book_recommendations"):
        """추천 도서 목록을 파일로 저장"""
        json_output_file = os.path.join(output_dir, f"{base_filename}.json")
        csv_output_file = os.path.join(output_dir, f"{base_filename}.csv")

        try:
            # 결과 요약 정보 추가 (JSON)
            summary = {
                "generated_at": datetime.now().isoformat(),
                "total_books": len(recommendations),
                "unique_keywords": len(set(book['keyword'] for book in recommendations)),
                "recommendations": recommendations
            }
            
            with open(json_output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            print(f"💾 추천 도서 목록이 '{json_output_file}'에 저장되었습니다.")
            
            # CSV 저장 (도서관 정보 포함)
            if recommendations:
                df = pd.DataFrame(recommendations)
                columns_to_keep = [
                    'keyword', 'title', 'author', 'publisher', 'pub_year', 
                    'type', 'call_no', 'isbn', 'library_location', 'library_name'
                ]
                existing_columns = [col for col in columns_to_keep if col in df.columns]
                df_filtered = df[existing_columns]
                
                # 컬럼명을 한국어로 변경 (가독성 향상)
                column_mapping = {
                    'keyword': '검색키워드',
                    'title': '도서명',
                    'author': '저자',
                    'publisher': '출판사',
                    'pub_year': '발행년도',
                    'type': '자료유형',
                    'call_no': '청구기호',
                    'isbn': 'ISBN',
                    'library_location': '소장도서관위치',
                    'library_name': '소장도서관명'
                }
                
                df_filtered = df_filtered.rename(columns=column_mapping)
                df_filtered.to_csv(csv_output_file, index=False, encoding='utf-8-sig')
                print(f"📋 CSV 보고서가 '{csv_output_file}'에 저장되었습니다.")
            else:
                print("CSV 보고서를 생성할 데이터가 없습니다.")
            
            return True
            
        except Exception as e:
            print(f"❌ 파일 저장 오류: {str(e)}")
            return False
    
    def print_summary(self, recommendations):
        """검색 결과 요약 출력"""
        if not recommendations:
            print("📭 추천할 도서가 없습니다.")
            return
        
        print(f"\n📊 === 검색 결과 요약 ===")
        print(f"총 추천 도서: {len(recommendations)}권")
        
        # 키워드별 통계
        keyword_stats = {}
        for book in recommendations:
            keyword = book['keyword']
            keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1
        
        print(f"검색 키워드: {len(keyword_stats)}개")
        
        # 도서관별 통계
        library_stats = {}
        for book in recommendations:
            library = book.get('library_name', '정보없음')
            library_stats[library] = library_stats.get(library, 0) + 1
        
        print(f"소장 도서관: {len(library_stats)}개")
        
        print(f"\n📚 키워드별 추천 도서 수:")
        for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {keyword}: {count}권")
        
        print(f"\n🏛️ 도서관별 소장 도서 수 (상위 5개):")
        for library, count in sorted(library_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  • {library}: {count}권")
        
        # 상위 추천 도서 미리보기
        print(f"\n🔥 주요 추천 도서 (상위 5권):")
        for i, book in enumerate(recommendations[:5], 1):
            title = book.get('title', '제목 없음')
            author = book.get('author', '저자 미상')
            keyword = book.get('keyword', '')
            library_name = book.get('library_name', '도서관 정보없음')
            library_location = book.get('library_location', '')
            
            print(f"  {i}. [{keyword}] {title}")
            print(f"    저자: {author}")
            print(f"    소장: {library_name} {f'({library_location})' if library_location else ''}")

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="우선순위 키워드 기반 도서 추천 시스템")
    parser.add_argument("--input_file", "-i", required=True, help="뉴스 요약 CSV 파일")
    parser.add_argument("--max_keywords", type=int, default=15, 
                        help="처리할 최대 키워드 수 (기본값: 15)")
    parser.add_argument("--max_books_per_keyword", "-m", type=int, default=3,
                        help="각 키워드당 검색할 최대 도서 수 (기본값: 3)")
    
    args = parser.parse_args()

    print("📖 우선순위 키워드 기반 도서 추천 시스템")
    print("=" * 50)
    
    # Book Recommender 초기화
    recommender = BookRecommender()
    
    # 우선순위 키워드 로드
    keywords = recommender.load_prioritized_keywords(args.input_file, args.max_keywords)
    
    if not keywords:
        print("❌ 처리할 키워드가 없습니다. 프로그램을 종료합니다.")
        return
    
    print(f"🎯 처리할 키워드: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
    
    # 모든 키워드에 대해 도서 검색
    recommendations = recommender.process_all_keywords(keywords, args.max_books_per_keyword)
    
    # 결과 요약 출력
    recommender.print_summary(recommendations)
    
    if recommendations:
        # 출력 파일 경로 설정
        output_dir = os.path.dirname(args.input_file) if args.input_file else "."
        
        # 결과 저장 (JSON, CSV)
        recommender.save_recommendations(recommendations, output_dir)
        
        print(f"\n✅ 총 {len(recommendations)}권의 도서를 추천했습니다!")
        print(f"📁 결과 파일은 '{output_dir}' 디렉토리에 저장되었습니다.")
        print(f"   • book_recommendations.json (상세 정보)")
        print(f"   • book_recommendations.csv (표 형태 - 도서관 정보 포함)")
    else:
        print("❌ 추천할 도서를 찾지 못했습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  프로그램이 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)