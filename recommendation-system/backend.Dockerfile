# backend.Dockerfile

# 1. 파이썬 3.9 버전을 기반으로 이미지를 만듭니다.
FROM python:3.9

# 2. [핵심 수정!] 컨테이너의 운영체제를 업데이트하고, 최신 보안 인증서를 설치합니다.
RUN apt-get update && apt-get install -y ca-certificates

# 3. 컨테이너 안의 작업 폴더를 /app으로 지정합니다.
WORKDIR /app

# 4. requirements.txt 파일을 먼저 복사합니다.
COPY requirements.txt .

# 5. 라이브러리를 설치합니다.
RUN pip install --no-cache-dir -r requirements.txt

# 6. 현재 프로젝트 폴더의 모든 파일을 컨테이너 안으로 복사합니다.
COPY . .

# 7. gunicorn 웹 서버를 사용해 5001번 포트로 api_server.py를 실행합니다.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "api_server:app"]