#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개인화된 추천 시스템 테스트 스크립트
각 사용자별로 다른 추천 결과가 나오는지 확인
"""

import requests
import json
import pandas as pd
from datetime import datetime
import sys

def test_personalization():
    """개인화 추천 테스트"""
    api_base_url = "http://localhost:5000"
    
    print("🧪 개인화 추천 시스템 테스트")
    print("=" * 50)
    
    # API 서버 상태 확인
    try:
        health_response = requests.get(f"{api_base_url}/api/health", timeout=5)
        if health_response.status_code != 200:
            print("❌ API 서버에 연결할 수 없습니다.")
            print("💡 먼저 API 서버를 실행해주세요: python recommendation_api_server.py")
            return
        
        health_data = health_response.json()
        print(f"✅ API 서버 연결 성공 - 도서 {health_data.get('books_loaded', 0)}권 로드")
        
    except Exception as e:
        print(f"❌ API 서버 연결 실패: {str(e)}")
        return
    
    # 테스트할 사용자들
    test_users = [
        'demo_user_001', 'demo_user_002', 'demo_user_003', 
        'demo_user_004', 'demo_user_005'
    ]
    
    all_recommendations = {}
    
    print(f"\n🔍 {len(test_users)}명 사용자별 추천 결과 수집 중...")
    
    # 각 사용자별 추천 데이터 수집
    for i, user_id in enumerate(test_users, 1):
        print(f"[{i}/{len(test_users)}] {user_id} 추천 데이터 수집...")
        
        try:
            response = requests.get(f"{api_base_url}/api/recommendations/{user_id}?top_k=10")
            
            if response.status_code == 200:
                recommendations = response.json()
                all_recommendations[user_id] = recommendations
                
                # 간단한 정보 출력
                personalized = recommendations.get('recommendations', {}).get('personalized', {})
                books = personalized.get('books', [])
                user_profile = recommendations.get('user_profile', {})
                
                print(f"   ✅ {len(books)}개 추천 완료")
                print(f"   👤 관심사: {', '.join(user_profile.get('preferred_keywords', []))}")
                print(f"   📊 개인화 강도: {recommendations.get('stats', {}).get('personalization_strength', 0):.2f}")
                
            else:
                print(f"   ❌ 추천 실패: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
    
    if not all_recommendations:
        print("\n❌ 추천 데이터를 수집할 수 없습니다.")
        return
    
    # 개인화 분석
    print(f"\n📊 개인화 분석 결과")
    print("=" * 50)
    
    analyze_personalization(all_recommendations)
    
    # 상세 비교 출력
    print(f"\n👥 사용자별 상위 3개 추천 비교")
    print("=" * 70)
    
    for user_id, rec_data in all_recommendations.items():
        user_profile = rec_data.get('user_profile', {})
        personalized = rec_data.get('recommendations', {}).get('personalized', {})
        books = personalized.get('books', [])
        
        print(f"\n🧑 {user_id} ({user_profile.get('name', '이름없음')})")
        print(f"   🎯 관심사: {', '.join(user_profile.get('preferred_keywords', []))}")
        print(f"   👶 연령대: {user_profile.get('age_group', '정보없음')}")
        print(f"   📈 개인화 강도: {rec_data.get('stats', {}).get('personalization_strength', 0):.2f}")
        
        for i, book in enumerate(books[:3], 1):
            print(f"      {i}. 📖 {book['title']}")
            print(f"         👤 저자: {book['author']}")
            print(f"         🏷️  키워드: {book['keyword']}")
            print(f"         ⭐ 점수: {book['score']:.3f} (개인: {book.get('personal_score', 0):.3f}, 트렌드: {book.get('trend_score', 0):.3f})")
            print(f"         💡 이유: {book['recommendation_reason']}")
    
    # Excel 저장
    save_to_excel(all_recommendations)

def analyze_personalization(all_recommendations):
    """개인화 효과 분석"""
    
    # 1. 추천 다양성 분석
    all_book_titles = set()
    user_books = {}
    
    for user_id, rec_data in all_recommendations.items():
        personalized = rec_data.get('recommendations', {}).get('personalized', {})
        books = personalized.get('books', [])
        
        user_book_titles = [book['title'] for book in books[:5]]  # 상위 5개
        user_books[user_id] = set(user_book_titles)
        all_book_titles.update(user_book_titles)
    
    # 2. 중복률 계산
    total_recommendations = sum(len(books) for books in user_books.values())
    unique_books = len(all_book_titles)
    
    print(f"📚 전체 추천된 고유 도서 수: {unique_books}개")
    print(f"📊 총 추천 수: {total_recommendations}개")
    print(f"🎯 다양성 지수: {(unique_books / total_recommendations * 100):.1f}%")
    
    # 3. 사용자간 유사도 분석
    print(f"\n👥 사용자간 추천 중복률:")
    user_ids = list(user_books.keys())
    
    for i in range(len(user_ids)):
        for j in range(i + 1, len(user_ids)):
            user1, user2 = user_ids[i], user_ids[j]
            books1, books2 = user_books[user1], user_books[user2]
            
            intersection = len(books1.intersection(books2))
            union = len(books1.union(books2))
            similarity = (intersection / union * 100) if union > 0 else 0
            
            print(f"   • {user1} ↔ {user2}: {intersection}개 중복 ({similarity:.1f}% 유사)")
    
    # 4. 키워드별 추천 분포
    keyword_distribution = {}
    user_preferences = {}
    
    for user_id, rec_data in all_recommendations.items():
        user_profile = rec_data.get('user_profile', {})
        preferred_keywords = user_profile.get('preferred_keywords', [])
        user_preferences[user_id] = preferred_keywords
        
        personalized = rec_data.get('recommendations', {}).get('personalized', {})
        books = personalized.get('books', [])
        
        for book in books[:5]:  # 상위 5개만 분석
            keyword = book['keyword']
            if keyword not in keyword_distribution:
                keyword_distribution[keyword] = []
            keyword_distribution[keyword].append(user_id)
    
    print(f"\n🏷️ 키워드별 추천 분포:")
    for keyword, users in sorted(keyword_distribution.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   • {keyword}: {len(users)}명에게 추천 ({', '.join(users[:3])}{'...' if len(users) > 3 else ''})")
    
    # 5. 개인화 강도 분석
    personalization_scores = []
    for user_id, rec_data in all_recommendations.items():
        score = rec_data.get('stats', {}).get('personalization_strength', 0)
        personalization_scores.append(score)
    
    if personalization_scores:
        avg_personalization = sum(personalization_scores) / len(personalization_scores)
        print(f"\n📈 평균 개인화 강도: {avg_personalization:.2f}")
        print(f"📊 개인화 강도 범위: {min(personalization_scores):.2f} ~ {max(personalization_scores):.2f}")
    
    # 6. 선호도 매칭 분석
    print(f"\n🎯 선호도 매칭 분석:")
    for user_id, rec_data in all_recommendations.items():
        user_profile = rec_data.get('user_profile', {})
        preferred_keywords = set(user_profile.get('preferred_keywords', []))
        
        personalized = rec_data.get('recommendations', {}).get('personalized', {})
        books = personalized.get('books', [])
        
        recommended_keywords = set(book['keyword'] for book in books[:5])
        
        if preferred_keywords:
            match_rate = len(preferred_keywords.intersection(recommended_keywords)) / len(preferred_keywords) * 100
            print(f"   • {user_id}: {match_rate:.1f}% 선호도 매칭")
        else:
            print(f"   • {user_id}: 선호도 정보 없음")

def save_to_excel(all_recommendations):
    """추천 결과를 Excel로 저장"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"personalization_test_results_{timestamp}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 사용자 프로필 시트
            profile_data = []
            for user_id, rec_data in all_recommendations.items():
                user_profile = rec_data.get('user_profile', {})
                stats = rec_data.get('stats', {})
                
                profile_data.append({
                    'user_id': user_id,
                    'name': user_profile.get('name', ''),
                    'age_group': user_profile.get('age_group', ''),
                    'preferred_keywords': ', '.join(user_profile.get('preferred_keywords', [])),
                    'reading_frequency': user_profile.get('reading_frequency', ''),
                    'personalization_strength': stats.get('personalization_strength', 0),
                    'total_books': stats.get('total_books', 0),
                    'recommendation_count': stats.get('recommendation_count', 0)
                })
            
            pd.DataFrame(profile_data).to_excel(writer, sheet_name='사용자프로필', index=False)
            
            # 추천 결과 시트
            recommendation_data = []
            for user_id, rec_data in all_recommendations.items():
                personalized = rec_data.get('recommendations', {}).get('personalized', {})
                books = personalized.get('books', [])
                
                for rank, book in enumerate(books, 1):
                    recommendation_data.append({
                        'user_id': user_id,
                        'rank': rank,
                        'title': book['title'],
                        'author': book['author'],
                        'keyword': book['keyword'],
                        'publisher': book['publisher'],
                        'pub_year': book['pub_year'],
                        'type': book['type'],
                        'library_name': book.get('library_name', ''),
                        'score': book['score'],
                        'personal_score': book.get('personal_score', 0),
                        'trend_score': book.get('trend_score', 0),
                        'recommendation_reason': book['recommendation_reason']
                    })
            
            pd.DataFrame(recommendation_data).to_excel(writer, sheet_name='개인화추천결과', index=False)
            
            # 비교 분석 시트
            comparison_data = []
            user_ids = list(all_recommendations.keys())
            
            for i in range(len(user_ids)):
                for j in range(i + 1, len(user_ids)):
                    user1, user2 = user_ids[i], user_ids[j]
                    
                    books1 = set(book['title'] for book in all_recommendations[user1]['recommendations']['personalized']['books'][:5])
                    books2 = set(book['title'] for book in all_recommendations[user2]['recommendations']['personalized']['books'][:5])
                    
                    intersection = len(books1.intersection(books2))
                    union = len(books1.union(books2))
                    similarity = (intersection / union * 100) if union > 0 else 0
                    
                    comparison_data.append({
                        'user1': user1,
                        'user2': user2,
                        'common_books': intersection,
                        'total_unique_books': union,
                        'similarity_percentage': similarity
                    })
            
            pd.DataFrame(comparison_data).to_excel(writer, sheet_name='사용자간비교', index=False)
        
        print(f"\n💾 테스트 결과가 '{filename}'에 저장되었습니다.")
        
    except Exception as e:
        print(f"\n❌ Excel 저장 실패: {str(e)}")

def test_feedback_learning():
    """피드백 학습 기능 테스트"""
    api_base_url = "http://localhost:5000"
    
    print(f"\n🧠 피드백 학습 기능 테스트")
    print("=" * 50)
    
    test_user = "demo_user_001"
    
    # 1. 초기 추천 결과 가져오기
    print(f"📊 {test_user} 초기 추천 결과 조회...")
    
    try:
        initial_response = requests.get(f"{api_base_url}/api/recommendations/{test_user}?top_k=5")
        
        if initial_response.status_code != 200:
            print("❌ 초기 추천 조회 실패")
            return
        
        initial_recs = initial_response.json()
        initial_books = initial_recs['recommendations']['personalized']['books']
        
        print(f"✅ 초기 추천 {len(initial_books)}개 조회 완료")
        print("📚 초기 추천 상위 3개:")
        for i, book in enumerate(initial_books[:3], 1):
            print(f"   {i}. {book['title']} (키워드: {book['keyword']}, 점수: {book['score']:.3f})")
        
        # 2. 첫 번째 도서에 긍정적 피드백 제출
        if initial_books:
            test_book = initial_books[0]
            feedback_data = {
                "user_id": test_user,
                "book_id": test_book['doc_id'],
                "rating": 5,
                "feedback_text": "개인화 테스트를 위한 긍정적 피드백입니다."
            }
            
            print(f"\n📝 '{test_book['title']}'에 긍정적 피드백(5점) 제출...")
            
            feedback_response = requests.post(
                f"{api_base_url}/api/feedback",
                json=feedback_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if feedback_response.status_code == 200:
                print("✅ 피드백 제출 성공")
                
                # 3. 피드백 후 새로운 추천 결과 확인
                print(f"🔄 피드백 반영 후 새로운 추천 결과 조회...")
                
                import time
                time.sleep(2)  # 처리 시간 대기
                
                updated_response = requests.get(f"{api_base_url}/api/recommendations/{test_user}?top_k=5")
                
                if updated_response.status_code == 200:
                    updated_recs = updated_response.json()
                    updated_books = updated_recs['recommendations']['personalized']['books']
                    
                    print(f"✅ 업데이트된 추천 {len(updated_books)}개 조회 완료")
                    print("📚 업데이트된 추천 상위 3개:")
                    for i, book in enumerate(updated_books[:3], 1):
                        print(f"   {i}. {book['title']} (키워드: {book['keyword']}, 점수: {book['score']:.3f})")
                    
                    # 4. 변화 분석
                    print(f"\n📈 피드백 학습 효과 분석:")
                    
                    initial_keywords = [book['keyword'] for book in initial_books[:5]]
                    updated_keywords = [book['keyword'] for book in updated_books[:5]]
                    
                    feedback_keyword = test_book['keyword']
                    
                    initial_count = initial_keywords.count(feedback_keyword)
                    updated_count = updated_keywords.count(feedback_keyword)
                    
                    print(f"   • 피드백 키워드 '{feedback_keyword}' 추천 수:")
                    print(f"     이전: {initial_count}개 → 이후: {updated_count}개")
                    
                    if updated_count > initial_count:
                        print(f"   ✅ 학습 효과 확인: '{feedback_keyword}' 관련 추천 증가")
                    elif updated_count == initial_count:
                        print(f"   ➖ 동일한 수준 유지")
                    else:
                        print(f"   ⚠️ 감소 (다른 요인 가능)")
                    
                    # 개인화 강도 변화
                    initial_strength = initial_recs.get('stats', {}).get('personalization_strength', 0)
                    updated_strength = updated_recs.get('stats', {}).get('personalization_strength', 0)
                    
                    print(f"   • 개인화 강도: {initial_strength:.3f} → {updated_strength:.3f}")
                    
                else:
                    print("❌ 업데이트된 추천 조회 실패")
            else:
                print(f"❌ 피드백 제출 실패: HTTP {feedback_response.status_code}")
        
    except Exception as e:
        print(f"❌ 피드백 학습 테스트 실패: {str(e)}")

def generate_demo_data():
    """새로운 데모 데이터 생성"""
    print(f"\n🎲 새로운 데모 데이터 생성")
    print("=" * 50)
    
    try:
        # trend_book_recommender 직접 실행
        import subprocess
        import os
        
        # 현재 디렉토리에서 trend_book_recommender.py 실행
        result = subprocess.run([
            sys.executable, 'trend_book_recommender.py', 
            '--generate_demo'
        ], capture_output=True, text=True, cwd='.')
        
        if result.returncode == 0:
            print("✅ 데모 데이터 생성 성공")
            print(result.stdout)
        else:
            print("❌ 데모 데이터 생성 실패")
            print(result.stderr)
    
    except Exception as e:
        print(f"❌ 데모 데이터 생성 오류: {str(e)}")

def compare_algorithms():
    """알고리즘 비교 테스트"""
    print(f"\n⚖️ 추천 알고리즘 성능 비교")
    print("=" * 50)
    
    api_base_url = "http://localhost:5000"
    test_users = ['demo_user_001', 'demo_user_002', 'demo_user_003']
    
    print("📊 개인화 vs 일반 추천 성능 비교...")
    
    for user_id in test_users:
        try:
            # 개인화 추천
            response = requests.get(f"{api_base_url}/api/recommendations/{user_id}?top_k=5")
            
            if response.status_code == 200:
                rec_data = response.json()
                personalized_books = rec_data['recommendations']['personalized']['books']
                trending_books = rec_data['recommendations']['trending']['books']
                
                user_profile = rec_data.get('user_profile', {})
                preferred_keywords = set(user_profile.get('preferred_keywords', []))
                
                # 개인화 추천의 선호도 매칭률
                personalized_keywords = set(book['keyword'] for book in personalized_books[:5])
                personalized_match = len(preferred_keywords.intersection(personalized_keywords)) / len(preferred_keywords) * 100 if preferred_keywords else 0
                
                # 트렌딩 추천의 선호도 매칭률
                trending_keywords = set(book['keyword'] for book in trending_books[:5])
                trending_match = len(preferred_keywords.intersection(trending_keywords)) / len(preferred_keywords) * 100 if preferred_keywords else 0
                
                print(f"\n👤 {user_id}:")
                print(f"   관심사: {', '.join(preferred_keywords)}")
                print(f"   개인화 추천 매칭률: {personalized_match:.1f}%")
                print(f"   트렌딩 추천 매칭률: {trending_match:.1f}%")
                print(f"   성능 개선: +{(personalized_match - trending_match):.1f}%p")
        
        except Exception as e:
            print(f"❌ {user_id} 비교 실패: {str(e)}")

def main():
    """메인 실행 함수"""
    print("🧪 개인화 추천 시스템 종합 테스트")
    print("=" * 60)
    
    print("📋 테스트 메뉴:")
    print("1. 개인화 효과 테스트 (사용자별 추천 차이 분석)")
    print("2. 피드백 학습 기능 테스트")
    print("3. 새로운 데모 데이터 생성")
    print("4. 알고리즘 성능 비교")
    print("5. 전체 테스트 (1 + 2 + 4)")
    
    choice = input("\n선택 (1-5): ").strip()
    
    if choice == "1":
        test_personalization()
    elif choice == "2":
        test_feedback_learning()
    elif choice == "3":
        generate_demo_data()
    elif choice == "4":
        compare_algorithms()
    elif choice == "5":
        test_personalization()
        test_feedback_learning()
        compare_algorithms()
    else:
        print("❌ 올바른 옵션을 선택해주세요.")
        return
    
    print(f"\n🎉 테스트 완료!")
    print("💡 팁:")
    print("   • API 서버가 실행 중이어야 테스트가 정상 작동합니다")
    print("   • 테스트 결과는 Excel 파일로 저장됩니다")
    print("   • 피드백 테스트 후 개인화 효과가 더욱 뚜렷해집니다")

if __name__ == "__main__":
    main()