# 개선된 recommender.py의 핵심 함수들

import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from typing import List, Dict, Optional
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
        self.books_cache = {}  # 도서 데이터 캐시 추가
        
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
        """📚 도서 데이터 로딩 개선 - 캐싱과 에러 처리 강화"""
        if self.books_df is not None and not self.books_df.empty:
            logger.info(f"📖 캐시된 {len(self.books_df)}개 도서 데이터를 사용합니다.")
            return self.books_df
            
        logger.info("🔄 Firestore에서 도서 데이터를 새로 로드합니다...")
        books_data = []
        
        try:
            source_ref = self.db.collection('source')
            
            # 최근 3일간의 데이터만 로드 (성능 최적화)
            recent_docs = []
            for doc in source_ref.stream():
                doc_id = doc.id
                # YYMMDD 형식의 날짜 확인
                if len(doc_id) == 6 and doc_id.isdigit():
                    recent_docs.append((doc_id, doc))
            
            # 최신 순으로 정렬하여 상위 3개만 사용
            recent_docs.sort(key=lambda x: x[0], reverse=True)
            recent_docs = recent_docs[:3]
            
            logger.info(f"📅 최근 {len(recent_docs)}개 날짜의 데이터를 로드합니다: {[d[0] for d in recent_docs]}")
            
            for date_id, date_doc in recent_docs:
                try:
                    keywords_ref = date_doc.reference.collection('keywords')
                    for keyword_doc in keywords_ref.stream():
                        keyword = keyword_doc.id
                        books_ref = keyword_doc.reference.collection('books')
                        
                        book_count = 0
                        for book_doc in books_ref.stream():
                            book_data = book_doc.to_dict()
                            book_data['doc_id'] = f"{date_id}_{keyword}_{book_doc.id}"
                            book_data['keyword'] = keyword
                            book_data['collection_date'] = date_id
                            books_data.append(book_data)
                            book_count += 1
                        
                        if book_count > 0:
                            logger.debug(f"  📚 {keyword}: {book_count}권")
                            
                except Exception as e:
                    logger.warning(f"⚠️ 날짜 {date_id} 처리 중 오류: {e}")
                    continue
            
            if books_data:
                self.books_df = pd.DataFrame(books_data)
                logger.info(f"✅ 총 {len(self.books_df)}개 도서를 로드했습니다.")
                
                # 키워드별 통계
                keyword_counts = self.books_df['keyword'].value_counts()
                logger.info(f"🏷️ 키워드별 도서 수: {dict(keyword_counts.head())}")
            else:
                logger.warning("📭 로드된 도서 데이터가 없습니다.")
                self.books_df = pd.DataFrame()
                
        except Exception as e:
            logger.error(f"❌ 도서 데이터 로드 중 오류: {e}")
            self.books_df = pd.DataFrame()
            
        return self.books_df

    def load_user_profile(self, user_id: str) -> Dict:
        """👤 사용자 프로필 로딩 개선"""
        if user_id in self.user_profiles: 
            return self.user_profiles[user_id]
            
        if self.db:
            try:
                user_doc = self.db.collection('users').document(user_id).get()
                if user_doc.exists:
                    profile = user_doc.to_dict()
                    
                    # 기본값 설정으로 안정성 향상
                    profile.setdefault('preferred_keywords', [])
                    profile.setdefault('preferred_types', [])
                    profile.setdefault('reading_frequency', '주 1회')
                    profile.setdefault('age_group', '20대')
                    
                    self.user_profiles[user_id] = profile
                    logger.info(f"👤 사용자 '{user_id}' 프로필 로드 완료")
                    return profile
                else:
                    logger.warning(f"⚠️ 사용자 '{user_id}'를 찾을 수 없습니다.")
            except Exception as e:
                logger.error(f"❌ 사용자 프로필 로드 실패: {e}")
        
        return {}

    def get_latest_trends(self) -> List[Dict]:
        """📈 최신 트렌드 로딩 최적화"""
        if self.latest_trends:
            logger.info("📊 캐시된 최신 트렌드를 사용합니다.")
            return self.latest_trends
            
        if not self.db: 
            return []
        
        try:
            logger.info("🔄 최신 트렌드 데이터를 로드합니다...")
            
            # 간단하고 확실한 방법: 오늘 날짜부터 역순으로 확인
            current_date = datetime.datetime.now()
            
            for days_back in range(7):  # 최대 7일 전까지 확인
                check_date = current_date - datetime.timedelta(days=days_back)
                date_str = check_date.strftime("%y%m%d")
                
                try:
                    doc = self.db.collection('trend').document(date_str).get()
                    
                    if doc.exists:
                        data = doc.to_dict()
                        trends_data = data.get('trends', [])
                        
                        if trends_data:
                            self.latest_trends = trends_data
                            logger.info(f"✅ {date_str} 날짜의 트렌드 {len(trends_data)}개를 로드했습니다.")
                            return trends_data
                        
                except Exception as e:
                    logger.debug(f"날짜 {date_str} 확인 중 오류: {e}")
                    continue
            
            logger.warning("📭 최근 7일간 트렌드 데이터를 찾을 수 없습니다.")
            return []

        except Exception as e: 
            logger.error(f"❌ 최신 트렌드 로드 실패: {e}")
            return []

    def get_books_for_keyword(self, user_id: str, keyword: str, max_books: int = 5) -> List[Dict]:
        """🎯 키워드별 도서 추천 개선 - 사용자 맞춤형 점수 계산"""
        if self.books_df is None or self.books_df.empty: 
            logger.warning("📭 로드된 도서 데이터가 없습니다.")
            return []

        user_profile = self.load_user_profile(user_id)
        preferred_keywords = user_profile.get('preferred_keywords', [])
        reading_frequency = user_profile.get('reading_frequency', '주 1회')
        age_group = user_profile.get('age_group', '20대')
        
        # 키워드별 도서 필터링
        keyword_books_df = self.books_df[self.books_df['keyword'] == keyword]
        
        if keyword_books_df.empty:
            logger.warning(f"⚠️ '{keyword}' 키워드에 해당하는 도서가 없습니다.")
            return []
        
        books_with_scores = []
        current_year = datetime.datetime.now().year
        
        for _, book_row in keyword_books_df.iterrows():
            score = 0.5  # 기본 점수
            
            # 1. 사용자 선호 키워드 보너스
            if book_row.get('keyword') in preferred_keywords:
                score += 0.3
                logger.debug(f"선호 키워드 보너스: {book_row.get('title', 'Unknown')}")
            
            # 2. 최신성 보너스
            try:
                pub_year = int(book_row.get('pub_year', 0))
                year_diff = current_year - pub_year
                if year_diff <= 2:
                    score += 0.25
                elif year_diff <= 5:
                    score += 0.15
                elif year_diff <= 10:
                    score += 0.1
            except (ValueError, TypeError):
                pass
            
            # 3. 도서 유형 보너스
            book_type = book_row.get('type', '').lower()
            if '도서' in book_type or '단행본' in book_type:
                score += 0.2
            
            # 4. AI 선별 보너스
            if book_row.get('ai_selected', False):
                score += 0.15
            
            # 5. 독서 빈도에 따른 난이도 조정
            if reading_frequency in ['매일', '주 2-3회']:
                # 활발한 독자에게는 다양한 도서 추천
                score += 0.1
            
            book_dict = book_row.to_dict()
            book_dict['score'] = round(score, 3)
            book_dict['user_id'] = user_id
            books_with_scores.append(book_dict)
        
        # 점수순으로 정렬
        books_with_scores.sort(key=lambda x: x['score'], reverse=True)
        
        result = books_with_scores[:max_books]
        logger.info(f"🎯 '{keyword}' 키워드: {len(result)}권 추천 (평균 점수: {sum(b['score'] for b in result)/len(result):.2f})")
        
        return result

    def get_general_recommendations(self, user_id: str) -> Dict:
        """🌟 일반 추천 시스템 대폭 개선"""
        user_profile = self.load_user_profile(user_id)
        
        if not user_profile:
            # 사용자 프로필이 없는 경우 기본 추천
            return self._get_fallback_recommendations()
        
        preferred_keywords = user_profile.get('preferred_keywords', [])
        latest_trends = self.get_latest_trends()
        
        # 전략 1: 사용자 선호 키워드가 있는 경우
        if preferred_keywords:
            # 선호 키워드 중 랜덤 선택
            selected_keyword = random.choice(preferred_keywords)
            books = self.get_books_for_keyword(user_id, selected_keyword, max_books=5)
            
            if books:
                logger.info(f"👍 선호 키워드 '{selected_keyword}' 기반 추천")
                return {
                    'category': f"맞춤 추천: {selected_keyword}",
                    'books': books,
                    'recommendation_type': 'preferred'
                }
        
        # 전략 2: 트렌드 기반 탐색 추천
        if latest_trends:
            # 사용자가 아직 경험하지 않은 새로운 트렌드 찾기
            trend_keywords = [t.get('keyword', '') for t in latest_trends if t.get('keyword')]
            new_keywords = [kw for kw in trend_keywords if kw not in preferred_keywords]
            
            if new_keywords:
                discovery_keyword = random.choice(new_keywords)
                books = self.get_books_for_keyword(user_id, discovery_keyword, max_books=5)
                
                if books:
                    logger.info(f"🔍 새로운 트렌드 '{discovery_keyword}' 탐색 추천")
                    return {
                        'category': f"새로운 발견: {discovery_keyword}",
                        'books': books,
                        'recommendation_type': 'discovery'
                    }
        
        # 전략 3: 폴백 - 인기 키워드 기반
        return self._get_fallback_recommendations()

    def _get_fallback_recommendations(self) -> Dict:
        """📚 폴백 추천 - 인기 키워드나 기본 추천"""
        try:
            if self.books_df is not None and not self.books_df.empty:
                # 가장 많은 도서가 있는 키워드 찾기
                keyword_counts = self.books_df['keyword'].value_counts()
                
                if not keyword_counts.empty:
                    popular_keyword = keyword_counts.index[0]
                    books = self.get_books_for_keyword('guest', popular_keyword, max_books=5)
                    
                    if books:
                        logger.info(f"📊 인기 키워드 '{popular_keyword}' 기반 폴백 추천")
                        return {
                            'category': f"인기 주제: {popular_keyword}",
                            'books': books,
                            'recommendation_type': 'popular'
                        }
            
            # 최종 폴백
            logger.warning("📭 추천할 도서가 없습니다.")
            return {
                'category': '추천 준비 중',
                'books': [],
                'recommendation_type': 'none',
                'message': '도서 데이터를 준비하고 있습니다. 잠시 후 다시 시도해주세요.'
            }
            
        except Exception as e:
            logger.error(f"❌ 폴백 추천 생성 실패: {e}")
            return {
                'category': '추천 서비스 오류',
                'books': [],
                'recommendation_type': 'error',
                'message': '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
            }

    def save_feedback(self, user_id: str, keyword: str, rating: int, book_id: str = None):
        """💾 피드백 저장 및 프로필 업데이트 개선"""
        if not self.db: 
            return
            
        try:
            # 피드백 데이터 저장
            feedback_data = {
                'user_id': user_id,
                'book_id': book_id,
                'keyword': keyword,
                'rating': rating,
                'timestamp': datetime.datetime.now(),
                'feedback_type': 'rating'
            }
            
            self.db.collection('feedback').add(feedback_data)
            logger.info(f"💾 피드백 저장 완료: {user_id} -> {keyword} ({rating}점)")
            
            # 사용자 프로필 업데이트
            user_ref = self.db.collection('users').document(user_id)
            update_data = {}
            
            # 긍정적 피드백 (4-5점)
            if rating >= 4:
                update_data['preferred_keywords'] = firestore.ArrayUnion([keyword])
                logger.info(f"👍 선호 키워드에 '{keyword}' 추가")
                
            # 부정적 피드백 (1-2점)
            elif rating <= 2:
                update_data['preferred_keywords'] = firestore.ArrayRemove([keyword])
                logger.info(f"👎 선호 키워드에서 '{keyword}' 제거")
            
            # 프로필 업데이트
            if update_data:
                user_ref.update(update_data)
                
                # 캐시된 프로필 갱신
                if user_id in self.user_profiles:
                    current_profile = self.user_profiles[user_id]
                    preferred = current_profile.get('preferred_keywords', [])
                    
                    if rating >= 4 and keyword not in preferred:
                        preferred.append(keyword)
                    elif rating <= 2 and keyword in preferred:
                        preferred.remove(keyword)
                    
                    current_profile['preferred_keywords'] = preferred
                    
        except Exception as e:
            logger.error(f"❌ 피드백 저장 실패: {e}")

    def get_all_users(self) -> List[Dict]:
        """👥 모든 사용자 목록 조회"""
        if not self.db: 
            return []
            
        try:
            users_ref = self.db.collection('users').stream()
            users = []
            
            for user in users_ref:
                user_data = user.to_dict()
                if user_data:
                    users.append(user_data)
            
            logger.info(f"👥 총 {len(users)}명의 사용자를 찾았습니다.")
            return users
            
        except Exception as e:
            logger.error(f"❌ 사용자 목록 조회 실패: {e}")
            return []

    def get_recommendation_stats(self) -> Dict:
        """📊 추천 시스템 통계"""
        try:
            stats = {
                'total_books': len(self.books_df) if self.books_df is not None else 0,
                'total_keywords': len(self.books_df['keyword'].unique()) if self.books_df is not None and not self.books_df.empty else 0,
                'total_users': len(self.user_profiles),
                'total_trends': len(self.latest_trends),
                'status': 'healthy' if self.db else 'disconnected'
            }
            
            if self.books_df is not None and not self.books_df.empty:
                stats['popular_keywords'] = self.books_df['keyword'].value_counts().head().to_dict()
                
            return stats
            
        except Exception as e:
            logger.error(f"❌ 통계 생성 실패: {e}")
            return {'status': 'error', 'message': str(e)}