#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간소화된 도서 추천 API 서버
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime
from recommender import BookRecommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 전역 추천 시스템
recommender = None

def init_recommender():
    """추천 시스템 초기화"""
    global recommender
    try:
        firebase_config = '../csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json'
        recommender = BookRecommender(firebase_config)
        recommender.load_books()
        logger.info("추천 시스템 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"추천 시스템 초기화 실패: {e}")
        return False

@app.route('/')
def index():
    """API 상태"""
    return jsonify({
        'status': 'running',
        'service': '도서 추천 API',
        'timestamp': datetime.now().isoformat(),
        'endpoints': [
            '/api/recommendations/{user_id}?books_per_category=5',
            '/api/feedback',
            '/api/books'
        ]
    })

@app.route('/api/recommendations/<user_id>')
def get_recommendations(user_id):
    """사용자 카테고리 추천 조회"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템 초기화 필요'}), 500
        
        books_per_category = int(request.args.get('books_per_category', 5))
        use_cache = request.args.get('cache', 'true').lower() == 'true'
        
        category_data = recommender.get_category_recommendation(user_id, books_per_category, use_cache)
        
        if not category_data or not category_data.get('books'):
            return jsonify({'error': '추천 데이터를 생성할 수 없습니다'}), 500
        
        return jsonify({
            'user_id': user_id,
            'category': category_data['category'],
            'books': category_data['books'],
            'total_books_in_category': category_data['total_books_in_category'],
            'books_count': len(category_data['books']),
            'cached': use_cache,
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"카테고리 추천 조회 실패: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """피드백 제출"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템 초기화 필요'}), 500
        
        data = request.get_json()
        
        required_fields = ['user_id', 'book_id', 'rating']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} 필수'}), 400
        
        if not (1 <= data['rating'] <= 5):
            return jsonify({'error': '평점은 1-5 사이'}), 400
        
        recommender.save_feedback(data['user_id'], data['book_id'], data['rating'])
        
        return jsonify({
            'message': '피드백 저장 완료',
            'user_id': data['user_id'],
            'rating': data['rating']
        })
        
    except Exception as e:
        logger.error(f"피드백 처리 실패: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/books')
def get_books():
    """도서 목록 조회"""
    try:
        if not recommender or recommender.books_df is None:
            return jsonify({'error': '도서 데이터 없음'}), 500
        
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        
        books = recommender.books_df.iloc[start_idx:end_idx]
        
        books_list = []
        for _, book in books.iterrows():
            books_list.append({
                'doc_id': book['doc_id'],
                'title': book['title'],
                'author': book['author'],
                'keyword': book['keyword'],
                'publisher': book['publisher'],
                'pub_year': book['pub_year']
            })
        
        return jsonify({
            'books': books_list,
            'page': page,
            'size': size,
            'total': len(recommender.books_df)
        })
        
    except Exception as e:
        logger.error(f"도서 목록 조회 실패: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    """사용자 생성"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템 초기화 필요'}), 500
        
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id 필수'}), 400
        
        user_profile = {
            'user_id': data['user_id'],
            'name': data.get('name', ''),
            'preferred_keywords': data.get('preferred_keywords', []),
            'created_at': datetime.now()
        }
        
        # Firebase에 저장
        if recommender.db:
            recommender.db.collection('users').document(data['user_id']).set(user_profile)
            recommender.user_profiles[data['user_id']] = user_profile
        
        return jsonify({
            'message': '사용자 생성 완료',
            'user_id': data['user_id']
        }), 201
        
    except Exception as e:
        logger.error(f"사용자 생성 실패: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("📚 간소화된 도서 추천 API 서버 시작")
    
    if init_recommender():
        print("✅ 추천 시스템 초기화 성공")
        print(f"📖 로드된 도서: {len(recommender.books_df)}권")
        print("\n🌐 API 엔드포인트:")
        print("   • GET  /api/recommendations/{user_id}?books_per_category=5 - 카테고리 추천")
        print("   • POST /api/feedback - 피드백 제출")
        print("   • GET  /api/books - 도서 목록")
        print("   • POST /api/users - 사용자 생성")
        
        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ 추천 시스템 초기화 실패")