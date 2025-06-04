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

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsSummarizer:
    """KoT5 모델을 사용한 뉴스 요약기"""
    
    def __init__(self, model_name="noahkim/KoT5_news_summarization"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = None
        self.timestamp = datetime.datetime.now().strftime("%y%m%d")
        
    def load_model(self):
        """KoT5 모델 로드"""
        logger.info(f"모델 로드 중: {self.model_name}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        
        # GPU 사용 가능 시 GPU로 이동
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()
        
        logger.info(f"모델 로드 완료: {self.device}")
        
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
        """키워드별로 뉴스 요약"""
        if self.model is None:
            self.load_model()
        
        logger.info("키워드별 뉴스 요약 시작...")
        
        # 키워드별로 그룹화
        keyword_groups = news_df.groupby('keyword')
        summary_results = []
        
        for keyword, group in keyword_groups:
            logger.info(f"'{keyword}' 키워드 요약 중... ({len(group)}개 기사)")
            
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
            else:
                summary = "요약할 내용이 없습니다."
            
            elapsed_time = time.time() - start_time
            
            # 결과 저장
            summary_results.append({
                'keyword': keyword,
                'article_count': len(group),
                'summary': summary,
                'original_length': len(combined_text),
                'summary_length': len(summary),
                'compression_ratio': round(len(summary) / len(combined_text) * 100, 1) if combined_text else 0,
                'processing_time': round(elapsed_time, 2),
                'created_at': datetime.datetime.now().isoformat()
            })
            
            logger.info(f"  완료: {len(summary)}자 요약 (압축률: {summary_results[-1]['compression_ratio']}%)")
        
        logger.info(f"요약 완료: {len(summary_results)}개 키워드")
        return summary_results

    def save_summaries(self, summaries, output_file=None):
        """요약 결과를 CSV로 저장"""
        if not output_file:
            output_file = f"summaries_{self.timestamp}.csv"
        
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
        
        print("\n" + "="*60)
        print("뉴스 요약 결과 리포트")
        print("="*60)
        
        total_articles = sum(s['article_count'] for s in summaries)
        avg_compression = sum(s['compression_ratio'] for s in summaries) / len(summaries)
        total_time = sum(s['processing_time'] for s in summaries)
        
        print(f"총 키워드 수: {len(summaries)}개")
        print(f"총 기사 수: {total_articles}개")
        print(f"평균 압축률: {avg_compression:.1f}%")
        print(f"총 처리 시간: {total_time:.2f}초")
        
        print(f"\n키워드별 요약 결과:")
        for i, summary in enumerate(summaries, 1):
            print(f"\n{i:2d}. {summary['keyword']} ({summary['article_count']}개 기사)")
            print(f"    요약: {summary['summary'][:100]}...")
            print(f"    압축률: {summary['compression_ratio']}% ({summary['original_length']}자 → {summary['summary_length']}자)")
        
        print("="*60)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="KoT5를 사용한 뉴스 요약기")
    parser.add_argument("--input", "-i", required=True, help="뉴스 CSV 파일")
    parser.add_argument("--output", "-o", default=None, help="요약 결과 CSV 파일")
    parser.add_argument("--model", "-m", default="noahkim/KoT5_news_summarization", help="사용할 모델")
    parser.add_argument("--max_length", type=int, default=150, help="최대 요약 길이")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("뉴스 요약기 (KoT5 기반)")
    print("=" * 60)
    print(f"입력 파일: {args.input}")
    print(f"모델: {args.model}")
    print(f"최대 요약 길이: {args.max_length}")
    
    # 요약기 초기화
    summarizer = NewsSummarizer(args.model)
    
    try:
        # 뉴스 데이터 로드
        news_df = summarizer.load_news_csv(args.input)
        if news_df is None or len(news_df) == 0:
            print("❌ 뉴스 데이터를 로드할 수 없습니다.")
            return
        
        # 키워드별 요약 생성
        summaries = summarizer.summarize_by_keyword(news_df)
        
        if not summaries:
            print("❌ 요약 생성에 실패했습니다.")
            return
        
        # 결과 저장
        output_file = summarizer.save_summaries(summaries, args.output)
        
        if output_file:
            print(f"\n✅ 요약 완료!")
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