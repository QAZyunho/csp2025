#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드 기반 도서 추천 API 서버
Flask + Firebase 연동
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import sys
import logging
from datetime import datetime
import json

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
    """추천 시스템 초기화"""
    global recommender, books_df
    try:
        firebase_config = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json'
        )
        
        if not os.path.exists(firebase_config):
            logger.error(f"Firebase 설정 파일을 찾을 수 없습니다: {firebase_config}")
            return False
            
        recommender = TrendBookRecommender(firebase_config)
        books_df = recommender.load_books_from_firebase()
        recommender.build_content_features(books_df)
        logger.info("✅ 추천 시스템 초기화 완료")
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
        <title>트렌드 기반 도서 추천 API</title>
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
            h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            h2 { color: #555; margin-top: 30px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📚 트렌드 기반 도서 추천 API</h1>
            <p>Firebase와 연동된 개인화 도서 추천 서비스입니다.</p>
            
            <div class="status {{ 'healthy' if book_count > 0 else 'unhealthy' }}">
                <strong>서비스 상태:</strong> {{ 'healthy' if book_count > 0 else 'unhealthy' }} | 
                <strong>로드된 도서:</strong> {{ book_count }}권 | 
                <strong>시작 시간:</strong> {{ start_time }}
            </div>
            
            <h2>📋 API 엔드포인트</h2>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/health</h3>
                <p><strong>설명:</strong> 서비스 상태 확인</p>
                <p><strong>응답:</strong> 서비스 상태, 로드된 도서 수, 추천 시스템 준비 상태</p>
            </div>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/books</h3>
                <p><strong>설명:</strong> 전체 도서 목록 조회</p>
                <p><strong>Parameters:</strong></p>
                <ul>
                    <li><code>page</code> - 페이지 번호 (기본값: 1)</li>
                    <li><code>size</code> - 페이지 크기 (기본값: 20)</li>
                    <li><code>keyword</code> - 키워드 필터</li>
                </ul>
            </div>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/recommendations/{user_id}</h3>
                <p><strong>설명:</strong> 사용자 맞춤 추천</p>
                <p><strong>Parameters:</strong></p>
                <ul>
                    <li><code>top_k</code> - 추천 도서 수 (기본값: 10)</li>
                </ul>
            </div>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/trending</h3>
                <p><strong>설명:</strong> 트렌딩 도서 목록</p>
                <p><strong>Parameters:</strong></p>
                <ul>
                    <li><code>limit</code> - 결과 수 (기본값: 10)</li>
                </ul>
            </div>
            
            <div class="endpoint">
                <h3><span class="method post">POST</span>/api/users</h3>
                <p><strong>설명:</strong> 새 사용자 생성</p>
                <p><strong>Body Example:</strong></p>
                <pre><code>{
  "user_id": "user_123",
  "name": "홍길동",
  "preferred_keywords": ["인공지능", "소설"],
  "age_group": "30대"
}</code></pre>
            </div>
            
            <div class="endpoint">
                <h3><span class="method post">POST</span>/api/feedback</h3>
                <p><strong>설명:</strong> 사용자 피드백 제출</p>
                <p><strong>Body Example:</strong></p>
                <pre><code>{
  "user_id": "user_123",
  "book_id": "250606_인공지능_book_001", 
  "rating": 5,
  "feedback_text": "매우 유익했습니다"
}</code></pre>
            </div>
            
            <div class="endpoint">
                <h3><span class="method">GET</span>/api/analytics</h3>
                <p><strong>설명:</strong> 피드백 분석 결과</p>
                <p><strong>응답:</strong> 전체 피드백 수, 평균 평점, 키워드별 성과</p>
            </div>
            
            <div class="endpoint">
                <h3><span class="method post">POST</span>/api/demo/generate</h3>
                <p><strong>설명:</strong> 데모 데이터 생성</p>
                <p><strong>Parameters:</strong></p>
                <ul>
                    <li><code>num_users</code> - 생성할 사용자 수 (기본값: 20)</li>
                </ul>
            </div>
            
            <h2>📖 사용 예제</h2>
            <pre><code># 서비스 상태 확인
curl http://localhost:5000/api/health

# 사용자 추천 조회
curl http://localhost:5000/api/recommendations/demo_user_001

# 피드백 제출
curl -X POST http://localhost:5000/api/feedback \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "demo_user_001", "book_id": "250606_인공지능_book_001", "rating": 5}'

# 트렌딩 도서 조회  
curl http://localhost:5000/api/trending</code></pre>
            
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
        'firebase_connected': recommender.db is not None if recommender else False
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
    """사용자 맞춤 추천"""
    try:
        if not recommender or books_df is None:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        top_k = int(request.args.get('top_k', 10))
        
        # 사용자 평점 데이터 로드 (Firebase에서)
        user_ratings = recommender.load_user_ratings(user_id)
        
        # 추천 생성
        recommendations = recommender.generate_recommendations_for_frontend(
            user_id, books_df, user_ratings
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
    """새 사용자 생성"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        data = request.get_json()
        
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id가 필요합니다'}), 400
        
        # 사용자 ID 중복 체크
        if data['user_id'] in recommender.user_profiles:
            return jsonify({'error': '이미 존재하는 사용자입니다'}), 409
        
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
                'age_group': user_profile['age_group']
            }
        }), 201
        
    except Exception as e:
        logger.error(f"사용자 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """사용자 피드백 제출"""
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
        
        # 피드백 처리
        success = recommender.process_user_feedback(
            user_id=data['user_id'],
            book_id=data['book_id'],
            rating=data['rating'],
            feedback_text=data.get('feedback_text', '')
        )
        
        if success:
            return jsonify({
                'message': '피드백이 처리되었습니다',
                'feedback': {
                    'user_id': data['user_id'],
                    'rating': data['rating'],
                    'timestamp': datetime.now().isoformat()
                }
            }), 200
        else:
            return jsonify({'error': '피드백 처리에 실패했습니다'}), 500
        
    except Exception as e:
        logger.error(f"피드백 처리 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    """피드백 분석 결과"""
    try:
        if not recommender:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        analytics = recommender.get_feedback_analytics()
        
        # 추가 통계 정보
        analytics['system_stats'] = {
            'total_books': len(books_df) if books_df is not None else 0,
            'total_users': len(recommender.user_profiles),
            'unique_keywords': books_df['keyword'].nunique() if books_df is not None else 0,
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f"분석 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/demo/generate', methods=['POST'])
def generate_demo_data():
    """데모 데이터 생성"""
    try:
        if not recommender or books_df is None:
            return jsonify({'error': '추천 시스템이 준비되지 않았습니다'}), 500
        
        num_users = int(request.args.get('num_users', 20))
        
        if num_users > 100:
            return jsonify({'error': '사용자 수는 100명을 초과할 수 없습니다'}), 400
        
        # 데모 사용자 생성
        demo_users = recommender.generate_demo_users(num_users)
        
        # 데모 평점 생성
        demo_ratings = recommender.generate_demo_ratings(demo_users, books_df, (3, 10))
        
        # Firebase에 저장
        recommender.save_demo_data_to_firebase(demo_users, demo_ratings)
        
        result = {
            'message': '데모 데이터가 생성되었습니다',
            'users_created': len(demo_users),
            'ratings_created': len(demo_ratings),
            'sample_user_ids': [user['user_id'] for user in demo_users[:5]],
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
            # 민감한 정보 제외하고 반환
            safe_profile = {
                'user_id': profile.get('user_id'),
                'name': profile.get('name'),
                'preferred_keywords': profile.get('preferred_keywords', []),
                'preferred_types': profile.get('preferred_types', []),
                'age_group': profile.get('age_group'),
                'reading_frequency': profile.get('reading_frequency'),
                'created_at': profile.get('created_at'),
                'last_active': profile.get('last_active')
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
        
        for field in allowed_fields:
            if field in data:
                profile[field] = data[field]
        
        profile['last_active'] = datetime.now()
        profile['updated_at'] = datetime.now()
        
        # 메모리와 Firebase에 저장
        recommender.user_profiles[user_id] = profile
        recommender.save_user_profile_to_firebase(user_id, profile)
        
        return jsonify({
            'message': '프로필이 업데이트되었습니다',
            'updated_fields': [field for field in allowed_fields if field in data]
        }), 200
        
    except Exception as e:
        logger.error(f"프로필 업데이트 실패: {str(e)}")
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
            '/api/analytics'
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
    print("🚀 트렌드 기반 도서 추천 API 서버 시작")
    print("=" * 50)
    
    # 추천 시스템 초기화
    if init_recommender():
        print("✅ 추천 시스템 초기화 성공")
        print(f"📚 로드된 도서: {len(books_df)}권")
        print(f"🔧 Firebase 연결: {'성공' if recommender.db else '실패'}")
        print("\n🌐 서버 엔드포인트:")
        print("   • http://localhost:5000/ - API 문서")
        print("   • http://localhost:5000/api/health - 상태 확인")
        print("   • http://localhost:5000/api/books - 도서 목록")
        print("   • http://localhost:5000/api/recommendations/{user_id} - 개인 추천")
        print("   • http://localhost:5000/api/trending - 트렌딩 도서")
        print("   • http://localhost:5000/api/analytics - 분석 데이터")
        
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