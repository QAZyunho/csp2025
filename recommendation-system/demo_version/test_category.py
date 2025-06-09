#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
카테고리 기반 추천 시스템 테스트
"""

import requests
import json

def test_category_recommendation():
    """카테고리 추천 테스트"""
    api_base_url = "http://localhost:5001"
    
    # 테스트 사용자 생성
    test_user = {
        "user_id": "test_user_001",
        "name": "테스트 사용자",
        "preferred_keywords": ["인공지능", "소설"]
    }
    
    print("🧪 카테고리 추천 시스템 테스트")
    print("=" * 40)
    
    # 1. 사용자 생성
    print("1. 테스트 사용자 생성...")
    try:
        response = requests.post(f"{api_base_url}/api/users", json=test_user)
        if response.status_code in [200, 201]:
            print(f"✅ 사용자 '{test_user['user_id']}' 생성 완료")
        else:
            print(f"⚠️  사용자 생성 응답: {response.status_code}")
    except Exception as e:
        print(f"❌ 사용자 생성 실패: {e}")
        return
    
    # 2. 카테고리 추천 조회
    print("\n2. 카테고리 추천 조회...")
    try:
        response = requests.get(f"{api_base_url}/api/recommendations/{test_user['user_id']}?books_per_category=5")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ 추천 카테고리: '{data['category']}'")
            print(f"📚 추천 도서 {data['books_count']}권:")
            
            for i, book in enumerate(data['books'], 1):
                print(f"\n   {i}. {book['title']}")
                print(f"      📖 저자: {book['author']}")
                print(f"      🏢 출판사: {book['publisher']} ({book['pub_year']})")
                
                # 소장 위치 정보 표시
                if book.get('library_name'):
                    print(f"      📍 소장처: {book['library_name']}")
                if book.get('library_location'):
                    print(f"      🗺️  위치: {book['library_location']}")
                if book.get('call_no'):
                    print(f"      📋 청구기호: {book['call_no']}")
                
                print(f"      ⭐ 점수: {book['score']:.2f}")
            
            print(f"\n📊 카테고리 '{data['category']}' 전체 도서: {data['total_books_in_category']}권")
            
        else:
            print(f"❌ 추천 조회 실패: HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 추천 조회 오류: {e}")
    
    # 3. 피드백 테스트
    print("\n3. 피드백 제출...")
    try:
        feedback_data = {
            "user_id": test_user['user_id'],
            "book_id": "test_book_001",
            "rating": 5
        }
        
        response = requests.post(f"{api_base_url}/api/feedback", json=feedback_data)
        
        if response.status_code == 200:
            print("✅ 피드백 제출 완료")
        else:
            print(f"⚠️  피드백 제출 응답: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 피드백 제출 오류: {e}")
    
    print("\n🎉 테스트 완료!")
    print("\n💡 주요 특징:")
    print("   • 사용자당 하나의 카테고리만 추천")
    print("   • 카테고리 내에서 여러 도서 제공")
    print("   • 도서관 소장 위치 정보 포함")

def test_multiple_users():
    """여러 사용자의 서로 다른 카테고리 추천 테스트"""
    api_base_url = "http://localhost:5001"
    
    test_users = [
        {"user_id": "user_ai", "preferred_keywords": ["인공지능", "기계학습"]},
        {"user_id": "user_novel", "preferred_keywords": ["소설", "문학"]},
        {"user_id": "user_science", "preferred_keywords": ["과학", "물리학"]}
    ]
    
    print("\n🔍 여러 사용자 카테고리 비교")
    print("=" * 40)
    
    for user_data in test_users:
        try:
            # 사용자 생성
            requests.post(f"{api_base_url}/api/users", json=user_data)
            
            # 추천 조회
            response = requests.get(f"{api_base_url}/api/recommendations/{user_data['user_id']}?books_per_category=3")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n👤 {user_data['user_id']}:")
                print(f"   관심사: {user_data['preferred_keywords']}")
                print(f"   추천 카테고리: '{data['category']}'")
                print(f"   추천 도서 수: {data['books_count']}권")
                
                if data['books']:
                    print(f"   상위 도서: {data['books'][0]['title']}")
            
        except Exception as e:
            print(f"❌ {user_data['user_id']} 테스트 실패: {e}")

if __name__ == "__main__":
    print("🚀 카테고리 기반 추천 시스템 테스트 시작")
    
    # API 서버 연결 확인
    try:
        response = requests.get("http://localhost:5001/", timeout=5)
        if response.status_code == 200:
            print("✅ API 서버 연결 확인")
        else:
            print("❌ API 서버가 실행되지 않았습니다.")
            print("💡 먼저 'python api_server.py'를 실행해주세요.")
            exit(1)
    except:
        print("❌ API 서버에 연결할 수 없습니다.")
        print("💡 먼저 'python api_server.py'를 실행해주세요.")
        exit(1)
    
    test_category_recommendation()
    test_multiple_users()