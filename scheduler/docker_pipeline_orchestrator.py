#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker 컨테이너 기반 파이프라인 오케스트레이터
각 단계를 별도의 Docker 컨테이너로 순차 실행
파일 위치: scheduler/docker_pipeline_orchestrator.py
"""

import os
import sys
import subprocess
import time
import datetime
import logging
import json
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DockerPipelineOrchestrator:
    """Docker 컨테이너 기반 파이프라인 오케스트레이터"""
    
    def __init__(self):
        self.date_str = datetime.datetime.now().strftime("%y%m%d")
        self.start_time = datetime.datetime.now()
        self.network_name = "cs-project-network"
        
        # 환경변수 로드
        self.firebase_config_path = os.getenv('FIREBASE_CONFIG_PATH', '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.naver_client_id = os.getenv('NAVER_CLIENT_ID')
        self.naver_client_secret = os.getenv('NAVER_CLIENT_SECRET')
        
        # Docker 이미지 태그 설정
        self.base_tag = "cs-project-2025"
        
        logger.info(f"🐳 Docker 파이프라인 오케스트레이터 초기화 (날짜: {self.date_str})")
    
    def check_environment(self):
        """환경변수 및 Docker 환경 확인"""
        logger.info("🔍 환경변수 및 Docker 환경 확인 중...")
        
        # 필수 환경변수 확인
        required_env = {
            'GEMINI_API_KEY': self.gemini_api_key,
            'NAVER_CLIENT_ID': self.naver_client_id,
            'NAVER_CLIENT_SECRET': self.naver_client_secret
        }
        
        missing_env = [key for key, value in required_env.items() if not value]
        if missing_env:
            logger.error(f"❌ 필수 환경변수가 설정되지 않았습니다: {', '.join(missing_env)}")
            return False
        
        # Firebase 설정 파일 확인
        if not os.path.exists(self.firebase_config_path):
            logger.error(f"❌ Firebase 설정 파일이 없습니다: {self.firebase_config_path}")
            return False
        
        # Docker 네트워크 확인/생성
        try:
            result = subprocess.run(['docker', 'network', 'ls'], capture_output=True, text=True)
            if self.network_name not in result.stdout:
                logger.info(f"🌐 Docker 네트워크 생성 중: {self.network_name}")
                subprocess.run(['docker', 'network', 'create', self.network_name], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Docker 네트워크 설정 실패: {e}")
            return False
        
        logger.info("✅ 환경변수 및 Docker 환경 확인 완료")
        return True
    
    def build_images_if_needed(self):
        """필요한 Docker 이미지들을 빌드"""
        logger.info("🔨 Docker 이미지 빌드 확인 중...")
        
        images_to_build = [
            {
                'name': f"{self.base_tag}-keyword-collector",
                'dockerfile': 'dockerfiles/Dockerfile.keyword-collector',
                'context': '.'
            },
            {
                'name': f"{self.base_tag}-news-collector", 
                'dockerfile': 'dockerfiles/Dockerfile.news-collector',
                'context': '.'
            },
            {
                'name': f"{self.base_tag}-trend-analyzer",
                'dockerfile': 'dockerfiles/Dockerfile.trend-analyzer', 
                'context': '.'
            },
            {
                'name': f"{self.base_tag}-library-searcher",
                'dockerfile': 'dockerfiles/Dockerfile.library-searcher',
                'context': '.'
            }
        ]
        
        for image_info in images_to_build:
            try:
                # 이미지 존재 확인
                result = subprocess.run(
                    ['docker', 'images', '-q', image_info['name']], 
                    capture_output=True, text=True
                )
                
                if not result.stdout.strip():
                    logger.info(f"🔨 이미지 빌드 중: {image_info['name']}")
                    
                    build_cmd = [
                        'docker', 'build',
                        '-t', image_info['name'],
                        '-f', image_info['dockerfile'],
                        image_info['context']
                    ]
                    
                    subprocess.run(build_cmd, check=True, cwd='/app')
                    logger.info(f"✅ 이미지 빌드 완료: {image_info['name']}")
                else:
                    logger.info(f"✅ 이미지 존재 확인: {image_info['name']}")
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ 이미지 빌드 실패: {image_info['name']} - {e}")
                return False
        
        return True
    
    def run_docker_step(self, step_name: str, image_name: str, command: list = None, 
                   volumes: dict = None, environment: dict = None, 
                   timeout: int = 1800) -> bool:
        """Docker 컨테이너로 파이프라인 단계 실행"""
        logger.info(f"🐳 {step_name} 시작...")
        
        # 컨테이너 이름을 영문으로 변환
        container_name_map = {
            '1단계: 트렌드 키워드 수집': 'pipeline-keyword-collector',
            '2단계: 네이버 뉴스 수집': 'pipeline-news-collector', 
            '3단계: Gemini 트렌드 분석': 'pipeline-trend-analyzer',
            '4단계: 도서 검색 및 추천': 'pipeline-library-searcher'
        }
        
        # 컨테이너 이름 생성 (안전한 이름으로 변환)
        safe_step_name = container_name_map.get(step_name, 'pipeline-unknown')
        container_name = f"{safe_step_name}-{self.date_str}"
        
        # 기본 환경변수 설정
        base_env = {
            'PYTHONUNBUFFERED': '1',
            'PYTHONPATH': '/app'
        }
        if environment:
            base_env.update(environment)
        
        # 기본 볼륨 설정 
        base_volumes = {}
        if volumes:
            base_volumes.update(volumes)
            
        # Docker run 명령 구성
        docker_cmd = [
            'docker', 'run', '--rm',
            '--network', self.network_name,
            '--name', container_name
        ]
        
        # 환경변수 추가
        for key, value in base_env.items():
            docker_cmd.extend(['-e', f"{key}={value}"])
        
        # 볼륨 마운트 추가
        for host_path, container_path in base_volumes.items():
            docker_cmd.extend(['-v', f"{host_path}:{container_path}"])
        
        # 이미지 이름 추가
        docker_cmd.append(image_name)
        
        # 실행 명령 추가
        if command:
            docker_cmd.extend(command)
        
        try:
            start_time = time.time()
            
            logger.info(f"🚀 실행 명령: {' '.join(docker_cmd[-10:])}")  # 마지막 부분만 로그
            
            # 컨테이너 실행
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd='/app'
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"✅ {step_name} 완료 (소요시간: {execution_time:.1f}초)")
                
                # 성공 로그 출력 (마지막 몇 줄만)
                if result.stdout:
                    stdout_lines = result.stdout.strip().split('\n')
                    for line in stdout_lines[-5:]:  # 마지막 5줄만
                        if line.strip():
                            logger.info(f"   📝 {line.strip()}")
                
                return True
            else:
                logger.error(f"❌ {step_name} 실패 (코드: {result.returncode})")
                
                # 오류 로그 출력
                if result.stderr:
                    for line in result.stderr.strip().split('\n')[-10:]:  # 마지막 10줄만
                        if line.strip():
                            logger.error(f"   ❌ {line.strip()}")
                
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {step_name} 시간 초과 ({timeout}초)")
            
            # 시간 초과된 컨테이너 정리
            try:
                subprocess.run(['docker', 'kill', container_name], check=False)
            except:
                pass
            
            return False
        except Exception as e:
            logger.error(f"❌ {step_name} 실행 중 오류: {str(e)}")
            return False
        
    def run_pipeline(self) -> bool:
        """Docker 컨테이너 기반 전체 파이프라인 실행"""
        logger.info("🚀 Docker 컨테이너 기반 파이프라인 시작")
        logger.info("=" * 70)
        
        # 파이프라인 단계 정의
        pipeline_steps = [
            {
                'name': '1단계: 트렌드 키워드 수집',
                'image': f"{self.base_tag}-keyword-collector",
                'command': [
                    'python', 'trend-collector/keyword_collector.py',
                    '--gemini_api_key', self.gemini_api_key,
                    '--firebase_config', '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json'
                ],
                'timeout': 1800  # 30분
            },
            {
                'name': '2단계: 네이버 뉴스 수집',
                'image': f"{self.base_tag}-news-collector",
                'command': [
                    'python', 'trend-collector/naver_news_collector.py',
                    '--firebase_config', '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                    '--max_articles', '5'
                ],
                'environment': {
                    'NAVER_CLIENT_ID': self.naver_client_id,
                    'NAVER_CLIENT_SECRET': self.naver_client_secret
                },
                'timeout': 900  # 15분
            },
            {
                'name': '3단계: Gemini 트렌드 분석',
                'image': f"{self.base_tag}-trend-analyzer",
                'command': [
                    'python', 'trend-analyzer/trend_analyzer.py',
                    '--gemini_api_key', self.gemini_api_key,
                    '--firebase_config', '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json'
                ],
                'timeout': 1200  # 20분
            },
            {
                'name': '4단계: 도서 검색 및 추천',
                'image': f"{self.base_tag}-library-searcher",
                'command': [
                    'python', 'library-searcher/search_book.py',
                    '--gemini_api_key', self.gemini_api_key,
                    '--firebase_config', '/app/csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json',
                    '--books_per_keyword', '10',
                    '--final_books_per_trend', '5'
                ],
                'timeout': 2400  # 40분
            }
        ]
        
        # 단계별 실행
        for i, step in enumerate(pipeline_steps, 1):
            logger.info(f"\n📋 {step['name']} 시작...")
            
            success = self.run_docker_step(
                step_name=step['name'],
                image_name=step['image'],
                command=step['command'],
                environment=step.get('environment'),
                timeout=step.get('timeout', 1800)
            )
            
            if not success:
                logger.error(f"❌ 파이프라인 중단: {step['name']} 실패")
                return False
            
            # 단계간 대기 (리소스 정리 및 안정성)
            if i < len(pipeline_steps):
                logger.info("⏳ 단계간 대기 중... (15초)")
                time.sleep(15)
        
        return True
    
    def cleanup_containers(self):
        """파이프라인 관련 컨테이너 정리"""
        logger.info("🧹 파이프라인 컨테이너 정리 중...")
        
        try:
            # 현재 날짜의 파이프라인 컨테이너 찾기
            result = subprocess.run(
                ['docker', 'ps', '-a', '--filter', f'name=pipeline-*-{self.date_str}', '-q'],
                capture_output=True, text=True
            )
            
            container_ids = result.stdout.strip().split('\n')
            container_ids = [cid for cid in container_ids if cid]
            
            if container_ids:
                # 컨테이너 삭제
                subprocess.run(['docker', 'rm', '-f'] + container_ids, check=False)
                logger.info(f"   🗑️ {len(container_ids)}개 컨테이너 정리 완료")
            
            # 오래된 파이프라인 컨테이너 정리 (7일 이상)
            old_result = subprocess.run(
                ['docker', 'ps', '-a', '--filter', 'name=pipeline-', '--format', '{{.Names}} {{.CreatedAt}}'],
                capture_output=True, text=True
            )
            
            for line in old_result.stdout.strip().split('\n'):
                if line and 'days ago' in line:
                    container_name = line.split()[0]
                    subprocess.run(['docker', 'rm', '-f', container_name], check=False)
            
        except Exception as e:
            logger.warning(f"⚠️ 컨테이너 정리 중 오류: {str(e)}")
    
    def check_api_health(self) -> bool:
        """추천 API 서버 상태 확인"""
        logger.info("🏥 추천 API 서버 상태 확인...")
        
        try:
            # Docker 네트워크 내에서 API 서버 확인
            result = subprocess.run([
                'docker', 'run', '--rm', '--network', self.network_name,
                'curlimages/curl:latest',
                'curl', '-f', '-s', 'http://recommendation-api:5001/'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("✅ 추천 API 서버 정상 동작 중")
                return True
            else:
                logger.warning("⚠️ 추천 API 서버 응답 없음 - 파이프라인은 계속 진행")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ API 서버 상태 확인 실패: {str(e)}")
            return False
    
    def run(self):
        """파이프라인 메인 실행"""
        try:
            # 환경 확인
            if not self.check_environment():
                logger.error("❌ 환경 확인 실패 - 파이프라인 중단")
                return False
            
            # Docker 이미지 빌드
            if not self.build_images_if_needed():
                logger.error("❌ Docker 이미지 빌드 실패 - 파이프라인 중단")
                return False
            
            # API 서버 상태 확인
            self.check_api_health()
            
            # 파이프라인 실행
            success = self.run_pipeline()
            
            # 실행 시간 계산
            execution_time = datetime.datetime.now() - self.start_time
            
            if success:
                logger.info("🎉 Docker 파이프라인 완료!")
                logger.info("📊 실행 요약:")
                logger.info(f"   📅 처리 날짜: {self.date_str}")
                logger.info(f"   🕐 총 소요시간: {execution_time}")
                logger.info(f"   🐳 실행 방식: Docker 컨테이너 기반")
                logger.info(f"   📁 Firebase 저장 경로:")
                logger.info(f"     - keywords/{self.date_str}")
                logger.info(f"     - news/{self.date_str}")
                logger.info(f"     - trend/{self.date_str}")
                logger.info(f"     - source/{self.date_str}")
                logger.info("🔔 추천 API 서버에서 새로운 데이터 사용 가능")
                
                # 컨테이너 정리
                self.cleanup_containers()
                
                return True
            else:
                logger.error("❌ Docker 파이프라인 실행 실패")
                self.cleanup_containers()
                return False
                
        except Exception as e:
            logger.exception(f"❌ 파이프라인 실행 중 예상치 못한 오류: {str(e)}")
            self.cleanup_containers()
            return False

def main():
    """메인 함수"""
    orchestrator = DockerPipelineOrchestrator()
    success = orchestrator.run()
    
    # 종료 코드 설정
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()