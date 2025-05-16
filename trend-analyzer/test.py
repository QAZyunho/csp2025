from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os
import time
import re
from rouge import Rouge  # pip install rouge

def load_model(model_name="noahkim/KoT5_news_summarization"):
    print(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    model.to(device)
    return model, tokenizer, device

def parse_test_articles(file_path):
    articles_by_keyword = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        current_keyword = None
        current_article = []
        
        for line in file:
            line = line.strip()
            if not line:
                if current_keyword and current_article:
                    if current_keyword not in articles_by_keyword:
                        articles_by_keyword[current_keyword] = []
                    articles_by_keyword[current_keyword].append(' '.join(current_article))
                    current_article = []
                continue
                
            if line.startswith('keyword:'):
                current_keyword = line[len('keyword:'):].strip()
            elif line.startswith('내용:'):
                current_article.append(line[len('내용:'):].strip())
            else:
                current_article.append(line)
        
        if current_keyword and current_article:
            if current_keyword not in articles_by_keyword:
                articles_by_keyword[current_keyword] = []
            articles_by_keyword[current_keyword].append(' '.join(current_article))
    
    return articles_by_keyword

def clean_summary(text):
    text = re.sub(r'\s+', ' ', text).strip()
    if not text.endswith(('.', '?', '!')):
        sentences = text.split('.')
        if len(sentences) > 1:
            text = '.'.join(sentences[:-1]) + '.'
        else:
            text += '.'
    return text

def summarize_with_kot5(text, model, tokenizer, device, max_length=150):
    max_input_length = 512
    input_text = "summarize: " + text
    inputs = tokenizer(input_text, return_tensors="pt", max_length=max_input_length, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model.generate(
            inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_length=max_length,
            min_length=20,
            length_penalty=1.0,
            num_beams=4,
            early_stopping=True
        )
    summary = tokenizer.decode(outputs[0], skip_special_tokens=True)
    summary = clean_summary(summary)
    return summary

def evaluate_rouge(hypothesis, reference):
    rouge = Rouge()
    try:
        scores = rouge.get_scores(hypothesis, reference)[0]
        return scores
    except Exception as e:
        print(f"ROUGE Error: {e}")
        return {
            "rouge-1": {"r": 0, "p": 0, "f": 0},
            "rouge-2": {"r": 0, "p": 0, "f": 0},
            "rouge-l": {"r": 0, "p": 0, "f": 0}
        }

def test_kot5_from_file(model_name, input_file, output_file):
    model, tokenizer, device = load_model(model_name)
    test_data = parse_test_articles(input_file)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=== KoT5 Summarization Results ===\n\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Device: {device}\n")
        f.write(f"Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for keyword, articles in test_data.items():
            print(f"Summarizing articles for '{keyword}' ...")
            combined_article = " ".join(articles)
            original_length = len(combined_article)

            start_time = time.time()
            target_length = max(50, min(150, int(original_length * 0.25)))
            combined_summary = summarize_with_kot5(combined_article, model, tokenizer, device, max_length=target_length)
            elapsed_time = time.time() - start_time

            f.write(f"## Keyword: {keyword}\n\n")
            f.write(f"Summary: {combined_summary}\n")
            f.write(f"Processing Time: {elapsed_time:.2f} seconds\n")
            f.write(f"Original Length: {original_length} characters\n")
            f.write(f"Summary Length: {len(combined_summary)} characters\n\n")
            f.write("-" * 80 + "\n\n")
            
            print(f"Summary for '{keyword}': {combined_summary}")
            print(f"Time: {elapsed_time:.2f}s")
            print("-" * 50)

    print(f"\nSummarization complete. Results saved to {output_file}")
    
if __name__ == "__main__":
    test_kot5_from_file("noahkim/KoT5_news_summarization", "example_data.txt", "kot5_summaries.txt")
