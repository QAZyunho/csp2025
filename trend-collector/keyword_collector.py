#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import xml.etree.ElementTree as ET
import pandas as pd
import logging
import time
import datetime
import os
import glob
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class SimpleKeywordCollector:
    """RSS와 자동 다운로드를 통합한 간소화된 키워드 수집기"""
    
    def __init__(self):
        self.all_keywords = []
        self.timestamp = datetime.datetime.now().strftime("%y%m%d")  # yymmdd 형식
        self.temp_files = []  # 임시 파일 추적용
        
    def collect_from_rss(self, geo_codes=['KR']):
        """RSS 피드를 통해 키워드 수집"""
        logger.info(f"RSS를 통한 키워드 수집 시작 - 국가: {geo_codes}")
        
        rss_keywords = []
        
        for geo in geo_codes:
            keywords = self._get_trends_from_rss(geo)
            for keyword in keywords:
                rss_keywords.append({
                    'keyword': keyword['title'],
                    'source': 'RSS',
                    'rank': keyword['index'] + 1,
                    'traffic': keyword.get('traffic', ''),
                    'country': geo,
                    'original_rank': keyword['index'] + 1  # 원본 순위 보존
                })
            time.sleep(1)  # API 호출 간격
            
        logger.info(f"RSS에서 {len(rss_keywords)}개 키워드 수집 완료")
        return rss_keywords
    
    def collect_from_auto_download(self, headless=True):
        """자동 다운로드를 통해 키워드 수집"""
        logger.info("📥 Google Trends 자동 다운로드 방식 시작...")
        
        auto_keywords = []
        driver = None
        
        try:
            # 다운로드 폴더 설정
            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(download_dir):
                download_dir = os.getcwd()  # 현재 디렉토리로 대체
            
            logger.info(f"다운로드 폴더: {download_dir}")
            
            # 기존 파일 목록 확인 (다운로드 전)
            before_files = set(os.listdir(download_dir))
            
            # Chrome 드라이버 초기화 (다운로드 설정 포함)
            driver = self._initialize_download_driver(headless, download_dir)
            
            # Google Trends 페이지 로드
            logger.info("🌐 Google Trends 페이지 로딩 중...")
            driver.get("https://trends.google.com/trends/trendingsearches/daily?geo=KR&hl=ko")
            
            # 페이지 로딩 대기
            self._wait_for_page_load(driver, timeout=30)
            
            # 쿠키 동의 처리
            try:
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), '동의') or contains(text(), 'Agree') or contains(text(), 'Accept')]")
                if cookie_buttons:
                    cookie_buttons[0].click()
                    logger.info("쿠키 동의 완료")
                    time.sleep(2)
            except Exception as e:
                logger.warning(f"쿠키 동의 처리 중 오류 (무시됨): {str(e)}")
            
            # 내보내기 버튼 찾기 및 클릭
            success = self._click_export_button(driver)
            if not success:
                logger.error("내보내기 버튼을 찾을 수 없습니다.")
                return auto_keywords
            
            time.sleep(2)
            
            # CSV 다운로드 버튼 클릭
            success = self._click_csv_download(driver)
            if not success:
                logger.error("CSV 다운로드 버튼을 찾을 수 없습니다.")
                return auto_keywords
            
            # 다운로드 완료 대기
            logger.info("📥 파일 다운로드 대기 중...")
            downloaded_file = self._wait_for_download(download_dir, before_files, timeout=30)
            
            if downloaded_file:
                logger.info(f"✅ 다운로드 완료: {downloaded_file}")
                # 임시 파일 목록에 추가
                self.temp_files.append(downloaded_file)
                
                # 다운로드된 파일에서 키워드 추출
                auto_keywords = self._parse_csv_file(downloaded_file)
                
            else:
                logger.error("파일 다운로드에 실패했습니다.")
                
        except Exception as e:
            logger.error(f"자동 다운로드 중 오류: {str(e)}")
            
        finally:
            if driver:
                driver.quit()
                
        logger.info(f"자동 다운로드에서 {len(auto_keywords)}개 키워드 수집 완료")
        return auto_keywords

    def _initialize_download_driver(self, headless=True, download_dir=None):
        """다운로드용 Chrome 드라이버 초기화"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless=new")
            
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--lang=ko-KR")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 다운로드 설정
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        return driver

    def _wait_for_page_load(self, driver, timeout=30):
        """페이지 로딩 대기"""
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(3)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            logger.info("페이지가 완전히 로드되었습니다.")
            return True
        except Exception as e:
            logger.warning(f"페이지 로드 대기 중 오류: {str(e)}")
            return False

    def _click_export_button(self, driver):
        """내보내기 버튼 클릭"""
        try:
            logger.info("🔍 내보내기 버튼 검색 중...")
            
            # JavaScript로 버튼 찾기
            export_found = driver.execute_script("""
                var buttons = document.querySelectorAll('button, div[role="button"], span');
                var exportButton = Array.from(buttons).find(b => 
                    b.textContent.includes('내보내기') || 
                    b.textContent.includes('Export') ||
                    b.textContent.includes('다운로드') || 
                    b.textContent.includes('Download')
                );
                if (exportButton) {
                    console.log('내보내기 버튼 찾음: ' + exportButton.textContent);
                    exportButton.click();
                    return true;
                }
                return false;
            """)
            
            if export_found:
                logger.info("✅ 내보내기 버튼 클릭 성공")
                return True
            
            # XPath로 시도
            export_xpath_patterns = [
                "//button[contains(., '내보내기')]",
                "//button[contains(., 'Export')]", 
                "//div[contains(@role, 'button')][contains(., '내보내기')]",
                "//div[contains(@role, 'button')][contains(., 'Export')]",
                "//*[contains(text(), '내보내기')]",
                "//*[contains(text(), 'Export')]"
            ]
            
            for xpath in export_xpath_patterns:
                try:
                    buttons = driver.find_elements(By.XPATH, xpath)
                    if buttons:
                        logger.info(f"XPath로 내보내기 버튼 찾음: {buttons[0].text}")
                        buttons[0].click()
                        return True
                except Exception as e:
                    continue
                    
            return False
            
        except Exception as e:
            logger.error(f"내보내기 버튼 클릭 중 오류: {str(e)}")
            return False

    def _click_csv_download(self, driver):
        """CSV 다운로드 버튼 클릭"""
        try:
            logger.info("📄 CSV 다운로드 옵션 검색 중...")
            
            # 다양한 방법으로 CSV 다운로드 버튼 찾기
            csv_found = driver.execute_script("""
                var items = document.querySelectorAll('li, div[role="menuitem"], span, a');
                var csvItem = Array.from(items).find(item => {
                    var text = item.textContent.toLowerCase();
                    return text.includes('csv') || 
                           text.includes('다운로드') ||
                           text.includes('download');
                });
                if (csvItem) {
                    console.log('CSV 다운로드 옵션 찾음: ' + csvItem.textContent);
                    csvItem.click();
                    return true;
                }
                return false;
            """)
            
            if csv_found:
                logger.info("✅ CSV 다운로드 버튼 클릭 성공")
                return True
            
            # XPath로 시도
            csv_xpath_patterns = [
                "//li[contains(., 'CSV')]",
                "//li[contains(., 'csv')]",
                "//div[contains(@role, 'menuitem')][contains(., 'CSV')]",
                "//a[contains(., 'CSV')]",
                "//*[contains(text(), 'CSV')]",
                "//*[contains(text(), '다운로드')]"
            ]
            
            for xpath in csv_xpath_patterns:
                try:
                    items = driver.find_elements(By.XPATH, xpath)
                    if items:
                        logger.info(f"XPath로 CSV 다운로드 옵션 찾음: {items[0].text}")
                        items[0].click()
                        return True
                except Exception as e:
                    continue
                    
            return False
            
        except Exception as e:
            logger.error(f"CSV 다운로드 버튼 클릭 중 오류: {str(e)}")
            return False

    def _wait_for_download(self, download_dir, before_files, timeout=30):
        """다운로드 완료 대기"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                current_files = set(os.listdir(download_dir))
                new_files = current_files - before_files
                
                # .crdownload 파일 (다운로드 중인 파일) 제외
                completed_files = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')]
                
                if completed_files:
                    # CSV 파일 우선 검색
                    csv_files = [f for f in completed_files if f.endswith('.csv')]
                    if csv_files:
                        downloaded_file = os.path.join(download_dir, csv_files[0])
                        # 파일이 완전히 다운로드되었는지 확인 (크기가 0이 아닌지)
                        if os.path.getsize(downloaded_file) > 0:
                            return downloaded_file
                    
                    # CSV가 아닌 다른 파일도 확인
                    for filename in completed_files:
                        file_path = os.path.join(download_dir, filename)
                        if os.path.getsize(file_path) > 0:
                            return file_path
                
                time.sleep(1)
                
            except Exception as e:
                logger.debug(f"다운로드 대기 중 오류: {str(e)}")
                time.sleep(1)
        
        logger.error(f"{timeout}초 내에 다운로드가 완료되지 않았습니다.")
        return None

    def _parse_csv_file(self, csv_file_path):
        """CSV 파일에서 키워드 추출"""
        keywords = []
        
        try:
            # CSV 파일 읽기 (다양한 인코딩 시도)
            csv_data = None
            for encoding in ['utf-8-sig', 'utf-8', 'cp949', 'latin-1']:
                try:
                    with open(csv_file_path, 'r', encoding=encoding) as f:
                        csv_data = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if not csv_data:
                logger.error("CSV 파일을 읽을 수 없습니다.")
                return keywords
            
            # CSV 데이터 파싱
            lines = csv_data.strip().split('\n')
            logger.info(f"CSV 파일에서 {len(lines)}줄 발견")
            
            rank = 1
            for i, line in enumerate(lines):
                # 빈 줄 건너뛰기
                if not line.strip():
                    continue
                
                # 첫 번째 줄이 헤더인 경우 건너뛰기
                if i == 0:
                    header_patterns = ['검색어', 'keyword', 'term', '순위', 'rank', '키워드']
                    if any(pattern in line.lower() for pattern in header_patterns):
                        logger.info(f"헤더 발견, 건너뛰기: {line}")
                        continue
                
                # 키워드 추출
                line_clean = line.strip().strip('﻿"')
                
                if ',' in line_clean:
                    keyword = line_clean.split(',')[0].strip().strip('"')
                else:
                    keyword = line_clean.strip().strip('"')
                
                # 빈 키워드나 숫자만 있는 경우 건너뛰기
                if keyword and not keyword.isdigit() and len(keyword) > 1:
                    keywords.append({
                        'keyword': keyword,
                        'source': 'Auto_Download',
                        'rank': rank,
                        'traffic': '',
                        'country': 'KR',  # 자동 다운로드는 한국 페이지에서
                        'original_rank': rank  # 원본 순위 보존
                    })
                    rank += 1
            
            logger.info(f"CSV에서 {len(keywords)}개 키워드 추출 완료")
            
        except Exception as e:
            logger.error(f"CSV 파일 처리 중 오류: {str(e)}")
            
        return keywords

    def _get_trends_from_rss(self, geo='KR'):
        """Google Trends RSS 피드에서 트렌드 가져오기"""
        url = f"https://trends.google.co.kr/trending/rss?geo={geo}"
        
        try:
            response = requests.get(url)
            if response.status_code != 200:
                logger.error(f"{geo} - Error: {response.status_code}")
                return []
            
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f"{geo} - XML 파싱 오류: {e}")
                content = response.content.decode('utf-8', errors='ignore')
                root = ET.fromstring(content.encode('utf-8'))
            
            trends = []
            channel = root.find('channel')
            if channel is None:
                logger.error(f"{geo} - 'channel' 요소를 찾을 수 없습니다.")
                return []
                
            items = channel.findall('item')
            logger.debug(f"{geo} - 총 {len(items)}개의 항목을 찾았습니다.")
            
            for idx, item in enumerate(items):
                try:
                    title_elem = item.find('title')
                    title = title_elem.text if title_elem is not None else 'No Title'
                    
                    # 트래픽 정보 찾기 (RSS에서 제공하는 추가 정보)
                    traffic = None
                    for elem in item:
                        if 'approxTraffic' in elem.tag:
                            traffic = elem.text
                            break
                    
                    trends.append({
                        'index': idx,
                        'title': title,
                        'traffic': traffic
                    })
                except Exception as e:
                    logger.error(f"{geo} - 항목 {idx} 처리 중 오류: {e}")
            
            return trends
        
        except Exception as e:
            logger.error(f"{geo} - 전체 처리 중 오류: {e}")
            return []

    def collect_all_keywords(self, use_rss=True, use_auto_download=True, geo_codes=['KR'], headless=True):
        """모든 방법으로 키워드 수집"""
        all_collected = []
        
        # RSS 방법
        if use_rss:
            try:
                rss_keywords = self.collect_from_rss(geo_codes)
                all_collected.extend(rss_keywords)
            except Exception as e:
                logger.error(f"RSS 수집 중 오류: {str(e)}")
        
        # 자동 다운로드 방법
        if use_auto_download:
            try:
                auto_keywords = self.collect_from_auto_download(headless)
                all_collected.extend(auto_keywords)
            except Exception as e:
                logger.error(f"자동 다운로드 수집 중 오류: {str(e)}")
        
        self.all_keywords = all_collected
        return all_collected
    
    def calculate_keyword_scores(self, external_ratings=None):
        """키워드 필터링 점수 시스템을 적용하여 점수 계산
        
        Args:
            external_ratings (dict): 외부 데이터베이스에서 가져온 키워드별 별점
                                   예: {'keyword1': 4.5, 'keyword2': 3.2}
                                   없으면 기본값 3.0 사용
        """
        logger.info("키워드 점수 계산 중...")
        
        if external_ratings is None:
            external_ratings = {}
        
        # 키워드별 클러스터 크기 계산 (같은 키워드가 여러 소스에서 나온 경우)
        keyword_counts = {}
        for item in self.all_keywords:
            keyword_lower = item['keyword'].lower().strip()
            keyword_counts[keyword_lower] = keyword_counts.get(keyword_lower, 0) + 1
        
        max_cluster_size = max(keyword_counts.values()) if keyword_counts else 1
        
        for item in self.all_keywords:
            keyword = item['keyword']
            keyword_lower = keyword.lower().strip()
            
            # 1. 클러스터 크기 점수 (기존 keyword_filter 방식)
            cluster_size = keyword_counts[keyword_lower]
            cluster_score = cluster_size / max_cluster_size
            
            # 2. 특수성 점수 (단어 수 기반)
            word_count = len(keyword.split())
            specificity_score = 1.0 + 0.1 * (word_count - 1)
            
            # 3. 특별 주제별 가중치 조정 (기존 keyword_filter 방식)
            # 날씨 관련 키워드 가중치 감소
            weather_terms = ['날씨', 'weather', '일기예보', '오늘의 날씨', '초단기', '장마']
            if keyword in weather_terms:
                specificity_score *= 0.6
            
            # 스포츠 경기 결과 패턴에 대한 가중치 감소
            if ' 대 ' in keyword or ' vs ' in keyword.lower() or 'vs' in keyword.lower():
                specificity_score *= 0.6
                cluster_score *= 0.7
            
            # 4. RSS 보너스 점수
            rss_bonus = 0.3 if item['source'] == 'RSS' else 0.0
            
            # 5. 원본 순위 기반 점수 (순위가 높을수록 점수 추가)
            original_rank = item.get('original_rank', 20)
            rank_score = max(0.5 - (original_rank - 1) * 0.02, 0.1)  # 1위=0.5점, 20위=0.12점
            
            # 6. 외부 데이터베이스 별점 점수 (1-5점을 0-1점으로 정규화)
            external_rating = external_ratings.get(keyword_lower, 3.0)  # 기본값 3점
            rating_score = (external_rating - 1) / 4  # 1점=0, 3점=0.5, 5점=1
            
            # 7. 최종 점수 계산 (가중 평균)
            final_score = (
                0.2 * cluster_score +      # 클러스터 크기 (20%)
                0.2 * specificity_score +   # 특수성 (20%)
                0.2 * rss_bonus +          # RSS 보너스 (20%)
                0.2 * rank_score +         # 원본 순위 (20%)
                0.2 * rating_score         # 외부 별점 (20%)
            )
            
            # 100점 만점으로 변환
            item['score'] = round(final_score * 100, 2)
            
        logger.info("키워드 점수 계산 완료")

    def load_external_ratings(self):
        """외부 데이터베이스에서 키워드 별점을 로드
        
        Returns:
            dict: 키워드별 별점 딕셔너리 또는 빈 딕셔너리
        
        Note:
            현재는 빈 딕셔너리를 반환하지만, 향후 데이터베이스 연동 시 
            이 메서드를 수정하여 실제 데이터를 가져오도록 구현
        """
        try:
            # TODO: 실제 데이터베이스 연동 시 구현
            # 예시:
            # import sqlite3
            # conn = sqlite3.connect('keyword_ratings.db')
            # cursor = conn.execute('SELECT keyword, rating FROM ratings')
            # ratings = {row[0].lower(): row[1] for row in cursor.fetchall()}
            # conn.close()
            # return ratings
            
            logger.info("외부 별점 데이터베이스를 확인했지만 데이터가 없습니다. 기본값 3.0을 사용합니다.")
            return {}
            
        except Exception as e:
            logger.warning(f"외부 별점 데이터 로드 실패: {str(e)}. 기본값 3.0을 사용합니다.")
            return {}

    def sort_by_final_score(self):
        """최종 점수 기준으로 키워드 정렬 및 순위 재할당"""
        # 점수 기준 내림차순 정렬
        self.all_keywords.sort(key=lambda x: x['score'], reverse=True)
        
        # 순위 재할당
        for i, keyword in enumerate(self.all_keywords, 1):
            keyword['rank'] = i
        
        logger.info("최종 점수 기준으로 키워드 정렬 완료")
    def remove_duplicates(self):
        """중복 키워드 제거 (점수 계산 전 단계)"""
        seen_keywords = {}
        unique_keywords = []
        
        # RSS 우선순위로 정렬 (중복 제거 시 RSS 우선 보존)
        priority_order = ['RSS', 'Auto_Download']
        sorted_keywords = sorted(self.all_keywords, 
                               key=lambda x: priority_order.index(x['source']) if x['source'] in priority_order else 999)
        
        for item in sorted_keywords:
            keyword_lower = item['keyword'].lower().strip()
            if keyword_lower not in seen_keywords:
                seen_keywords[keyword_lower] = True
                unique_keywords.append(item)
            else:
                logger.debug(f"중복 키워드 제거: {item['keyword']} ({item['source']})")
        
        original_count = len(self.all_keywords)
        self.all_keywords = unique_keywords
        
        logger.info(f"중복 제거: {original_count}개 → {len(unique_keywords)}개")
        return unique_keywords
    
    def save_final_result(self, filename=None):
        """최종 결과를 CSV로 저장 (rank, keyword, score)"""
        if not filename:
            filename = f"keywords_{self.timestamp}.csv"
        
        if not self.all_keywords:
            logger.warning("저장할 키워드가 없습니다.")
            return None
        
        # rank, keyword, score만 추출
        simple_data = []
        for item in self.all_keywords:
            simple_data.append({
                'rank': item['rank'],
                'keyword': item['keyword'],
                'score': item.get('score', 0)
            })
        
        df = pd.DataFrame(simple_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        logger.info(f"최종 결과 저장: {filename}")
        return filename
    
    def cleanup_temp_files(self):
        """임시 파일들 삭제"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"임시 파일 삭제: {temp_file}")
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패 {temp_file}: {str(e)}")
        
        self.temp_files.clear()
    
    def print_summary(self):
        """수집 결과 요약 출력"""
        if not self.all_keywords:
            print("수집된 키워드가 없습니다.")
            return
        
        # 소스별 통계
        source_stats = {}
        for item in self.all_keywords:
            source = item['source']
            source_stats[source] = source_stats.get(source, 0) + 1
        
        print("\n" + "="*50)
        print(f"키워드 수집 결과 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        print(f"총 키워드 수: {len(self.all_keywords)}개")
        
        print(f"\n소스별 분포:")
        for source, count in source_stats.items():
            print(f"  - {source}: {count}개")
        
        print(f"\n상위 20개 키워드:")
        for i, item in enumerate(self.all_keywords[:20], 1):
            source_tag = f"[{item['source']}]"
            score_info = f"(점수: {item.get('score', 0):.1f})"
            print(f"  {i:2d}. {item['keyword']} {score_info} {source_tag}")
        
        if len(self.all_keywords) > 20:
            print(f"  ... 외 {len(self.all_keywords) - 20}개")
        
        print("="*50)


def main():
    """메인 함수"""
    print("=" * 50)
    print("통합 키워드 수집기 (RSS + 자동다운로드)")
    print("=" * 50)
    
    # 수집기 초기화
    collector = SimpleKeywordCollector()
    
    # 고정 설정
    # geo_codes = ['KR', 'US']  # 한국, 미국 고정
    geo_codes = ['KR']  # 한국, 고정
    headless = True  # 헤드리스 모드 고정
    
    print(f"\n키워드 수집을 시작합니다...")
    print(f"RSS 국가: {', '.join(geo_codes)} (고정)")
    print(f"자동 다운로드: 헤드리스 모드 (고정)")
    print(f"우선순위: RSS → 자동다운로드 순서")
    
    # 키워드 수집 (RSS + 자동다운로드 통합)
    try:
        collected_keywords = collector.collect_all_keywords(
            use_rss=True,
            use_auto_download=True,
            geo_codes=geo_codes,
            headless=headless
        )
        
        if not collected_keywords:
            print("\n키워드를 수집하지 못했습니다.")
            return
        
        print(f"\n수집 완료! {len(collected_keywords)}개의 키워드를 수집했습니다.")
        
        # 중복 제거
        print("\n중복 키워드 제거 중...")
        collector.remove_duplicates()
        
        # 외부 데이터베이스에서 별점 로드
        print("외부 데이터베이스에서 키워드 별점 확인 중...")
        external_ratings = collector.load_external_ratings()
        
        # 키워드 점수 계산 및 정렬
        print("키워드 점수 계산 및 정렬 중...")
        collector.calculate_keyword_scores(external_ratings)
        collector.sort_by_final_score()
        
        # 결과 요약 출력
        collector.print_summary()
        
        # 파일 저장 - 자동 실행
        print("\n결과를 파일로 저장 중...")
        saved_file = collector.save_final_result()
        
        if saved_file:
            print(f"✅ 최종 결과 저장: {saved_file}")
        
        # 임시 파일 정리 - 자동 실행
        print("임시 다운로드 파일 정리 중...")
        collector.cleanup_temp_files()
        print("🗑️  임시 파일 정리 완료")
        
        print(f"\n✅ 키워드 수집이 완료되었습니다!")
        print(f"📊 최종 순서: RSS 키워드 (KR+US) → 자동다운로드 키워드")
        
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        # 중단되어도 임시 파일 정리
        collector.cleanup_temp_files()
    except Exception as e:
        logger.exception(f"키워드 수집 중 오류 발생: {str(e)}")
        # 오류 발생 시에도 임시 파일 정리
        collector.cleanup_temp_files()


if __name__ == "__main__":
    main()