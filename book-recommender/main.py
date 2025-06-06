#!/usr/bin/env python3
# Firebase 연동 도서 추천 시스템
# Firebase trend 컬렉션에서 데이터를 읽어와서 도서 검색 후 source 컬렉션에 저장

import requests
import sys
import os
import re
import json
from datetime import datetime
import urllib.parse
import argparse
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Dict, Optional
import time

class FirebaseBookRecommender:
    def __init__(self, api_key="0dfddd5045ff123245cc00ab9034d122d6b6c1e6fba60c838f7304b8f98a69c1", 
                 gemini_api_key=None, firebase_config_path=None):
        self.api_key = api_key
        self.base_url = "https://www.nl.go.kr/NL/search/openApi/search.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Firebase 초기화
        self.init_firebase(firebase_config_path)
        
        # Gemini API 설정 (필수)
        if not gemini_api_key:
            raise ValueError("❌ Gemini API 키가 필수입니다. --gemini_api_key 옵션을 제공해주세요.")
        
        self.gemini_api_key = gemini_api_key
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini API가 설정되었습니다. 모든 검색 결과는 관련성 검증을 거칩니다.")
    
    def init_firebase(self, config_path):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                if config_path and os.path.exists(config_path):
                    cred = credentials.Certificate(config_path)
                    firebase_admin.initialize_app(cred)
                    print(f"✅ Firebase 서비스 계정으로 연결: {config_path}")
                else:
                    # 환경변수 사용
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
                    print("✅ Firebase 기본 인증으로 연결")
            
            self.db = firestore.client(database_id='csproject2025')
            print("✅ Firestore 연결 성공 - csproject2025 데이터베이스")
            
        except Exception as e:
            print(f"❌ Firebase 연결 실패: {str(e)}")
            self.db = None
    
    def load_trends_from_firebase(self, date_filter=None):
        """Firebase trend 컬렉션에서 트렌드 데이터 로드"""
        if not self.db:
            print("❌ Firebase 연결이 없습니다.")
            return []
        
        try:
            print("🔍 Firebase에서 트렌드 데이터 로드 중...")
            
            trends_ref = self.db.collection('trend')
            
            if date_filter:
                # 특정 날짜 문서 조회
                doc_ref = trends_ref.document(date_filter)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    trends = data.get('trends', [])
                    print(f"✅ {date_filter} 날짜의 트렌드 {len(trends)}개 로드")
                    return trends
                else:
                    print(f"❌ {date_filter} 날짜의 트렌드 데이터를 찾을 수 없습니다.")
                    return []
            else:
                # 모든 트렌드 문서 조회 (최신순)
                docs = trends_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(5).stream()
                all_trends = []
                
                for doc in docs:
                    data = doc.to_dict()
                    trends = data.get('trends', [])
                    print(f"📅 {doc.id}: {len(trends)}개 트렌드")
                    all_trends.extend(trends)
                
                print(f"✅ 총 {len(all_trends)}개 트렌드 로드")
                return all_trends
                
        except Exception as e:
            print(f"❌ Firebase 트렌드 로드 실패: {str(e)}")
            return []
    
    def extract_keywords_from_trends(self, trends, max_keywords=15):
        """트렌드 데이터에서 키워드 쌍 추출"""
        keyword_pairs = []
        
        for trend in trends[:max_keywords]:
            original_keyword = trend.get('keyword', '')
            book_keywords = trend.get('book_keywords', [])
            
            if original_keyword:
                if book_keywords and isinstance(book_keywords, list):
                    # book_keywords가 있는 경우 각각을 검색 키워드로 사용
                    for search_keyword in book_keywords[:3]:  # 최대 3개까지
                        if search_keyword and search_keyword.strip():
                            keyword_pairs.append((original_keyword, search_keyword.strip()))
                else:
                    # book_keywords가 없는 경우 원본 키워드 사용
                    keyword_pairs.append((original_keyword, original_keyword))
        
        print(f"📝 {len(keyword_pairs)}개의 키워드 쌍 추출")
        return keyword_pairs
    
    def filter_by_material_type(self, books):
        """원하는 자료유형으로 필터링 (도서, 기사, 신문, 멀티미디어만)"""
        desired_types = ['도서', '기사', '신문', '멀티미디어', '단행본', '연속간행물']
        filtered_books = []
        
        for book in books:
            book_type = book.get('type', '').lower()
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
            
            key = (title.lower(), author.lower())
            
            if key not in seen and title:
                seen.add(key)
                unique_books.append(book)
        
        return unique_books
    
    def verify_relevance_with_gemini(self, books: List[Dict], search_keyword: str) -> List[Dict]:
        """Gemini API를 사용하여 검색 결과와 키워드의 관련성 검증"""
        if not books:
            return books
        
        try:
            print(f"🤖 Gemini로 '{search_keyword}' 관련성 검증 중... ({len(books)}개 자료)")
            
            book_summaries = []
            for i, book in enumerate(books):
                title = book.get('title', '제목없음')
                author = book.get('author', '저자미상')
                book_type = book.get('type', '자료유형미상')
                summary = f"{i+1}. 제목: {title} | 저자: {author} | 유형: {book_type}"
                book_summaries.append(summary)
            
            books_text = "\n".join(book_summaries)
            
            prompt = f"""
다음은 '{search_keyword}' 키워드로 검색한 도서/자료 목록입니다.
각 자료가 검색 키워드와 얼마나 관련성이 있는지 평가해주세요.

검색 키워드: {search_keyword}

자료 목록:
{books_text}

평가 기준(점수 0~100점):
- 제목이나 내용이 검색 키워드와 직접적으로 관련이 있는가?
- 해당 도서를 읽었을 때 검색 키워드에 대한 이해가 깊어질 수 있는가?(가장 중요)
- 키워드의 의미나 주제와 연결점이 있는가?
- 너무 광범위하거나 관련성이 낮은 자료는 제외

다음 형식으로만 답변해주세요:
RELEVANT: [관련성이 80점 이상인 자료의 번호들을 쉼표로 구분] 
예: RELEVANT: 1,3,5

관련성이 높은 자료가 없다면:
RELEVANT: NONE
"""

            response = self.gemini_model.generate_content(prompt)
            response_text = response.text.strip()
            
            relevant_books = []
            if "RELEVANT:" in response_text:
                relevant_part = response_text.split("RELEVANT:")[1].strip()
                
                if relevant_part.upper() == "NONE":
                    print(f"🚫 Gemini 검증: '{search_keyword}' 관련 자료 없음")
                    return []
                
                try:
                    relevant_numbers = [int(num.strip()) for num in relevant_part.split(',') if num.strip().isdigit()]
                    
                    for num in relevant_numbers:
                        if 1 <= num <= len(books):
                            relevant_books.append(books[num-1])
                    
                    print(f"✅ Gemini 검증: {len(books)}개 중 {len(relevant_books)}개 자료가 관련성 높음")
                    
                except ValueError:
                    print(f"⚠️ Gemini 응답 파싱 실패, 모든 자료 제외")
                    return []
            else:
                print(f"⚠️ Gemini 응답 형식 오류, 모든 자료 제외")
                return []
                
            return relevant_books
            
        except Exception as e:
            print(f"❌ Gemini 검증 중 오류: {str(e)}")
            return []
    
    def search_books_by_keyword(self, original_keyword, search_keyword, max_results=3):
        """특정 키워드로 도서 검색"""
        try:
            encoded_keyword = urllib.parse.quote(search_keyword)
            
            url = (f"{self.base_url}?key={self.api_key}&apiType=xml"
                  f"&srchTarget=total&kwd={encoded_keyword}"
                  f"&pageSize={max_results * 4}&pageNum=1&sort=ipub_year,order=desc")
            
            print(f"🔍 '{search_keyword}' 검색 중... (원래 키워드: '{original_keyword}')")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                books = self.parse_search_results(response.text, original_keyword, search_keyword)
                
                # 필터링 및 검증 과정
                filtered_books = self.filter_by_material_type(books)
                unique_books = self.remove_duplicates(filtered_books)
                verified_books = self.verify_relevance_with_gemini(unique_books, search_keyword)
                final_books = verified_books[:max_results]
                
                if final_books:
                    print(f"📚 '{search_keyword}': {len(final_books)}개 자료 최종 선정")
                else:
                    print(f"📭 '{search_keyword}': 관련성 검증 후 최종 자료 없음")
                    
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
            total_match = re.search(r'<total>(\d+)</total>', xml_text)
            total_count = int(total_match.group(1)) if total_match else 0
            
            item_pattern = r'<item>(.*?)</item>'
            for i, item_match in enumerate(re.finditer(item_pattern, xml_text, re.DOTALL), 1):
                if i > 20:
                    break
                    
                item_text = item_match.group(1)
                book = self.extract_book_info(item_text)
                
                if book and book.get('title'):
                    book['keyword'] = original_keyword
                    book['search_keyword'] = search_keyword
                    book['total_results'] = total_count
                    
                    pub_year = book.get('pub_year')
                    if pub_year and pub_year.isdigit():
                        book['pub_year_int'] = int(pub_year)
                    else:
                        book['pub_year_int'] = 0
                    
                    books.append(book)
                    
        except Exception as e:
            print(f"XML 파싱 오류: {str(e)}")
        
        books.sort(key=lambda x: x.get('pub_year_int', 0), reverse=True)
        return books
    
    def extract_book_info(self, item_text):
        """개별 도서 항목에서 정보 추출"""
        book = {}
        
        patterns = {
            'title': r'<title_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</title_info>',
            'author': r'<author_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</author_info>',
            'publisher': r'<pub_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</pub_info>',
            'pub_year': r'<pub_year_info>(\d+)</pub_year_info>',
            'call_no': r'<call_no>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</call_no>',
            'type': r'<type_name>([^<]+)</type_name>',
            'isbn': r'<isbn>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</isbn>',
            'library_location': r'<place_info>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</place_info>',
            'library_name': r'<manage_name>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</manage_name>'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, item_text, re.DOTALL)
            if match:
                value = match.group(1) or match.group(2) if len(match.groups()) >= 2 else match.group(1)
                if value:
                    book[field] = value.strip()
        
        return book
    
    def process_all_keywords(self, keyword_pairs, max_books_per_keyword=2):
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
            
            # API 호출 간격 조절
            if i < len(keyword_pairs):
                time.sleep(0.5)
        
        return all_recommendations
    
    def save_to_firebase_source(self, recommendations, batch_id=None):
        """추천 도서 목록을 Firebase source 컬렉션에 키워드별로 계층 구조로 저장"""
        if not self.db:
            print("❌ Firebase 연결이 없습니다.")
            return False
        
        if not recommendations:
            print("💾 저장할 추천 도서가 없습니다.")
            return False
        
        try:
            if not batch_id:
                batch_id = datetime.now().strftime("%y%m%d")
            
            print(f"💾 Firebase source 컬렉션에 {len(recommendations)}개 도서를 키워드별로 저장 중...")
            
            batch = self.db.batch()
            source_ref = self.db.collection('source')
            
            # 날짜별 메타데이터 문서 생성
            date_doc_ref = source_ref.document(batch_id)
            
            # 키워드별로 도서 그룹핑
            keyword_groups = {}
            for book in recommendations:
                keyword = book.get('keyword', '기타')
                if keyword not in keyword_groups:
                    keyword_groups[keyword] = []
                keyword_groups[keyword].append(book)
            
            # 날짜 문서에 메타데이터 저장
            date_metadata = {
                'date': batch_id,
                'total_keywords': len(keyword_groups),
                'total_books': len(recommendations),
                'created_at': datetime.now(),
                'source': 'book_recommender',
                'status': 'completed',
                'keywords': list(keyword_groups.keys())
            }
            batch.set(date_doc_ref, date_metadata)
            
            # 키워드별로 서브컬렉션에 도서 저장
            for keyword, books in keyword_groups.items():
                print(f"📚 '{keyword}': {len(books)}개 도서 저장")
                
                # 키워드 문서 생성 (source/날짜/키워드)
                keyword_doc_ref = date_doc_ref.collection('keywords').document(keyword)
                keyword_metadata = {
                    'keyword': keyword,
                    'book_count': len(books),
                    'created_at': datetime.now(),
                    'date': batch_id
                }
                batch.set(keyword_doc_ref, keyword_metadata)
                
                # 도서별로 서브컬렉션에 저장 (source/날짜/키워드/books/도서ID)
                books_collection = keyword_doc_ref.collection('books')
                
                for i, book in enumerate(books):
                    book_doc_ref = books_collection.document(f"book_{i:03d}")
                    book_data = {
                        'book_id': f"book_{i:03d}",
                        'title': book.get('title', ''),
                        'author': book.get('author', ''),
                        'publisher': book.get('publisher', ''),
                        'pub_year': book.get('pub_year', ''),
                        'isbn': book.get('isbn', ''),
                        'call_no': book.get('call_no', ''),
                        'type': book.get('type', ''),
                        'library_name': book.get('library_name', ''),
                        'library_location': book.get('library_location', ''),
                        'keyword': book.get('keyword', ''),
                        'search_keyword': book.get('search_keyword', ''),
                        'created_at': datetime.now(),
                        'order': i,
                        'date': batch_id
                    }
                    batch.set(book_doc_ref, book_data)
            
            batch.commit()
            print(f"✅ {len(recommendations)}개 도서가 키워드별로 계층 구조로 저장됨")
            print(f"   📅 날짜: {batch_id}")
            print(f"   🏷️ 키워드: {len(keyword_groups)}개")
            for keyword, books in keyword_groups.items():
                print(f"      • {keyword}: {len(books)}권")
            
            return True
            
        except Exception as e:
            print(f"❌ Firebase 저장 실패: {str(e)}")
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
        
        print(f"\n📚 키워드별 추천 자료 수:")
        for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  • {keyword}: {count}개")
        
        # 상위 추천 자료 미리보기
        print(f"\n🔥 주요 추천 자료 (최신순 상위 5개):")
        sorted_recommendations = sorted(recommendations, 
                                      key=lambda x: x.get('pub_year_int', 0), 
                                      reverse=True)
        
        for i, book in enumerate(sorted_recommendations[:5], 1):
            title = book.get('title', '제목 없음')
            author = book.get('author', '저자 미상')
            keyword = book.get('keyword', '')
            pub_year = book.get('pub_year', '발행년도 미상')
            
            print(f"  {i}. [{keyword}] {title} ({pub_year})")
            print(f"     저자: {author}")

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="Firebase 연동 도서 추천 시스템")
    parser.add_argument("--date", "-d", help="특정 날짜의 트렌드 사용 (예: 250606)")
    parser.add_argument("--max_keywords", "-m", type=int, default=15, 
                        help="처리할 최대 키워드 수 (기본값: 15)")
    parser.add_argument("--max_books_per_keyword", type=int, default=2,
                        help="각 키워드당 검색할 최대 도서 수 (기본값: 2)")
    parser.add_argument("--gemini_api_key", "-g", default='AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs',
                        help="Gemini API 키 (필수)")
    parser.add_argument("--firebase_config", "-f", 
                        default='/home/yunho/csp2025/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                        help="Firebase 설정 파일 경로")
    
    args = parser.parse_args()

    print("📖 Firebase 연동 도서 추천 시스템")
    print("=" * 50)
    print("🔥 Firebase trend 컬렉션에서 데이터를 읽어와서 도서를 검색합니다.")
    print("💾 검색 결과는 Firebase source 컬렉션에 저장됩니다.")
    
    try:
        # Book Recommender 초기화
        recommender = FirebaseBookRecommender(
            gemini_api_key=args.gemini_api_key,
            firebase_config_path=args.firebase_config
        )
    except Exception as e:
        print(f"❌ 초기화 실패: {str(e)}")
        sys.exit(1)
    
    # Firebase에서 트렌드 데이터 로드
    trends = recommender.load_trends_from_firebase(args.date)
    
    if not trends:
        print("❌ 처리할 트렌드 데이터가 없습니다.")
        return
    
    # 키워드 쌍 추출
    keyword_pairs = recommender.extract_keywords_from_trends(trends, args.max_keywords)
    
    if not keyword_pairs:
        print("❌ 처리할 키워드가 없습니다.")
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
        # Firebase source 컬렉션에 저장
        batch_id = args.date if args.date else datetime.now().strftime("%y%m%d")
        firebase_success = recommender.save_to_firebase_source(recommendations, batch_id)
        
        if firebase_success:
            print(f"\n✅ 총 {len(recommendations)}개의 자료를 추천하고 Firebase에 저장했습니다!")
            print("🤖 모든 결과는 Gemini API로 관련성이 검증되었습니다.")
        else:
            print("❌ Firebase 저장에 실패했습니다.")
    else:
        print("❌ 추천할 자료를 찾지 못했습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ 프로그램이 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)