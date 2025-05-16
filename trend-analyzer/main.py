import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import argparse
import os
import time

def load_model(model_name):
    """모델과 토크나이저를 로드하는 함수 - Auto 클래스 사용"""
    print(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    
    # GPU 사용 가능 시 모델을 GPU로 이동
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    model.to(device)
    
    return model, tokenizer, device

def summarize_text(text, model, tokenizer, device, max_length=50):
    """텍스트를 요약하는 함수"""
    # 입력 인코딩
    inputs = tokenizer(text, return_tensors="pt", max_length=1024, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # 추론 모드 및 그래디언트 계산 비활성화
    model.eval()
    with torch.no_grad():
        # 요약 생성
        summary_ids = model.generate(
            inputs["input_ids"],
            num_beams=4,
            max_length=max_length,
            min_length=10,
            early_stopping=True
        )
    
    # 토큰 디코딩
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

# 나머지 코드는 동일하게 유지