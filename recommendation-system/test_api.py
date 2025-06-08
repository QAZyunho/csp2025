#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
추천 시스템 API 테스트 스크립트
"""

import requests
import json
import time
from datetime import datetime

class RecommendationAPITester:
    """추천 API 테스터"""
    
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def test_health(self):
        """서비스 상태 확인"""
        print("🔍 서비스 상태 확인...")
        try:
            response = self.session.get(f"{self.base_url}/api/health")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ 서비스 정상 (도서: {data.get('books_loaded', 0)}권)")
                return True
            else:
                print(f"   ❌ 서비스 오류: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 연결 실패: {str(e)}")
            return False
    
    def test_books_list(self):
        """도서 목록 조회 테스트"""
        print("\n📚 도서 목록 조회 테스트...")
        try:
            response = self.session.get(f"{self.base_url}/api/books?page=1&size=5")
            if response.status_code == 200:
                data = response.json()
                books = data.get('books', [])
                pagination = data.get('pagination', {})
                
                print(f"   ✅ 총 {pagination.get('total_books', 0)}권 도서")
                print(f"   📖 조회된 도서 {len(books)}권:")
                
                for i, book in enumerate(books[:3], 1):
                    print(f"      {i}. {book['title']} - {book['author']} ({book['keyword']})")
                
                return books[0] if books else None
            else:
                print(f"   ❌ 조회 실패: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            return None
    
    def test_create_user(self):
        """사용자 생성 테스트"""
        print("\n👤 테스트 사용자 생성...")
        
        test_user = {
            "user_id": f"test_user_{int(time.time())}",
            "name": "API 테스트 사용자",
            "preferred_keywords": ["인공지능", "소설"],
            "preferred_types": ["도서", "단행본"],
            "age_group": "30대",
            "reading_frequency": "주 2-3회"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/users",
                json=test_user,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 201:
                print(f"   ✅ 사용자 생성 성공: {test_user['user_id']}")
                return test_user['user_id']
            else:
                print(f"   ❌ 생성 실패: HTTP {response.status_code}")
                print(f"      응답: {response.text}")
                return None
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            return None
    
    def test_recommendations(self, user_id):
        """개인화 추천 테스트"""
        print(f"\n🎯 '{user_id}' 사용자 추천 테스트...")
        try:
            response = self.session.get(f"{self.base_url}/api/recommendations/{user_id}?top_k=5")
            
            if response.status_code == 200:
                data = response.json()
                personalized = data.get('recommendations', {}).get('personalized', {})
                books = personalized.get('books', [])
                
                print(f"   ✅ {len(books)}개 도서 추천")
                print(f"   📚 추천 도서:")
                
                for i, book in enumerate(books[:3], 1):
                    print(f"      {i}. {book['title']} (점수: {book['score']:.3f})")
                    print(f"         이유: {book['recommendation_reason']}")
                
                return books[0] if books else None
            else:
                print(f"   ❌ 추천 실패: HTTP {response.status_code}")
                print(f"      응답: {response.text}")
                return None
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            return None
    
    def test_trending(self):
        """트렌딩 도서 테스트"""
        print("\n🔥 트렌딩 도서 테스트...")
        try:
            response = self.session.get(f"{self.base_url}/api/trending?limit=3")
            
            if response.status_code == 200:
                data = response.json()
                trending_books = data.get('trending_books', [])
                
                print(f"   ✅ {len(trending_books)}개 트렌딩 도서")
                
                for i, book in enumerate(trending_books, 1):
                    print(f"      {i}. {book['title']} - {book['author']}")
                    print(f"         키워드: {book['keyword']} (점수: {book['score']:.3f})")
                
                return True
            else:
                print(f"   ❌ 조회 실패: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            return False
    
    def test_feedback(self, user_id, book):
        """피드백 제출 테스트"""
        if not book:
            print("\n📝 피드백 테스트 - 도서 정보 없음으로 스킵")
            return False
            
        print(f"\n📝 '{book['title']}' 도서 피드백 테스트...")
        
        feedback_data = {
            "user_id": user_id,
            "book_id": book['doc_id'],
            "rating": 4,
            "feedback_text": "API 테스트로 제출한 피드백입니다."
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/feedback",
                json=feedback_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print("   ✅ 피드백 제출 성공")
                return True
            else:
                print(f"   ❌ 제출 실패: HTTP {response.status_code}")
                print(f"      응답: {response.text}")
                return False
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            return False
    
    def test_analytics(self):
        """분석 데이터 테스트"""
        print("\n📊 분석 데이터 테스트...")
        try:
            response = self.session.get(f"{self.base_url}/api/analytics")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ 총 피드백: {data.get('total_feedback', 0)}개")
                print(f"   ⭐ 평균 평점: {data.get('average_rating', 0):.2f}")
                
                keyword_performance = data.get('keyword_performance', {})
                if keyword_performance:
                    print("   📈 키워드별 성과 (상위 3개):")
                    sorted_keywords = sorted(
                        keyword_performance.items(),
                        key=lambda x: x[1].get('average_rating', 0),
                        reverse=True
                    )
                    
                    for keyword, stats in sorted_keywords[:3]:
                        avg_rating = stats.get('average_rating', 0)
                        count = stats.get('count', 0)
                        print(f"      • {keyword}: {avg_rating:.2f}점 ({count}개)")
                
                return True
            else:
                print(f"   ❌ 조회 실패: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            return False
    
    def run_full_test(self):
        """전체 테스트 실행"""
        print("🧪 추천 시스템 API 전체 테스트")
        print("=" * 50)
        
        test_results = []
        
        # 1. 서비스 상태 확인
        health_ok = self.test_health()
        test_results.append(("서비스 상태", health_ok))
        
        if not health_ok:
            print("\n❌ 서비스가 실행되지 않았습니다!")
            print("💡 다음 명령어로 서버를 먼저 실행해주세요:")
            print("   python recommendation_api_server.py")
            return
        
        # 2. 도서 목록 조회
        sample_book = self.test_books_list()
        test_results.append(("도서 목록 조회", sample_book is not None))
        
        # 3. 사용자 생성
        test_user_id = self.test_create_user()
        test_results.append(("사용자 생성", test_user_id is not None))
        
        # 4. 개인화 추천
        recommended_book = None
        if test_user_id:
            recommended_book = self.test_recommendations(test_user_id)
            test_results.append(("개인화 추천", recommended_book is not None))
        
        # 5. 트렌딩 도서
        trending_ok = self.test_trending()
        test_results.append(("트렌딩 도서", trending_ok))
        
        # 6. 피드백 제출
        feedback_ok = False
        if test_user_id and (recommended_book or sample_book):
            book_for_feedback = recommended_book or sample_book
            feedback_ok = self.test_feedback(test_user_id, book_for_feedback)
        test_results.append(("피드백 제출", feedback_ok))
        
        # 7. 분석 데이터
        analytics_ok = self.test_analytics()
        test_results.append(("분석 데이터", analytics_ok))
        
        # 테스트 결과 요약
        print("\n📋 테스트 결과 요약")
        print("=" * 50)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ 통과" if result else "❌ 실패"
            print(f"   {test_name:<15}: {status}")
            if result:
                passed += 1
        
        print(f"\n🎯 전체 결과: {passed}/{total} 테스트 통과")
        
        if passed == total:
            print("🎉 모든 테스트가 성공적으로 완료되었습니다!")
            print("\n📖 다음 단계:")
            print("   1. 프론트엔드 애플리케이션 개발")
            print("   2. 실제 사용자 데이터로 테스트")
            print("   3. 성능 최적화 및 배포")
        else:
            print("⚠️  일부 테스트가 실패했습니다. 로그를 확인해주세요.")

def main():
    """메인 실행 함수"""
    print("🧪 추천 시스템 API 테스터")
    print("=" * 30)
    
    # API 서버 URL 설정
    api_url = input("API 서버 URL (기본값: http://localhost:5000): ").strip()
    if not api_url:
        api_url = "http://localhost:5000"
    
    # 테스터 실행
    tester = RecommendationAPITester(api_url)
    tester.run_full_test()

if __name__ == "__main__":
    main()