#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import pandas as pd
import argparse
import time
import datetime
import re
import logging
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsSummarizer:
    """KoT5 모델을 사용한 뉴스 요약기 + KeyBERT 키워드 추출"""
    
    def __init__(self, model_name="noahkim/KoT5_news_summarization"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = None
        self.timestamp = datetime.datetime.now().strftime("%y%m%d")
        
        # KeyBERT 모델 초기화
        self.kw_model = None
        self.current_model = None  # 현재 사용 중인 모델명
        
    def load_models(self):
        """KoT5 요약 모델과 KeyBERT 모델 로드"""
        logger.info(f"요약 모델 로드 중: {self.model_name}")
        
        # KoT5 요약 모델 로드
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        
        # GPU 사용 가능 시 GPU로 이동
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()
        
        logger.info(f"요약 모델 로드 완료: {self.device}")
        
        # KeyBERT 모델 로드 (도서 검색 최적화된 한국어 모델)
        logger.info("KeyBERT 모델 로드 중 (도서 검색 최적화)...")
        try:
            # 도서 검색에 적합한 한국어 모델들 우선순위
            korean_models = [
                'snunlp/KR-SBERT-V40K-klueNLI-augSTS',  # 한국어 SBERT - 의미 유사도 특화
                'jhgan/ko-sbert-nli',  # 한국어 SBERT NLI 모델
                'beomi/KcELECTRA-base-v2022',  # 한국어 ELECTRA
                'jhgan/ko-sroberta-multitask',  # 한국어 RoBERTa
                'bongsoo/kpf-sbert-128d-v1',  # 한국어 특화 SBERT
                'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',  # 다국어
            ]
            
            for model_name in korean_models:
                try:
                    logger.info(f"모델 로드 시도: {model_name}")
                    sentence_model = SentenceTransformer(model_name)
                    self.kw_model = KeyBERT(model=sentence_model)
                    logger.info(f"✅ KeyBERT 모델 로드 성공: {model_name}")
                    self.current_model = model_name  # 현재 사용 중인 모델 저장
                    break
                    
                except Exception as e:
                    logger.warning(f"❌ 모델 {model_name} 로드 실패: {str(e)}")
                    continue
            
            if self.kw_model is None:
                # 최후의 수단으로 기본 모델 사용
                logger.info("모든 한국어 모델 로드 실패, 기본 KeyBERT 모델 사용")
                self.kw_model = KeyBERT()
                self.current_model = "default"
                
        except Exception as e:
            logger.error(f"KeyBERT 모델 로드 중 오류: {str(e)}")
            self.kw_model = KeyBERT()
            self.current_model = "default"
            logger.info("기본 KeyBERT 모델로 대체")
        
    def clean_summary(self, text):
        """요약 텍스트 정리"""
        text = re.sub(r'\s+', ' ', text).strip()
        if not text.endswith(('.', '?', '!')):
            sentences = text.split('.')
            if len(sentences) > 1:
                text = '.'.join(sentences[:-1]) + '.'
            else:
                text += '.'
        return text

    def summarize_text(self, text, max_length=150):
        """텍스트 요약"""
        try:
            max_input_length = 512
            input_text = "summarize: " + text
            
            inputs = self.tokenizer(
                input_text, 
                return_tensors="pt", 
                max_length=max_input_length, 
                truncation=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                    max_length=max_length,
                    min_length=20,
                    length_penalty=1.0,
                    num_beams=4,
                    early_stopping=True
                )
            
            summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            summary = self.clean_summary(summary)
            return summary
            
        except Exception as e:
            logger.error(f"요약 생성 오류: {str(e)}")
            return text[:100] + "..." if len(text) > 100 else text

    def extract_keywords(self, text, top_k=5):
        """KeyBERT를 사용하여 도서 검색용 간단한 키워드 추출"""
        try:
            if not text or not text.strip():
                return []
            
            # 텍스트 전처리
            text = text.strip()
            
            # 간단한 키워드 추출을 위한 KeyBERT 설정
            keywords = self.kw_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2),  # 1-2개 단어만 (간단하게)
                stop_words=None,
                use_mmr=True,
                diversity=0.8,  # 높은 다양성으로 중복 방지
                nr_candidates=30
            )
            
            # KeyBERT 결과 정제
            refined_keywords = self._extract_simple_keywords(keywords, text)
            
            return refined_keywords[:top_k]
            
        except Exception as e:
            logger.error(f"키워드 추출 오류: {str(e)}")
            return self._simple_keyword_extraction(text, top_k)

    def _extract_simple_keywords(self, keybert_results, text):
        """간단하고 핵심적인 키워드만 추출"""
        simple_keywords = []
        
        # 불용어 확장 (도서 검색에 불필요한 단어들)
        stopwords = {
            '것', '수', '등', '더', '매우', '정말', '아주', '가장', '오늘', '어제', '내일',
            '이번', '저번', '다음', '지난', '최근', '요즘', '현재', '이제', '벌써', '또한',
            '기사', '뉴스', '보도', '발표', '소식', '알려', '한다', '된다', '있다', '없다',
            '했다', '했습니다', '합니다', '입니다', '때문', '따라', '통해', '대해', '위해',
            '관련', '경우', '상황', '문제', '결과', '영향', '변화', '증가', '감소', '그리고',
            '하지만', '그러나', '또는', '그래서', '따라서', '그런데', '만약', '만일',
            '대통령', '정부', '국가', '사회', '국민', '시민', '우리', '저희', '이들',
            '모든', '각각', '여러', '다양한', '주요', '중요', '필요', '가능', '어려운',
            '새로운', '지난해', '올해', '내년', '이후', '이전', '당시', '현재', '미래'
        }
        
        for keyword, score in keybert_results:
            keyword = keyword.strip()
            
            # 기본 필터링
            if (len(keyword) < 2 or 
                keyword.isdigit() or 
                keyword in stopwords):
                continue
            
            # 구두점이나 특수문자 제거
            import re
            keyword = re.sub(r'[^\w\s가-힣]', '', keyword).strip()
            if not keyword:
                continue
            
            # 너무 긴 구문은 단어로 분할
            if len(keyword) > 10 or ' ' in keyword:
                words = keyword.split()
                for word in words:
                    word = word.strip()
                    if (len(word) >= 2 and 
                        word not in stopwords and 
                        not word.isdigit() and
                        word not in simple_keywords):
                        simple_keywords.append(word)
            else:
                if keyword not in simple_keywords:
                    simple_keywords.append(keyword)
        
        # 추가로 중요 단어 추출 (고유명사, 전문용어)
        important_words = self._extract_important_words(text)
        for word in important_words:
            if word not in simple_keywords and len(simple_keywords) < 10:
                simple_keywords.append(word)
        
        return simple_keywords

    def _extract_important_words(self, text):
        """텍스트에서 중요한 단어들 추출 (고유명사, 전문용어 등)"""
        import re
        
        important_words = []
        
        # 고유명사 패턴 (대문자로 시작하는 영어 단어)
        english_proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', text)
        important_words.extend(english_proper_nouns)
        
        # 한국어 인명 패턴 (3-4글자 한글)
        korean_names = re.findall(r'[가-힣]{3,4}(?=\s|$|[^\w가-힣])', text)
        for name in korean_names:
            # 일반적인 단어가 아닌 것 같은 경우만 (성+이름 패턴)
            if not any(common in name for common in ['것입니다', '합니다', '있습니다']):
                important_words.append(name)
        
        # 전문용어나 브랜드명 (영어+숫자 조합)
        tech_terms = re.findall(r'[A-Za-z]+\d+|[A-Za-z]{3,}', text)
        important_words.extend(tech_terms)
        
        # 중복 제거 및 필터링
        filtered_words = []
        for word in important_words:
            if (len(word) >= 2 and 
                word not in filtered_words and
                not word.isdigit()):
                filtered_words.append(word)
        
        return filtered_words[:5]  # 상위 5개만

    def _are_similar_keywords(self, kw1, kw2):
        """두 키워드가 유사한지 확인"""
        if kw1 == kw2:
            return True
        
        # 한 키워드가 다른 키워드에 포함되는 경우
        if kw1 in kw2 or kw2 in kw1:
            return True
        
        # 공통 단어가 많은 경우
        words1 = set(kw1.split())
        words2 = set(kw2.split())
        if len(words1.intersection(words2)) >= max(1, min(len(words1), len(words2)) // 2):
            return True
        
        return False

    def _simple_keyword_extraction(self, text, top_k):
        """KeyBERT 실패 시 간단한 키워드 추출"""
        import re
        
        # 한글 단어 추출 (2-6글자)
        korean_words = re.findall(r'[가-힣]{2,6}', text)
        
        # 영어 단어 추출 (대문자로 시작하는 단어 우선)
        english_words = re.findall(r'[A-Z][a-zA-Z]{1,10}', text)
        english_words.extend(re.findall(r'[a-zA-Z]{3,8}', text))
        
        all_words = korean_words + english_words
        
        # 불용어 제거
        stopwords = {'것', '수', '등', '더', '매우', '정말', '아주', '가장', '한다', '된다', '있다', '없다'}
        filtered_words = [word for word in all_words if word not in stopwords and len(word) >= 2]
        
        # 빈도 계산
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 빈도순 정렬하되, 길이도 고려 (짧은 단어 우선)
        sorted_words = sorted(word_freq.items(), key=lambda x: (x[1], -len(x[0])), reverse=True)
        
        return [word for word, freq in sorted_words[:top_k]]

    def load_news_csv(self, csv_path):
        """뉴스 CSV 파일 로드"""
        try:
            logger.info(f"뉴스 파일 로드: {csv_path}")
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            logger.info(f"로드된 뉴스 기사 수: {len(df)}개")
            return df
        except Exception as e:
            logger.error(f"뉴스 파일 로드 실패: {str(e)}")
            return None

    def summarize_by_keyword(self, news_df):
        """키워드별로 뉴스 요약 및 주요 키워드 추출"""
        if self.model is None or self.kw_model is None:
            self.load_models()
        
        logger.info("키워드별 뉴스 요약 및 키워드 추출 시작...")
        
        # 키워드별로 그룹화
        keyword_groups = news_df.groupby('keyword')
        summary_results = []
        
        for keyword, group in keyword_groups:
            logger.info(f"'{keyword}' 키워드 처리 중... ({len(group)}개 기사)")
            
            # 제목과 설명을 합쳐서 하나의 텍스트로 만들기
            combined_text = ""
            for _, row in group.iterrows():
                title = str(row.get('title', ''))
                description = str(row.get('description', ''))
                if title and title != 'nan':
                    combined_text += title + ". "
                if description and description != 'nan':
                    combined_text += description + " "
            
            # 텍스트가 너무 길면 앞부분만 사용
            if len(combined_text) > 2000:
                combined_text = combined_text[:2000]
            
            # 요약 생성
            start_time = time.time()
            if combined_text.strip():
                summary = self.summarize_text(combined_text)
                # 주요 키워드 추출 (요약된 텍스트 우선, 원본 텍스트 보조)
                # 요약문에서 더 정확한 키워드를 추출할 수 있음
                summary_keywords = self.extract_keywords(summary, top_k=3)
                original_keywords = self.extract_keywords(combined_text[:1000], top_k=3)  # 원본은 일부만 사용
                
                # 중복 제거하면서 합치기
                all_keywords = summary_keywords.copy()
                for kw in original_keywords:
                    if kw not in all_keywords and len(all_keywords) < 5:
                        all_keywords.append(kw)
                
                main_keywords = all_keywords[:5]  # 최대 5개
            else:
                summary = "요약할 내용이 없습니다."
                main_keywords = []
            
            elapsed_time = time.time() - start_time
            
            # 결과 저장
            summary_results.append({
                'keyword': keyword,
                'article_count': len(group),
                'summary': summary,
                'main_keywords': ', '.join(main_keywords),  # 리스트를 문자열로 변환
                'original_length': len(combined_text),
                'summary_length': len(summary),
                'compression_ratio': round(len(summary) / len(combined_text) * 100, 1) if combined_text else 0,
                'processing_time': round(elapsed_time, 2),
                'created_at': datetime.datetime.now().isoformat()
            })
            
            logger.info(f"  완료: {len(summary)}자 요약, 주요 키워드: {main_keywords[:3]}...")
        
        logger.info(f"요약 및 키워드 추출 완료: {len(summary_results)}개 키워드")
        return summary_results

    def save_summaries(self, summaries, output_file=None):
        """요약 결과를 CSV로 저장"""
        if not output_file:
            output_file = f"summaries_with_keywords_{self.timestamp}.csv"
        
        try:
            df = pd.DataFrame(summaries)
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"요약 결과 저장: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"요약 결과 저장 실패: {str(e)}")
            return None

    def print_summary_report(self, summaries):
        """요약 결과 리포트 출력"""
        if not summaries:
            print("요약 결과가 없습니다.")
            return
        
        print("\n" + "="*80)
        print("뉴스 요약 및 키워드 추출 결과 리포트")
        print("="*80)
        
        total_articles = sum(s['article_count'] for s in summaries)
        avg_compression = sum(s['compression_ratio'] for s in summaries) / len(summaries)
        total_time = sum(s['processing_time'] for s in summaries)
        
        print(f"총 키워드 수: {len(summaries)}개")
        print(f"총 기사 수: {total_articles}개")
        print(f"평균 압축률: {avg_compression:.1f}%")
        print(f"총 처리 시간: {total_time:.2f}초")
        
        print(f"\n키워드별 요약 및 주요 키워드:")
        for i, summary in enumerate(summaries, 1):
            print(f"\n{i:2d}. 검색 키워드: {summary['keyword']} ({summary['article_count']}개 기사)")
            print(f"    요약: {summary['summary'][:100]}...")
            print(f"    주요 키워드: {summary['main_keywords']}")
            print(f"    압축률: {summary['compression_ratio']}% ({summary['original_length']}자 → {summary['summary_length']}자)")
        
        print("="*80)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="KoT5 + KeyBERT를 사용한 뉴스 요약 및 키워드 추출기")
    parser.add_argument("--input", "-i", required=True, help="뉴스 CSV 파일")
    parser.add_argument("--output", "-o", default=None, help="요약 결과 CSV 파일")
    parser.add_argument("--model", "-m", default="noahkim/KoT5_news_summarization", help="사용할 요약 모델")
    parser.add_argument("--max_length", type=int, default=150, help="최대 요약 길이")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("뉴스 요약 및 키워드 추출기 (KoT5 + KeyBERT)")
    print("=" * 80)
    print(f"입력 파일: {args.input}")
    print(f"요약 모델: {args.model}")
    print(f"최대 요약 길이: {args.max_length}")
    
    # 요약기 초기화
    summarizer = NewsSummarizer(args.model)
    
    try:
        # 뉴스 데이터 로드
        news_df = summarizer.load_news_csv(args.input)
        if news_df is None or len(news_df) == 0:
            print("❌ 뉴스 데이터를 로드할 수 없습니다.")
            return
        
        # 키워드별 요약 및 키워드 추출
        summaries = summarizer.summarize_by_keyword(news_df)
        
        # 사용된 KeyBERT 모델 정보 출력
        if hasattr(summarizer, 'current_model'):
            print(f"\n사용된 KeyBERT 모델: {summarizer.current_model}")
        
        if not summaries:
            print("❌ 요약 및 키워드 추출에 실패했습니다.")
            return
        
        # 결과 저장
        output_file = summarizer.save_summaries(summaries, args.output)
        
        if output_file:
            print(f"\n✅ 요약 및 키워드 추출 완료!")
            print(f"📄 저장된 파일: {output_file}")
            
            # 결과 리포트
            summarizer.print_summary_report(summaries)
        else:
            print("❌ 결과 저장에 실패했습니다.")
    
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.exception(f"요약 처리 중 오류 발생: {str(e)}")


if __name__ == "__main__":
    main()