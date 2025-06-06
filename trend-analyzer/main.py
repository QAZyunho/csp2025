#!/usr/bin/env python3
# trend-analyzer/main.py - Firebase 연동 버전
# 뉴스 요약 결과를 Firebase 'trend' 컬렉션에 저장

import google.generativeai as genai
import pandas as pd
import argparse
import time
import datetime
import logging
import os
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path
from typing import List, Dict, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsAnalyzerFirebase:
    """Firebase 연동 뉴스 분석기"""
    
    def __init__(self, api_key: str, firebase_config_path: str = None, model_name: str = "gemini-1.5-flash"):
        """초기화"""
        try:
            # Firebase 초기화
            self.init_firebase(firebase_config_path)
            
            # Gemini API 설정
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
            self.timestamp = datetime.datetime.now().strftime("%y%m%d")
            
            # Gemini 설정
            self.generation_config = {
                "temperature": 0.2,
                "top_p": 0.7,
                "top_k": 30,
                "max_output_tokens": 400,
                "candidate_count": 1,
            }
            
            logger.info(f"뉴스 분석기 초기화 완료: {model_name}")
            
        except Exception as e:
            logger.error(f"뉴스 분석기 초기화 실패: {str(e)}")
            raise
    
    def init_firebase(self, config_path):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                if config_path and os.path.exists(config_path):
                    cred = credentials.Certificate(config_path)
                    firebase_admin.initialize_app(cred)
                    logger.info(f"Firebase 서비스 계정으로 연결: {config_path}")
                else:
                    # 환경변수 사용
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase 기본 인증으로 연결")
            
            self.db = firestore.client(database_id='csproject2025')
            logger.info("Firestore 연결 성공")
            
        except Exception as e:
            logger.error(f"Firebase 연결 실패: {str(e)}")
            self.db = None
    
    def save_to_firebase_trend(self, summaries: List[Dict]) -> bool:
        """요약 결과를 하나의 문서에 필드로 저장"""
        if not self.db:
            logger.error("Firebase 연결이 없습니다.")
            return False
        
        try:
            # trend/250606 문서 하나에 모든 데이터 저장
            doc_ref = self.db.collection('trend').document(self.timestamp)
            
            trend_data = {
                'date': self.timestamp,
                'total_items': len(summaries),
                'created_at': datetime.datetime.now(),
                'source': 'news_analyzer',
                'status': 'completed',
                'trends': summaries  # 전체 트렌드를 배열로 저장
            }
            
            doc_ref.set(trend_data)
            logger.info(f"💾 {len(summaries)}개 요약 결과를 Firebase에 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase 저장 실패: {str(e)}")
            return False
    
    def load_news_csv(self, csv_path: str) -> Optional[pd.DataFrame]:
        """뉴스 CSV 파일 로드"""
        try:
            logger.info(f"뉴스 파일 로드: {csv_path}")
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            logger.info(f"로드된 뉴스 기사 수: {len(df)}개")
            return df
        except Exception as e:
            logger.error(f"뉴스 파일 로드 실패: {str(e)}")
            return None

    def create_summary_prompt(self, keyword: str, articles: List[Dict]) -> str:
        """요약 + 도서 검색 키워드 생성 프롬프트"""
        
        # 기사 텍스트 준비
        article_texts = []
        for i, article in enumerate(articles, 1):
            title = article.get('title', '제목 없음').strip()
            description = article.get('description', '').strip()
            
            article_text = f"[기사 {i}] {title}"
            if description and description != 'nan':
                article_text += f" - {description}"
            article_texts.append(article_text)
        
        combined_articles = "\n".join(article_texts)
        
        prompt = f"""다음 '{keyword}' 관련 뉴스들을 분석하여 요약하고, 관련 도서 검색 키워드를 제안해주세요.

뉴스 기사들:
{combined_articles}

다음 형식으로 정확히 출력해주세요:

요약: [100-200자 이내로 이 키워드가 왜 주목받는지, 주요 동향을 자연스러운 문장으로 설명]

도서검색키워드: [키워드1, 키워드2, 키워드3, 키워드4, 키워드5]

지침:
1. 요약은 100-200자 이내, 자연스러운 문장
2. 도서 검색 키워드는 이 주제와 관련된 책을 찾을 때 유용한 단어 3-5개
3. 키워드는 쉼표로 구분하고 대괄호 안에 작성
4. 다른 형식이나 설명 추가 금지

위 형식으로 '{keyword}' 키워드를 분석해주세요:"""

        return prompt

    def summarize_with_gemini(self, keyword: str, articles: List[Dict]) -> Dict:
        """Gemini를 사용하여 요약 + 키워드 생성"""
        try:
            prompt = self.create_summary_prompt(keyword, articles)
            
            # 재시도 로직
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(
                        prompt,
                        generation_config=self.generation_config
                    )
                    break
                except Exception as api_error:
                    if attempt < max_retries - 1:
                        wait_time = 3 + attempt * 2
                        logger.warning(f"⚠️ '{keyword}' API 오류, {wait_time}초 후 재시도... ({attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        raise api_error
            
            # 응답 처리
            if response.text:
                response_text = response.text.strip()
                summary, book_keywords = self._parse_response(response_text)
                
                result = {
                    'keyword': keyword,
                    'summary': summary,
                    'book_keywords': book_keywords,
                    'article_count': len(articles),
                    'created_at': datetime.datetime.now().isoformat()
                }
                
                logger.info(f"✅ '{keyword}' 완료: {len(summary)}자, 키워드 {len(book_keywords)}개")
                return result
            else:
                logger.warning(f"⚠️ '{keyword}': 응답이 비어있음")
                return self._create_fallback_result(keyword, articles)
                
        except Exception as e:
            logger.error(f"❌ '{keyword}' 처리 중 오류: {str(e)}")
            return self._create_fallback_result(keyword, articles)

    def _parse_response(self, response_text: str) -> tuple:
        """응답에서 요약과 키워드 추출"""
        try:
            lines = response_text.split('\n')
            summary = ""
            book_keywords = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('요약:'):
                    summary = line.replace('요약:', '').strip()
                elif line.startswith('도서검색키워드:'):
                    keywords_part = line.replace('도서검색키워드:', '').strip()
                    keywords_part = keywords_part.strip('[]')
                    if keywords_part:
                        book_keywords = [kw.strip() for kw in keywords_part.split(',') if kw.strip()]
            
            if not summary:
                summary = response_text[:200] + ('...' if len(response_text) > 200 else '')
            
            return summary, book_keywords
            
        except Exception as e:
            logger.warning(f"응답 파싱 실패: {str(e)}")
            return response_text[:200] + ('...' if len(response_text) > 200 else ''), []

    def _create_fallback_result(self, keyword: str, articles: List[Dict]) -> Dict:
        """API 실패 시 폴백 결과 생성"""
        return {
            'keyword': keyword,
            'summary': f"'{keyword}' 관련 최신 뉴스가 있습니다.",
            'book_keywords': [keyword],
            'article_count': len(articles),
            'created_at': datetime.datetime.now().isoformat()
        }

    def summarize_by_keyword(self, news_df: pd.DataFrame) -> List[Dict]:
        """키워드별로 뉴스 요약"""
        logger.info("🚀 뉴스 요약 시작...")
        
        keyword_groups = news_df.groupby('keyword')
        summary_results = []
        total_keywords = len(keyword_groups)
        
        for i, (keyword, group) in enumerate(keyword_groups, 1):
            logger.info(f"📰 [{i}/{total_keywords}] '{keyword}' 분석 중... ({len(group)}개 기사)")
            
            # 기사 데이터 준비
            articles = []
            for _, row in group.iterrows():
                article = {
                    'title': str(row.get('title', '')),
                    'description': str(row.get('description', '')),
                }
                articles.append(article)
            
            # 요약 생성
            summary_result = self.summarize_with_gemini(keyword, articles)
            summary_results.append(summary_result)
            
            # API 안정성을 위한 대기
            if i < total_keywords:
                time.sleep(2)
        
        logger.info(f"🎉 요약 완료: {len(summary_results)}개 키워드")
        return summary_results

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Firebase 연동 뉴스 분석기")
    parser.add_argument("--input", "-i", required=True, help="뉴스 CSV 파일")
    parser.add_argument("--api_key", "-k", default='AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs', help="Google AI Studio API 키")
    parser.add_argument("--firebase_config", "-f", default='/home/yunho/csp2025/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json', help="Firebase 설정 파일 경로")
    
    args = parser.parse_args()
    
    # API 키 확인
    api_key = args.api_key or os.getenv('GOOGLE_AI_API_KEY')
    if not api_key:
        print("❌ Google AI Studio API 키가 필요합니다.")
        return
    
    # 입력 파일 존재 확인
    if not os.path.exists(args.input):
        print(f"❌ 입력 파일을 찾을 수 없습니다: {args.input}")
        return
    
    print("📰 Firebase 연동 뉴스 분석기")
    print("=" * 40)
    print(f"📁 입력: {args.input}")
    
    # 분석기 초기화
    try:
        analyzer = NewsAnalyzerFirebase(
            api_key=api_key,
            firebase_config_path=args.firebase_config
        )
    except Exception as e:
        print(f"❌ 초기화 실패: {str(e)}")
        return
    
    try:
        # 뉴스 데이터 로드
        news_df = analyzer.load_news_csv(args.input)
        if news_df is None or len(news_df) == 0:
            print("❌ 뉴스 데이터를 로드할 수 없습니다.")
            return
        
        print(f"📊 {len(news_df)}개 기사, {news_df['keyword'].nunique()}개 키워드")
        
        # 요약 생성
        summaries = analyzer.summarize_by_keyword(news_df)
        
        if not summaries:
            print("❌ 요약 생성 실패")
            return
        
        # Firebase에 저장
        firebase_success = analyzer.save_to_firebase_trend(summaries)
        
        if firebase_success:
            print(f"\n✅ 완료!")
            print(f"🔥 Firebase 'trend' 컬렉션에 저장됨")
            
            print(f"\n📊 처리 결과:")
            print(f"   - 총 키워드: {len(summaries)}개")
            print(f"   - 처리된 기사: {sum(s.get('article_count', 0) for s in summaries)}개")
        else:
            print("❌ 저장 실패")
    
    except KeyboardInterrupt:
        print("\n\n⏹️ 중단됨")
    except Exception as e:
        logger.exception(f"❌ 오류: {str(e)}")

if __name__ == "__main__":
    main()