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
        """우선순위가 높은 키워드들을 CSV에서 로드 (book_keywords 컬럼 우선 사용)"""
        if not csv_path:
            print("❌ 키워드 CSV 파일 경로가 제공되지 않았습니다.")
            return []
        
        try:
            df = pd.read_csv(csv_path)
            keyword_pairs = []  # (original_keyword, search_keyword) 쌍으로 저장
            
            # book_keywords 컬럼이 있는지 확인하고 우선 사용
            if 'book_keywords' in df.columns:
                print("📚 book_keywords 컬럼을 발견했습니다. 도서 검색 최적화 키워드를 사용합니다.")
                
                for i, row in df.head(max_keywords).iterrows():
                    # 원래 키워드 추출 (저장용)
                    original_keyword = None
                    if 'keyword' in df.columns:
                        original_keyword = row.get('keyword', '')
                    elif len(df.columns) >= 2:
                        original_keyword = row.iloc[1] if i < len(df) else ''
                    else:
                        original_keyword = row.iloc[0] if i < len(df) else ''
                    
                    # 검색용 키워드 추출
                    book_keywords_str = row.get('book_keywords', '')
                    if pd.notna(book_keywords_str) and book_keywords_str.strip():
                        # 문자열을 리스트로 변환 (eval 사용 - 안전성을 위해 try-except 사용)
                        try:
                            if book_keywords_str.startswith('[') and book_keywords_str.endswith(']'):
                                # 리스트 형태의 문자열인 경우
                                keywords_list = eval(book_keywords_str)
                                if isinstance(keywords_list, list):
                                    # 각 키워드를 개별적으로 추가 (최대 3개까지)
                                    for keyword in keywords_list[:3]:
                                        if isinstance(keyword, str) and keyword.strip():
                                            keyword_pairs.append((str(original_keyword).strip(), keyword.strip()))
                            else:
                                # 단일 문자열인 경우
                                keyword_pairs.append((str(original_keyword).strip(), book_keywords_str.strip()))
                        except:
                            # eval 실패 시 문자열 그대로 사용
                            print(f"⚠️ book_keywords 파싱 실패, 원본 사용: {book_keywords_str}")
                            keyword_pairs.append((str(original_keyword).strip(), book_keywords_str.strip()))
                
                if keyword_pairs:
                    print(f"✅ book_keywords에서 {len(keyword_pairs)}개의 키워드 쌍을 로드했습니다.")
                    return keyword_pairs[:max_keywords * 3]  # 더 많은 키워드 허용
            
            # book_keywords가 없거나 비어있는 경우 기존 방식 사용
            print("📖 일반 키워드 컬럼을 사용합니다.")
            
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
            
            # 일반 키워드의 경우 (original, search) 쌍을 동일하게 설정
            keyword_pairs = [(kw, kw) for kw in keywords]
            
            print(f"✅ {len(keyword_pairs)}개의 우선순위 키워드를 로드했습니다.")
            return keyword_pairs
            
        except FileNotFoundError:
            print(f"❌ 파일을 찾을 수 없습니다: {csv_path}")
            return []
        except Exception as e:
            print(f"❌ 키워드 로드 중 오류: {str(e)}")
            return []
    
    def filter_by_material_type(self, books):
        """원하는 자료유형으로 필터링 (도서, 기사, 신문, 멀티미디어만)"""
        # 원하는 자료유형만 필터링
        desired_types = ['도서', '기사', '신문', '멀티미디어', '단행본', '연속간행물']
        filtered_books = []
        
        for book in books:
            book_type = book.get('type', '').lower()
            # 원하는 자료유형이거나 자료유형 정보가 없는 경우 포함
            if not book_type or any(dtype.lower() in book_type for dtype in desired_types):
                filtered_books.append(book)
        
        return filtered_books
    
    def remove_duplicates(self, books):
        """중복 도서 제거 (제목과 저자 기준)"""
        seen = set()
        unique_books = []
        
        for book in books:
            title = book.get('title', '').strip()
            author = book.get('author', '').strip()
            
            # 제목과 저자의 조합으로 중복 체크
            key = (title.lower(), author.lower())
            
            if key not in seen and title:  # 제목이 있고 중복이 아닌 경우
                seen.add(key)
                unique_books.append(book)
        
        return unique_books
    
    def search_books_by_keyword(self, original_keyword, search_keyword, max_results=5):
        """특정 키워드로 도서 검색 (검색용 키워드 사용, 원래 키워드로 저장)"""
        try:
            # URL 인코딩
            encoded_keyword = urllib.parse.quote(search_keyword)
            
            # 대량 검색 (발행년도 내림차순)
            url = (f"{self.base_url}?key={self.api_key}&apiType=xml"
                  f"&srchTarget=total&kwd={encoded_keyword}"
                  f"&pageSize={max_results * 4}&pageNum=1&sort=ipub_year,order=desc")
            
            print(f"🔍 '{search_keyword}' 검색 중... (원래 키워드: '{original_keyword}')")
            
            # API 요청
            response = requests.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                books = self.parse_search_results(response.text, original_keyword, search_keyword)
                
                # 원하는 자료유형만 필터링
                filtered_books = self.filter_by_material_type(books)
                
                # 중복 제거
                unique_books = self.remove_duplicates(filtered_books)
                
                # 결과 제한
                final_books = unique_books[:max_results]
                
                if final_books:
                    print(f"📚 '{search_keyword}': {len(final_books)}개 자료 발견")
                    print(f"    (전체 {len(books)}개 → 필터링 {len(filtered_books)}개 → 중복제거 {len(unique_books)}개)")
                else:
                    print(f"📭 '{search_keyword}': 관련 자료 없음")
                    
                return final_books
            else:
                print(f"❌ '{search_keyword}' 검색 실패: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ '{search_keyword}' 검색 중 오류: {str(e)}")
            return []
    
    def parse_search_results(self, xml_text, original_keyword, search_keyword):
        """XML 검색 결과를 파싱하여 도서 정보 추출"""
        books = []
        
        try:
            # 총 검색 결과 수 추출
            total_match = re.search(r'<total>(\d+)</total>', xml_text)
            total_count = int(total_match.group(1)) if total_match else 0
            
            # 각 도서 항목 추출 (더 많이 파싱)
            item_pattern = r'<item>(.*?)</item>'
            for i, item_match in enumerate(re.finditer(item_pattern, xml_text, re.DOTALL), 1):
                if i > 30:  # 최대 30개까지 파싱 (중복 제거 후에도 충분한 결과 확보)
                    break
                    
                item_text = item_match.group(1)
                book = self.extract_book_info(item_text)
                
                if book and book.get('title'):  # 제목이 있는 경우만 추가
                    book['keyword'] = original_keyword  # 원래 키워드로 저장
                    book['search_keyword'] = search_keyword  # 검색용 키워드도 별도 저장
                    book['total_results'] = total_count
                    
                    # 최신 자료 우선 - 발행년도가 있는 경우 우선순위 부여
                    pub_year = book.get('pub_year')
                    if pub_year and pub_year.isdigit():
                        book['pub_year_int'] = int(pub_year)
                    else:
                        book['pub_year_int'] = 0  # 발행년도 없는 경우 낮은 우선순위
                    
                    books.append(book)
                    
        except Exception as e:
            print(f"XML 파싱 오류: {str(e)}")
        
        # 발행년도 내림차순으로 정렬 (최신 자료 우선)
        books.sort(key=lambda x: x.get('pub_year_int', 0), reverse=True)
        
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
    
    def process_all_keywords(self, keyword_pairs, max_books_per_keyword=3):
        """모든 키워드에 대해 도서 검색 수행"""
        all_recommendations = []
        
        print(f"\n🚀 {len(keyword_pairs)}개 키워드로 도서 검색을 시작합니다...\n")
        
        for i, (original_keyword, search_keyword) in enumerate(keyword_pairs, 1):
            print(f"[{i}/{len(keyword_pairs)}] ", end="")
            books = self.search_books_by_keyword(original_keyword, search_keyword, max_books_per_keyword)
            
            if books:
                all_recommendations.extend(books)
            else:
                print(f"⚠️  '{search_keyword}': 관련 도서를 찾지 못했습니다.")
            
            # API 호출 간격 조절 (너무 빠른 요청 방지)
            if i < len(keyword_pairs):
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
                    'type', 'call_no', 'isbn', 'library_location', 'library_name', 'search_category'
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
                    'library_name': '소장도서관명',
                    'search_category': '검색카테고리'  # 새로 추가
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
        
        # 카테고리별 통계 (자료유형별)
        type_stats = {}
        for book in recommendations:
            book_type = book.get('type', '기타')
            type_stats[book_type] = type_stats.get(book_type, 0) + 1
        
        print(f"자료 유형: {len(type_stats)}개")
        
        # 도서관별 통계
        library_stats = {}
        for book in recommendations:
            library = book.get('library_name', '정보없음')
            library_stats[library] = library_stats.get(library, 0) + 1
        
        print(f"소장 도서관: {len(library_stats)}개")
        
        print(f"\n📚 키워드별 추천 자료 수:")
        for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {keyword}: {count}개")
        
        print(f"\n📂 자료유형별 추천 자료 수:")
        for book_type, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {book_type}: {count}개")
        
        print(f"\n🏛️ 도서관별 소장 도서 수 (상위 5개):")
        for library, count in sorted(library_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  • {library}: {count}권")
        
        # 상위 추천 자료 미리보기 (발행년도순 정렬)
        print(f"\n🔥 주요 추천 자료 (최신순 상위 5개):")
        
        # 발행년도 기준으로 정렬
        sorted_recommendations = sorted(recommendations, 
                                      key=lambda x: x.get('pub_year_int', 0), 
                                      reverse=True)
        
        for i, book in enumerate(sorted_recommendations[:5], 1):
            title = book.get('title', '제목 없음')
            author = book.get('author', '저자 미상')
            keyword = book.get('keyword', '')
            search_keyword = book.get('search_keyword', '')
            book_type = book.get('type', '자료유형 미상')
            pub_year = book.get('pub_year', '발행년도 미상')
            library_name = book.get('library_name', '도서관 정보없음')
            library_location = book.get('library_location', '')
            
            print(f"  {i}. [{keyword}] {title} ({pub_year})")
            print(f"    저자: {author} | 자료유형: {book_type}")
            print(f"    검색키워드: {search_keyword}")
            print(f"    소장: {library_name} {f'({library_location})' if library_location else ''}")"    소장: {library_name} {f'({library_location})' if library_location else ''}")

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="우선순위 키워드 기반 도서 추천 시스템")
    parser.add_argument("--input_file", "-i", required=True, help="뉴스 요약 CSV 파일 (book_keywords 컬럼 포함)")
    parser.add_argument("--max_keywords", "-m", type=int, default=15, 
                        help="처리할 최대 키워드 수 (기본값: 15)")
    parser.add_argument("--max_books_per_keyword", type=int, default=2,
                        help="각 키워드당 검색할 최대 도서 수 (기본값: 2)")
    
    args = parser.parse_args()

    print("📖 우선순위 키워드 기반 도서 추천 시스템")
    print("=" * 50)
    print("💡 book_keywords 컬럼을 우선적으로 사용하여 도서를 검색합니다.")
    
    # Book Recommender 초기화
    recommender = BookRecommender()
    
    # 우선순위 키워드 로드 (book_keywords 우선)
    keyword_pairs = recommender.load_prioritized_keywords(args.input_file, args.max_keywords)
    
    if not keyword_pairs:
        print("❌ 처리할 키워드가 없습니다. 프로그램을 종료합니다.")
        return
    
    print(f"🎯 처리할 키워드 ({len(keyword_pairs)}개):")
    for i, (original, search) in enumerate(keyword_pairs[:5]):
        print(f"   {i+1}. {original} → {search}")
    if len(keyword_pairs) > 5:
        print(f"   ... 외 {len(keyword_pairs) - 5}개")
    
    # 모든 키워드에 대해 도서 검색
    recommendations = recommender.process_all_keywords(keyword_pairs, args.max_books_per_keyword)
    
    # 결과 요약 출력
    recommender.print_summary(recommendations)
    
    if recommendations:
        # 출력 파일 경로 설정
        output_dir = os.path.dirname(args.input_file) if args.input_file else "."
        
        # 결과 저장 (JSON, CSV)
        recommender.save_recommendations(recommendations, output_dir)
        
        print(f"\n✅ 총 {len(recommendations)}개의 자료를 추천했습니다!")
        print(f"📁 결과 파일은 '{output_dir}' 디렉토리에 저장되었습니다.")
        print(f"   • book_recommendations.json (상세 정보)")
        print(f"   • book_recommendations.csv (표 형태 - 원본키워드와 검색키워드 분리)")
    else:
        print("❌ 추천할 자료를 찾지 못했습니다.")
        print("💡 다른 키워드를 시도해보거나 검색 조건을 완화해보세요.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  프로그램이 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)