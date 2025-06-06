#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import google.generativeai as genai
import pandas as pd
import argparse
import time
import datetime
import json
import logging
import os
import random
from pathlib import Path
from typing import List, Dict, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleNewsSummarizer:
    """간단한 뉴스 요약기 - 요약과 도서 검색 키워드만"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        초기화
        
        Args:
            api_key: Google AI Studio API 키
            model_name: 사용할 Gemini 모델
        """
        try:
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
            
            # 안전 설정
            self.safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                }
            ]
            
            logger.info(f"요약기 초기화 완료: {model_name}")
            
        except Exception as e:
            logger.error(f"요약기 초기화 실패: {str(e)}")
            raise

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

예시:
요약: 테슬라 주가가 전기차 판매 호조와 자율주행 기술 발전으로 상승세다. 중국 시장 실적 개선과 새 모델 출시 계획이 투자자들의 관심을 끌고 있다.

도서검색키워드: [전기차, 테슬라, 자율주행, 친환경 자동차, 일론 머스크]

위 형식으로 '{keyword}' 키워드를 분석해주세요:"""

        return prompt

    def summarize_with_gemini(self, keyword: str, articles: List[Dict]) -> Dict:
        """
        Gemini를 사용하여 요약 + 키워드 생성
        
        Args:
            keyword: 키워드
            articles: 기사 리스트
            
        Returns:
            요약 결과 딕셔너리
        """
        try:
            # 프롬프트 생성
            prompt = self.create_summary_prompt(keyword, articles)
            
            # 재시도 로직
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(
                        prompt,
                        generation_config=self.generation_config,
                        safety_settings=self.safety_settings
                    )
                    break
                except Exception as api_error:
                    if attempt < max_retries - 1:
                        wait_time = random.uniform(3, 7)
                        logger.warning(f"⚠️ '{keyword}' API 오류, {wait_time:.1f}초 후 재시도... ({attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        raise api_error
            
            # 응답 처리
            if response.text:
                response_text = response.text.strip()
                
                # 요약과 키워드 파싱
                summary, book_keywords = self._parse_response(response_text)
                
                result = {
                    'keyword': keyword,
                    'summary': summary,
                    'book_keywords': book_keywords
                }
                
                logger.info(f"✅ '{keyword}' 완료: {len(summary)}자, 키워드 {len(book_keywords)}개")
                return result
            else:
                logger.warning(f"⚠️ '{keyword}': 응답이 비어있음")
                return self._create_fallback_result(keyword)
                
        except Exception as e:
            logger.error(f"❌ '{keyword}' 처리 중 오류: {str(e)}")
            return self._create_fallback_result(keyword)

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
                    # 대괄호 제거하고 쉼표로 분리
                    keywords_part = keywords_part.strip('[]')
                    if keywords_part:
                        book_keywords = [kw.strip() for kw in keywords_part.split(',') if kw.strip()]
            
            # 파싱 실패시 전체 텍스트를 요약으로 사용
            if not summary:
                summary = response_text[:200] + ('...' if len(response_text) > 200 else '')
            
            return summary, book_keywords
            
        except Exception as e:
            logger.warning(f"응답 파싱 실패: {str(e)}")
            # 파싱 실패시 전체 응답을 요약으로 사용
            return response_text[:200] + ('...' if len(response_text) > 200 else ''), []

    def _create_fallback_result(self, keyword: str) -> Dict:
        """API 실패 시 폴백 결과 생성"""
        return {
            'keyword': keyword,
            'summary': f"'{keyword}' 관련 최신 뉴스가 있습니다.",
            'book_keywords': [keyword]
        }

    def summarize_by_keyword(self, news_df: pd.DataFrame) -> List[Dict]:
        """
        키워드별로 뉴스 요약
        
        Args:
            news_df: 뉴스 데이터프레임
            
        Returns:
            요약 결과 리스트
        """
        logger.info("🚀 간단한 뉴스 요약 시작...")
        
        # 키워드별로 그룹화
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
                wait_time = random.uniform(2, 4)
                time.sleep(wait_time)
        
        logger.info(f"🎉 요약 완료: {len(summary_results)}개 키워드")
        return summary_results

    def save_summaries(self, summaries: List[Dict], output_file: Optional[str] = None) -> Optional[str]:
        """요약 결과를 CSV와 JSON으로 저장"""
        if not output_file:
            output_file = f"news_summaries_{self.timestamp}.csv"
        
        try:
            # CSV 저장
            df = pd.DataFrame(summaries)
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"💾 CSV 저장: {output_file}")
            
            # JSON 저장
            json_file = output_file.replace('.csv', '.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "generated_at": datetime.datetime.now().isoformat(),
                    "total_keywords": len(summaries),
                    "summaries": summaries
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 JSON 저장: {json_file}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"❌ 저장 실패: {str(e)}")
            return None

    def print_summary_report(self, summaries: List[Dict]):
        """요약 결과 리포트 출력"""
        if not summaries:
            print("📭 요약 결과가 없습니다.")
            return
        
        print("\n" + "="*70)
        print("📰 뉴스 요약 + 도서 검색 키워드 결과")
        print("="*70)
        
        print(f"📊 총 키워드 수: {len(summaries)}개")
        
        for i, summary in enumerate(summaries, 1):
            print(f"\n{i:2d}. 🔸 {summary['keyword']}")
            print(f"    📝 요약: {summary['summary']}")
            if summary['book_keywords']:
                keywords_str = ", ".join(summary['book_keywords'])
                print(f"    📚 도서검색: {keywords_str}")
            else:
                print(f"    📚 도서검색: (키워드 없음)")
        
        print("="*70)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="간단한 뉴스 요약기")
    parser.add_argument("--input", "-i", required=True, help="뉴스 CSV 파일")
    parser.add_argument("--output", "-o", default=None, help="결과 파일 (선택사항)")
    parser.add_argument("--api_key", "-k", default='AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs', help="Google AI Studio API 키")
    
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
    
    print("📰 간단한 뉴스 요약기")
    print("=" * 40)
    print(f"📁 입력: {args.input}")
    
    # 출력 파일명
    if args.output:
        output_file = args.output
    else:
        input_path = Path(args.input)
        timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M")
        output_file = input_path.parent / f"news_summaries_{timestamp}.csv"
    
    print(f"📄 출력: {output_file}")
    
    # 요약기 초기화
    try:
        summarizer = SimpleNewsSummarizer(api_key)
    except Exception as e:
        print(f"❌ 초기화 실패: {str(e)}")
        return
    
    try:
        # 뉴스 데이터 로드
        news_df = summarizer.load_news_csv(args.input)
        if news_df is None or len(news_df) == 0:
            print("❌ 뉴스 데이터를 로드할 수 없습니다.")
            return
        
        print(f"📊 {len(news_df)}개 기사, {news_df['keyword'].nunique()}개 키워드")
        
        # 요약 생성
        summaries = summarizer.summarize_by_keyword(news_df)
        
        if not summaries:
            print("❌ 요약 생성 실패")
            return
        
        # 결과 저장
        saved_file = summarizer.save_summaries(summaries, str(output_file))
        
        if saved_file:
            print(f"\n✅ 완료!")
            print(f"📄 파일: {saved_file}")
            
            # 결과 출력
            summarizer.print_summary_report(summaries)
        else:
            print("❌ 저장 실패")
    
    except KeyboardInterrupt:
        print("\n\n⏹️ 중단됨")
    except Exception as e:
        logger.exception(f"❌ 오류: {str(e)}")


if __name__ == "__main__":
    main()