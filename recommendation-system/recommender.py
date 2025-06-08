#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간소화된 도서 추천 시스템
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class BookRecommender:
    def __init__(self, firebase_config_path: str):
        self.init_firebase(firebase_config_path)
        self.books_df = None
        self.user_profiles = {}
        
    def init_firebase(self, config_path: str):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(config_path)
                firebase_admin.initialize_app(cred)
            self.db = firestore.client(database_id='csproject2025')
            logger.info("Firebase 연결 성공")
        except Exception as e:
            logger.error(f"Firebase 연결 실패: {e}")
            self.db = None

    def load_books(self) -> pd.DataFrame:
        """도서 데이터 로드"""
        if not self.db:
            raise Exception("Firebase 연결 필요")
        
        books_data = []
        source_ref = self.db.collection('source')
        
        # 최근 5개 날짜의 데이터만 로드
        docs = source_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(5).stream()
        
        for date_doc in docs:
            keywords_ref = date_doc.reference.collection('keywords')
            for keyword_doc in keywords_ref.stream():
                keyword = keyword_doc.id
                books_ref = keyword_doc.reference.collection('books')
                for book_doc in books_ref.stream():
                    book_data = book_doc.to_dict()
                    book_data['doc_id'] = f"{date_doc.id}_{keyword}_{book_doc.id}"
                    book_data['keyword'] = keyword
                    books_data.append(book_data)
        
        self.books_df = pd.DataFrame(books_data)
        logger.info(f"{len(self.books_df)}개 도서 로드")
        return self.books_df

    def load_user_profile(self, user_id: str) -> Dict:
        """사용자 프로필 로드"""
        if user_id in self.user_profiles:
            return self.user_profiles[user_id]
        
        if self.db:
            user_doc = self.db.collection('users').document(user_id).get()
            if user_doc.exists:
                profile = user_doc.to_dict()
                self.user_profiles[user_id] = profile
                return profile
        
        return {}

    def calculate_category_recommendation(self, user_id: str, books_per_category: int = 5) -> Dict:
        """사용자별 단일 카테고리 추천 (카테고리 하나에 여러 책)"""
        if self.books_df is None:
            self.load_books()
        
        user_profile = self.load_user_profile(user_id)
        preferred_keywords = user_profile.get('preferred_keywords', [])
        
        # 1순위: 선호 키워드가 있으면 그 중 가장 많은 책이 있는 카테고리
        if preferred_keywords:
            keyword_counts = {}
            for keyword in preferred_keywords:
                count = len(self.books_df[self.books_df['keyword'] == keyword])
                keyword_counts[keyword] = count
            
            if keyword_counts:
                best_keyword = max(keyword_counts, key=keyword_counts.get)
                category_books = self.books_df[self.books_df['keyword'] == best_keyword]
            else:
                # 선호 키워드에 책이 없으면 가장 많은 책이 있는 카테고리
                best_keyword = self.books_df['keyword'].value_counts().index[0]
                category_books = self.books_df[self.books_df['keyword'] == best_keyword]
        else:
            # 선호도가 없으면 가장 많은 책이 있는 카테고리
            best_keyword = self.books_df['keyword'].value_counts().index[0]
            category_books = self.books_df[self.books_df['keyword'] == best_keyword]
        
        # 카테고리 내 도서들의 점수 계산
        books_with_scores = []
        for _, book in category_books.iterrows():
            score = 0.5  # 기본 점수
            
            # 선호 키워드면 보너스
            if book['keyword'] in preferred_keywords:
                score += 0.4
            
            # 최신도 반영
            try:
                pub_year = int(book['pub_year'])
                current_year = datetime.datetime.now().year
                if current_year - pub_year <= 3:
                    score += 0.2
                elif current_year - pub_year <= 10:
                    score += 0.1
            except:
                pass
            
            books_with_scores.append({
                'doc_id': book['doc_id'],
                'title': book['title'],
                'author': book['author'],
                'keyword': book['keyword'],
                'publisher': book['publisher'],
                'pub_year': book['pub_year'],
                'library_name': book.get('library_name', ''),
                'library_location': book.get('library_location', ''),
                'call_no': book.get('call_no', ''),
                'score': score
            })
        
        # 점수 순으로 정렬
        books_with_scores.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'category': best_keyword,
            'books': books_with_scores[:books_per_category],
            'total_books_in_category': len(category_books)
        }

    def save_category_recommendation(self, user_id: str, category_data: Dict):
        """카테고리 추천 결과를 Firebase 계층 구조로 저장"""
        if not self.db:
            return
        
        try:
            today = datetime.datetime.now().strftime("%Y%m%d")
            category = category_data['category']
            
            # 기본 경로: /recommendations/{user_id}/{date}/{category}
            category_ref = (self.db.collection('recommendations')
                          .document(user_id)
                          .collection(today)
                          .document(category))
            
            # 메타데이터 저장
            metadata = {
                'user_id': user_id,
                'date': today,
                'category': category,
                'total_books': len(category_data['books']),
                'total_books_in_category': category_data['total_books_in_category'],
                'created_at': datetime.datetime.now(),
                'expires_at': datetime.datetime.now() + datetime.timedelta(hours=24)
            }
            
            batch = self.db.batch()
            batch.set(category_ref, metadata)
            
            # 각 책을 개별 문서로 저장: /books/{book_id}
            books_ref = category_ref.collection('books')
            
            for i, book in enumerate(category_data['books']):
                book_doc_ref = books_ref.document(f"book_{i:03d}")
                book_data = {
                    'book_id': f"book_{i:03d}",
                    'doc_id': book['doc_id'],
                    'title': book['title'],
                    'author': book['author'],
                    'keyword': book['keyword'],
                    'publisher': book['publisher'],
                    'pub_year': book['pub_year'],
                    'library_name': book.get('library_name', ''),
                    'library_location': book.get('library_location', ''),
                    'call_no': book.get('call_no', ''),
                    'score': book['score'],
                    'order': i,
                    'created_at': datetime.datetime.now()
                }
                batch.set(book_doc_ref, book_data)
            
            batch.commit()
            logger.info(f"사용자 {user_id} 추천 저장: {today}/{category} ({len(category_data['books'])}권)")
            
        except Exception as e:
            logger.error(f"카테고리 추천 결과 저장 실패: {e}")

    def get_cached_category_recommendation(self, user_id: str, date: str = None) -> Dict:
        """캐시된 카테고리 추천 결과 조회 (계층 구조에서)"""
        if not self.db:
            return {}
        
        try:
            if not date:
                date = datetime.datetime.now().strftime("%Y%m%d")
            
            # 해당 날짜의 모든 카테고리 조회
            user_date_ref = (self.db.collection('recommendations')
                           .document(user_id)
                           .collection(date))
            
            categories = user_date_ref.stream()
            
            for category_doc in categories:
                category_data = category_doc.to_dict()
                expires_at = category_data.get('expires_at')
                
                # 만료되지 않았으면 해당 카테고리의 책들 조회
                if expires_at and expires_at > datetime.datetime.now():
                    category_name = category_doc.id
                    
                    # 책들 조회
                    books_ref = category_doc.reference.collection('books')
                    books_docs = books_ref.order_by('order').stream()
                    
                    books = []
                    for book_doc in books_docs:
                        book_data = book_doc.to_dict()
                        books.append({
                            'doc_id': book_data.get('doc_id'),
                            'title': book_data.get('title'),
                            'author': book_data.get('author'),
                            'keyword': book_data.get('keyword'),
                            'publisher': book_data.get('publisher'),
                            'pub_year': book_data.get('pub_year'),
                            'library_name': book_data.get('library_name', ''),
                            'library_location': book_data.get('library_location', ''),
                            'call_no': book_data.get('call_no', ''),
                            'score': book_data.get('score', 0)
                        })
                    
                    if books:
                        return {
                            'category': category_name,
                            'books': books,
                            'total_books_in_category': category_data.get('total_books_in_category', 0)
                        }
            
            return {}
            
        except Exception as e:
            logger.error(f"캐시된 카테고리 추천 조회 실패: {e}")
            return {}

    def get_category_recommendation(self, user_id: str, books_per_category: int = 5, use_cache: bool = True) -> Dict:
        """카테고리 추천 결과 조회 (캐시 우선)"""
        # 캐시된 결과 확인
        if use_cache:
            cached = self.get_cached_category_recommendation(user_id)
            if cached and cached.get('books'):
                return cached
        
        # 새로 계산
        category_data = self.calculate_category_recommendation(user_id, books_per_category)
        
        # 결과 저장
        self.save_category_recommendation(user_id, category_data)
        
        return category_data

    def save_feedback(self, user_id: str, book_id: str, rating: int):
        """사용자 피드백 저장 및 해당 날짜 추천 캐시 삭제"""
        if not self.db:
            return
        
        try:
            feedback_data = {
                'user_id': user_id,
                'book_id': book_id,
                'rating': rating,
                'timestamp': datetime.datetime.now()
            }
            
            self.db.collection('feedback').add(feedback_data)
            
            # 오늘 날짜의 추천 캐시 삭제 (다음에 새로 계산하도록)
            today = datetime.datetime.now().strftime("%Y%m%d")
            user_date_ref = (self.db.collection('recommendations')
                           .document(user_id)
                           .collection(today))
            
            # 오늘의 모든 카테고리 삭제
            categories = user_date_ref.stream()
            batch = self.db.batch()
            
            for category_doc in categories:
                # 카테고리 내 책들 삭제
                books_ref = category_doc.reference.collection('books')
                books = books_ref.stream()
                for book_doc in books:
                    batch.delete(book_doc.reference)
                
                # 카테고리 문서 삭제
                batch.delete(category_doc.reference)
            
            batch.commit()
            logger.info(f"피드백 저장 및 {user_id}/{today} 캐시 삭제 완료")
            
        except Exception as e:
            logger.error(f"피드백 저장 실패: {e}")