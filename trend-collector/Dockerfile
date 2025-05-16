FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV PORT=3001
ENV DEBUG=True
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]