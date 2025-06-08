#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드 기반 개인화 도서 추천 시스템
Firebase 연동, 사용자 선호도 기반 추천
"""

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
import firebase_admin
from firebase_admin import credentials, firestore
import json
import datetime
import random
from typing import List, Dict, Optional, Tuple
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrendBookRecommender:
    """트렌드 기반 개인화 도서 추천 시스템"""
    
    def __init__(self, firebase_config_path: str = None):
        """초기화"""
        self.init_firebase(firebase_config_path)
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,  # 한국어는 별도 불용어 처리 필요
            ngram_range=(1, 2)
        )
        self.svd = TruncatedSVD(n_components=50, random_state=42)
        self.book_features = None
        self.user_profiles = {}
        
    def init_firebase(self, config_path: str):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                if config_path:
                    cred = credentials.Certificate(config_path)
                    firebase_admin.initialize_app(cred)
                else:
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
            
            self.db = firestore.client(database_id='csproject2025')
            logger.info("✅ Firebase 연결 성공")
        except Exception as e:
            logger.error(f"❌ Firebase 연결 실패: {str(e)}")
            self.db = None

    # ================== 1단계: 추천 알고리즘 구축 ==================
    
    def load_books_from_firebase(self, date_filter: str = None) -> pd.DataFrame:
        """Firebase에서 도서 데이터 로드"""
        if not self.db:
            raise Exception("Firebase 연결이 없습니다")
        
        try:
            books_data = []
            source_ref = self.db.collection('source')
            
            if date_filter:
                # 특정 날짜 데이터만 로드
                date_doc = source_ref.document(date_filter).get()
                if date_doc.exists:
                    self._extract_books_from_date_doc(date_doc, books_data)
            else:
                # 최근 5일 데이터 로드
                docs = source_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(5).stream()
                for doc in docs:
                    self._extract_books_from_date_doc(doc, books_data)
            
            if not books_data:
                raise Exception("로드된 도서 데이터가 없습니다")
            
            df = pd.DataFrame(books_data)
            logger.info(f"✅ {len(df)}개 도서 데이터 로드")
            return df
            
        except Exception as e:
            logger.error(f"❌ 도서 데이터 로드 실패: {str(e)}")
            raise
    
    def _extract_books_from_date_doc(self, date_doc, books_data: List[Dict]):
        """날짜 문서에서 도서 데이터 추출"""
        keywords_ref = date_doc.reference.collection('keywords')
        keyword_docs = keywords_ref.stream()
        
        for keyword_doc in keyword_docs:
            keyword = keyword_doc.id
            books_ref = keyword_doc.reference.collection('books')
            book_docs = books_ref.stream()
            
            for book_doc in book_docs:
                book_data = book_doc.to_dict()
                book_data['doc_id'] = f"{date_doc.id}_{keyword}_{book_doc.id}"
                book_data['date'] = date_doc.id
                books_data.append(book_data)
    
    def build_content_features(self, books_df: pd.DataFrame):
        """도서 콘텐츠 기반 특성 벡터 구축"""
        try:
            # 텍스트 특성 결합 (제목, 저자, 키워드)
            books_df['content_text'] = (
                books_df['title'].fillna('') + ' ' +
                books_df['author'].fillna('') + ' ' + 
                books_df['keyword'].fillna('') + ' ' +
                books_df['type'].fillna('')
            )
            
            # TF-IDF 벡터화
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(books_df['content_text'])
            
            # 차원 축소 (협업 필터링과 결합하기 위해)
            content_features = self.svd.fit_transform(tfidf_matrix)
            
            # 추가 수치 특성
            numerical_features = []
            
            # 발행년도 특성 (최신성)
            current_year = datetime.datetime.now().year
            pub_years = pd.to_numeric(books_df['pub_year'], errors='coerce').fillna(2000)
            recency_scores = np.clip((pub_years - 1950) / (current_year - 1950), 0, 1)
            numerical_features.append(recency_scores.values.reshape(-1, 1))
            
            # 키워드 인기도 (같은 키워드의 도서 수)
            keyword_counts = books_df.groupby('keyword').size()
            popularity_scores = books_df['keyword'].map(keyword_counts)
            popularity_scores = (popularity_scores - popularity_scores.min()) / (popularity_scores.max() - popularity_scores.min())
            numerical_features.append(popularity_scores.values.reshape(-1, 1))
            
            # 특성 결합
            if numerical_features:
                numerical_array = np.hstack(numerical_features)
                self.book_features = np.hstack([content_features, numerical_array])
            else:
                self.book_features = content_features
            
            logger.info(f"✅ 도서 특성 벡터 구축 완료: {self.book_features.shape}")
            return self.book_features
            
        except Exception as e:
            logger.error(f"❌ 특성 벡터 구축 실패: {str(e)}")
            raise
    
    def calculate_content_similarity(self, books_df: pd.DataFrame) -> np.ndarray:
        """콘텐츠 기반 유사도 계산"""
        if self.book_features is None:
            self.build_content_features(books_df)
        
        similarity_matrix = cosine_similarity(self.book_features)
        return similarity_matrix
    
    def collaborative_filtering(self, user_ratings: pd.DataFrame, books_df: pd.DataFrame) -> np.ndarray:
        """협업 필터링 기반 추천"""
        try:
            # 사용자-도서 평점 매트릭스 생성
            user_book_matrix = user_ratings.pivot_table(
                index='user_id', 
                columns='book_id', 
                values='rating',
                fill_value=0
            )
            
            # 사용자 간 유사도 계산
            user_similarity = cosine_similarity(user_book_matrix)
            
            # 평점 예측 (사용자 기반 협업 필터링)
            predictions = np.dot(user_similarity, user_book_matrix.values) / np.sum(np.abs(user_similarity), axis=1)[:, np.newaxis]
            
            return predictions, user_book_matrix.index, user_book_matrix.columns
            
        except Exception as e:
            logger.error(f"❌ 협업 필터링 실패: {str(e)}")
            return None, None, None
    
    def hybrid_recommendation(self, user_id: str, books_df: pd.DataFrame, 
                            user_ratings: pd.DataFrame = None, top_k: int = 10) -> List[Dict]:
        """하이브리드 추천 (콘텐츠 + 협업 필터링)"""
        try:
            recommendations = []
            
            # 1. 콘텐츠 기반 추천
            content_scores = self.get_content_based_recommendations(user_id, books_df)
            
            # 2. 협업 필터링 추천 (평점 데이터가 있는 경우)
            collaborative_scores = None
            if user_ratings is not None and len(user_ratings) > 0:
                collaborative_scores = self.get_collaborative_recommendations(user_id, user_ratings, books_df)
            
            # 3. 트렌드 기반 가중치
            trend_scores = self.get_trend_based_scores(books_df)
            
            # 4. 하이브리드 점수 계산
            for idx, book in books_df.iterrows():
                final_score = 0.0
                
                # 콘텐츠 기반 점수 (40%)
                if content_scores is not None:
                    final_score += 0.4 * content_scores.get(idx, 0)
                
                # 협업 필터링 점수 (30%)
                if collaborative_scores is not None:
                    final_score += 0.3 * collaborative_scores.get(book['doc_id'], 0)
                
                # 트렌드 점수 (30%)
                final_score += 0.3 * trend_scores.get(idx, 0)
                
                recommendations.append({
                    'doc_id': book['doc_id'],
                    'title': book['title'],
                    'author': book['author'],
                    'keyword': book['keyword'],
                    'publisher': book['publisher'],
                    'pub_year': book['pub_year'],
                    'type': book['type'],
                    'library_name': book.get('library_name', ''),
                    'library_location': book.get('library_location', ''),
                    'call_no': book.get('call_no', ''),
                    'score': final_score,
                    'recommendation_reason': self.generate_recommendation_reason(book, content_scores, collaborative_scores, trend_scores, idx)
                })
            
            # 점수 순으로 정렬하여 상위 k개 반환
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            return recommendations[:top_k]
            
        except Exception as e:
            logger.error(f"❌ 하이브리드 추천 실패: {str(e)}")
            return []
    
    def get_content_based_recommendations(self, user_id: str, books_df: pd.DataFrame) -> Dict[int, float]:
        """콘텐츠 기반 추천 점수"""
        user_profile = self.user_profiles.get(user_id, {})
        preferred_keywords = user_profile.get('preferred_keywords', [])
        preferred_types = user_profile.get('preferred_types', [])
        
        scores = {}
        for idx, book in books_df.iterrows():
            score = 0.0
            
            # 선호 키워드 매칭
            if book['keyword'] in preferred_keywords:
                score += 0.6
            
            # 선호 자료 유형 매칭
            if book['type'] in preferred_types:
                score += 0.4
            
            scores[idx] = score
        
        return scores
    
    def get_collaborative_recommendations(self, user_id: str, user_ratings: pd.DataFrame, books_df: pd.DataFrame) -> Dict[str, float]:
        """협업 필터링 기반 추천 점수"""
        predictions, user_indices, book_indices = self.collaborative_filtering(user_ratings, books_df)
        
        if predictions is None:
            return {}
        
        scores = {}
        if user_id in user_indices:
            user_idx = list(user_indices).index(user_id)
            user_predictions = predictions[user_idx]
            
            for book_idx, score in enumerate(user_predictions):
                if book_idx < len(book_indices):
                    book_id = book_indices[book_idx]
                    scores[book_id] = float(score)
        
        return scores
    
    def get_trend_based_scores(self, books_df: pd.DataFrame) -> Dict[int, float]:
        """트렌드 기반 점수"""
        scores = {}
        
        # 최신성 점수
        current_year = datetime.datetime.now().year
        
        for idx, book in books_df.iterrows():
            score = 0.0
            
            # 발행년도 기반 점수
            pub_year = pd.to_numeric(book['pub_year'], errors='coerce')
            if pd.notna(pub_year):
                recency_score = max(0, 1 - (current_year - pub_year) / 20)  # 20년 기준
                score += 0.5 * recency_score
            
            # 키워드 인기도
            keyword_count = len(books_df[books_df['keyword'] == book['keyword']])
            popularity_score = min(1.0, keyword_count / 10)  # 정규화
            score += 0.5 * popularity_score
            
            scores[idx] = score
        
        return scores
    
    def generate_recommendation_reason(self, book: pd.Series, content_scores: Dict, 
                                     collaborative_scores: Dict, trend_scores: Dict, idx: int) -> str:
        """추천 이유 생성"""
        reasons = []
        
        if content_scores and content_scores.get(idx, 0) > 0.5:
            reasons.append(f"'{book['keyword']}' 관심사와 일치")
        
        if collaborative_scores and collaborative_scores.get(book.get('doc_id'), 0) > 0.5:
            reasons.append("유사한 취향의 사용자가 선호")
        
        if trend_scores and trend_scores.get(idx, 0) > 0.5:
            reasons.append("최근 트렌드 도서")
        
        if not reasons:
            reasons.append("다양한 주제 탐색을 위한 추천")
        
        return " • ".join(reasons)

    # ================== 2단계: 사용자 선호도 데모데이터 ==================
    
    def generate_demo_users(self, num_users: int = 50) -> List[Dict]:
        """데모 사용자 데이터 생성"""
        keywords = ['인공지능', '자율주행', '기후 변화', '블록체인', '문학', '소설', '사회', '법', '윤리']
        book_types = ['도서', '기사', '신문', '멀티미디어', '단행본', '연속간행물']
        
        demo_users = []
        
        for i in range(num_users):
            user_id = f"demo_user_{i:03d}"
            
            # 랜덤한 선호도 생성
            preferred_keywords = random.sample(keywords, random.randint(2, 5))
            preferred_types = random.sample(book_types, random.randint(1, 3))
            
            user_profile = {
                'user_id': user_id,
                'name': f"사용자{i+1}",
                'age_group': random.choice(['20대', '30대', '40대', '50대']),
                'preferred_keywords': preferred_keywords,
                'preferred_types': preferred_types,
                'reading_frequency': random.choice(['주 1회', '주 2-3회', '매일']),
                'created_at': datetime.datetime.now(),
                'last_active': datetime.datetime.now()
            }
            
            demo_users.append(user_profile)
            self.user_profiles[user_id] = user_profile
        
        logger.info(f"✅ {num_users}명의 데모 사용자 생성")
        return demo_users
    
    def generate_demo_ratings(self, users: List[Dict], books_df: pd.DataFrame, 
                            ratings_per_user: Tuple[int, int] = (5, 15)) -> pd.DataFrame:
        """데모 평점 데이터 생성"""
        ratings_data = []
        
        for user in users:
            user_id = user['user_id']
            preferred_keywords = user['preferred_keywords']
            
            # 사용자별 평점 개수
            num_ratings = random.randint(ratings_per_user[0], ratings_per_user[1])
            
            # 선호 키워드 도서에 높은 확률로 높은 평점
            for _ in range(num_ratings):
                book = books_df.sample(1).iloc[0]
                
                # 선호 키워드면 높은 평점 확률 증가
                if book['keyword'] in preferred_keywords:
                    rating = random.choices([3, 4, 5], weights=[0.2, 0.3, 0.5])[0]
                else:
                    rating = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.2, 0.4, 0.2, 0.1])[0]
                
                ratings_data.append({
                    'user_id': user_id,
                    'book_id': book['doc_id'],
                    'rating': rating,
                    'timestamp': datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 365))
                })
        
        ratings_df = pd.DataFrame(ratings_data)
        logger.info(f"✅ {len(ratings_df)}개의 데모 평점 생성")
        return ratings_df
    
    def save_demo_data_to_firebase(self, users: List[Dict], ratings_df: pd.DataFrame):
        """데모 데이터를 Firebase에 저장"""
        if not self.db:
            logger.error("Firebase 연결이 없습니다")
            return
        
        try:
            batch = self.db.batch()
            
            # 사용자 프로필 저장
            users_ref = self.db.collection('users')
            for user in users:
                user_doc_ref = users_ref.document(user['user_id'])
                batch.set(user_doc_ref, user)
            
            # 평점 데이터 저장
            ratings_ref = self.db.collection('feedback')
            for _, rating in ratings_df.iterrows():
                rating_doc_ref = ratings_ref.document()
                batch.set(rating_doc_ref, rating.to_dict())
            
            batch.commit()
            logger.info("✅ 데모 데이터 Firebase 저장 완료")
            
        except Exception as e:
            logger.error(f"❌ 데모 데이터 저장 실패: {str(e)}")

    # ================== 3단계: 프론트엔드용 데이터 형태 ==================
    
    def generate_recommendations_for_frontend(self, user_id: str, books_df: pd.DataFrame, 
                                            user_ratings: pd.DataFrame = None) -> Dict:
        """프론트엔드용 추천 결과 생성"""
        try:
            # 개인화 추천
            personalized_recs = self.hybrid_recommendation(user_id, books_df, user_ratings, top_k=10)
            
            # 트렌드 추천 (최신순)
            trend_recs = self.get_trending_books(books_df, top_k=5)
            
            # 카테고리별 추천
            category_recs = self.get_category_recommendations(books_df, top_k=3)
            
            # 사용자 프로필
            user_profile = self.user_profiles.get(user_id, {})
            
            frontend_data = {
                'user_id': user_id,
                'user_profile': {
                    'name': user_profile.get('name', '사용자'),
                    'preferred_keywords': user_profile.get('preferred_keywords', []),
                    'age_group': user_profile.get('age_group', ''),
                    'reading_frequency': user_profile.get('reading_frequency', '')
                },
                'recommendations': {
                    'personalized': {
                        'title': '맞춤 추천',
                        'description': '회원님의 관심사를 바탕으로 추천해드립니다',
                        'books': personalized_recs
                    },
                    'trending': {
                        'title': '트렌드 도서',
                        'description': '지금 주목받고 있는 화제의 도서들',
                        'books': trend_recs
                    },
                    'categories': category_recs
                },
                'stats': {
                    'total_books': len(books_df),
                    'total_keywords': books_df['keyword'].nunique(),
                    'recommendation_count': len(personalized_recs)
                },
                'generated_at': datetime.datetime.now().isoformat()
            }
            
            return frontend_data
            
        except Exception as e:
            logger.error(f"❌ 프론트엔드 데이터 생성 실패: {str(e)}")
            return {}
    
    def get_trending_books(self, books_df: pd.DataFrame, top_k: int = 5) -> List[Dict]:
        """트렌딩 도서 목록"""
        # 최신 발행년도와 키워드 인기도 기준
        trending_scores = []
        
        for idx, book in books_df.iterrows():
            score = 0.0
            
            # 발행년도 점수
            pub_year = pd.to_numeric(book['pub_year'], errors='coerce')
            if pd.notna(pub_year):
                current_year = datetime.datetime.now().year
                recency_score = max(0, 1 - (current_year - pub_year) / 10)
                score += recency_score
            
            # 키워드 빈도 점수
            keyword_count = len(books_df[books_df['keyword'] == book['keyword']])
            popularity_score = min(1.0, keyword_count / 5)
            score += popularity_score
            
            trending_scores.append((idx, score))
        
        # 점수순 정렬
        trending_scores.sort(key=lambda x: x[1], reverse=True)
        
        trending_books = []
        for idx, score in trending_scores[:top_k]:
            book = books_df.iloc[idx]
            trending_books.append({
                'doc_id': book['doc_id'],
                'title': book['title'],
                'author': book['author'],
                'keyword': book['keyword'],
                'publisher': book['publisher'],
                'pub_year': book['pub_year'],
                'type': book['type'],
                'library_name': book.get('library_name', ''),
                'score': score,
                'trending_reason': f"'{book['keyword']}' 분야 인기 도서"
            })
        
        return trending_books
    
    def get_category_recommendations(self, books_df: pd.DataFrame, top_k: int = 3) -> Dict:
        """카테고리별 추천"""
        categories = {}
        
        # 키워드별로 그룹화
        for keyword in books_df['keyword'].unique():
            keyword_books = books_df[books_df['keyword'] == keyword]
            
            # 각 카테고리에서 상위 도서 선택
            top_books = []
            for idx, book in keyword_books.head(top_k).iterrows():
                top_books.append({
                    'doc_id': book['doc_id'],
                    'title': book['title'],
                    'author': book['author'],
                    'publisher': book['publisher'],
                    'pub_year': book['pub_year'],
                    'type': book['type'],
                    'library_name': book.get('library_name', '')
                })
            
            categories[keyword] = {
                'title': f'{keyword} 도서',
                'description': f'{keyword} 관련 추천 도서',
                'books': top_books
            }
        
        return categories

    # ================== 4단계: 사용자 피드백 반영 ==================
    
    def process_user_feedback(self, user_id: str, book_id: str, rating: int, 
                            feedback_text: str = None) -> bool:
        """사용자 피드백 처리"""
        try:
            if not self.db:
                logger.error("Firebase 연결이 없습니다")
                return False
            
            # 평점 데이터 저장
            feedback_data = {
                'user_id': user_id,
                'book_id': book_id,
                'rating': rating,
                'feedback_text': feedback_text or '',
                'timestamp': datetime.datetime.now(),
                'processed': False
            }
            
            self.db.collection('feedback').add(feedback_data)
            
            # 사용자 프로필 업데이트
            self.update_user_profile_from_feedback(user_id, book_id, rating)
            
            logger.info(f"✅ 사용자 {user_id} 피드백 처리 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 피드백 처리 실패: {str(e)}")
            return False
    
    def update_user_profile_from_feedback(self, user_id: str, book_id: str, rating: int):
        """피드백을 바탕으로 사용자 프로필 업데이트"""
        try:
            # 해당 도서 정보 조회
            book_info = self.get_book_info_by_id(book_id)
            if not book_info:
                return
            
            # 사용자 프로필 가져오기
            if user_id not in self.user_profiles:
                self.user_profiles[user_id] = {
                    'user_id': user_id,
                    'preferred_keywords': [],
                    'preferred_types': [],
                    'disliked_keywords': [],
                    'disliked_types': []
                }
            
            profile = self.user_profiles[user_id]
            
            # 평점에 따른 선호도 업데이트
            if rating >= 4:  # 긍정적 피드백
                if book_info['keyword'] not in profile['preferred_keywords']:
                    profile['preferred_keywords'].append(book_info['keyword'])
                
                if book_info['type'] not in profile['preferred_types']:
                    profile['preferred_types'].append(book_info['type'])
                
                # 부정적 목록에서 제거
                if book_info['keyword'] in profile.get('disliked_keywords', []):
                    profile['disliked_keywords'].remove(book_info['keyword'])
                    
            elif rating <= 2:  # 부정적 피드백
                if book_info['keyword'] not in profile.get('disliked_keywords', []):
                    if 'disliked_keywords' not in profile:
                        profile['disliked_keywords'] = []
                    profile['disliked_keywords'].append(book_info['keyword'])
                
                # 선호 목록에서 제거 (조건부)
                if book_info['keyword'] in profile['preferred_keywords']:
                    # 여러 번의 부정적 피드백이 있을 때만 제거
                    negative_count = self.count_negative_feedback(user_id, book_info['keyword'])
                    if negative_count >= 2:
                        profile['preferred_keywords'].remove(book_info['keyword'])
            
            # Firebase에 업데이트된 프로필 저장
            self.save_user_profile_to_firebase(user_id, profile)
            
        except Exception as e:
            logger.error(f"❌ 사용자 프로필 업데이트 실패: {str(e)}")
    
    def get_book_info_by_id(self, book_id: str) -> Dict:
        """도서 ID로 도서 정보 조회"""
        # book_id 형식: "날짜_키워드_book_xxx"
        try:
            parts = book_id.split('_')
            if len(parts) >= 3:
                date_id = parts[0]
                keyword = parts[1]
                book_doc_id = '_'.join(parts[2:])
                
                if self.db:
                    book_ref = (self.db.collection('source')
                              .document(date_id)
                              .collection('keywords')
                              .document(keyword)
                              .collection('books')
                              .document(book_doc_id))
                    
                    book_doc = book_ref.get()
                    if book_doc.exists:
                        return book_doc.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 도서 정보 조회 실패: {str(e)}")
            return None
    
    def count_negative_feedback(self, user_id: str, keyword: str) -> int:
        """특정 키워드에 대한 사용자의 부정적 피드백 횟수 조회"""
        try:
            if not self.db:
                return 0
            
            feedback_ref = self.db.collection('feedback')
            negative_feedback = feedback_ref.where('user_id', '==', user_id).where('rating', '<=', 2).stream()
            
            count = 0
            for feedback_doc in negative_feedback:
                feedback_data = feedback_doc.to_dict()
                book_info = self.get_book_info_by_id(feedback_data['book_id'])
                if book_info and book_info.get('keyword') == keyword:
                    count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"❌ 부정적 피드백 횟수 조회 실패: {str(e)}")
            return 0
    
    def save_user_profile_to_firebase(self, user_id: str, profile: Dict):
        """사용자 프로필을 Firebase에 저장"""
        try:
            if self.db:
                profile['updated_at'] = datetime.datetime.now()
                self.db.collection('users').document(user_id).set(profile, merge=True)
                logger.info(f"✅ 사용자 {user_id} 프로필 업데이트")
        except Exception as e:
            logger.error(f"❌ 사용자 프로필 저장 실패: {str(e)}")
    
    def load_user_ratings(self, user_id: str) -> pd.DataFrame:
        """사용자 평점 데이터 로드"""
        try:
            if not self.db:
                return pd.DataFrame()
            
            ratings_ref = self.db.collection('feedback')
            user_ratings_docs = ratings_ref.where('user_id', '==', user_id).stream()
            
            ratings_data = []
            for doc in user_ratings_docs:
                data = doc.to_dict()
                ratings_data.append({
                    'user_id': user_id,
                    'book_id': data.get('book_id'),
                    'rating': data.get('rating'),
                    'timestamp': data.get('timestamp')
                })
            
            return pd.DataFrame(ratings_data)
            
        except Exception as e:
            logger.error(f"사용자 평점 로드 실패: {str(e)}")
            return pd.DataFrame()
    
    def get_feedback_analytics(self, date_from: datetime.datetime = None) -> Dict:
        """피드백 분석 결과"""
        try:
            if not self.db:
                return {}
            
            feedback_ref = self.db.collection('feedback')
            if date_from:
                feedback_docs = feedback_ref.where('timestamp', '>=', date_from).stream()
            else:
                feedback_docs = feedback_ref.stream()
            
            ratings = []
            keyword_ratings = {}
            
            for doc in feedback_docs:
                data = doc.to_dict()
                rating = data.get('rating', 0)
                ratings.append(rating)
                
                # 도서 정보 조회
                book_info = self.get_book_info_by_id(data.get('book_id', ''))
                if book_info:
                    keyword = book_info.get('keyword', '')
                    if keyword not in keyword_ratings:
                        keyword_ratings[keyword] = []
                    keyword_ratings[keyword].append(rating)
            
            analytics = {
                'total_feedback': len(ratings),
                'average_rating': np.mean(ratings) if ratings else 0,
                'rating_distribution': {
                    '1': ratings.count(1),
                    '2': ratings.count(2),
                    '3': ratings.count(3),
                    '4': ratings.count(4),
                    '5': ratings.count(5)
                },
                'keyword_performance': {}
            }
            
            # 키워드별 성과
            for keyword, keyword_rating_list in keyword_ratings.items():
                analytics['keyword_performance'][keyword] = {
                    'count': len(keyword_rating_list),
                    'average_rating': np.mean(keyword_rating_list),
                    'satisfaction_rate': len([r for r in keyword_rating_list if r >= 4]) / len(keyword_rating_list)
                }
            
            return analytics
            
        except Exception as e:
            logger.error(f"❌ 피드백 분석 실패: {str(e)}")
            return {}

    # ================== 통합 실행 함수 ==================
    
    def run_full_pipeline(self, firebase_config_path: str = None, 
                         generate_demo: bool = True) -> Dict:
        """전체 파이프라인 실행"""
        try:
            logger.info("🚀 트렌드 기반 도서 추천 시스템 시작")
            
            # 1. Firebase에서 도서 데이터 로드
            books_df = self.load_books_from_firebase()
            logger.info(f"📚 {len(books_df)}개 도서 로드")
            
            # 2. 콘텐츠 특성 벡터 구축
            self.build_content_features(books_df)
            
            # 3. 데모 데이터 생성 (옵션)
            demo_users = []
            demo_ratings = pd.DataFrame()
            
            if generate_demo:
                demo_users = self.generate_demo_users(num_users=20)
                demo_ratings = self.generate_demo_ratings(demo_users, books_df)
                self.save_demo_data_to_firebase(demo_users, demo_ratings)
            
            # 4. 샘플 사용자에 대한 추천 생성
            sample_user_id = demo_users[0]['user_id'] if demo_users else 'demo_user_001'
            recommendations = self.generate_recommendations_for_frontend(
                sample_user_id, books_df, demo_ratings
            )
            
            # 5. 결과 반환
            result = {
                'status': 'success',
                'books_count': len(books_df),
                'users_count': len(demo_users),
                'ratings_count': len(demo_ratings),
                'sample_recommendations': recommendations,
                'analytics': self.get_feedback_analytics()
            }
            
            logger.info("✅ 파이프라인 실행 완료")
            return result
            
        except Exception as e:
            logger.error(f"❌ 파이프라인 실행 실패: {str(e)}")
            return {'status': 'error', 'message': str(e)}


# ================== 실행 예제 ==================

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="트렌드 기반 도서 추천 시스템")
    parser.add_argument("--firebase_config", "-f", 
                        default='../csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                        help="Firebase 설정 파일 경로")
    parser.add_argument("--user_id", "-u", default="demo_user_001", 
                        help="추천을 받을 사용자 ID")
    parser.add_argument("--generate_demo", "-d", action='store_true', 
                        help="데모 데이터 생성")
    parser.add_argument("--top_k", "-k", type=int, default=10, 
                        help="추천 도서 수")
    
    args = parser.parse_args()
    
    print("📖 트렌드 기반 개인화 도서 추천 시스템")
    print("=" * 60)
    
    try:
        # 추천 시스템 초기화
        recommender = TrendBookRecommender(args.firebase_config)
        
        if args.generate_demo:
            # 전체 파이프라인 실행 (데모 데이터 포함)
            result = recommender.run_full_pipeline(
                firebase_config_path=args.firebase_config,
                generate_demo=True
            )
            
            print(f"\n📊 실행 결과:")
            print(f"   • 처리된 도서: {result.get('books_count', 0)}권")
            print(f"   • 생성된 사용자: {result.get('users_count', 0)}명")
            print(f"   • 생성된 평점: {result.get('ratings_count', 0)}개")
            
            # 샘플 추천 결과 출력
            sample_recs = result.get('sample_recommendations', {})
            if sample_recs:
                personalized = sample_recs.get('recommendations', {}).get('personalized', {})
                books = personalized.get('books', [])
                
                print(f"\n🎯 샘플 사용자 맞춤 추천 (상위 5개):")
                for i, book in enumerate(books[:5], 1):
                    print(f"   {i}. {book['title']} - {book['author']}")
                    print(f"      키워드: {book['keyword']} | 점수: {book['score']:.3f}")
                    print(f"      추천이유: {book['recommendation_reason']}")
                    print()
        
        else:
            # 기존 데이터로 추천만 실행
            books_df = recommender.load_books_from_firebase()
            recommendations = recommender.generate_recommendations_for_frontend(
                args.user_id, books_df
            )
            
            print(f"\n🎯 사용자 '{args.user_id}' 맞춤 추천:")
            personalized = recommendations.get('recommendations', {}).get('personalized', {})
            books = personalized.get('books', [])
            
            for i, book in enumerate(books[:args.top_k], 1):
                print(f"   {i}. {book['title']} - {book['author']}")
                print(f"      키워드: {book['keyword']} | 점수: {book['score']:.3f}")
                print(f"      추천이유: {book['recommendation_reason']}")
                print()
        
        # 피드백 시뮬레이션 예제
        print("\n📝 피드백 처리 예제:")
        if args.generate_demo:
            sample_book_id = result['sample_recommendations']['recommendations']['personalized']['books'][0]['doc_id']
            success = recommender.process_user_feedback(
                user_id=args.user_id,
                book_id=sample_book_id,
                rating=5,
                feedback_text="매우 유익한 도서였습니다!"
            )
            print(f"   • 피드백 처리 {'성공' if success else '실패'}")
        
        print("\n✅ 시스템 실행 완료!")
        
    except Exception as e:
        print(f"\n❌ 시스템 실행 실패: {str(e)}")


if __name__ == "__main__":
    main()