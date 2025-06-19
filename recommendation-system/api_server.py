# 개선된 api_server.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import traceback
from datetime import datetime
from recommender import BookRecommender
import sys
import os

# 로깅 설정 개선
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/api.log') if os.path.exists('/var/log') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용
recommender = None

def init_recommender():
    """추천 시스템 초기화 - 에러 처리 강화"""
    global recommender
    try:
        # 환경변수에서 Firebase 설정 경로 확인
        firebase_config = os.environ.get('FIREBASE_CONFIG_PATH', 
                                       '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json')
        
        if not os.path.exists(firebase_config):
            logger.error(f"❌ Firebase 설정 파일이 없습니다: {firebase_config}")
            return False
        
        logger.info(f"🔧 Firebase 설정 파일 사용: {firebase_config}")
        recommender = BookRecommender(firebase_config)
        
        # 도서 데이터 로드
        books_df = recommender.load_books()
        logger.info(f"📚 도서 로드 완료: {len(books_df)}권")
        
        # 트렌드 데이터 로드
        trends = recommender.get_latest_trends()
        logger.info(f"📈 트렌드 로드 완료: {len(trends)}개")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 추천 시스템 초기화 실패: {str(e)}")
        logger.error(f"상세 오류: {traceback.format_exc()}")
        return False

@app.errorhandler(404)
def not_found(error):
    """404 에러 핸들러"""
    return jsonify({
        'error': 'Not Found',
        'message': '요청한 엔드포인트를 찾을 수 없습니다.',
        'available_endpoints': [
            'GET /',
            'GET /api/users',
            'POST /api/users',
            'GET /api/users/<user_id>',
            'GET /api/trends/latest',
            'GET /api/books/by_keyword/<user_id>',
            'GET /api/recommendations/general/<user_id>',
            'POST /api/feedback'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500 에러 핸들러"""
    logger.error(f"내부 서버 오류: {str(error)}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': '서버에서 오류가 발생했습니다.',
        'timestamp': datetime.now().isoformat()
    }), 500

@app.route('/')
def index():
    """상태 확인 엔드포인트"""
    status = {
        'status': 'running',
        'service': 'book-recommendation-api',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0'
    }
    
    if recommender:
        stats = recommender.get_recommendation_stats()
        status.update(stats)
    else:
        status['recommender'] = 'not_initialized'
    
    return jsonify(status)

@app.route('/api/users')
def get_all_users_api():
    """사용자 목록 조회"""
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        users = recommender.get_all_users()
        user_ids = [user.get('user_id') for user in users if user.get('user_id')]
        
        logger.info(f"👥 사용자 목록 요청: {len(user_ids)}명 반환")
        
        return jsonify({
            'user_ids': sorted(user_ids),
            'total_count': len(user_ids),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 사용자 목록 조회 오류: {str(e)}")
        return jsonify({'error': 'Failed to fetch users', 'message': str(e)}), 500

@app.route('/api/users/<user_id>')
def get_user_profile_api(user_id):
    """사용자 프로필 조회"""
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        profile = recommender.load_user_profile(user_id)
        
        if not profile: 
            logger.warning(f"⚠️ 사용자 '{user_id}'를 찾을 수 없음")
            return jsonify({'error': f"User '{user_id}' not found"}), 404
        
        logger.info(f"👤 사용자 프로필 조회: {user_id}")
        
        # 응답에 추가 정보 포함
        response_data = profile.copy()
        response_data['timestamp'] = datetime.now().isoformat()
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ 사용자 프로필 조회 오류: {str(e)}")
        return jsonify({'error': 'Failed to fetch user profile', 'message': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user_api():
    """신규 사용자 생성"""
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        data = request.get_json()
        
        if not data or 'user_id' not in data or 'name' not in data: 
            return jsonify({
                'error': 'Invalid request', 
                'message': 'user_id and name are required'
            }), 400
        
        # 사용자 프로필 구성
        user_profile = {
            'user_id': data['user_id'],
            'name': data.get('name', ''),
            'age_group': data.get('age_group', ''),
            'reading_frequency': data.get('reading_frequency', ''),
            'preferred_keywords': data.get('preferred_keywords', []),
            'preferred_types': data.get('preferred_types', []),
            'created_at': datetime.now(),
            'last_active': datetime.now()
        }
        
        # Firebase에 저장
        recommender.db.collection('users').document(data['user_id']).set(user_profile)
        
        # 캐시에 추가
        recommender.user_profiles[data['user_id']] = user_profile
        
        logger.info(f"👤 신규 사용자 생성: {data['user_id']}")
        
        return jsonify({
            'message': 'User created successfully', 
            'user': user_profile,
            'timestamp': datetime.now().isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"❌ 사용자 생성 오류: {str(e)}")
        return jsonify({'error': 'Failed to create user', 'message': str(e)}), 500

@app.route('/api/trends/latest')
def get_latest_trends_api():
    """최신 트렌드 조회"""
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        trends = recommender.get_latest_trends()
        
        logger.info(f"📈 트렌드 데이터 요청: {len(trends)}개 반환")
        
        return jsonify({
            'trends': trends,
            'total_count': len(trends),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 트렌드 조회 오류: {str(e)}")
        return jsonify({'error': 'Failed to fetch trends', 'message': str(e)}), 500

@app.route('/api/books/by_keyword/<user_id>')
def get_books_by_keyword_api(user_id):
    """키워드별 도서 추천"""
    keyword = request.args.get('keyword')
    max_books = request.args.get('max_books', 5, type=int)
    
    if not keyword: 
        return jsonify({'error': 'keyword parameter is required'}), 400
    
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        books = recommender.get_books_for_keyword(user_id, keyword, max_books)
        
        logger.info(f"🔍 키워드 검색: '{keyword}' by {user_id} -> {len(books)}권")
        
        return jsonify({
            'keyword': keyword,
            'books': books,
            'user_id': user_id,
            'total_count': len(books),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 키워드별 도서 조회 오류: {str(e)}")
        return jsonify({'error': 'Failed to fetch books', 'message': str(e)}), 500

@app.route('/api/recommendations/general/<user_id>')
def get_general_recommendations_api(user_id):
    """일반 맞춤 추천"""
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        result = recommender.get_general_recommendations(user_id)
        
        logger.info(f"🎯 맞춤 추천: {user_id} -> {result.get('category', 'Unknown')}")
        
        # 응답에 추가 메타데이터 포함
        result['user_id'] = user_id
        result['timestamp'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ 맞춤 추천 오류: {str(e)}")
        return jsonify({
            'error': 'Failed to generate recommendations', 
            'message': str(e),
            'category': '추천 서비스 오류',
            'books': []
        }), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback_api():
    """피드백 제출"""
    if not recommender: 
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        data = request.get_json()
        required = ['user_id', 'book_id', 'rating', 'keyword']
        
        if not all(k in data for k in required): 
            return jsonify({
                'error': 'Missing required fields', 
                'required': required
            }), 400
        
        # 평점 유효성 검사
        rating = data['rating']
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({
                'error': 'Invalid rating', 
                'message': 'Rating must be an integer between 1 and 5'
            }), 400
        
        recommender.save_feedback(
            data['user_id'], 
            data['keyword'], 
            rating, 
            data['book_id']
        )
        
        logger.info(f"💾 피드백 제출: {data['user_id']} -> {data['keyword']} ({rating}점)")
        
        return jsonify({
            'message': 'Feedback received successfully',
            'user_id': data['user_id'],
            'keyword': data['keyword'],
            'rating': rating,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 피드백 제출 오류: {str(e)}")
        return jsonify({'error': 'Failed to submit feedback', 'message': str(e)}), 500

@app.route('/api/stats')
def get_stats_api():
    """시스템 통계 조회"""
    if not recommender:
        return jsonify({'error': 'Recommender not initialized'}), 500
    
    try:
        stats = recommender.get_recommendation_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"❌ 통계 조회 오류: {str(e)}")
        return jsonify({'error': 'Failed to fetch stats', 'message': str(e)}), 500

if __name__ == '__main__':
    print("📚 향상된 도서 추천 API 서버 시작")
    print("=" * 50)
    
    if init_recommender():
        print("✅ 추천 시스템 초기화 성공")
        
        if recommender:
            stats = recommender.get_recommendation_stats()
            print(f"📖 로드된 도서: {stats.get('total_books', 0)}권")
            print(f"🏷️ 키워드: {stats.get('total_keywords', 0)}개")
            print(f"📈 트렌드: {stats.get('total_trends', 0)}개")
        
        print("\n🌐 API 엔드포인트:")
        print("   • GET  / - 상태 확인")
        print("   • GET  /api/users - 사용자 목록")
        print("   • POST /api/users - 사용자 생성")
        print("   • GET  /api/users/<user_id> - 사용자 프로필")
        print("   • GET  /api/trends/latest - 최신 트렌드")
        print("   • GET  /api/books/by_keyword/<user_id> - 키워드별 도서")
        print("   • GET  /api/recommendations/general/<user_id> - 맞춤 추천")
        print("   • POST /api/feedback - 피드백 제출")
        print("   • GET  /api/stats - 시스템 통계")
        
        print(f"\n🚀 서버 실행: http://0.0.0.0:5001")
        
        app.run(host='0.0.0.0', port=5001, debug=False)
    else:
        print("❌ 추천 시스템 초기화 실패")
        print("💡 Firebase 설정과 데이터를 확인해주세요.")
        sys.exit(1)