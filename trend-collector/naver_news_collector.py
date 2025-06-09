#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase 연동 네이버 뉴스 수집기
Firebase keywords 컬렉션에서 키워드를 읽어와서 네이버 뉴스 검색
"""

import urllib.request
import urllib.parse
import json
import pandas as pd
import time
import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import os
from typing import List, Dict, Optional

class NaverNewsCollectorFirebase:
    def __init__(self, client_id: str, client_secret: str, firebase_config_path: str = None):
        """
        Firebase 연동 네이버 뉴스 수집기 초기화
        
        Args:
            client_id: 네이버 API 클라이언트 ID
            client_secret: 네이버 API 클라이언트 시크릿
            firebase_config_path: Firebase 설정 파일 경로
        """
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Firebase 초기화
        self.init_firebase(firebase_config_path)
        
        print("✅ 네이버 뉴스 수집기 초기화 완료")
    
    def init_firebase(self, config_path: str):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                if config_path and os.path.exists(config_path):
                    cred = credentials.Certificate(config_path)
                    firebase_admin.initialize_app(cred)
                    print(f"✅ Firebase 서비스 계정으로 연결: {config_path}")
                else:
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
                    print("✅ Firebase 기본 인증으로 연결")
            
            self.db = firestore.client(database_id='csproject2025')
            print("✅ Firestore 연결 성공 - csproject2025 데이터베이스")
            
        except Exception as e:
            print(f"❌ Firebase 연결 실패: {str(e)}")
            self.db = None
    
    def load_keywords_from_firebase(self, date_str: str = None) -> List[str]:
        """
        Firebase keywords 컬렉션에서 키워드 로드
        
        Args:
            date_str: 특정 날짜 (YYMMDD 형식, None이면 오늘)
            
        Returns:
            키워드 리스트
        """
        if not self.db:
            print("❌ Firebase 연결이 없습니다.")
            return []
        
        try:
            if not date_str:
                date_str = datetime.datetime.now().strftime("%y%m%d")
            
            print(f"🔍 Firebase에서 키워드 로드 중... (날짜: {date_str})")
            
            # keywords/{date} 문서에서 키워드 로드
            doc_ref = self.db.collection('keywords').document(date_str)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                keywords = data.get('keywords', [])
                
                if keywords:
                    print(f"✅ {len(keywords)}개 키워드 로드 완료")
                    print(f"📊 데이터 소스: {data.get('data_source', 'unknown')}")
                    
                    # 메타데이터 정보 출력
                    metadata = data.get('metadata', {})
                    if metadata:
                        user_count = metadata.get('user_preferred_keywords', 0)
                        trend_count = metadata.get('trend_keywords', 0)
                        print(f"📈 구성: 사용자선호 {user_count}개, 트렌드 {trend_count}개")
                    
                    return keywords
                else:
                    print(f"⚠️ {date_str} 날짜에 키워드가 없습니다.")
                    return []
            else:
                print(f"❌ {date_str} 날짜의 키워드 데이터를 찾을 수 없습니다.")
                
                # 최근 날짜 데이터 찾기 시도
                return self._find_recent_keywords()
                
        except Exception as e:
            print(f"❌ Firebase 키워드 로드 실패: {str(e)}")
            return []
    
    def _find_recent_keywords(self, days_back: int = 7) -> List[str]:
        """최근 며칠 내의 키워드 데이터 찾기"""
        print(f"🔍 최근 {days_back}일 내 키워드 데이터 검색 중...")
        
        try:
            keywords_ref = self.db.collection('keywords')
            
            # 최근 문서들을 날짜 역순으로 조회
            docs = keywords_ref.order_by('collection_time', direction=firestore.Query.DESCENDING).limit(days_back).stream()
            
            for doc in docs:
                doc_data = doc.to_dict()
                keywords = doc_data.get('keywords', [])
                
                if keywords:
                    date_str = doc.id
                    print(f"✅ {date_str} 날짜의 키워드 {len(keywords)}개 발견")
                    return keywords
            
            print(f"❌ 최근 {days_back}일 내에 키워드 데이터가 없습니다.")
            return []
            
        except Exception as e:
            print(f"❌ 최근 키워드 검색 실패: {str(e)}")
            return []
    
    def search_news_for_keyword(self, keyword: str, max_articles: int = 5) -> List[Dict]:
        """
        특정 키워드로 네이버 뉴스 검색
        
        Args:
            keyword: 검색할 키워드
            max_articles: 최대 기사 수
            
        Returns:
            뉴스 기사 리스트
        """
        try:
            encoded_keyword = urllib.parse.quote(keyword)
            url = f"https://openapi.naver.com/v1/search/news?query={encoded_keyword}&display={max_articles}&start=1&sort=date"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", self.client_id)
            request.add_header("X-Naver-Client-Secret", self.client_secret)
            
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
                print(f"❌ '{keyword}' 검색 실패: HTTP {response.getcode()}")
                return []
                
        except Exception as e:
            print(f"❌ '{keyword}' 뉴스 검색 오류: {str(e)}")
            return []
    
    def collect_all_news(self, keywords: List[str], max_articles_per_keyword: int = 5) -> List[Dict]:
        """
        모든 키워드에 대해 뉴스 수집
        
        Args:
            keywords: 키워드 리스트
            max_articles_per_keyword: 키워드당 최대 기사 수
            
        Returns:
            전체 뉴스 기사 리스트
        """
        if not keywords:
            print("❌ 수집할 키워드가 없습니다.")
            return []
        
        print(f"🚀 {len(keywords)}개 키워드로 뉴스 수집 시작...")
        print(f"📰 키워드당 최대 {max_articles_per_keyword}개 기사")
        
        all_news = []
        
        for i, keyword in enumerate(keywords, 1):
            print(f"[{i}/{len(keywords)}] '{keyword}' 검색 중...")
            
            articles = self.search_news_for_keyword(keyword, max_articles_per_keyword)
            
            if articles:
                all_news.extend(articles)
                print(f"  ✅ {len(articles)}개 기사 수집")
            else:
                print(f"  ⚠️ 기사 없음")
            
            # API 제한 방지를 위한 딜레이
            if i < len(keywords):
                time.sleep(0.1)
        
        print(f"\n🎉 수집 완료: 총 {len(all_news)}개 기사")
        return all_news
    
    def save_news_to_firebase(self, news_data: List[Dict], date_str: str = None) -> bool:
        """
        수집된 뉴스를 Firebase에 저장
        
        Args:
            news_data: 뉴스 기사 리스트
            date_str: 저장할 날짜 (None이면 오늘)
            
        Returns:
            저장 성공 여부
        """
        if not self.db or not news_data:
            print("❌ Firebase 연결이 없거나 저장할 뉴스가 없습니다.")
            return False
        
        try:
            if not date_str:
                date_str = datetime.datetime.now().strftime("%y%m%d")
            
            print(f"💾 Firebase에 뉴스 데이터 저장 중... (날짜: {date_str})")
            
            # 키워드별로 그룹핑
            keyword_groups = {}
            for article in news_data:
                keyword = article['keyword']
                if keyword not in keyword_groups:
                    keyword_groups[keyword] = []
                keyword_groups[keyword].append(article)
            
            # news/{date} 문서에 저장
            doc_ref = self.db.collection('news').document(date_str)
            
            firebase_data = {
                'date': date_str,
                'collection_time': datetime.datetime.now(),
                'total_articles': len(news_data),
                'total_keywords': len(keyword_groups),
                'data_source': 'naver_news_api',
                'keyword_groups': keyword_groups
            }
            
            doc_ref.set(firebase_data)
            
            print(f"✅ Firebase 저장 완료:")
            print(f"   📅 날짜: {date_str}")
            print(f"   📰 총 기사: {len(news_data)}개")
            print(f"   🏷️ 키워드: {len(keyword_groups)}개")
            print(f"   📁 저장 경로: news/{date_str}")
            
            return True
            
        except Exception as e:
            print(f"❌ Firebase 저장 실패: {str(e)}")
            return False
    
    def save_news_to_csv(self, news_data: List[Dict], filename: str = None) -> bool:
        """
        뉴스 데이터를 CSV 파일로도 저장 (백업용)
        
        Args:
            news_data: 뉴스 기사 리스트
            filename: 파일명 (None이면 자동 생성)
            
        Returns:
            저장 성공 여부
        """
        if not news_data:
            print("❌ 저장할 뉴스 데이터가 없습니다.")
            return False
        
        try:
            if not filename:
                timestamp = datetime.datetime.now().strftime("%y%m%d")
                filename = f"news_{timestamp}.csv"
            
            df = pd.DataFrame(news_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            
            print(f"📄 CSV 백업 저장: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ CSV 저장 실패: {str(e)}")
            return False
    
    def get_keywords_summary(self, days: int = 7):
        """저장된 키워드 데이터 요약 조회"""
        if not self.db:
            print("❌ Firebase 연결이 없습니다.")
            return
        
        try:
            print(f"\n📊 최근 {days}일간 키워드 데이터 요약:")
            print("-" * 50)
            
            keywords_ref = self.db.collection('keywords')
            docs = keywords_ref.order_by('collection_time', direction=firestore.Query.DESCENDING).limit(days).stream()
            
            for doc in docs:
                doc_data = doc.to_dict()
                date_str = doc.id
                keywords = doc_data.get('keywords', [])
                source = doc_data.get('data_source', 'unknown')
                
                print(f"📅 {date_str}: {len(keywords)}개 키워드 ({source})")
                
                # 상위 5개 키워드 표시
                if keywords:
                    top_keywords = keywords[:5]
                    print(f"      상위 키워드: {', '.join(top_keywords)}")
                    if len(keywords) > 5:
                        print(f"      ... 외 {len(keywords) - 5}개")
            
        except Exception as e:
            print(f"❌ 키워드 요약 조회 실패: {str(e)}")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Firebase 연동 네이버 뉴스 수집기")
    parser.add_argument("--firebase_config", "-f",
                        default='../csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                        help="Firebase 설정 파일 경로")
    parser.add_argument("--date", "-d",
                        help="키워드를 가져올 날짜 (YYMMDD 형식, 기본값: 오늘)")
    parser.add_argument("--max_articles", "-a", type=int, default=5,
                        help="키워드당 최대 기사 수 (기본값: 5)")
    parser.add_argument("--save_csv", action="store_true",
                        help="CSV 파일로도 저장")
    parser.add_argument("--keywords_summary", "-s", action="store_true",
                        help="키워드 데이터 요약만 조회")
    
    args = parser.parse_args()
    
    print("🔥 Firebase 연동 네이버 뉴스 수집기")
    print("=" * 50)
    
    # 네이버 API 키 설정
    client_id = "RPUhkWY7UVq81hlMiHNL"
    client_secret = "u5HUugAYuv"
    
    # 수집기 초기화
    collector = NaverNewsCollectorFirebase(
        client_id=client_id,
        client_secret=client_secret,
        firebase_config_path=args.firebase_config
    )
    
    if args.keywords_summary:
        # 키워드 요약만 조회
        collector.get_keywords_summary()
        return
    
    # 키워드 로드
    keywords = collector.load_keywords_from_firebase(args.date)
    
    if not keywords:
        print("❌ 수집할 키워드를 찾을 수 없습니다.")
        print("💡 먼저 keyword_collector.py를 실행하여 키워드를 수집해주세요.")
        return
    
    # 날짜 설정
    date_str = args.date if args.date else datetime.datetime.now().strftime("%y%m%d")
    
    print(f"\n🎯 뉴스 수집 설정:")
    print(f"   📅 날짜: {date_str}")
    print(f"   🏷️ 키워드 수: {len(keywords)}개")
    print(f"   📰 키워드당 최대 기사: {args.max_articles}개")
    
    # 뉴스 수집
    all_news = collector.collect_all_news(keywords, args.max_articles)
    
    if all_news:
        # Firebase에 저장
        firebase_success = collector.save_news_to_firebase(all_news, date_str)
        
        # CSV 저장 (옵션)
        if args.save_csv:
            collector.save_news_to_csv(all_news, f"news_{date_str}.csv")
        
        if firebase_success:
            print(f"\n✅ 뉴스 수집 및 저장 완료!")
            print(f"📁 Firebase 경로: news/{date_str}")
            
            # 키워드별 통계
            keyword_stats = {}
            for article in all_news:
                keyword = article['keyword']
                keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1
            
            print(f"\n📊 키워드별 기사 수:")
            for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   {keyword}: {count}개")
                
        else:
            print(f"\n❌ Firebase 저장 실패")
    else:
        print(f"\n❌ 수집된 뉴스가 없습니다.")
    
    print(f"\n💡 다음 명령어로 키워드 현황을 확인할 수 있습니다:")
    print(f"   python {__file__} --keywords_summary")

if __name__ == "__main__":
    main()