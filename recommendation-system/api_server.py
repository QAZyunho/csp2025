from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
from recommender import BookRecommender
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)
recommender = None

def init_recommender():
    global recommender
    try:
        firebase_config = "csproject2025-cfcb7-firebase-adminsdk-fbsvc-f15f257ae3.json"
        recommender = BookRecommender(firebase_config)
        recommender.load_books()
        return True
    except Exception as e:
        logger.error(f"추천 시스템 초기화 실패: {e}"); return False
    
init_recommender()

@app.route('/')
def index(): return jsonify({'status': 'running'})

@app.route('/api/users')
def get_all_users_api():
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    users = recommender.get_all_users()
    user_ids = [user.get('user_id') for user in users if user.get('user_id')]
    return jsonify({'user_ids': sorted(user_ids)})

@app.route('/api/users/<user_id>')
def get_user_profile_api(user_id):
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    profile = recommender.load_user_profile(user_id)
    if not profile: return jsonify({'error': f"User '{user_id}' not found"}), 404
    return jsonify(profile)

@app.route('/api/users', methods=['POST'])
def create_user_api():
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    data = request.get_json()
    if not data or 'user_id' not in data or 'name' not in data: return jsonify({'error': 'user_id and name are required'}), 400
    user_profile = {'user_id': data['user_id'], 'name': data.get('name', ''), 'age_group': data.get('age_group', ''), 'reading_frequency': data.get('reading_frequency', ''), 'keyword_scores': data.get('keyword_scores', {}), 'preferred_types': data.get('preferred_types', []), 'created_at': datetime.now(), 'last_active': datetime.now()}
    recommender.db.collection('users').document(data['user_id']).set(user_profile)
    recommender.user_profiles[data['user_id']] = user_profile
    return jsonify({'message': 'User created successfully', 'user': user_profile}), 201

@app.route('/api/trends/latest')
def get_latest_trends_api():
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    trends = recommender.get_latest_trends()
    return jsonify({'trends': trends})

@app.route('/api/books/by_keyword/<user_id>')
def get_books_by_keyword_api(user_id):
    keyword = request.args.get('keyword')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 5, type=int)

    if not keyword: return jsonify({'error': 'keyword parameter is required'}), 400
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    result = recommender.get_books_for_keyword(user_id, keyword, page=page, page_size=page_size)
    
    # keyword와 함께 결과 반환
    return jsonify({'keyword': keyword, **result})

@app.route('/api/recommendations/general/<user_id>')
def get_general_recommendations_api(user_id):
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    result = recommender.get_general_recommendations(user_id)
    return jsonify(result)

@app.route('/api/feedback', methods=['POST'])
def submit_feedback_api():
    if not recommender: return jsonify({'error': 'Recommender not initialized'}), 500
    data = request.get_json()
    required = ['user_id', 'book_id', 'rating', 'keyword']
    if not all(k in data for k in required): return jsonify({'error': 'Missing required fields'}), 400
    recommender.save_feedback(data['user_id'], data['keyword'], data['rating'], data['book_id'])
    return jsonify({'message': 'Feedback received successfully'})

if __name__ == '__main__':
    print("📚 간소화된 도서 추천 API 서버 시작")
    
    if recommender:
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