# frontend.Dockerfile

# 1. 가볍고 빠른 웹서버인 Nginx를 기반으로 시작합니다.
FROM nginx:alpine

# 2. [핵심 수정!] 현재 폴더의 'frontend' 폴더 안의 내용물만 Nginx의 웹사이트 폴더로 복사합니다.
COPY ./frontend/ /usr/share/nginx/html/