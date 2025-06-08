#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개인화된 트렌드 기반 도서 추천 시스템
Firebase 연동, 사용자별 맞춤 추천 제공
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
    """개인화된 트렌드 기반 도서 추천 시스템"""
    
    def __init__(self, firebase_config_path: str = None):
        """초기화"""
        self.init_firebase(firebase_config_path)
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,
            ngram_range=(1, 2)
        )
        self.svd = TruncatedSVD(n_components=50, random_state=42)
        self.book_features = None
        self.user_profiles = {}
        self.user_book_similarity = {}  # 사용자별 도서 유사도 캐시
        
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

    def load_books_from_firebase(self, date_filter: str = None) -> pd.DataFrame:
        """Firebase에서 도서 데이터 로드"""
        if not self.db:
            raise Exception("Firebase 연결이 없습니다")
        
        try:
            books_data = []
            source_ref = self.db.collection('source')
            
            if date_filter:
                date_doc = source_ref.document(date_filter).get()
                if date_doc.exists:
                    self._extract_books_from_date_doc(date_doc, books_data)
            else:
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
            # 텍스트 특성 결합
            books_df['content_text'] = (
                books_df['title'].fillna('') + ' ' +
                books_df['author'].fillna('') + ' ' + 
                books_df['keyword'].fillna('') + ' ' +
                books_df['type'].fillna('')
            )
            
            # TF-IDF 벡터화
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(books_df['content_text'])
            
            # 차원 축소
            content_features = self.svd.fit_transform(tfidf_matrix)
            
            # 추가 수치 특성
            numerical_features = []
            
            # 발행년도 특성
            current_year = datetime.datetime.now().year
            pub_years = pd.to_numeric(books_df['pub_year'], errors='coerce').fillna(2000)
            recency_scores = np.clip((pub_years - 1950) / (current_year - 1950), 0, 1)
            numerical_features.append(recency_scores.values.reshape(-1, 1))
            
            # 키워드 인기도
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

    def load_user_profiles(self):
        """Firebase에서 모든 사용자 프로필 로드"""
        if not self.db:
            return
        
        try:
            users_ref = self.db.collection('users')
            users = users_ref.stream()
            
            for user_doc in users:
                user_data = user_doc.to_dict()
                self.user_profiles[user_doc.id] = user_data
            
            logger.info(f"✅ {len(self.user_profiles)}명의 사용자 프로필 로드")
            
        except Exception as e:
            logger.error(f"❌ 사용자 프로필 로드 실패: {str(e)}")

    def calculate_user_book_similarity(self, user_id: str, books_df: pd.DataFrame) -> np.ndarray:
        """사용자별 도서 유사도 계산 (개인화 핵심)"""
        if user_id in self.user_book_similarity:
            return self.user_book_similarity[user_id]
        
        user_profile = self.user_profiles.get(user_id, {})
        preferred_keywords = user_profile.get('preferred_keywords', [])
        preferred_types = user_profile.get('preferred_types', ['도서'])
        age_group = user_profile.get('age_group', '')
        
        # 사용자별 가중치 벡터 생성
        similarity_scores = np.zeros(len(books_df))
        
        for idx, book in books_df.iterrows():
            score = 0.0
            
            # 1. 선호 키워드 매칭 (가장 중요)
            if book['keyword'] in preferred_keywords:
                score += 0.8
            
            # 2. 선호 자료 유형 매칭
            if book['type'] in preferred_types:
                score += 0.3
            
            # 3. 연령대별 가중치
            pub_year = pd.to_numeric(book['pub_year'], errors='coerce')
            if pd.notna(pub_year):
                current_year = datetime.datetime.now().year
                book_age = current_year - pub_year
                
                if age_group == '20대':
                    if book_age <= 5:
                        score += 0.4
                    elif book_age <= 10:
                        score += 0.2
                elif age_group == '30대':
                    if 3 <= book_age <= 15:
                        score += 0.3
                elif age_group in ['40대', '50대']:
                    if book_age >= 5:
                        score += 0.3
            
            # 4. 키워드 다양성 보상
            if len(preferred_keywords) > 3:
                if book['keyword'] not in preferred_keywords:
                    score += 0.1
            
            # 5. 사용자별 랜덤 요소 (일관된 개인화)
            user_seed = hash(user_id) % 1000
            np.random.seed(user_seed + idx)
            random_bonus = np.random.uniform(0, 0.15)
            score += random_bonus
            
            similarity_scores[idx] = score
        
        # 정규화
        if similarity_scores.max() > 0:
            similarity_scores = similarity_scores / similarity_scores.max()
        
        # 캐시에 저장
        self.user_book_similarity[user_id] = similarity_scores
        
        return similarity_scores

    def get_user_specific_recommendations(self, user_id: str, books_df: pd.DataFrame, top_k: int = 10) -> List[Dict]:
        """사용자별 맞춤 추천 생성"""
        try:
            # 사용자별 유사도 계산
            user_similarity = self.calculate_user_book_similarity(user_id, books_df)
            
            # 사용자 피드백 반영
            user_ratings = self.load_user_ratings(user_id)
            
            # 피드백이 있는 도서들에 대한 보정
            if not user_ratings.empty:
                for _, rating_row in user_ratings.iterrows():
                    book_id = rating_row['book_id']
                    rating = rating_row['rating']
                    
                    book_indices = books_df[books_df['doc_id'] == book_id].index
                    
                    if len(book_indices) > 0:
                        book_idx = book_indices[0]
                        
                        if rating >= 4:  # 긍정적 피드백
                            user_similarity[book_idx] *= 1.3
                            
                            # 유사한 키워드의 다른 도서들에도 보너스
                            book_keyword = books_df.iloc[book_idx]['keyword']
                            same_keyword_indices = books_df[books_df['keyword'] == book_keyword].index
                            for idx in same_keyword_indices:
                                if idx != book_idx:
                                    user_similarity[idx] *= 1.1
                                    
                        elif rating <= 2:  # 부정적 피드백
                            user_similarity[book_idx] *= 0.3
                            
                            book_keyword = books_df.iloc[book_idx]['keyword']
                            same_keyword_indices = books_df[books_df['keyword'] == book_keyword].index
                            for idx in same_keyword_indices:
                                if idx != book_idx:
                                    user_similarity[idx] *= 0.9
            
            # 트렌드 점수와 결합
            trend_scores = self.get_trend_based_scores(books_df)
            
            recommendations = []
            for idx, book in books_df.iterrows():
                # 하이브리드 점수 계산 (개인화 70%, 트렌드 30%)
                personal_score = user_similarity[idx]
                trend_score = trend_scores.get(idx, 0)
                final_score = 0.7 * personal_score + 0.3 * trend_score
                
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
                    'personal_score': personal_score,
                    'trend_score': trend_score,
                    'recommendation_reason': self.generate_personalized_reason(book, user_id, personal_score, trend_score)
                })
            
            # 점수 순으로 정렬하여 상위 k개 반환
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            return recommendations[:top_k]
            
        except Exception as e:
            logger.error(f"❌ 사용자별 추천 실패: {str(e)}")
            return []

    def generate_personalized_reason(self, book: pd.Series, user_id: str, personal_score: float, trend_score: float) -> str:
        """개인화된 추천 이유 생성"""
        user_profile = self.user_profiles.get(user_id, {})
        preferred_keywords = user_profile.get('preferred_keywords', [])
        reasons = []
        
        if personal_score > 0.6:
            if book['keyword'] in preferred_keywords:
                reasons.append(f"'{book['keyword']}' 관심 분야와 정확히 일치")
            else:
                reasons.append("회원님의 취향을 고려한 맞춤 추천")
        
        if trend_score > 0.6:
            reasons.append("최근 주목받는 화제의 도서")
        
        pub_year = pd.to_numeric(book['pub_year'], errors='coerce')
        if pd.notna(pub_year):
            current_year = datetime.datetime.now().year
            if current_year - pub_year <= 3:
                reasons.append("최신 출간도서")
            elif current_year - pub_year >= 10:
                reasons.append("검증된 양서")
        
        if not reasons:
            reasons.append("다양한 주제 탐색을 위한 추천")
        
        return " • ".join(reasons)

    def get_trend_based_scores(self, books_df: pd.DataFrame) -> Dict[int, float]:
        """트렌드 기반 점수"""
        scores = {}
        current_year = datetime.datetime.now().year
        
        for idx, book in books_df.iterrows():
            score = 0.0
            
            # 발행년도 기반 점수
            pub_year = pd.to_numeric(book['pub_year'], errors='coerce')
            if pd.notna(pub_year):
                recency_score = max(0, 1 - (current_year - pub_year) / 20)
                score += 0.5 * recency_score
            
            # 키워드 인기도
            keyword_count = len(books_df[books_df['keyword'] == book['keyword']])
            popularity_score = min(1.0, keyword_count / 10)
            score += 0.5 * popularity_score
            
            scores[idx] = score
        
        return scores

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

    def generate_recommendations_for_frontend(self, user_id: str, books_df: pd.DataFrame, 
                                            user_ratings: pd.DataFrame = None) -> Dict:
        """프론트엔드용 추천 결과 생성"""
        try:
            # 사용자 프로필 로드
            if user_id not in self.user_profiles and self.db:
                user_doc = self.db.collection('users').document(user_id).get()
                if user_doc.exists:
                    self.user_profiles[user_id] = user_doc.to_dict()
            
            # 개인화 추천
            personalized_recs = self.get_user_specific_recommendations(user_id, books_df, top_k=10)
            
            # 트렌드 추천
            trend_recs = self.get_trending_books(books_df, top_k=5)
            
            # 카테고리별 추천
            category_recs = self.get_user_category_recommendations(user_id, books_df, top_k=3)
            
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
                        'title': f"{user_profile.get('name', '회원님')} 맞춤 추천",
                        'description': '회원님의 관심사와 취향을 분석한 개인화 추천입니다',
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
                    'recommendation_count': len(personalized_recs),
                    'personalization_strength': self.calculate_personalization_strength(user_id)
                },
                'generated_at': datetime.datetime.now().isoformat()
            }
            
            return frontend_data
            
        except Exception as e:
            logger.error(f"❌ 프론트엔드 데이터 생성 실패: {str(e)}")
            return {}

    def get_user_category_recommendations(self, user_id: str, books_df: pd.DataFrame, top_k: int = 3) -> Dict:
        """사용자 관심사 기반 카테고리별 추천"""
        user_profile = self.user_profiles.get(user_id, {})
        preferred_keywords = user_profile.get('preferred_keywords', [])
        
        categories = {}
        priority_keywords = preferred_keywords + list(books_df['keyword'].unique())
        
        for keyword in set(priority_keywords[:10]):
            keyword_books = books_df[books_df['keyword'] == keyword]
            
            if len(keyword_books) == 0:
                continue
            
            user_similarity = self.calculate_user_book_similarity(user_id, keyword_books)
            
            scored_books = []
            for idx, (_, book) in enumerate(keyword_books.iterrows()):
                scored_books.append((user_similarity[idx], book))
            
            scored_books.sort(key=lambda x: x[0], reverse=True)
            
            top_books = []
            for score, book in scored_books[:top_k]:
                top_books.append({
                    'doc_id': book['doc_id'],
                    'title': book['title'],
                    'author': book['author'],
                    'publisher': book['publisher'],
                    'pub_year': book['pub_year'],
                    'type': book['type'],
                    'library_name': book.get('library_name', ''),
                    'score': score
                })
            
            if top_books:
                priority = 1 if keyword in preferred_keywords else 2
                categories[keyword] = {
                    'title': f'{keyword} 도서',
                    'description': f'{keyword} 관련 맞춤 추천 도서',
                    'books': top_books,
                    'priority': priority
                }
        
        return dict(sorted(categories.items(), key=lambda x: x[1]['priority']))

    def calculate_personalization_strength(self, user_id: str) -> float:
        """개인화 강도 계산"""
        user_profile = self.user_profiles.get(user_id, {})
        
        strength = 0.0
        
        preferred_keywords = user_profile.get('preferred_keywords', [])
        strength += min(len(preferred_keywords) * 0.2, 0.6)
        
        if user_profile.get('age_group'):
            strength += 0.2
        
        user_ratings = self.load_user_ratings(user_id)
        if not user_ratings.empty:
            strength += min(len(user_ratings) * 0.1, 0.4)
        
        return min(strength, 1.0)

    def get_trending_books(self, books_df: pd.DataFrame, top_k: int = 5) -> List[Dict]:
        """트렌딩 도서 목록"""
        trending_scores = []
        
        for idx, book in books_df.iterrows():
            score = 0.0
            
            pub_year = pd.to_numeric(book['pub_year'], errors='coerce')
            if pd.notna(pub_year):
                current_year = datetime.datetime.now().year
                recency_score = max(0, 1 - (current_year - pub_year) / 10)
                score += recency_score
            
            keyword_count = len(books_df[books_df['keyword'] == book['keyword']])
            popularity_score = min(1.0, keyword_count / 5)
            score += popularity_score
            
            trending_scores.append((idx, score))
        
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

    def generate_demo_users(self, num_users: int = 50) -> List[Dict]:
        """다양한 데모 사용자 생성"""
        keywords = ['인공지능', '자율주행', '기후 변화', '블록체인', '문학', '소설', '사회', '법', '윤리']
        book_types = ['도서', '기사', '신문', '멀티미디어', '단행본', '연속간행물']
        age_groups = ['20대', '30대', '40대', '50대']
        reading_frequencies = ['주 1회', '주 2-3회', '매일']
        
        demo_users = []
        
        for i in range(num_users):
            user_id = f"demo_user_{i:03d}"
            
            # 다양한 선호도 패턴 생성
            if i % 4 == 0:  # 기술 중심
                preferred_keywords = ['인공지능', '자율주행', '블록체인']
            elif i % 4 == 1:  # 사회과학 중심
                preferred_keywords = ['사회', '법', '윤리']
            elif i % 4 == 2:  # 문학 중심
                preferred_keywords = ['문학', '소설']
            else:  # 혼합형
                preferred_keywords = random.sample(keywords, random.randint(3, 6))
            
            user_profile = {
                'user_id': user_id,
                'name': f"사용자{i+1}",
                'age_group': age_groups[i % len(age_groups)],
                'preferred_keywords': preferred_keywords,
                'preferred_types': random.sample(book_types, random.randint(1, 3)),
                'reading_frequency': random.choice(reading_frequencies),
                'created_at': datetime.datetime.now(),
                'last_active': datetime.datetime.now()
            }
            
            demo_users.append(user_profile)
            self.user_profiles[user_id] = user_profile
        
        logger.info(f"✅ {num_users}명의 다양한 데모 사용자 생성")
        return demo_users

    def generate_demo_ratings(self, users: List[Dict], books_df: pd.DataFrame, 
                            ratings_per_user: Tuple[int, int] = (5, 15)) -> pd.DataFrame:
        """현실적인 데모 평점 생성"""
        ratings_data = []
        
        for user in users:
            user_id = user['user_id']
            preferred_keywords = user['preferred_keywords']
            
            num_ratings = random.randint(ratings_per_user[0], ratings_per_user[1])
            
            for _ in range(num_ratings):
                # 80% 확률로 선호 키워드 도서
                if random.random() < 0.8 and preferred_keywords:
                    preferred_keyword = random.choice(preferred_keywords)
                    candidate_books = books_df[books_df['keyword'] == preferred_keyword]
                    if len(candidate_books) > 0:
                        book = candidate_books.sample(1).iloc[0]
                    else:
                        book = books_df.sample(1).iloc[0]
                else:
                    book = books_df.sample(1).iloc[0]
                
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
        logger.info(f"✅ {len(ratings_df)}개의 현실적인 데모 평점 생성")
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
            logger.info("✅ 개선된 데모 데이터 Firebase 저장 완료")
            
        except Exception as e:
            logger.error(f"❌ 데모 데이터 저장 실패: {str(e)}")

    def process_user_feedback(self, user_id: str, book_id: str, rating: int, 
                            feedback_text: str = None) -> bool:
        """사용자 피드백 처리 및 개인화 업데이트"""
        try:
            if not self.db:
                logger.error("Firebase 연결이 없습니다")
                return False
            
            feedback_data = {
                'user_id': user_id,
                'book_id': book_id,
                'rating': rating,
                'feedback_text': feedback_text or '',
                'timestamp': datetime.datetime.now(),
                'processed': False
            }
            
            self.db.collection('feedback').add(feedback_data)
            
            # 사용자별 유사도 캐시 삭제 (재계산 필요)
            if user_id in self.user_book_similarity:
                del self.user_book_similarity[user_id]
            
            # 사용자 프로필 업데이트
            self.update_user_profile_from_feedback(user_id, book_id, rating)
            
            logger.info(f"✅ 사용자 {user_id} 피드백 처리 및 개인화 업데이트 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 피드백 처리 실패: {str(e)}")
            return False
    
    def update_user_profile_from_feedback(self, user_id: str, book_id: str, rating: int):
        """피드백을 바탕으로 사용자 프로필 업데이트"""
        try:
            book_info = self.get_book_info_by_id(book_id)
            if not book_info:
                return
            
            if user_id not in self.user_profiles:
                self.user_profiles[user_id] = {
                    'user_id': user_id,
                    'preferred_keywords': [],
                    'preferred_types': [],
                    'disliked_keywords': [],
                    'disliked_types': []
                }
            
            profile = self.user_profiles[user_id]
            
            if rating >= 4:  # 긍정적 피드백
                if book_info['keyword'] not in profile['preferred_keywords']:
                    profile['preferred_keywords'].append(book_info['keyword'])
                
                if book_info['type'] not in profile['preferred_types']:
                    profile['preferred_types'].append(book_info['type'])
                
                if book_info['keyword'] in profile.get('disliked_keywords', []):
                    profile['disliked_keywords'].remove(book_info['keyword'])
                    
            elif rating <= 2:  # 부정적 피드백
                if book_info['keyword'] not in profile.get('disliked_keywords', []):
                    if 'disliked_keywords' not in profile:
                        profile['disliked_keywords'] = []
                    profile['disliked_keywords'].append(book_info['keyword'])
                
                if book_info['keyword'] in profile['preferred_keywords']:
                    negative_count = self.count_negative_feedback(user_id, book_info['keyword'])
                    if negative_count >= 2:
                        profile['preferred_keywords'].remove(book_info['keyword'])
            
            self.save_user_profile_to_firebase(user_id, profile)
            
        except Exception as e:
            logger.error(f"❌ 사용자 프로필 업데이트 실패: {str(e)}")
    
    def get_book_info_by_id(self, book_id: str) -> Dict:
        """도서 ID로 도서 정보 조회"""
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
            user_ratings = {}
            
            for doc in feedback_docs:
                data = doc.to_dict()
                rating = data.get('rating', 0)
                user_id = data.get('user_id', '')
                ratings.append(rating)
                
                if user_id not in user_ratings:
                    user_ratings[user_id] = []
                user_ratings[user_id].append(rating)
                
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
                'keyword_performance': {},
                'personalization_stats': {
                    'users_with_feedback': len(user_ratings),
                    'avg_feedback_per_user': np.mean([len(ratings) for ratings in user_ratings.values()]) if user_ratings else 0
                }
            }
            
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

    # 기존 API 호환성을 위한 메서드들
    def hybrid_recommendation(self, user_id: str, books_df: pd.DataFrame, 
                            user_ratings: pd.DataFrame = None, top_k: int = 10) -> List[Dict]:
        """기존 API 호환성 - 내부적으로는 개선된 알고리즘 사용"""
        return self.get_user_specific_recommendations(user_id, books_df, top_k)
    
    def calculate_content_similarity(self, books_df: pd.DataFrame) -> np.ndarray:
        """기존 API 호환성"""
        if self.book_features is None:
            self.build_content_features(books_df)
        return cosine_similarity(self.book_features)
    
    def collaborative_filtering(self, user_ratings: pd.DataFrame, books_df: pd.DataFrame) -> tuple:
        """기존 API 호환성"""
        try:
            user_book_matrix = user_ratings.pivot_table(
                index='user_id', 
                columns='book_id', 
                values='rating',
                fill_value=0
            )
            
            user_similarity = cosine_similarity(user_book_matrix)
            predictions = np.dot(user_similarity, user_book_matrix.values) / np.sum(np.abs(user_similarity), axis=1)[:, np.newaxis]
            
            return predictions, user_book_matrix.index, user_book_matrix.columns
            
        except Exception as e:
            logger.error(f"❌ 협업 필터링 실패: {str(e)}")
            return None, None, None

    def run_full_pipeline(self, firebase_config_path: str = None, 
                         generate_demo: bool = True) -> Dict:
        """전체 파이프라인 실행"""
        try:
            logger.info("🚀 개선된 트렌드 기반 도서 추천 시스템 시작")
            
            books_df = self.load_books_from_firebase()
            logger.info(f"📚 {len(books_df)}개 도서 로드")
            
            self.build_content_features(books_df)
            self.load_user_profiles()
            
            demo_users = []
            demo_ratings = pd.DataFrame()
            
            if generate_demo:
                demo_users = self.generate_demo_users(num_users=20)
                demo_ratings = self.generate_demo_ratings(demo_users, books_df)
                self.save_demo_data_to_firebase(demo_users, demo_ratings)
            
            sample_recommendations = {}
            
            if demo_users:
                for i, user in enumerate(demo_users[:5]):
                    user_id = user['user_id']
                    recommendations = self.generate_recommendations_for_frontend(
                        user_id, books_df, demo_ratings[demo_ratings['user_id'] == user_id]
                    )
                    sample_recommendations[user_id] = recommendations
            
            result = {
                'status': 'success',
                'books_count': len(books_df),
                'users_count': len(demo_users),
                'ratings_count': len(demo_ratings),
                'sample_recommendations': sample_recommendations,
                'analytics': self.get_feedback_analytics(),
                'personalization_enabled': True
            }
            
            logger.info("✅ 개선된 파이프라인 실행 완료")
            return result
            
        except Exception as e:
            logger.error(f"❌ 파이프라인 실행 실패: {str(e)}")
            return {'status': 'error', 'message': str(e)}


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="개인화된 트렌드 기반 도서 추천 시스템")
    parser.add_argument("--firebase_config", "-f", 
                        default='../csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                        help="Firebase 설정 파일 경로")
    parser.add_argument("--user_id", "-u", default="demo_user_001", 
                        help="추천을 받을 사용자 ID")
    parser.add_argument("--generate_demo", "-d", action='store_true', 
                        help="개선된 데모 데이터 생성")
    parser.add_argument("--top_k", "-k", type=int, default=10, 
                        help="추천 도서 수")
    parser.add_argument("--compare_users", "-c", action='store_true',
                        help="여러 사용자 추천 결과 비교")
    
    args = parser.parse_args()
    
    print("📖 개인화된 트렌드 기반 도서 추천 시스템")
    print("=" * 60)
    
    try:
        recommender = TrendBookRecommender(args.firebase_config)
        
        if args.generate_demo:
            result = recommender.run_full_pipeline(
                firebase_config_path=args.firebase_config,
                generate_demo=True
            )
            
            print(f"\n📊 실행 결과:")
            print(f"   • 처리된 도서: {result.get('books_count', 0)}권")
            print(f"   • 생성된 사용자: {result.get('users_count', 0)}명")
            print(f"   • 생성된 평점: {result.get('ratings_count', 0)}개")
            print(f"   • 개인화 활성화: {result.get('personalization_enabled', False)}")
            
            sample_recs = result.get('sample_recommendations', {})
            if sample_recs:
                print(f"\n🎯 사용자별 추천 결과 비교 (상위 3개씩):")
                for user_id, rec_data in list(sample_recs.items())[:3]:
                    user_profile = rec_data.get('user_profile', {})
                    personalized = rec_data.get('recommendations', {}).get('personalized', {})
                    books = personalized.get('books', [])
                    
                    print(f"\n👤 {user_id} ({user_profile.get('name', '이름없음')})")
                    print(f"   관심사: {', '.join(user_profile.get('preferred_keywords', []))}")
                    print(f"   연령대: {user_profile.get('age_group', '정보없음')}")
                    print(f"   맞춤 추천:")
                    
                    for i, book in enumerate(books[:3], 1):
                        print(f"     {i}. {book['title']} (키워드: {book['keyword']}, 점수: {book['score']:.3f})")
                        print(f"        이유: {book['recommendation_reason']}")
        
        elif args.compare_users:
            books_df = recommender.load_books_from_firebase()
            recommender.build_content_features(books_df)
            recommender.load_user_profiles()
            
            test_users = ['demo_user_001', 'demo_user_002', 'demo_user_003', 'demo_user_004', 'demo_user_005']
            
            print(f"\n🔍 {len(test_users)}명 사용자 추천 결과 비교:")
            
            for user_id in test_users:
                if user_id in recommender.user_profiles:
                    recommendations = recommender.generate_recommendations_for_frontend(user_id, books_df)
                    user_profile = recommendations.get('user_profile', {})
                    personalized = recommendations.get('recommendations', {}).get('personalized', {})
                    books = personalized.get('books', [])
                    
                    print(f"\n👤 {user_id} ({user_profile.get('name', '이름없음')})")
                    print(f"   관심사: {', '.join(user_profile.get('preferred_keywords', []))}")
                    print(f"   개인화 강도: {recommendations.get('stats', {}).get('personalization_strength', 0):.2f}")
                    print(f"   추천 결과:")
                    
                    for i, book in enumerate(books[:3], 1):
                        print(f"     {i}. {book['title']} (점수: {book['score']:.3f})")
                        print(f"        키워드: {book['keyword']} | 이유: {book['recommendation_reason']}")
                else:
                    print(f"\n❌ {user_id}: 프로필을 찾을 수 없습니다.")
        
        else:
            books_df = recommender.load_books_from_firebase()
            recommender.build_content_features(books_df)
            recommender.load_user_profiles()
            
            recommendations = recommender.generate_recommendations_for_frontend(args.user_id, books_df)
            
            print(f"\n🎯 사용자 '{args.user_id}' 개인화 추천:")
            user_profile = recommendations.get('user_profile', {})
            personalized = recommendations.get('recommendations', {}).get('personalized', {})
            books = personalized.get('books', [])
            
            print(f"   관심사: {', '.join(user_profile.get('preferred_keywords', []))}")
            print(f"   개인화 강도: {recommendations.get('stats', {}).get('personalization_strength', 0):.2f}")
            
            for i, book in enumerate(books[:args.top_k], 1):
                print(f"\n   {i}. {book['title']} - {book['author']}")
                print(f"      키워드: {book['keyword']} | 점수: {book['score']:.3f}")
                print(f"      개인점수: {book.get('personal_score', 0):.3f} | 트렌드점수: {book.get('trend_score', 0):.3f}")
                print(f"      추천이유: {book['recommendation_reason']}")
        
        print("\n✅ 시스템 실행 완료!")
        print("\n📖 이제 각 사용자별로 다른 추천 결과를 확인할 수 있습니다.")
        
    except Exception as e:
        print(f"\n❌ 시스템 실행 실패: {str(e)}")


if __name__ == "__main__":
    main()