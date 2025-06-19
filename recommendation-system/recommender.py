import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from typing import List, Dict
import logging
import random
import math
import unicodedata

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
        """[최종판] 유니코드 정규화 및 공백제거 후 중복을 제거한 DataFrame을 만듭니다."""
        if self.books_df is not None and not self.books_df.empty:
            logger.info(f"기존에 로드된 {len(self.books_df)}개 도서 데이터를 사용합니다.")
            return self.books_df
        
        logger.info("Firestore에서 모든 도서 데이터를 로드합니다...")
        # ... (데이터 로드 try-except 구문 앞부분은 이전과 동일합니다) ...
        # books_data 리스트를 만드는 for문까지는 모두 동일합니다.
        try:
            source_ref = self.db.collection('source')
            date_docs = source_ref.stream()
            books_data = []
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

            if not books_data:
                self.books_df = pd.DataFrame(); return self.books_df

            self.books_df = pd.DataFrame(books_data)
            initial_count = len(self.books_df)
            logger.info(f"성공! {initial_count}개 도서 데이터를 로드했습니다.")
            
            # --- [최종 중복 제거 로직] ---
            if 'title' in self.books_df.columns and 'author' in self.books_df.columns:
                logger.info("데이터 정규화 및 최종 중복 제거를 시작합니다...")

                # 1. 비교를 위한 정규화된 임시 컬럼 생성
                # NFC 방식은 가장 표준적인 유니코드 정규화 방식입니다.
                self.books_df['title_norm'] = self.books_df['title'].astype(str).apply(lambda x: unicodedata.normalize('NFC', x).strip())
                self.books_df['author_norm'] = self.books_df['author'].astype(str).apply(lambda x: unicodedata.normalize('NFC', x).strip())
                
                # 2. 정규화된 임시 컬럼을 기준으로 중복 제거
                # inplace=False를 사용하고 결과를 다시 할당하여 더 확실하게 만듭니다.
                self.books_df = self.books_df.drop_duplicates(subset=['title_norm', 'author_norm'], keep='first')
                
                # 3. 임시로 만들었던 정규화 컬럼을 최종적으로 삭제
                self.books_df = self.books_df.drop(columns=['title_norm', 'author_norm'])

                final_count = len(self.books_df)
                logger.info(f"중복 제거 완료! {initial_count - final_count}개의 중복 항목을 제거했으며, 최종 {final_count}개 도서를 메모리에 저장했습니다.")
            # --------------------------------

        except Exception as e:
            logger.error(f"도서 데이터 로드 중 오류: {e}", exc_info=True)
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
        
    def get_all_trend_dates(self) -> List[str]:
        """Firestore 'trend' 컬렉션의 모든 문서 ID(날짜)를 가져와 정렬하여 반환합니다."""
        if not self.db: return []
        try:
            docs_ref = self.db.collection('trend').list_documents()
            # ID가 'YYMMDD' 형식이므로, 문자열 정렬을 위해 숫자 변환 없이 그대로 사용하고 내림차순 정렬
            doc_ids = sorted([doc.id for doc in docs_ref], reverse=True)
            return doc_ids
        except Exception as e:
            logger.error(f"모든 트렌드 날짜 로드 실패: {e}")
            return []

    def get_trend_by_date(self, date_id: str) -> List[Dict]:
        """특정 날짜 ID의 트렌드 문서를 가져옵니다."""
        if not self.db: return []
        try:
            doc_ref = self.db.collection('trend').document(date_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict().get('trends', [])
            else:
                logger.warning(f"'{date_id}'에 해당하는 트렌드 문서를 찾을 수 없습니다.")
                return []
        except Exception as e:
            logger.error(f"'{date_id}' 트렌드 데이터 로드 실패: {e}")
            return []

    def _clean_nan_values(self, data_dict: Dict) -> Dict:
        """재귀적으로 딕셔너리의 NaN 값을 None으로 바꿉니다."""
        for key, value in data_dict.items():
            if isinstance(value, float) and math.isnan(value):
                data_dict[key] = None
            elif isinstance(value, dict):
                self._clean_nan_values(value)
        return data_dict

    def get_books_for_keyword(self, user_id: str, keyword: str, page: int = 1, page_size: int = 5) -> Dict:
        """미리 로드된 DataFrame에서 특정 키워드의 책 목록을 페이지에 맞게 점수화하여 반환합니다."""
        if self.books_df is None or self.books_df.empty:
            return {'books': [], 'total_books': 0}

        user_profile = self.load_user_profile(user_id)
        keyword_scores = user_profile.get('keyword_scores', {})
        preferred_keywords_from_scores = [k for k, v in keyword_scores.items() if v >= 4]

        keyword_books_df = self.books_df[self.books_df['keyword'] == keyword]
        
        if keyword_books_df.empty:
            return {'books': [], 'total_books': 0}

        books_with_scores = []
        for _, book_row in keyword_books_df.iterrows():
            score = 0.5
            if book_row.get('keyword') in preferred_keywords_from_scores: score += 0.4
            
            try:
                pub_year = int(book_row.get('pub_year', 0))
                current_year = datetime.datetime.now().year
                if current_year - pub_year <= 3: score += 0.2
                elif current_year - pub_year <= 10: score += 0.1
            except (ValueError, TypeError): pass
            
            book_dict = book_row.to_dict()
            book_dict['score'] = score
            cleaned_book_dict = self._clean_nan_values(book_dict)
            books_with_scores.append(cleaned_book_dict)
            
        books_with_scores.sort(key=lambda x: x['score'], reverse=True)

        # [핵심 수정!] 페이지네이션 로직 추가
        total_books = len(books_with_scores)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        paginated_books = books_with_scores[start_index:end_index]

        return {'books': paginated_books, 'total_books': total_books}

    def get_general_recommendations(self, user_id: str) -> Dict:
        """선호 키워드를 제외한 새로운 트렌드 기반 추천"""
        user_profile = self.load_user_profile(user_id)
        keyword_scores = user_profile.get('keyword_scores', {})
        # 점수가 4점 이상인 키워드를 사용자의 '선호 키워드'로 간주합니다.
        preferred_keywords_from_scores = [k for k, v in keyword_scores.items() if v >= 4]
        latest_trends = self.get_latest_trends()
        
        new_trend_keywords = [t['keyword'] for t in latest_trends if t.get('keyword') and t.get('keyword') not in preferred_keywords_from_scores]
        
        if not new_trend_keywords:
            return {'category': '더 이상 새로운 트렌드가 없습니다', 'books': []}
            
        discovery_keyword = random.choice(new_trend_keywords)
        books = self.get_books_for_keyword(user_id, discovery_keyword)
        
        return {'category': f"새로운 추천: {discovery_keyword}", 'books': books}
        
    def save_feedback(self, user_id: str, keyword: str, rating: int, book_id: str = None):
        """사용자 피드백을 기반으로 keyword_scores를 트랜잭션을 사용해 안전하게 업데이트합니다."""
        if not self.db:
            logger.error("DB 연결이 없어 피드백을 저장할 수 없습니다.")
            return

        try:
            # 1. 피드백 로그는 트랜잭션과 별개로 저장
            feedback_data = {'user_id': user_id, 'book_id': book_id, 'keyword': keyword, 'rating': rating, 'timestamp': datetime.datetime.now()}
            self.db.collection('feedback').add(feedback_data)
            
            # 2. 트랜잭션을 사용하여 점수 업데이트
            user_ref = self.db.collection('users').document(user_id)

            @firestore.transactional
            def update_in_transaction(transaction, user_ref_param):
                snapshot = user_ref_param.get(transaction=transaction)
                if not snapshot.exists:
                    logger.warning(f"트랜잭션 중 사용자를 찾을 수 없음: {user_id}")
                    return None, "Not Found"

                user_profile = snapshot.to_dict()
                keyword_scores = user_profile.get('keyword_scores', {})

                # [핵심 수정!] 키워드의 존재 여부에 따라 로직 분기
                # -----------------------------------------------------
                # Case 1: 이미 점수가 있는 키워드 -> 평점과 상관없이 점수 가감
                if keyword in keyword_scores:
                    current_score = keyword_scores[keyword]
                    score_change = rating - 3
                    new_score = current_score + score_change
                    transaction.update(user_ref_param, {f'keyword_scores.{keyword}': new_score})
                    return new_score, "Updated"
                
                # Case 2: 새로운 키워드 -> 3점 이상일 때만 추가
                else:
                    if rating >= 3:
                        # 새 키워드는 (기본점수 3 + 변동폭) = 평점으로 바로 추가
                        new_score = rating
                        transaction.update(user_ref_param, {f'keyword_scores.{keyword}': 3})
                        return 3, "Added"
                    else:
                        # 평점이 3점 미만이면 아무 작업도 하지 않음
                        return None, "Ignored"
                # -----------------------------------------------------

            # 트랜잭션 실행 및 결과 로깅
            new_score_result, status = update_in_transaction(self.db.transaction(), user_ref)

            if status == "Updated":
                logger.info(f"사용자({user_id}) 키워드({keyword}) 점수 업데이트! 새 점수: {new_score_result} (별점: {rating})")
            elif status == "Added":
                logger.info(f"사용자({user_id}) 신규 키워드({keyword}) 추가! 점수: {new_score_result} (별점: {rating})")
            elif status == "Ignored":
                logger.info(f"사용자({user_id}) 신규 키워드({keyword})는 평점이 3점 미만이라 추가하지 않음 (별점: {rating})")
            
            # 프로필 캐시 삭제
            if user_id in self.user_profiles:
                del self.user_profiles[user_id]

        except Exception as e:
            logger.error(f"피드백 저장 실패: {e}", exc_info=True)