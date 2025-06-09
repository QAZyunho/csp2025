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
        """Firebase trend 컬렉션에서 트렌드 데이터 로드 (오늘 날짜만)"""
        if not self.db:
            print("❌ Firebase 연결이 없습니다.")
            return []
        
        try:
            print("🔍 Firebase에서 오늘 날짜 트렌드 데이터 로드 중...")
            
            trends_ref = self.db.collection('trend')
            
            # 날짜가 지정되지 않으면 오늘 날짜 사용
            if not date_filter:
                date_filter = datetime.now().strftime("%y%m%d")
            
            print(f"📅 대상 날짜: {date_filter}")
            
            # 특정 날짜 문서만 조회
            doc_ref = trends_ref.document(date_filter)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                trends = data.get('trends', [])
                print(f"✅ {date_filter} 날짜의 트렌드 {len(trends)}개 로드")
                print(f"🎯 오늘 날짜 트렌드만 사용하여 정확성 향상")
                return trends
            else:
                print(f"❌ {date_filter} 날짜의 트렌드 데이터를 찾을 수 없습니다.")
                print("💡 trend_analyzer.py를 먼저 실행하여 트렌드를 생성해주세요.")
                return []
                
        except Exception as e:
            print(f"❌ Firebase 트렌드 로드 실패: {str(e)}")
            return []
    
    def extract_keywords_from_trends(self, trends, max_trends=None):
        """트렌드 데이터에서 트렌드별로 book_keywords 그룹핑"""
        trend_groups = []
        
        # max_trends가 지정되지 않으면 모든 트렌드 처리
        trends_to_process = trends[:max_trends] if max_trends else trends
        
        print(f"📊 {len(trends_to_process)}개 트렌드 처리 중...")
        
        for trend in trends_to_process:
            original_keyword = trend.get('keyword', '')
            book_keywords = trend.get('book_keywords', [])
            
            if original_keyword:
                if book_keywords and isinstance(book_keywords, list):
                    # 트렌드별로 그룹핑
                    trend_group = {
                        'trend_keyword': original_keyword,
                        'search_keywords': [kw.strip() for kw in book_keywords if kw and kw.strip()],
                        'summary': trend.get('summary', '')
                    }
                    trend_groups.append(trend_group)
                    print(f"  • {original_keyword}: {len(trend_group['search_keywords'])}개 검색 키워드")
                else:
                    # book_keywords가 없는 경우 원본 키워드 사용
                    trend_group = {
                        'trend_keyword': original_keyword,
                        'search_keywords': [original_keyword],
                        'summary': trend.get('summary', '')
                    }
                    trend_groups.append(trend_group)
                    print(f"  • {original_keyword}: 원본 키워드 사용")
        
        total_search_keywords = sum(len(group['search_keywords']) for group in trend_groups)
        print(f"🎯 총 {len(trend_groups)}개 트렌드, {total_search_keywords}개 검색 키워드")
        print(f"📚 예상 검색량: {total_search_keywords}개 키워드 × 10권 = {total_search_keywords * 10}권 후보")
        print(f"🎯 최종 결과: {len(trend_groups)}개 트렌드 × 5권 = 최대 {len(trend_groups) * 5}권")
        
        return trend_groups
    
    def filter_by_material_type(self, books):
        """원하는 자료유형으로 필터링 (도서 우선, 기타 자료 포함)"""
        # 도서 우선, 하지만 다른 유용한 자료도 포함
        priority_types = ['도서', '단행본']
        allowed_types = ['도서', '기사', '신문', '멀티미디어', '단행본', '연속간행물']
        
        high_priority_books = []  # 도서 우선
        other_books = []          # 기타 자료
        
        for book in books:
            book_type = book.get('type', '').lower()
            
            # 도서류는 최우선
            if any(ptype.lower() in book_type for ptype in priority_types):
                high_priority_books.append(book)
            # 기타 허용된 자료유형
            elif not book_type or any(atype.lower() in book_type for atype in allowed_types):
                other_books.append(book)
        
        # 도서 우선으로 결합하되, 적절한 비율 유지
        total_books = len(high_priority_books) + len(other_books)
        if total_books > 0:
            print(f"📊 자료 유형 분포: 도서 {len(high_priority_books)}권, 기타 {len(other_books)}권")
        
        # 도서를 우선하되, 전체적인 다양성도 고려
        filtered_books = high_priority_books + other_books
        
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
    
    def get_trend_context_from_firebase(self, original_keyword: str, date_filter: str = None) -> str:
        """Firebase trend 컬렉션에서 해당 키워드의 기사 분석 정보 가져오기"""
        if not self.db:
            return ""
        
        try:
            if not date_filter:
                date_filter = datetime.now().strftime("%y%m%d")
            
            # trend/{date} 문서에서 해당 키워드 정보 찾기
            doc_ref = self.db.collection('trend').document(date_filter)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                trends = data.get('trends', [])
                
                # 해당 키워드의 트렌드 정보 찾기
                for trend in trends:
                    if trend.get('keyword') == original_keyword:
                        summary = trend.get('summary', '')
                        article_count = trend.get('article_count', 0)
                        return f"[기사 분석 정보] {original_keyword}에 대한 최신 뉴스 분석: {summary} (관련 기사 {article_count}개)"
                
                print(f"⚠️ '{original_keyword}' 키워드의 트렌드 분석 정보를 찾지 못했습니다.")
                return ""
            else:
                print(f"⚠️ {date_filter} 날짜의 트렌드 데이터가 없습니다.")
                return ""
                
        except Exception as e:
            print(f"❌ 트렌드 컨텍스트 로드 실패: {str(e)}")
            return ""

    def select_top_books_with_gemini(self, books: List[Dict], search_keyword: str, top_n: int = 5) -> List[Dict]:
        """Gemini API를 사용하여 검색 결과에서 가장 관련성 높은 상위 N권 선택"""
        if not books:
            return books
        
        if len(books) <= top_n:
            print(f"📚 전체 도서 수({len(books)})가 요청 수({top_n}) 이하이므로 모든 도서 반환")
            return books
        
        try:
            # 원본 키워드로 트렌드 컨텍스트 가져오기
            original_keyword = books[0].get('keyword', search_keyword) if books else search_keyword
            trend_context = self.get_trend_context_from_firebase(original_keyword)
            
            print(f"🤖 Gemini로 '{search_keyword}' 주제에 가장 적합한 상위 {top_n}권 선택 중... (총 {len(books)}권에서)")
            if trend_context:
                print(f"📰 기사 분석 정보 활용하여 더 정확한 추천")
            
            book_summaries = []
            for i, book in enumerate(books):
                title = book.get('title', '제목없음')
                author = book.get('author', '저자미상')
                publisher = book.get('publisher', '출판사미상')
                pub_year = book.get('pub_year', '발행년도미상')
                book_type = book.get('type', '자료유형미상')
                
                summary = f"{i+1}. 제목: {title}\n   저자: {author}\n   출판사: {publisher}\n   발행년도: {pub_year}\n   자료유형: {book_type}"
                book_summaries.append(summary)
            
            books_text = "\n\n".join(book_summaries)
            
            # 트렌드 컨텍스트가 있는 경우 포함
            context_section = ""
            if trend_context:
                context_section = f"\n\n🔥 최신 뉴스 트렌드 분석:\n{trend_context}\n"
            
            prompt = f"""
다음은 '{search_keyword}' 키워드로 검색한 도서/자료 목록입니다.
이 중에서 해당 키워드와 가장 관련성이 높고 유용한 상위 {top_n}권을 선택해주세요.
{context_section}
검색 키워드: {search_keyword}

자료 목록:
{books_text}

선택 기준 (우선순위대로):
1. **도서 우선**: 보고서, 논문, 학위논문보다는 일반 도서(단행본)를 강력히 우선 선택
2. **트렌드 연관성**: 위 뉴스 분석 내용과 관련이 높은 도서 우선
3. **직접적 관련성**: 제목이나 내용이 '{search_keyword}' 키워드와 직접적으로 관련
4. **실용적 가치**: 해당 주제에 대한 이해나 학습에 실질적으로 도움이 되는 자료
5. **최신성**: 최근 발행된 자료 우선 (단, 고전적 가치가 있는 경우 예외)
6. **접근성**: 일반 독자가 읽기 쉬운 도서 우선

⚠️ 중요 지침:
- 학술논문, 학위논문, 연구보고서는 가능한 한 제외
- '도서', '단행본' 유형의 자료를 최우선으로 선택
- 위 뉴스 분석과 관련성이 높은 도서를 우선 고려
- 너무 전문적이거나 접근하기 어려운 자료는 후순위

가장 적합한 상위 {top_n}권의 번호만 선택해서 다음 형식으로 답변해주세요:
SELECTED: [선택된 자료의 번호들을 관련성 순서대로 쉼표로 구분]
예: SELECTED: 3,1,7,12,5

적합한 도서가 {top_n}권 미만이라면 있는 만큼만 선택하세요.
관련성이 높은 도서가 전혀 없다면: SELECTED: NONE
"""

            response = self.gemini_model.generate_content(prompt)
            response_text = response.text.strip()
            
            selected_books = []
            if "SELECTED:" in response_text:
                selected_part = response_text.split("SELECTED:")[1].strip()
                
                if selected_part.upper() == "NONE":
                    print(f"🚫 Gemini 선택: '{search_keyword}' 관련 적합한 자료 없음")
                    return []
                
                try:
                    selected_numbers = [int(num.strip()) for num in selected_part.split(',') if num.strip().isdigit()]
                    
                    for num in selected_numbers:
                        if 1 <= num <= len(books):
                            selected_books.append(books[num-1])
                    
                    # 선택된 도서의 유형 분석
                    book_types = [book.get('type', '').lower() for book in selected_books]
                    book_count = sum(1 for t in book_types if '도서' in t or '단행본' in t)
                    
                    print(f"✅ Gemini 선택: {len(books)}권 중 상위 {len(selected_books)}권 선정")
                    if book_count > 0:
                        print(f"📚 도서 {book_count}권, 기타 자료 {len(selected_books) - book_count}권")
                    
                    # 선택된 도서들을 관련성 순서대로 정렬된 상태로 반환
                    return selected_books
                    
                except ValueError:
                    print(f"⚠️ Gemini 응답 파싱 실패, 도서 우선 + 발행년도 기준으로 상위 {top_n}권 선택")
                    return self._fallback_book_selection(books, top_n)
            else:
                print(f"⚠️ Gemini 응답 형식 오류, 도서 우선 + 발행년도 기준으로 상위 {top_n}권 선택")
                return self._fallback_book_selection(books, top_n)
                
        except Exception as e:
            print(f"❌ Gemini 선택 중 오류: {str(e)}")
            print(f"⚠️ 도서 우선 + 발행년도 기준으로 상위 {top_n}권 반환")
            return self._fallback_book_selection(books, top_n)
    
    def _fallback_book_selection(self, books: List[Dict], top_n: int) -> List[Dict]:
        """폴백: 도서 우선 + 최신순 선택"""
        # 1차: 도서 유형 우선 선별
        book_type_books = []
        other_books = []
        
        for book in books:
            book_type = book.get('type', '').lower()
            if '도서' in book_type or '단행본' in book_type:
                book_type_books.append(book)
            else:
                other_books.append(book)
        
        # 2차: 각각 발행년도순 정렬
        book_type_books.sort(key=lambda x: x.get('pub_year_int', 0), reverse=True)
        other_books.sort(key=lambda x: x.get('pub_year_int', 0), reverse=True)
        
        # 3차: 도서 우선으로 결합
        final_selection = book_type_books + other_books
        
        return final_selection[:top_n]
    
    def search_books_for_single_keyword(self, search_keyword, original_keyword, target_count=10):
        """단일 키워드로 도서 검색 (Gemini 선택 없이 원시 결과만 반환)"""
        try:
            encoded_keyword = urllib.parse.quote(search_keyword)
            
            url = (f"{self.base_url}?key={self.api_key}&apiType=xml"
                  f"&srchTarget=total&kwd={encoded_keyword}"
                  f"&pageSize={target_count * 2}&pageNum=1&sort=ipub_year,order=desc")
            
            print(f"      🔍 '{search_keyword}' 검색 중...")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                all_books = self.parse_search_results(response.text, original_keyword, search_keyword)
                
                # 필터링 과정
                filtered_books = self.filter_by_material_type(all_books)
                unique_books = self.remove_duplicates(filtered_books)
                
                # 상위 target_count개만 반환
                result_books = unique_books[:target_count]
                print(f"      📚 '{search_keyword}': {len(result_books)}권 수집")
                
                return result_books
            else:
                print(f"      ❌ '{search_keyword}' 검색 실패: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"      ❌ '{search_keyword}' 검색 중 오류: {str(e)}")
            return []

    def search_books_for_trend_group(self, trend_group, books_per_keyword=10, final_count=5):
        """하나의 트렌드 그룹에 대해 모든 키워드로 검색 후 최종 선별"""
        trend_keyword = trend_group['trend_keyword']
        search_keywords = trend_group['search_keywords']
        
        print(f"🎯 트렌드 '{trend_keyword}' 처리 중...")
        print(f"   📝 검색 키워드 {len(search_keywords)}개: {', '.join(search_keywords)}")
        
        all_candidate_books = []
        
        # 각 검색 키워드로 도서 수집
        for search_keyword in search_keywords:
            books = self.search_books_for_single_keyword(search_keyword, trend_keyword, books_per_keyword)
            all_candidate_books.extend(books)
        
        # 중복 제거
        unique_candidates = self.remove_duplicates(all_candidate_books)
        
        print(f"   📊 수집 결과: 총 {len(all_candidate_books)}권 → 중복 제거 후 {len(unique_candidates)}권")
        
        if not unique_candidates:
            print(f"   ❌ '{trend_keyword}': 수집된 도서가 없습니다.")
            return []
        
        # Gemini로 최종 상위 N권 선택
        if len(unique_candidates) <= final_count:
            print(f"   📚 전체 {len(unique_candidates)}권이 {final_count}권 이하이므로 모두 선택")
            final_books = unique_candidates
        else:
            print(f"   🤖 Gemini로 {len(unique_candidates)}권 중 상위 {final_count}권 선택...")
            final_books = self.select_top_books_with_gemini(unique_candidates, trend_keyword, final_count)
        
        if final_books:
            print(f"   ✅ '{trend_keyword}': 최종 {len(final_books)}권 선정 완료")
            
            # 선정된 도서 목록 출력
            trend_context = self.get_trend_context_from_firebase(trend_keyword)
            if trend_context:
                print(f"   📰 관련 뉴스: {trend_context[:80]}...")
            
            print("   📋 선정된 도서:")
            for i, book in enumerate(final_books, 1):
                title = book.get('title', '제목없음')
                author = book.get('author', '저자미상')
                pub_year = book.get('pub_year', '미상')
                book_type = book.get('type', '미상')
                print(f"      {i}. {title} ({pub_year}) - {author}")
                print(f"         유형: {book_type}")
        else:
            print(f"   📭 '{trend_keyword}': Gemini 선택 후 최종 자료 없음")
        
        return final_books
    
    def parse_search_results(self, xml_text, original_keyword, search_keyword):
        """XML 검색 결과를 파싱하여 도서 정보 추출"""
        books = []
        
        try:
            total_match = re.search(r'<total>(\d+)</total>', xml_text)
            total_count = int(total_match.group(1)) if total_match else 0
            
            item_pattern = r'<item>(.*?)</item>'
            for i, item_match in enumerate(re.finditer(item_pattern, xml_text, re.DOTALL), 1):
                if i > 50:  # 최대 50개까지 파싱
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
    
    def process_all_trend_groups(self, trend_groups, books_per_keyword=10, final_books_per_trend=5):
        """모든 트렌드 그룹에 대해 도서 검색 수행"""
        all_recommendations = []
        
        total_trends = len(trend_groups)
        total_search_keywords = sum(len(group['search_keywords']) for group in trend_groups)
        
        print(f"\n🚀 {total_trends}개 트렌드 그룹으로 도서 검색을 시작합니다...")
        print(f"   📊 총 검색 키워드: {total_search_keywords}개")
        print(f"   📚 각 키워드당 {books_per_keyword}권 검색")
        print(f"   🎯 각 트렌드당 최종 {final_books_per_trend}권 선별")
        print(f"   🎯 예상 최대 결과: {total_trends * final_books_per_trend}권\n")
        
        for i, trend_group in enumerate(trend_groups, 1):
            print(f"\n[{i:2d}/{total_trends}] ", end="")
            
            books = self.search_books_for_trend_group(
                trend_group, 
                books_per_keyword, 
                final_books_per_trend
            )
            
            if books:
                all_recommendations.extend(books)
                trend_keyword = trend_group['trend_keyword']
                print(f"✅ '{trend_keyword}': {len(books)}권 최종 추가")
            else:
                trend_keyword = trend_group['trend_keyword']
                print(f"⚠️ '{trend_keyword}': 추천 도서를 찾지 못했습니다.")
            
            # API 안정성을 위한 대기
            if i < total_trends:
                time.sleep(1)  # 트렌드별 처리간 간격
                
            # 중간 저장 (10개 트렌드마다)
            if i % 10 == 0:
                print(f"\n💾 중간 진행상황: {len(all_recommendations)}권 수집됨 ({i}/{total_trends} 트렌드 완료)")
        
        print(f"\n🎉 검색 완료! 총 {len(all_recommendations)}권의 도서가 선별되었습니다.")
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
                'source': 'book_recommender_v2',
                'status': 'completed',
                'keywords': list(keyword_groups.keys()),
                'selection_method': 'gemini_top_selection'
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
                    'date': batch_id,
                    'selection_method': 'gemini_trend_aware_curated',
                    'book_priority': True
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
                        'date': batch_id,
                        'selection_rank': i + 1,  # Gemini가 선택한 순위
                        'ai_selected': True,
                        'trend_aware': True,      # 트렌드 기반 선택
                        'book_priority': True     # 도서 우선 선택
                    }
                    batch.set(book_doc_ref, book_data)
            
            batch.commit()
            print(f"✅ {len(recommendations)}개 도서가 키워드별로 계층 구조로 저장됨")
            print(f"   📅 날짜: {batch_id}")
            print(f"   🏷️ 키워드: {len(keyword_groups)}개")
            print(f"   🤖 AI 큐레이션: Gemini로 선별된 고품질 도서 (트렌드 기반)")
            print(f"   📚 도서 우선: 학술자료보다 일반도서 우선 선택")
            for keyword, books in keyword_groups.items():
                book_count = sum(1 for book in books if '도서' in book.get('type', '').lower() or '단행본' in book.get('type', '').lower())
                print(f"      • {keyword}: {len(books)}권 (도서 {book_count}권)")
            
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
        print(f"총 추천 도서: {len(recommendations)}권 (🤖 Gemini AI 트렌드 기반 큐레이션)")
        
        # 도서 vs 기타 자료 통계
        book_types = [book.get('type', '').lower() for book in recommendations]
        book_count = sum(1 for t in book_types if '도서' in t or '단행본' in t)
        other_count = len(recommendations) - book_count
        
        print(f"📚 자료 구성: 도서 {book_count}권, 기타 자료 {other_count}권")
        
        # 키워드별 통계
        keyword_stats = {}
        for book in recommendations:
            keyword = book['keyword']
            keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1
        
        print(f"\n📚 키워드별 추천 자료 수:")
        for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  • {keyword}: {count}개")
        
        # 상위 추천 자료 미리보기
        print(f"\n🔥 주요 추천 자료 (최신순 상위 10개):")
        sorted_recommendations = sorted(recommendations, 
                                      key=lambda x: x.get('pub_year_int', 0), 
                                      reverse=True)
        
        for i, book in enumerate(sorted_recommendations[:10], 1):
            title = book.get('title', '제목 없음')
            author = book.get('author', '저자 미상')
            keyword = book.get('keyword', '')
            pub_year = book.get('pub_year', '발행년도 미상')
            
            print(f"  {i:2d}. [{keyword}] {title} ({pub_year})")
            print(f"      저자: {author}")

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="Firebase 연동 도서 추천 시스템 v3.0 - 트렌드 기반 Gemini AI 큐레이션")
    parser.add_argument("--date", "-d", help="특정 날짜의 트렌드 사용 (예: 250606)")
    parser.add_argument("--max_trends", "-m", type=int, default=None, 
                        help="처리할 최대 트렌드 수 (기본값: 모든 트렌드)")
    parser.add_argument("--books_per_keyword", type=int, default=10,
                        help="각 키워드당 검색할 도서 수 (기본값: 10)")
    parser.add_argument("--final_books_per_trend", type=int, default=5,
                        help="각 트렌드당 Gemini가 선택할 최종 도서 수 (기본값: 5)")
    parser.add_argument("--gemini_api_key", "-g", default='AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs',
                        help="Gemini API 키 (필수)")
    parser.add_argument("--firebase_config", "-f", 
                        default='/home/yunho/csp2025/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                        help="Firebase 설정 파일 경로")
    
    args = parser.parse_args()

    print("📖 Firebase 연동 도서 추천 시스템 v3.0")
    print("=" * 50)
    print("🔥 Firebase trend 컬렉션에서 데이터를 읽어와서 도서를 검색합니다.")
    print("🤖 Gemini AI가 각 주제별로 가장 적합한 상위 도서를 선별합니다.")
    print("📰 최신 뉴스 트렌드 분석 정보를 활용하여 더 정확한 추천을 제공합니다.")
    print("📚 학술자료보다 일반 도서를 우선적으로 추천합니다.")
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
    
    # 키워드 그룹 추출 (트렌드별로 그룹핑)
    trend_groups = recommender.extract_keywords_from_trends(trends, args.max_trends)
    
    if not trend_groups:
        print("❌ 처리할 트렌드 그룹이 없습니다.")
        return
    
    print(f"🎯 처리할 트렌드 그룹 ({len(trend_groups)}개):")
    for i, group in enumerate(trend_groups[:5]):  # 상위 5개만 미리보기
        trend_keyword = group['trend_keyword']
        search_keywords = group['search_keywords']
        print(f"   {i+1:2d}. {trend_keyword}")
        print(f"       검색키워드: {', '.join(search_keywords)}")
    if len(trend_groups) > 5:
        print(f"   ... 외 {len(trend_groups) - 5}개 트렌드")
    
    total_search_keywords = sum(len(group['search_keywords']) for group in trend_groups)
    print(f"\n📚 검색 전략:")
    print(f"   • 오늘 날짜 트렌드만 사용 (정확성 향상)")
    print(f"   • 총 트렌드: {len(trend_groups)}개")
    print(f"   • 총 검색 키워드: {total_search_keywords}개")
    print(f"   • 각 키워드당 {args.books_per_keyword}권 검색")
    print(f"   • 트렌드별로 최대 {len(trend_groups[0]['search_keywords']) * args.books_per_keyword if trend_groups else 0}권 후보 수집")
    print(f"   • 뉴스 트렌드 분석 정보 활용하여 관련성 향상")
    print(f"   • 일반 도서 우선 선택 (학술자료 < 일반도서)")
    print(f"   • 각 트렌드당 Gemini AI로 상위 {args.final_books_per_trend}권 선별")
    print(f"   • 총 예상 결과: 최대 {len(trend_groups) * args.final_books_per_trend}권")
    
    # 모든 트렌드 그룹에 대해 도서 검색
    recommendations = recommender.process_all_trend_groups(
        trend_groups, 
        args.books_per_keyword, 
        args.final_books_per_trend
    )
    
    # 결과 요약 출력
    recommender.print_summary(recommendations)
    
    if recommendations:
        # Firebase source 컬렉션에 저장
        batch_id = args.date if args.date else datetime.now().strftime("%y%m%d")
        firebase_success = recommender.save_to_firebase_source(recommendations, batch_id)
        
        if firebase_success:
            print(f"\n✅ 총 {len(recommendations)}개의 고품질 자료를 추천하고 Firebase에 저장했습니다!")
            print("🤖 모든 결과는 Gemini AI로 선별된 최고 품질의 도서입니다.")
            print("📰 최신 뉴스 트렌드 분석을 기반으로 한 정확한 추천입니다.")
            print("📚 일반 독자가 접근하기 쉬운 도서를 우선적으로 선별했습니다.")
            print(f"🎯 트렌드당 평균 {len(recommendations) / len(set([r['keyword'] for r in recommendations])):.1f}권 선정")
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