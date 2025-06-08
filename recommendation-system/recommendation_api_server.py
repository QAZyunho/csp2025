#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개인화된 트렌드 기반 도서 추천 API 서버
Flask + Firebase 연동
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import sys
import logging
from datetime import datetime
import json
import pandas as pd

# 추천 시스템 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trend_book_recommender import TrendBookRecommender

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # React 등 프론트엔드와 연동을 위한 CORS 설정

# 전역 추천 시스템 인스턴스
recommender = None
books_df = None

def init_recommender():
    """개선된 추천 시스템 초기화"""
    global recommender, books_df
    try:
        firebase_config = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json'
        )
        
        if not os.path.exists(firebase_config):
            logger.error(f"Firebase 설정 파일을 찾을 수 없습니다: {firebase_config}")
            return False
            
        # 개선된 TrendBookRecommender 사용
        recommender = TrendBookRecommender(firebase_config)
        books_df = recommender.load_books_from_firebase()
        recommender.build_content_features(books_df)
        
        # 기존 사용자 프로필 로드
        recommender.load_user_profiles()
        
        logger.info("✅ 개선된 추천 시스템 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"❌ 추천 시스템 초기화 실패: {str(e)}")
        return False

# ================== API 엔드포인트 ==================

@app.route('/')
def index():
    """API 서비스 상태 및 문서"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>개인화된 트렌드 기반 도서 추천 API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            .method { background: #007bff; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px; margin-right: 10px; }
            .post { background: #28a745; }
            .put { background: #ffc107; }
            code { background: #e9ecef; padding: 2px 5px; border-radius: 3px; }
            .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
            .healthy { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .unhealthy { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .personalized { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            h2 { color: #555; margin-top: 30px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📚 개인화된 트렌드 기반 도서 추천 API</h1>
            <p>Firebase와 연동된 개인화 도서 추천 서비스입니다.</p>
            
            <div class="status {{ 'healthy' if book_count > 0 else 'unhealthy' }}">
                <strong>서비스 상태:</strong> {{ 'healthy' if book_count > 0 else 'unhealthy' }} | 
                <strong>로드된 도서:</strong> {{ book_count }}권 | 
                <strong>시작 시간:</strong> {{ start_time }}
            </div>
            
            <div class="status personalized">
                <strong>✨ 개인화 기능:</strong> 활성화됨 | 
                <strong>사용자별 맞춤 추천:</strong> 지원 | 
                <strong>피드백 학습:</strong> 실시간 반영
            </div>
            
            <h2>📋 주요 API 엔드포인트</h2>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/health</h3>
                <p><strong>설명:</strong> 서비스 상태 확인</p>
            </div>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/recommendations/{user_id}</h3>
                <p><strong>설명:</strong> 🎯 사용자 맞춤 개인화 추천</p>
                <p><strong>새로운 기능:</strong> 사용자 선호도, 연령대, 피드백 기반 개인화</p>
            </div>
            
            <div class="endpoint">
                <h3><span class="method post">POST</span>/api/feedback</h3>
                <p><strong>설명:</strong> 🧠 사용자 피드백 제출 (학습 기능)</p>
                <p><strong>새로운 기능:</strong> 실시간 프로필 업데이트 및 추천 개선</p>
            </div>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/users/{user_id}/personalization</h3>
                <p><strong>설명:</strong> 🆕 사용자 개인화 강도 조회</p>
            </div>
            
            <h2>🆕 개인화 기능</h2>
            <ul>
                <li><strong>사용자별 맞춤 추천:</strong> 관심사, 연령대, 읽기 패턴 분석</li>
                <li><strong>실시간 학습:</strong> 피드백을 통한 즉시 프로필 업데이트</li>
                <li><strong>다양성 보장:</strong> 사용자마다 다른 추천 결과</li>
                <li><strong>개인화 강도 측정:</strong> 추천 품질 정량화</li>
            </ul>
            
            <h2>🔗 관련 링크</h2>
            <ul>
                <li><a href="/api/health">서비스 상태 확인</a></li>
                <li><a href="/api/books?page=1&size=5">도서 목록 (샘플)</a></li>
                <li><a href="/api/trending?limit=5">트렌딩 도서 (샘플)</a></li>
                <li><a href="/api/analytics">분석 데이터</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_template, 
                                start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                book_count=len(books_df) if books_df is not None else 0)

@app.route('/api/health')
def health_check():
    """서비스 상태 확인"""
    status = {
        'status': 'healthy' if recommender and books_df is not None else 'unhealthy',
        'timestamp': datetime.now().isoformat(),
        'books_loaded': len(books_df) if books_df is not None else 0,
        'recommender_ready': recommender is not None,
        'firebase_connected': recommender.db is not None if recommender else False,
        'personalization_enabled': True,  # 개인화 활성화 표시
        'users_loaded': len(recommender.user_profiles) if recommender else 0
    }
    return jsonify(status)

@app.route('/api/books')
def get_books():
    """전체 도서 목록 조회"""
    try:
        if books_df is None:
            return jsonify({'error': '도서 데이터가 로드되지 않았습니다'}), 500
        
        # 쿼리 파라미터
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        keyword_filter = request.args.get('keyword')
        
        # 필터링
        filtered_df = books_df
        if keyword_filter:
            filtered_df = books_df[books_df['keyword'].str.contains(keyword_filter, case=False, na=False)]
        
        # 페이징
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_books = filtered_df.iloc[start_idx:end_idx]
        
        books_list = []
        for _, book in page_books.iterrows():
            books_list.append({
                'doc_id': book['doc_id'],
                'title': book['title'],
                'author': book['author'],
                'keyword': book['keyword'],
                'publisher': book['publisher'],
                'pub_year': book['pub_year'],
                'type': book['type'],
                'library_name': book.get('library_name', ''),
                'library_location': book.get('library_location', ''),
                'call_no': book.get('call_no', '')
            })
        
        result = {
            'books': books_list,
            'pagination': {
                'page': page,
                'size': size,
                'total_books': len(filtered_df),
                'total_pages': (len(filtered_df) + size - 1) // size,
                'has_next': end_idx < len(filtered_df),
                'has_prev': page > 1
            },
            'generated_at': datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"도서 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recommendations/<user_id>')
def get_recommendations(user_id):
    """사용자 맞춤 개인화 추천"""
    try:
        if not recommender or books_df is None:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        top_k = int(request.args.get('top_k', 10))
        
        # 개선된 추천 생성
        recommendations = recommender.generate_recommendations_for_frontend(
            user_id, books_df
        )
        
        if not recommendations:
            return jsonify({'error': '추천 생성에 실패했습니다'}), 500
        
        return jsonify(recommendations)
        
    except Exception as e:
        logger.error(f"추천 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trending')
def get_trending():
    """트렌딩 도서 목록"""
    try:
        if not recommender or books_df is None:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        limit = int(request.args.get('limit', 10))
        
        trending_books = recommender.get_trending_books(books_df, top_k=limit)
        
        result = {
            'trending_books': trending_books,
            'total_count': len(trending_books),
            'generated_at': datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"트렌딩 도서 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    """새 사용자 생성 - 개선된 프로필 구조"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        data = request.get_json()
        
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id가 필요합니다'}), 400
        
        # 사용자 ID 중복 체크
        if data['user_id'] in recommender.user_profiles:
            return jsonify({'error': '이미 존재하는 사용자입니다'}), 409
        
        # 개선된 사용자 프로필 구조
        user_profile = {
            'user_id': data['user_id'],
            'name': data.get('name', ''),
            'preferred_keywords': data.get('preferred_keywords', []),
            'preferred_types': data.get('preferred_types', ['도서']),
            'age_group': data.get('age_group', ''),
            'reading_frequency': data.get('reading_frequency', ''),
            'created_at': datetime.now(),
            'last_active': datetime.now()
        }
        
        # 메모리와 Firebase에 저장
        recommender.user_profiles[data['user_id']] = user_profile
        recommender.save_user_profile_to_firebase(data['user_id'], user_profile)
        
        return jsonify({
            'message': '사용자가 생성되었습니다', 
            'user_profile': {
                'user_id': user_profile['user_id'],
                'name': user_profile['name'],
                'preferred_keywords': user_profile['preferred_keywords'],
                'age_group': user_profile['age_group'],
                'personalization_strength': recommender.calculate_personalization_strength(data['user_id'])
            }
        }), 201
        
    except Exception as e:
        logger.error(f"사용자 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """사용자 피드백 제출 - 개선된 학습 기능"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        data = request.get_json()
        
        required_fields = ['user_id', 'book_id', 'rating']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field}가 필요합니다'}), 400
        
        if not (1 <= data['rating'] <= 5):
            return jsonify({'error': '평점은 1-5 사이여야 합니다'}), 400
        
        # 개선된 피드백 처리 (학습 기능 포함)
        success = recommender.process_user_feedback(
            user_id=data['user_id'],
            book_id=data['book_id'],
            rating=data['rating'],
            feedback_text=data.get('feedback_text', '')
        )
        
        if success:
            # 업데이트된 개인화 강도 계산
            new_strength = recommender.calculate_personalization_strength(data['user_id'])
            
            return jsonify({
                'message': '피드백이 처리되었습니다',
                'feedback': {
                    'user_id': data['user_id'],
                    'rating': data['rating'],
                    'timestamp': datetime.now().isoformat(),
                    'learning_applied': True,  # 학습 적용 표시
                    'new_personalization_strength': new_strength
                }
            }), 200
        else:
            return jsonify({'error': '피드백 처리에 실패했습니다'}), 500
        
    except Exception as e:
        logger.error(f"피드백 처리 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    """피드백 분석 결과 - 개인화 통계 포함"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        # 개선된 분석 (개인화 통계 포함)
        analytics = recommender.get_feedback_analytics()
        
        # 추가 시스템 통계
        analytics['system_stats'] = {
            'total_books': len(books_df) if books_df is not None else 0,
            'total_users': len(recommender.user_profiles),
            'unique_keywords': books_df['keyword'].nunique() if books_df is not None else 0,
            'personalization_enabled': True,  # 개인화 활성화 표시
            'last_updated': datetime.now().isoformat()
        }
        
        # 개인화 통계 추가
        if recommender.user_profiles:
            personalization_strengths = []
            for user_id in recommender.user_profiles.keys():
                strength = recommender.calculate_personalization_strength(user_id)
                personalization_strengths.append(strength)
            
            if personalization_strengths:
                analytics['personalization_stats'] = {
                    'avg_personalization_strength': sum(personalization_strengths) / len(personalization_strengths),
                    'max_personalization_strength': max(personalization_strengths),
                    'min_personalization_strength': min(personalization_strengths),
                    'users_with_strong_personalization': len([s for s in personalization_strengths if s > 0.5]),
                    'users_with_weak_personalization': len([s for s in personalization_strengths if s < 0.3])
                }
        
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f"분석 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/demo/generate', methods=['POST'])
def generate_demo_data():
    """데모 데이터 생성 - 개선된 다양성"""
    try:
        if not recommender or books_df is None:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        num_users = int(request.args.get('num_users', 20))
        
        if num_users > 100:
            return jsonify({'error': '사용자 수는 100명을 초과할 수 없습니다'}), 400
        
        # 개선된 데모 사용자 생성 (더 다양한 프로필)
        demo_users = recommender.generate_demo_users(num_users)
        
        # 개선된 데모 평점 생성 (더 현실적인 패턴)
        demo_ratings = recommender.generate_demo_ratings(demo_users, books_df, (3, 10))
        
        # Firebase에 저장
        recommender.save_demo_data_to_firebase(demo_users, demo_ratings)
        
        # 개인화 강도 미리보기
        personalization_preview = {}
        for user in demo_users[:5]:
            strength = recommender.calculate_personalization_strength(user['user_id'])
            personalization_preview[user['user_id']] = {
                'preferred_keywords': user['preferred_keywords'],
                'age_group': user['age_group'],
                'personalization_strength': strength
            }
        
        result = {
            'message': '개선된 데모 데이터가 생성되었습니다',
            'users_created': len(demo_users),
            'ratings_created': len(demo_ratings),
            'sample_user_ids': [user['user_id'] for user in demo_users[:5]],
            'personalization_preview': personalization_preview,
            'diversity_info': {
                'unique_user_types': len(set(user['age_group'] for user in demo_users)),
                'avg_keywords_per_user': sum(len(user['preferred_keywords']) for user in demo_users) / len(demo_users),
                'total_unique_keywords': len(set(kw for user in demo_users for kw in user['preferred_keywords']))
            },
            'created_at': datetime.now().isoformat()
        }
        
        return jsonify(result), 201
        
    except Exception as e:
        logger.error(f"데모 데이터 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<user_id>/profile')
def get_user_profile(user_id):
    """사용자 프로필 조회"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        profile = recommender.user_profiles.get(user_id)
        
        if not profile:
            # Firebase에서 조회 시도
            if recommender.db:
                user_doc = recommender.db.collection('users').document(user_id).get()
                if user_doc.exists:
                    profile = user_doc.to_dict()
                    recommender.user_profiles[user_id] = profile
        
        if profile:
            # 개인화 정보 추가
            personalization_strength = recommender.calculate_personalization_strength(user_id)
            user_ratings = recommender.load_user_ratings(user_id)
            
            safe_profile = {
                'user_id': profile.get('user_id'),
                'name': profile.get('name'),
                'preferred_keywords': profile.get('preferred_keywords', []),
                'preferred_types': profile.get('preferred_types', []),
                'age_group': profile.get('age_group'),
                'reading_frequency': profile.get('reading_frequency'),
                'created_at': profile.get('created_at'),
                'last_active': profile.get('last_active'),
                'personalization_strength': personalization_strength,
                'feedback_count': len(user_ratings)
            }
            return jsonify(safe_profile)
        else:
            return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404
        
    except Exception as e:
        logger.error(f"사용자 프로필 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<user_id>/profile', methods=['PUT'])
def update_user_profile(user_id):
    """사용자 프로필 업데이트"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': '업데이트할 데이터가 필요합니다'}), 400
        
        # 기존 프로필 조회
        profile = recommender.user_profiles.get(user_id)
        if not profile:
            return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404
        
        # 허용된 필드만 업데이트
        allowed_fields = ['name', 'preferred_keywords', 'preferred_types', 'age_group', 'reading_frequency']
        
        old_strength = recommender.calculate_personalization_strength(user_id)
        
        for field in allowed_fields:
            if field in data:
                profile[field] = data[field]
        
        profile['last_active'] = datetime.now()
        profile['updated_at'] = datetime.now()
        
        # 사용자별 유사도 캐시 삭제 (재계산 필요)
        if user_id in recommender.user_book_similarity:
            del recommender.user_book_similarity[user_id]
        
        # 메모리와 Firebase에 저장
        recommender.user_profiles[user_id] = profile
        recommender.save_user_profile_to_firebase(user_id, profile)
        
        new_strength = recommender.calculate_personalization_strength(user_id)
        
        return jsonify({
            'message': '프로필이 업데이트되었습니다',
            'updated_fields': [field for field in allowed_fields if field in data],
            'personalization_change': {
                'old_strength': old_strength,
                'new_strength': new_strength,
                'improvement': new_strength - old_strength
            }
        }), 200
        
    except Exception as e:
        logger.error(f"프로필 업데이트 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<user_id>/personalization')
def get_user_personalization(user_id):
    """사용자 개인화 강도 조회"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        if user_id not in recommender.user_profiles:
            # Firebase에서 조회 시도
            if recommender.db:
                user_doc = recommender.db.collection('users').document(user_id).get()
                if user_doc.exists:
                    recommender.user_profiles[user_id] = user_doc.to_dict()
                else:
                    return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404
            else:
                return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404
        
        strength = recommender.calculate_personalization_strength(user_id)
        user_profile = recommender.user_profiles[user_id]
        user_ratings = recommender.load_user_ratings(user_id)
        
        # 개인화 수준 분류
        if strength >= 0.7:
            level = 'High'
            description = '매우 정확한 맞춤 추천 가능'
        elif strength >= 0.4:
            level = 'Medium'
            description = '좋은 수준의 맞춤 추천 가능'
        else:
            level = 'Low'
            description = '기본 추천 제공, 더 많은 정보 필요'
        
        personalization_info = {
            'user_id': user_id,
            'personalization_strength': strength,
            'personalization_level': level,
            'description': description,
            'contributing_factors': {
                'preferred_keywords_count': len(user_profile.get('preferred_keywords', [])),
                'has_age_info': bool(user_profile.get('age_group')),
                'has_reading_frequency': bool(user_profile.get('reading_frequency')),
                'feedback_count': len(user_ratings)
            },
            'improvement_suggestions': []
        }
        
        # 개선 제안
        if len(user_profile.get('preferred_keywords', [])) < 3:
            personalization_info['improvement_suggestions'].append('관심 키워드를 더 추가해보세요')
        
        if not user_profile.get('age_group'):
            personalization_info['improvement_suggestions'].append('연령대 정보를 추가해보세요')
        
        if len(user_ratings) < 5:
            personalization_info['improvement_suggestions'].append('더 많은 도서에 평점을 남겨보세요')
        
        return jsonify(personalization_info)
        
    except Exception as e:
        logger.error(f"개인화 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/books/<book_id>')
def get_book_detail(book_id):
    """특정 도서 상세 정보 조회"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        # Firebase에서 도서 정보 조회
        book_info = recommender.get_book_info_by_id(book_id)
        
        if book_info:
            # 추가 정보 포함
            book_detail = {
                'doc_id': book_id,
                'title': book_info.get('title'),
                'author': book_info.get('author'),
                'keyword': book_info.get('keyword'),
                'publisher': book_info.get('publisher'),
                'pub_year': book_info.get('pub_year'),
                'type': book_info.get('type'),
                'library_name': book_info.get('library_name'),
                'library_location': book_info.get('library_location'),
                'call_no': book_info.get('call_no'),
                'isbn': book_info.get('isbn'),
                'order': book_info.get('order'),
                'date': book_info.get('date')
            }
            
            return jsonify(book_detail)
        else:
            return jsonify({'error': '도서를 찾을 수 없습니다'}), 404
        
    except Exception as e:
        logger.error(f"도서 상세 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/keywords')
def get_keywords():
    """사용 가능한 키워드 목록 조회"""
    try:
        if books_df is None:
            return jsonify({'error': '도서 데이터가 로드되지 않았습니다'}), 500
        
        # 키워드별 도서 수와 함께 반환
        keyword_stats = books_df.groupby('keyword').agg({
            'doc_id': 'count',
            'pub_year': lambda x: pd.to_numeric(x, errors='coerce').max()
        }).reset_index()
        
        keyword_stats.columns = ['keyword', 'book_count', 'latest_year']
        keyword_stats = keyword_stats.sort_values('book_count', ascending=False)
        
        keywords = []
        for _, row in keyword_stats.iterrows():
            keywords.append({
                'keyword': row['keyword'],
                'book_count': int(row['book_count']),
                'latest_year': int(row['latest_year']) if pd.notna(row['latest_year']) else None
            })
        
        result = {
            'keywords': keywords,
            'total_keywords': len(keywords),
            'generated_at': datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"키워드 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<user_id>/recommendations/history')
def get_user_recommendation_history(user_id):
    """사용자 추천 이력 조회"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        # 사용자 피드백 기록 조회
        user_ratings = recommender.load_user_ratings(user_id)
        
        if user_ratings.empty:
            return jsonify({
                'user_id': user_id,
                'history': [],
                'total_feedback': 0,
                'average_rating': 0
            })
        
        history = []
        for _, rating in user_ratings.iterrows():
            book_info = recommender.get_book_info_by_id(rating['book_id'])
            
            history_item = {
                'book_id': rating['book_id'],
                'title': book_info.get('title', '정보없음') if book_info else '정보없음',
                'keyword': book_info.get('keyword', '정보없음') if book_info else '정보없음',
                'rating': rating['rating'],
                'timestamp': rating['timestamp'].isoformat() if hasattr(rating['timestamp'], 'isoformat') else str(rating['timestamp'])
            }
            history.append(history_item)
        
        # 최신순 정렬
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        result = {
            'user_id': user_id,
            'history': history,
            'total_feedback': len(history),
            'average_rating': float(user_ratings['rating'].mean()),
            'rating_distribution': user_ratings['rating'].value_counts().to_dict()
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"추천 이력 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare/users')
def compare_users():
    """사용자간 추천 결과 비교"""
    try:
        if not recommender or books_df is None:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        user_ids = request.args.get('user_ids', '').split(',')
        user_ids = [uid.strip() for uid in user_ids if uid.strip()]
        
        if len(user_ids) < 2:
            return jsonify({'error': '최소 2명의 사용자 ID가 필요합니다'}), 400
        
        if len(user_ids) > 5:
            return jsonify({'error': '최대 5명까지 비교 가능합니다'}), 400
        
        comparison_result = {
            'compared_users': user_ids,
            'user_profiles': {},
            'recommendations': {},
            'similarity_analysis': {}
        }
        
        # 각 사용자별 추천 생성
        for user_id in user_ids:
            if user_id not in recommender.user_profiles:
                continue
            
            # 프로필 정보
            profile = recommender.user_profiles[user_id]
            comparison_result['user_profiles'][user_id] = {
                'name': profile.get('name', ''),
                'preferred_keywords': profile.get('preferred_keywords', []),
                'age_group': profile.get('age_group', ''),
                'personalization_strength': recommender.calculate_personalization_strength(user_id)
            }
            
            # 추천 결과 (상위 5개)
            recommendations = recommender.generate_recommendations_for_frontend(user_id, books_df)
            personalized_books = recommendations.get('recommendations', {}).get('personalized', {}).get('books', [])
            
            comparison_result['recommendations'][user_id] = [
                {
                    'title': book['title'],
                    'keyword': book['keyword'],
                    'score': book['score']
                }
                for book in personalized_books[:5]
            ]
        
        # 유사도 분석
        valid_users = list(comparison_result['recommendations'].keys())
        
        for i, user1 in enumerate(valid_users):
            for user2 in valid_users[i+1:]:
                books1 = set(book['title'] for book in comparison_result['recommendations'][user1])
                books2 = set(book['title'] for book in comparison_result['recommendations'][user2])
                
                intersection = len(books1.intersection(books2))
                union = len(books1.union(books2))
                similarity = (intersection / union * 100) if union > 0 else 0
                
                comparison_result['similarity_analysis'][f"{user1}_vs_{user2}"] = {
                    'common_books': intersection,
                    'similarity_percentage': similarity,
                    'total_unique_books': union
                }
        
        return jsonify(comparison_result)
        
    except Exception as e:
        logger.error(f"사용자 비교 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ================== 에러 핸들러 ==================

@app.errorhandler(404)
def not_found(error):
    """404 에러 핸들러"""
    return jsonify({
        'error': 'Endpoint not found',
        'message': '요청한 엔드포인트를 찾을 수 없습니다',
        'available_endpoints': [
            '/api/health',
            '/api/books',
            '/api/recommendations/{user_id}',
            '/api/trending',
            '/api/users',
            '/api/feedback',
            '/api/analytics',
            '/api/users/{user_id}/personalization',
            '/api/compare/users'
        ]
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """405 에러 핸들러"""
    return jsonify({
        'error': 'Method not allowed',
        'message': '허용되지 않은 HTTP 메서드입니다'
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """500 에러 핸들러"""
    return jsonify({
        'error': 'Internal server error',
        'message': '서버 내부 오류가 발생했습니다'
    }), 500

# ================== 서버 시작 ==================

if __name__ == '__main__':
    print("🚀 개인화된 트렌드 기반 도서 추천 API 서버 시작")
    print("=" * 60)
    
    # 추천 시스템 초기화
    if init_recommender():
        print("✅ 개선된 추천 시스템 초기화 성공")
        print(f"📚 로드된 도서: {len(books_df)}권")
        print(f"👥 로드된 사용자: {len(recommender.user_profiles)}명")
        print(f"🔧 Firebase 연결: {'성공' if recommender.db else '실패'}")
        print(f"🎯 개인화 기능: 활성화")
        
        print("\n🌐 서버 엔드포인트:")
        print("   • http://localhost:5000/ - API 문서")
        print("   • http://localhost:5000/api/health - 상태 확인")
        print("   • http://localhost:5000/api/books - 도서 목록")
        print("   • http://localhost:5000/api/recommendations/{user_id} - 개인화 추천")
        print("   • http://localhost:5000/api/trending - 트렌딩 도서")
        print("   • http://localhost:5000/api/analytics - 분석 데이터")
        print("   • http://localhost:5000/api/users/{user_id}/personalization - 개인화 강도")
        
        print("\n🆕 개선된 기능:")
        print("   ✨ 사용자별 맞춤 추천 알고리즘")
        print("   🧠 실시간 피드백 학습")
        print("   📊 개인화 강도 측정")
        print("   🔍 사용자간 추천 비교")
        
        # Flask 서버 실행
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('DEBUG', 'False').lower() == 'true'
        
        print(f"\n🎯 서버가 포트 {port}에서 실행됩니다...")
        print("⏹️  서버를 중지하려면 Ctrl+C를 누르세요")
        
        app.run(host='0.0.0.0', port=port, debug=debug)
    else:
        print("❌ 추천 시스템 초기화 실패")
        print("\n🔧 문제 해결:")
        print("   1. Firebase 설정 파일 경로 확인")
        print("   2. 프로젝트 루트에 'csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json' 파일 존재 확인")
        print("   3. Firebase 데이터베이스에 도서 데이터 존재 여부 확인")
        print("   4. 네트워크 연결 상태 확인")
        print("   5. 필요한 Python 패키지 설치: pip install -r requirements.txt")
        print("   6. 개선된 trend_book_recommender.py 파일 확인")