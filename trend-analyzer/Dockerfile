FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 예시 데이터 복사
COPY example_data.txt .

# 모델을 캐시하기 위한 초기 실행 (선택사항)
# RUN python -c "from transformers import MBartTokenizer, MBartForConditionalGeneration; MBartTokenizer.from_pretrained('facebook/mbart-large-cc25'); MBartForConditionalGeneration.from_pretrained('facebook/mbart-large-cc25')"

# 컨테이너 실행 시 예시 명령
CMD ["python", "main.py", "--input", "example_data.txt", "--output", "output_summaries.txt"]