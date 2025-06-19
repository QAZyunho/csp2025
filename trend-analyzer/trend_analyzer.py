#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase 연동 트렌드 분석기
Firebase news 컬렉션에서 뉴스를 읽어와서 Gemini로 분석 후 trend 컬렉션에 저장
"""

import google.generativeai as genai
import argparse
import time
import datetime
import logging
import os
import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Dict, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrendAnalyzerFirebase:
    """Firebase 연동 트렌드 분석기"""
    
    def __init__(self, gemini_api_key: str, firebase_config_path: str = None, model_name: str = "gemini-1.5-flash"):
        """초기화"""
        try:
            # Firebase 초기화
            self.init_firebase(firebase_config_path)
            
            # Gemini API 설정
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel(model_name)
            
            # Gemini 설정
            self.generation_config = {
                "temperature": 0.2,
                "top_p": 0.7,
                "top_k": 30,
                "max_output_tokens": 400,
                "candidate_count": 1,
            }
            
            logger.info(f"트렌드 분석기 초기화 완료: {model_name}")
            
        except Exception as e:
            logger.error(f"트렌드 분석기 초기화 실패: {str(e)}")
            raise
    
    def init_firebase(self, config_path: str):
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
    
    def load_news_from_firebase(self, date_str: str = None) -> Optional[Dict]:
        """
        Firebase news 컬렉션에서 뉴스 데이터 로드
        
        Args:
            date_str: 날짜 (YYMMDD 형식, None이면 오늘)
            
        Returns:
            뉴스 데이터 또는 None
        """
        if not self.db:
            logger.error("Firebase 연결이 없습니다.")
            return None
        
        try:
            if not date_str:
                date_str = datetime.datetime.now().strftime("%y%m%d")
            
            logger.info(f"Firebase에서 뉴스 데이터 로드 중... (날짜: {date_str})")
            
            # news/{date} 문서에서 뉴스 로드
            doc_ref = self.db.collection('news').document(date_str)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                keyword_groups = data.get('keyword_groups', {})
                
                if keyword_groups:
                    total_articles = data.get('total_articles', 0)
                    total_keywords = data.get('total_keywords', 0)
                    
                    logger.info(f"✅ 뉴스 데이터 로드 완료:")
                    logger.info(f"   📰 총 기사: {total_articles}개")
                    logger.info(f"   🏷️ 키워드: {total_keywords}개")
                    
                    return data
                else:
                    logger.warning(f"{date_str} 날짜에 뉴스 데이터가 없습니다.")
                    return None
            else:
                logger.error(f"{date_str} 날짜의 뉴스 데이터를 찾을 수 없습니다.")
                
                # 최근 날짜 데이터 찾기 시도
                return self._find_recent_news()
                
        except Exception as e:
            logger.error(f"Firebase 뉴스 로드 실패: {str(e)}")
            return None
    
    def _find_recent_news(self, days_back: int = 7) -> Optional[Dict]:
        """최근 며칠 내의 뉴스 데이터 찾기"""
        logger.info(f"최근 {days_back}일 내 뉴스 데이터 검색 중...")
        
        try:
            news_ref = self.db.collection('news')
            
            # 최근 문서들을 날짜 역순으로 조회
            docs = news_ref.order_by('collection_time', direction=firestore.Query.DESCENDING).limit(days_back).stream()
            
            for doc in docs:
                doc_data = doc.to_dict()
                keyword_groups = doc_data.get('keyword_groups', {})
                
                if keyword_groups:
                    date_str = doc.id
                    total_articles = doc_data.get('total_articles', 0)
                    logger.info(f"✅ {date_str} 날짜의 뉴스 데이터 발견 (기사 {total_articles}개)")
                    return doc_data
            
            logger.error(f"최근 {days_back}일 내에 뉴스 데이터가 없습니다.")
            return None
            
        except Exception as e:
            logger.error(f"최근 뉴스 검색 실패: {str(e)}")
            return None
    
    def create_summary_prompt(self, keyword: str, articles: List[Dict]) -> str:
        """요약 + 도서 검색 키워드 생성 프롬프트"""
        
        # 기사 텍스트 준비
        article_texts = []
        for i, article in enumerate(articles, 1):
            title = article.get('title', '제목 없음').strip()
            description = article.get('description', '').strip()
            
            article_text = f"[기사 {i}] {title}"
            if description and description != 'nan' and description:
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
    
    def analyze_keyword_with_gemini(self, keyword: str, articles: List[Dict]) -> Dict:
        """Gemini를 사용하여 키워드별 뉴스 분석"""
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
    
    def analyze_all_keywords(self, news_data: Dict) -> List[Dict]:
        """모든 키워드에 대해 뉴스 분석"""
        keyword_groups = news_data.get('keyword_groups', {})
        
        if not keyword_groups:
            logger.error("분석할 키워드 그룹이 없습니다.")
            return []
        
        logger.info(f"🚀 {len(keyword_groups)}개 키워드 분석 시작...")
        
        analysis_results = []
        total_keywords = len(keyword_groups)
        
        for i, (keyword, articles) in enumerate(keyword_groups.items(), 1):
            logger.info(f"📰 [{i}/{total_keywords}] '{keyword}' 분석 중... ({len(articles)}개 기사)")
            
            # 키워드별 분석
            analysis_result = self.analyze_keyword_with_gemini(keyword, articles)
            analysis_results.append(analysis_result)
            
            # API 안정성을 위한 대기
            if i < total_keywords:
                time.sleep(2)
        
        logger.info(f"🎉 분석 완료: {len(analysis_results)}개 키워드")
        return analysis_results
    
    def save_analysis_to_firebase(self, analysis_results: List[Dict], date_str: str = None) -> bool:
        """분석 결과를 Firebase trend 컬렉션에 저장"""
        if not self.db or not analysis_results:
            logger.error("Firebase 연결이 없거나 저장할 분석 결과가 없습니다.")
            return False
        
        try:
            if not date_str:
                date_str = datetime.datetime.now().strftime("%y%m%d")
            
            logger.info(f"💾 Firebase trend 컬렉션에 분석 결과 저장 중... (날짜: {date_str})")
            
            # trend/{date} 문서에 저장
            doc_ref = self.db.collection('trend').document(date_str)
            
            trend_data = {
                'date': date_str,
                'total_items': len(analysis_results),
                'created_at': datetime.datetime.now(),
                'source': 'news_analyzer_firebase',
                'status': 'completed',
                'trends': analysis_results  # 전체 트렌드를 배열로 저장
            }
            
            doc_ref.set(trend_data)
            
            logger.info(f"✅ {len(analysis_results)}개 분석 결과를 Firebase에 저장 완료")
            logger.info(f"📁 저장 경로: trend/{date_str}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase 저장 실패: {str(e)}")
            return False
    
    def get_analysis_summary(self, analysis_results: List[Dict]):
        """분석 결과 요약 출력"""
        if not analysis_results:
            print("📭 분석 결과가 없습니다.")
            return
        
        print(f"\n📊 === 분석 결과 요약 ===")
        print(f"총 분석 키워드: {len(analysis_results)}개")
        
        # 키워드별 기사 수 통계
        total_articles = sum(result.get('article_count', 0) for result in analysis_results)
        avg_articles = total_articles / len(analysis_results) if analysis_results else 0
        
        print(f"총 분석 기사: {total_articles}개")
        print(f"키워드당 평균 기사: {avg_articles:.1f}개")
        
        # 상위 분석 결과 미리보기
        print(f"\n🔥 주요 분석 결과 (상위 5개):")
        
        # 기사 수가 많은 순으로 정렬
        sorted_results = sorted(analysis_results, 
                              key=lambda x: x.get('article_count', 0), 
                              reverse=True)
        
        for i, result in enumerate(sorted_results[:5], 1):
            keyword = result.get('keyword', '')
            summary = result.get('summary', '')
            article_count = result.get('article_count', 0)
            book_keywords = result.get('book_keywords', [])
            
            print(f"  {i}. [{keyword}] ({article_count}개 기사)")
            print(f"     요약: {summary[:100]}{'...' if len(summary) > 100 else ''}")
            if book_keywords:
                print(f"     도서키워드: {', '.join(book_keywords[:3])}")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Firebase 연동 트렌드 분석기")
    parser.add_argument("--date", "-d", help="분석할 날짜 (YYMMDD 형식, 기본값: 오늘)")
    parser.add_argument("--gemini_api_key", "-g", 
                        default=os.getenv('GEMINI_API_KEY'),  # ✅ 환경변수 사용
                        help="Gemini API 키")
    parser.add_argument("--firebase_config", "-f", 
                        default= os.getenv('FIREBASE_CONFIG_PATH', '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json')
,
                        help="Firebase 설정 파일 경로")
    
    args = parser.parse_args()
    
    # API 키 확인
    gemini_api_key = args.gemini_api_key or os.getenv('GOOGLE_AI_API_KEY')
    if not gemini_api_key:
        print("❌ Gemini API 키가 필요합니다.")
        return
    
    print("📰 Firebase 연동 트렌드 분석기")
    print("=" * 40)
    
    # 분석기 초기화
    try:
        analyzer = TrendAnalyzerFirebase(
            gemini_api_key=gemini_api_key,
            firebase_config_path=args.firebase_config
        )
    except Exception as e:
        print(f"❌ 초기화 실패: {str(e)}")
        return
    
    # 날짜 설정
    date_str = args.date if args.date else datetime.datetime.now().strftime("%y%m%d")
    print(f"📅 분석 날짜: {date_str}")
    
    try:
        # 1. Firebase에서 뉴스 데이터 로드
        news_data = analyzer.load_news_from_firebase(date_str)
        if not news_data:
            print("❌ 분석할 뉴스 데이터를 찾을 수 없습니다.")
            print("💡 먼저 naver_news_collector.py를 실행하여 뉴스를 수집해주세요.")
            return
        
        # 2. 모든 키워드에 대해 분석
        analysis_results = analyzer.analyze_all_keywords(news_data)
        
        if not analysis_results:
            print("❌ 분석 결과 생성 실패")
            return
        
        # 3. Firebase trend 컬렉션에 저장
        firebase_success = analyzer.save_analysis_to_firebase(analysis_results, date_str)
        
        # 4. 결과 요약
        analyzer.get_analysis_summary(analysis_results)
        
        if firebase_success:
            print(f"\n✅ 완료!")
            print(f"🔥 Firebase 'trend' 컬렉션에 저장됨")
            print(f"📊 분석된 키워드: {len(analysis_results)}개")
            print(f"📁 저장 경로: trend/{date_str}")
        else:
            print("❌ Firebase 저장 실패")
    
    except KeyboardInterrupt:
        print("\n\n⏹️ 중단됨")
    except Exception as e:
        logger.exception(f"❌ 오류: {str(e)}")

if __name__ == "__main__":
    main()