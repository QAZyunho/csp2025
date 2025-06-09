import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from typing import List, Dict
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookRecommender:
    def __init__(self, firebase_config_path: str):
        self.db = self.init_firebase(firebase_config_path)
        self.books_df = None
        self.user_profiles = {}
        self.latest_trends = []

    def init_firebase(self, config_path: str):
        try:
            cred = credentials.Certificate(config_path)
            if not firebase_admin._apps:
                app = firebase_admin.initialize_app(cred)
            else:
                app = firebase_admin.get_app()
            gcloud_credentials = app.credential.get_credential()
            project_id = app.project_id
            db_client = firestore.Client(project=project_id, credentials=gcloud_credentials, database='csproject2025')
            logger.info(f"Firebase 연결 성공 (Project: {project_id}, DB: csproject2025)")
            return db_client
        except Exception as e:
            logger.error(f"Firebase 연결 실패: {e}"); return None

    def load_books(self) -> pd.DataFrame:
        """Firestore의 모든 책 데이터를 로드하여 DataFrame으로 만듭니다 (팀원분의 원래 방식)."""
        if self.books_df is not None and not self.books_df.empty:
            logger.info(f"기존에 로드된 {len(self.books_df)}개 도서 데이터를 사용합니다.")
            return self.books_df
        logger.info("Firestore에서 모든 도서 데이터를 로드합니다...")
        books_data = []
        try:
            source_ref = self.db.collection('source')
            date_docs = source_ref.stream()
            for date_doc in date_docs:
                keywords_ref = date_doc.reference.collection('keywords')
                for keyword_doc in keywords_ref.stream():
                    keyword = keyword_doc.id
                    books_ref = keyword_doc.reference.collection('books')
                    for book_doc in books_ref.stream():
                        book_data = book_doc.to_dict()
                        book_data['doc_id'] = f"{date_doc.id}_{keyword}_{book_doc.id}"
                        book_data['keyword'] = keyword
                        books_data.append(book_data)
            self.books_df = pd.DataFrame(books_data) if books_data else pd.DataFrame()
            logger.info(f"성공! {len(self.books_df)}개 도서를 로드하여 메모리에 저장했습니다.")
        except Exception as e:
            logger.error(f"도서 데이터 로드 중 오류: {e}")
            self.books_df = pd.DataFrame()
        return self.books_df

    def load_user_profile(self, user_id: str) -> Dict:
        if user_id in self.user_profiles: return self.user_profiles[user_id]
        if self.db:
            user_doc = self.db.collection('users').document(user_id).get()
            if user_doc.exists:
                profile = user_doc.to_dict(); self.user_profiles[user_id] = profile; return profile
        return {}
        
    def get_all_users(self) -> List[Dict]:
        if not self.db: return []
        users_ref = self.db.collection('users').stream()
        return [user.to_dict() for user in users_ref]

    def get_latest_trends(self) -> List[Dict]:
        """[최종 수정] 정렬을 사용하지 않고, 모든 문서 ID를 가져와 직접 최신 문서를 찾습니다."""
        if self.latest_trends:
            logger.info("캐시된 최신 트렌드를 사용합니다.")
            return self.latest_trends
            
        if not self.db: return []
        
        try:
            logger.info("Firestore 'trend' 컬렉션에서 최신 날짜의 트렌드를 로드합니다 (정렬 없는 방식)...")
            
            # 1. 컬렉션의 모든 문서 참조를 가져옵니다.
            docs_ref = self.db.collection('trend').list_documents()
            doc_ids = [doc.id for doc in docs_ref]
            
            if not doc_ids:
                logger.warning("'trend' 컬렉션에 문서가 없습니다.")
                return []
            
            # 2. 파이썬에서 직접 ID를 정렬하여 최신 날짜를 찾습니다.
            latest_doc_id = sorted(doc_ids, reverse=True)[0]
            logger.info(f"찾아낸 최신 트렌드 문서 ID: '{latest_doc_id}'")

            # 3. 최신 ID로 문서 하나만 정확히 가져옵니다.
            doc = self.db.collection('trend').document(latest_doc_id).get()
            
            if doc.exists:
                logger.info(f"성공! 최신 트렌드 문서 '{doc.id}'의 내용을 가져왔습니다.")
                trends_data = doc.to_dict().get('trends', [])
                self.latest_trends = trends_data # 메모리에 캐시
                return trends_data
            else:
                # 이 경우는 거의 없지만, ID 목록은 있는데 문서를 못가져온 경우를 대비한 안전장치
                logger.error(f"'{latest_doc_id}' 문서를 가져오는 데 실패했습니다.")
                return []

        except Exception as e: 
            logger.error(f"최신 트렌드 로드 실패: {e}"); return []
        
    def get_books_for_keyword(self, user_id: str, keyword: str, max_books: int = 5) -> List[Dict]:
        """미리 로드된 DataFrame에서 특정 키워드의 책 목록을 점수화하여 반환합니다."""
        if self.books_df is None or self.books_df.empty: return []

        user_profile = self.load_user_profile(user_id)
        preferred_keywords = user_profile.get('preferred_keywords', [])
        keyword_books_df = self.books_df[self.books_df['keyword'] == keyword]
        
        books_with_scores = []
        for _, book_row in keyword_books_df.iterrows():
            score = 0.5
            if book_row.get('keyword') in preferred_keywords: score += 0.4
            try:
                pub_year = int(book_row.get('pub_year', 0))
                current_year = datetime.datetime.now().year
                if current_year - pub_year <= 3: score += 0.2
                elif current_year - pub_year <= 10: score += 0.1
            except (ValueError, TypeError): pass
            
            book_dict = book_row.to_dict(); book_dict['score'] = score
            books_with_scores.append(book_dict)
            
        books_with_scores.sort(key=lambda x: x['score'], reverse=True)
        return books_with_scores[:max_books]

    def get_general_recommendations(self, user_id: str) -> Dict:
        """선호 키워드를 제외한 새로운 트렌드 기반 추천"""
        user_profile = self.load_user_profile(user_id)
        preferred_keywords = user_profile.get('preferred_keywords', [])
        latest_trends = self.get_latest_trends()
        
        new_trend_keywords = [t['keyword'] for t in latest_trends if t.get('keyword') and t.get('keyword') not in preferred_keywords]
        
        if not new_trend_keywords:
            return {'category': '더 이상 새로운 트렌드가 없습니다', 'books': []}
            
        discovery_keyword = random.choice(new_trend_keywords)
        books = self.get_books_for_keyword(user_id, discovery_keyword)
        
        return {'category': f"새로운 추천: {discovery_keyword}", 'books': books}
        
    def save_feedback(self, user_id: str, keyword: str, rating: int, book_id: str = None):
        """사용자 피드백 저장 및 프로필/캐시 업데이트"""
        if not self.db: return
        try:
            feedback_data = {'user_id': user_id, 'book_id': book_id, 'keyword': keyword, 'rating': rating, 'timestamp': datetime.datetime.now()}
            self.db.collection('feedback').add(feedback_data)
            user_ref = self.db.collection('users').document(user_id)
            update_data = {}
            if rating >= 4:
                update_data['preferred_keywords'] = firestore.ArrayUnion([keyword])
            elif rating <= 2:
                update_data['preferred_keywords'] = firestore.ArrayRemove([keyword])
            if update_data:
                user_ref.update(update_data)
                logger.info(f"사용자 프로필 업데이트: {user_id} -> {update_data}")
                if user_id in self.user_profiles:
                    del self.user_profiles[user_id]
        except Exception as e:
            logger.error(f"피드백 저장 실패: {e}")