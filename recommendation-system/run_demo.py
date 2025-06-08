#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드 기반 도서 추천 시스템 - 간단한 데모 실행
"""

import os
import sys
import json
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trend_book_recommender import TrendBookRecommender

def main():
    """데모 실행"""
    print("🚀 트렌드 기반 도서 추천 시스템 데모")
    print("=" * 50)
    
    # Firebase 설정 파일 경로 (프로젝트 루트에서)
    firebase_config = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json'
    )
    
    if not os.path.exists(firebase_config):
        print(f"❌ Firebase 설정 파일을 찾을 수 없습니다: {firebase_config}")
        print("💡 프로젝트 루트에 Firebase 서비스 계정 키 파일을 배치해주세요.")
        return
    
    try:
        # 1. 추천 시스템 초기화
        print("📚 추천 시스템 초기화 중...")
        recommender = TrendBookRecommender(firebase_config)
        
        # 2. 도서 데이터 로드
        print("📖 Firebase에서 도서 데이터 로드 중...")
        books_df = recommender.load_books_from_firebase()
        print(f"   ✅ {len(books_df)}개 도서 로드 완료")
        
        # 3. 특성 벡터 구축
        print("🔧 도서 특성 벡터 구축 중...")
        recommender.build_content_features(books_df)
        print("   ✅ 특성 벡터 구축 완료")
        
        # 4. 데모 사용자 생성 (선택)
        print("\n📝 데모 사용자를 생성하시겠습니까? (y/n): ", end="")
        create_demo = input().lower().startswith('y')
        
        if create_demo:
            print("👥 데모 사용자 생성 중...")
            demo_users = recommender.generate_demo_users(num_users=5)
            demo_ratings = recommender.generate_demo_ratings(demo_users, books_df, (3, 8))
            recommender.save_demo_data_to_firebase(demo_users, demo_ratings)
            print(f"   ✅ {len(demo_users)}명 사용자, {len(demo_ratings)}개 평점 생성")
        else:
            demo_users = [{'user_id': 'demo_user_001', 'name': '테스트 사용자'}]
        
        # 5. 추천 생성 및 출력
        print(f"\n🎯 '{demo_users[0]['user_id']}' 사용자 맞춤 추천:")
        recommendations = recommender.generate_recommendations_for_frontend(
            demo_users[0]['user_id'], books_df
        )
        
        # 개인화 추천 출력
        personalized = recommendations.get('recommendations', {}).get('personalized', {})
        books = personalized.get('books', [])
        
        print(f"\n📚 {personalized.get('title', '맞춤 추천')} (상위 5개):")
        print("-" * 60)
        
        for i, book in enumerate(books[:5], 1):
            print(f"{i}. 📖 {book['title']}")
            print(f"   👤 저자: {book['author']}")
            print(f"   🏷️  키워드: {book['keyword']}")
            print(f"   🏛️  소장: {book.get('library_name', '정보없음')}")
            print(f"   ⭐ 점수: {book['score']:.3f}")
            print(f"   💡 이유: {book['recommendation_reason']}")
            print()
        
        # 트렌딩 도서 출력
        trending = recommendations.get('recommendations', {}).get('trending', {})
        trending_books = trending.get('books', [])
        
        if trending_books:
            print(f"🔥 {trending.get('title', '트렌딩 도서')} (상위 3개):")
            print("-" * 60)
            
            for i, book in enumerate(trending_books[:3], 1):
                print(f"{i}. 📖 {book['title']}")
                print(f"   👤 저자: {book['author']}")
                print(f"   🏷️  키워드: {book['keyword']}")
                print(f"   ⭐ 점수: {book['score']:.3f}")
                print()
        
        # 6. 피드백 시뮬레이션
        print("📝 피드백 시뮬레이션을 진행하시겠습니까? (y/n): ", end="")
        test_feedback = input().lower().startswith('y')
        
        if test_feedback and books:
            print("📩 샘플 피드백 제출 중...")
            sample_book = books[0]
            success = recommender.process_user_feedback(
                user_id=demo_users[0]['user_id'],
                book_id=sample_book['doc_id'],
                rating=5,
                feedback_text="매우 유익한 도서였습니다!"
            )
            
            if success:
                print("   ✅ 피드백 처리 완료")
                
                # 업데이트된 추천 확인
                print("🔄 피드백 반영 후 새로운 추천:")
                new_recommendations = recommender.generate_recommendations_for_frontend(
                    demo_users[0]['user_id'], books_df
                )
                new_books = new_recommendations.get('recommendations', {}).get('personalized', {}).get('books', [])
                
                if new_books:
                    print(f"   📖 새 추천 1위: {new_books[0]['title']} (점수: {new_books[0]['score']:.3f})")
            else:
                print("   ❌ 피드백 처리 실패")
        
        # 7. 결과 저장
        print("\n💾 결과를 JSON 파일로 저장하시겠습니까? (y/n): ", end="")
        save_results = input().lower().startswith('y')
        
        if save_results:
            output_file = f"demo_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            demo_result = {
                'timestamp': datetime.now().isoformat(),
                'books_count': len(books_df),
                'user_id': demo_users[0]['user_id'],
                'recommendations': recommendations,
                'demo_info': {
                    'firebase_config_found': True,
                    'demo_users_created': create_demo,
                    'feedback_tested': test_feedback if 'test_feedback' in locals() else False
                }
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(demo_result, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"   ✅ 결과가 '{output_file}'에 저장되었습니다")
        
        print("\n✨ 데모 완료!")
        print("\n📖 다음 단계:")
        print("   1. API 서버 실행: python recommendation_api_server.py")
        print("   2. API 테스트: python test_api.py")
        print("   3. 프론트엔드 연동")
        
    except Exception as e:
        print(f"\n❌ 데모 실행 중 오류 발생: {str(e)}")
        print("\n🔧 문제 해결:")
        print("   1. Firebase 설정 파일 경로 확인")
        print("   2. 필요한 Python 패키지 설치: pip install -r requirements.txt")
        print("   3. Firebase 데이터베이스에 도서 데이터 존재 여부 확인")

if __name__ == "__main__":
    main()