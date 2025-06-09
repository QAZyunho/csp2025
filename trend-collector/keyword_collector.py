import requests
import xml.etree.ElementTree as ET
import pandas as pd
import logging
import time
import datetime
import os
import json
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import firebase_admin
from firebase_admin import credentials, firestore

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class CompleteKeywordProcessor:
    """키워드 수집 + Gemini 그룹핑을 통합한 완전한 처리기"""
    
    def __init__(self, gemini_api_key: str, firebase_config_path: str = None):
        # 기본 설정
        self.all_keywords = []
        self.timestamp = datetime.datetime.now().strftime("%y%m%d")
        self.temp_files = [] # 다운로드된 임시 파일들을 추적하여 삭제
        
        # Gemini 설정
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.init_firebase(firebase_config_path)
        
    def init_firebase(self, config_path):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                if config_path and os.path.exists(config_path):
                    cred = credentials.Certificate(config_path)
                    firebase_admin.initialize_app(cred)
                else:
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
            
            self.db = firestore.client(database_id='csproject2025')
            logger.info("✅ Firebase 연결 성공")
        except Exception as e:
            logger.error(f"❌ Firebase 연결 실패: {str(e)}")
            self.db = None
    
    def _save_results(self, final_keywords):
        """그룹핑된 키워드를 Firebase에 저장 (파일 저장 대신)"""
        if not final_keywords or not self.db:
            logger.warning("저장할 키워드가 없거나 Firebase 연결이 없습니다.")
            return False
        
        try:
            # keywords/{date} 문서에 저장
            doc_ref = self.db.collection('keywords').document(self.timestamp)
            
            # 키워드만 추출 (소스, 우선순위 정보는 메타데이터로)
            keywords_only = []
            trend_count = 0
            user_preferred_count = 0
            both_count = 0
            
            for item in final_keywords:
                keyword = item.get('keyword', '')
                source = item.get('source', 'unknown')
                
                if keyword:
                    keywords_only.append(keyword)
                    
                    # 소스별 카운트
                    if source == 'trend':
                        trend_count += 1
                    elif source == 'user_preferred':
                        user_preferred_count += 1
                    elif source == 'both':
                        both_count += 1
            
            # Firebase 저장 데이터 구조
            firebase_data = {
                'date': self.timestamp,
                'collection_time': datetime.datetime.now(),
                'total_keywords': len(keywords_only),
                'data_source': 'google_trends_gemini_with_user_preferences',
                'keywords': keywords_only,
                'metadata': {
                    'trend_keywords': trend_count,
                    'user_preferred_keywords': user_preferred_count,
                    'both_keywords': both_count
                }
            }
            
            doc_ref.set(firebase_data)
            logger.info(f"✅ Firebase에 {len(keywords_only)}개 키워드 저장 완료 (트렌드: {trend_count}, 사용자선호: {user_preferred_count}, 공통: {both_count})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase 저장 실패: {e}")
            return False
         
    def run_complete_workflow(self, geo_codes=['KR'], headless=True, use_rss=True, use_auto_download=True):
        """
        전체 워크플로우 실행: 수집 → 그룹핑 → 저장
        
        Args:
            geo_codes (list): 수집할 국가 코드 목록 (예: ['KR', 'US']).
            headless (bool): Selenium 브라우저를 헤드리스 모드로 실행할지 여부.
            use_rss (bool): RSS 피드를 통해 키워드를 수집할지 여부.
            use_auto_download (bool): 자동 다운로드 방식을 통해 키워드를 수집할지 여부.
        """
        logger.info("🚀 완전한 키워드 처리 워크플로우 시작...")
        
        try:
            # 1단계: 키워드 수집
            logger.info("📡 1단계: 키워드 수집 중...")
            raw_collected_keywords = self.collect_all_keywords(use_rss, use_auto_download, geo_codes, headless)
                        
            if not raw_collected_keywords:
                logger.error("키워드 수집 실패: 수집된 키워드가 없습니다.")
                return None
            
            logger.info(f"수집 완료: {len(raw_collected_keywords)}개 키워드")
            
            # Gemini에 보낼 키워드 텍스트만 추출
            keywords_for_gemini = [item['keyword'] for item in raw_collected_keywords]

            #1.5단계 사용자 선호도와 결합 
            logger.info("🤝 1.5단계: 사용자 선호도와 결합 중...")
            merged_keywords = self.merge_with_user_preferences_for_gemini(keywords_for_gemini)
    
            # 2단계: Gemini로 그룹핑
            logger.info("🤖 2단계: Gemini 그룹핑 중...")
            grouped_keywords = self._group_with_gemini(merged_keywords)
            
            if not grouped_keywords:
                logger.error("그룹핑 실패: Gemini로부터 유효한 응답을 받지 못했습니다.")
                return None
            
            logger.info(f"그룹핑 완료: {len(grouped_keywords)}개 키워드")
            
            # 3단계: 결과 저장 (키워드만)
            logger.info("💾 3단계: 결과 저장 중...")
            save_success  = self._save_results(grouped_keywords)
            
            if save_success:
                # 4단계: 요약 출력
                self._print_summary(grouped_keywords)
                return self.timestamp  # 날짜 ID 반환
            else:
                logger.error("Firebase 저장 실패")
                return None
            
        except Exception as e:
            logger.exception(f"워크플로우 실행 중 오류: {e}")
            return None
        finally:
            # 임시 파일 정리
            self._cleanup_temp_files()

    def collect_all_keywords(self, use_rss=True, use_auto_download=True, geo_codes=['KR'], headless=True):
        """
        모든 방법으로 키워드 수집을 총괄합니다.
        
        Args:
            use_rss (bool): RSS 피드를 통해 키워드를 수집할지 여부.
            use_auto_download (bool): 자동 다운로드 방식을 통해 키워드를 수집할지 여부.
            geo_codes (list): 수집할 국가 코드 목록.
            headless (bool): Selenium 브라우저를 헤드리스 모드로 실행할지 여부.
            
        Returns:
            list: 수집된 모든 키워드 (딕셔너리 리스트).
        """
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
        
        # 중복 제거 (키워드 텍스트 기준)
        unique_keywords = {}
        for item in all_collected:
            keyword_text = item['keyword'].strip().lower()
            if keyword_text not in unique_keywords:
                unique_keywords[keyword_text] = item
            else:
                # 더 높은 랭크 (낮은 숫자)를 가진 항목 유지
                if item.get('rank', float('inf')) < unique_keywords[keyword_text].get('rank', float('inf')):
                    unique_keywords[keyword_text] = item

        self.all_keywords = list(unique_keywords.values())
        logger.info(f"총 {len(self.all_keywords)}개의 고유 키워드 수집 완료 (중복 제거 후).")
        return self.all_keywords

    def collect_from_rss(self, geo_codes=['KR']):
        """
        RSS 피드를 통해 키워드 수집
        
        Args:
            geo_codes (list): 수집할 국가 코드 목록.
            
        Returns:
            list: 수집된 키워드 (딕셔너리 리스트).
        """
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
        """
        자동 다운로드를 통해 키워드 수집
        
        Args:
            headless (bool): Selenium 브라우저를 헤드리스 모드로 실행할지 여부.
            
        Returns:
            list: 수집된 키워드 (딕셔너리 리스트).
        """
        logger.info("📥 Google Trends 자동 다운로드 방식 시작...")
        
        auto_keywords = []
        driver = None
        
        try:
            # 다운로드 폴더 설정
            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            # 다운로드 디렉토리가 없으면 생성하거나 현재 디렉토리로 대체
            if not os.path.exists(download_dir):
                try:
                    os.makedirs(download_dir)
                    logger.info(f"다운로드 폴더 생성: {download_dir}")
                except OSError:
                    logger.warning(f"다운로드 폴더 '{download_dir}' 생성 실패. 현재 디렉토리로 대체합니다.")
                    download_dir = os.getcwd() 
            
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
                # 동의 버튼 텍스트 패턴 확장
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), '동의') or contains(text(), 'Agree') or contains(text(), 'Accept') or contains(text(), 'I agree')]")
                if cookie_buttons:
                    cookie_buttons[0].click()
                    logger.info("쿠키 동의 완료")
                    time.sleep(2) # 클릭 후 잠시 대기
                else:
                    logger.info("쿠키 동의 버튼을 찾을 수 없습니다 (없거나 이미 동의됨).")
            except Exception as e:
                logger.warning(f"쿠키 동의 처리 중 오류 (무시됨): {str(e)}")
            
            # 내보내기 버튼 찾기 및 클릭
            success = self._click_export_button(driver)
            if not success:
                logger.error("내보내기 버튼을 찾을 수 없습니다. 자동 다운로드를 건너뜝니다.")
                return auto_keywords
            
            time.sleep(2) # 메뉴가 나타날 때까지 잠시 대기
            
            # CSV 다운로드 버튼 클릭
            success = self._click_csv_download(driver)
            if not success:
                logger.error("CSV 다운로드 버튼을 찾을 수 없습니다. 자동 다운로드를 건너뜝니다.")
                return auto_keywords
            
            # 다운로드 완료 대기
            logger.info("📥 파일 다운로드 대기 중...")
            downloaded_file = self._wait_for_download(download_dir, before_files, timeout=30)
            
            if downloaded_file:
                logger.info(f"✅ 다운로드 완료: {downloaded_file}")
                # 임시 파일 목록에 추가
                self.temp_files.append(downloaded_file)
                
                # 다운로드된 파일에서 키워드 추출
                parsed_keywords = self._parse_csv_file(downloaded_file)
                
                # _parse_csv_file에서 반환된 키워드에 추가 정보 추가
                rank_counter = 1
                for kw_item in parsed_keywords:
                    auto_keywords.append({
                        'keyword': kw_item['keyword'],
                        'source': 'Auto_Download',
                        'rank': rank_counter,
                        'traffic': '', # 자동 다운로드 CSV에는 트래픽 정보가 없음
                        'country': 'KR', # 자동 다운로드는 현재 한국 페이지에서만 수행
                        'original_rank': rank_counter
                    })
                    rank_counter += 1
                
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
        """
        다운로드용 Chrome 드라이버 초기화
        
        Args:
            headless (bool): 헤드리스 모드 여부.
            download_dir (str): 다운로드 디렉토리 경로.
            
        Returns:
            webdriver.Chrome: 초기화된 Chrome 웹 드라이버.
        """
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless=new")
            
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--lang=ko-KR") # 언어 설정
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 다운로드 설정
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safeBrowse.enabled": True, # 안전 브라우징 기능 활성화 (보안 강화)
            "profile.default_content_settings.popups": 0, # 팝업 차단
            "profile.default_content_setting_values.automatic_downloads": 1, # 자동 다운로드 허용
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10) # 암시적 대기 시간 설정
        return driver

    def _wait_for_page_load(self, driver, timeout=30):
        """
        페이지 로딩 완료 대기 및 스크롤 동작.
        
        Args:
            driver (webdriver.Chrome): Selenium 웹 드라이버.
            timeout (int): 대기 시간 (초).
            
        Returns:
            bool: 페이지 로딩 성공 여부.
        """
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(3) # 페이지 컨텐츠가 완전히 렌더링될 시간 추가 대기
            # 페이지 스크롤하여 동적 콘텐츠 로드 유도
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            logger.info("페이지가 완전히 로드되었습니다.")
            return True
        except Exception as e:
            logger.warning(f"페이지 로드 대기 중 오류: {str(e)}")
            return False

    def _click_export_button(self, driver):
        """
        Google Trends 페이지에서 '내보내기' 또는 'Export' 버튼을 찾아 클릭합니다.
        
        Args:
            driver (webdriver.Chrome): Selenium 웹 드라이버.
            
        Returns:
            bool: 버튼 클릭 성공 여부.
        """
        try:
            logger.info("🔍 내보내기 버튼 검색 중...")
            
            # JavaScript로 버튼 찾기 (가장 유연한 방법)
            export_found = driver.execute_script("""
                var buttons = document.querySelectorAll('button, div[role="button"], span, a');
                var exportButton = Array.from(buttons).find(b => {
                    var text = b.textContent.trim();
                    return text.includes('내보내기') || 
                           text.includes('Export') ||
                           text.includes('다운로드') || 
                           text.includes('Download') ||
                           (b.getAttribute('aria-label') && (b.getAttribute('aria-label').includes('내보내기') || b.getAttribute('aria-label').includes('Export')));
                });
                if (exportButton) {
                    console.log('내보내기 버튼 찾음 (JS): ' + exportButton.textContent);
                    exportButton.click();
                    return true;
                }
                return false;
            """)
            
            if export_found:
                logger.info("✅ 내보내기 버튼 클릭 성공 (JavaScript)")
                return True
            
            # XPath로 시도 (JavaScript 실패 시 대체)
            export_xpath_patterns = [
                "//button[contains(normalize-space(), '내보내기')]",
                "//button[contains(normalize-space(), 'Export')]", 
                "//div[contains(@role, 'button')][contains(normalize-space(), '내보내기')]",
                "//div[contains(@role, 'button')][contains(normalize-space(), 'Export')]",
                "//button[contains(normalize-space(), '다운로드')]",
                "//button[contains(normalize-space(), 'Download')]",
                "//*[contains(@aria-label, '내보내기')]", # aria-label 속성도 확인
                "//*[contains(@aria-label, 'Export')]"
            ]
            
            for xpath in export_xpath_patterns:
                try:
                    buttons = driver.find_elements(By.XPATH, xpath)
                    if buttons:
                        # 첫 번째 유효한 버튼 클릭
                        for button in buttons:
                            if button.is_displayed() and button.is_enabled():
                                logger.info(f"XPath로 내보내기 버튼 찾음 및 클릭: {button.text}")
                                button.click()
                                return True
                except Exception:
                    # 특정 XPath 패턴에서 오류 발생해도 계속 시도
                    pass
                    
            logger.warning("모든 방법을 시도했지만 내보내기 버튼을 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            logger.error(f"내보내기 버튼 클릭 중 오류: {str(e)}")
            return False

    def _click_csv_download(self, driver):
        """
        드롭다운 메뉴에서 CSV 다운로드 버튼을 찾아 클릭합니다.
        
        Args:
            driver (webdriver.Chrome): Selenium 웹 드라이버.
            
        Returns:
            bool: CSV 다운로드 버튼 클릭 성공 여부.
        """
        try:
            logger.info("📄 CSV 다운로드 옵션 검색 중...")
            
            # JavaScript로 CSV 다운로드 버튼 찾기 (가장 유연한 방법)
            csv_found = driver.execute_script("""
                var items = document.querySelectorAll('li, div[role="menuitem"], span, a');
                var csvItem = Array.from(items).find(item => {
                    var text = item.textContent.toLowerCase().trim();
                    return text.includes('csv') || 
                           text.includes('다운로드') ||
                           text.includes('download') ||
                           (item.getAttribute('aria-label') && (item.getAttribute('aria-label').toLowerCase().includes('csv') || item.getAttribute('aria-label').toLowerCase().includes('다운로드')));
                });
                if (csvItem) {
                    console.log('CSV 다운로드 옵션 찾음 (JS): ' + csvItem.textContent);
                    csvItem.click();
                    return true;
                }
                return false;
            """)
            
            if csv_found:
                logger.info("✅ CSV 다운로드 버튼 클릭 성공 (JavaScript)")
                return True
            
            # XPath로 시도 (JavaScript 실패 시 대체)
            csv_xpath_patterns = [
                "//li[contains(normalize-space(), 'CSV')]",
                "//li[contains(normalize-space(), 'csv')]",
                "//div[contains(@role, 'menuitem')][contains(normalize-space(), 'CSV')]",
                "//a[contains(normalize-space(), 'CSV')]",
                "//*[contains(text(), 'CSV')]",
                "//*[contains(text(), '다운로드')]",
                "//*[contains(@aria-label, 'CSV 다운로드')]"
            ]
            
            for xpath in csv_xpath_patterns:
                try:
                    items = driver.find_elements(By.XPATH, xpath)
                    if items:
                        for item in items:
                            if item.is_displayed() and item.is_enabled():
                                logger.info(f"XPath로 CSV 다운로드 옵션 찾음 및 클릭: {item.text}")
                                item.click()
                                return True
                except Exception:
                    # 특정 XPath 패턴에서 오류 발생해도 계속 시도
                    pass
                    
            logger.warning("모든 방법을 시도했지만 CSV 다운로드 옵션을 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            logger.error(f"CSV 다운로드 버튼 클릭 중 오류: {str(e)}")
            return False

    def _wait_for_download(self, download_dir, before_files, timeout=30):
        """
        지정된 디렉토리에서 새 파일 (특히 CSV)이 다운로드 완료될 때까지 대기합니다.
        
        Args:
            download_dir (str): 다운로드 디렉토리 경로.
            before_files (set): 다운로드 시작 전 디렉토리 내 파일 집합.
            timeout (int): 대기 시간 (초).
            
        Returns:
            str or None: 다운로드된 파일의 전체 경로 또는 다운로드 실패 시 None.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                current_files = set(os.listdir(download_dir))
                new_files = current_files - before_files
                
                # .crdownload (Chrome 임시), .tmp (일반 임시) 파일 제외
                completed_files = [f for f in new_files if not f.endswith(('.crdownload', '.tmp'))]
                
                if completed_files:
                    # CSV 파일 우선 검색
                    csv_files = [f for f in completed_files if f.endswith('.csv')]
                    if csv_files:
                        # 최신 파일을 선택하거나 가장 큰 파일을 선택
                        latest_csv = max(csv_files, key=lambda f: os.path.getmtime(os.path.join(download_dir, f)))
                        downloaded_file_path = os.path.join(download_dir, latest_csv)
                        
                        # 파일이 완전히 다운로드되었는지 확인 (크기가 0이 아닌지)
                        if os.path.exists(downloaded_file_path) and os.path.getsize(downloaded_file_path) > 0:
                            logger.info(f"새로운 CSV 파일 감지 및 다운로드 완료 확인: {downloaded_file_path}")
                            return downloaded_file_path
                    
                    # CSV가 없는 경우, 다른 유형의 완료된 파일이라도 반환 (덜 선호됨)
                    for filename in completed_files:
                        file_path = os.path.join(download_dir, filename)
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            logger.warning(f"CSV가 아닌 다른 파일 다운로드 완료: {file_path}")
                            return file_path
                
                time.sleep(1) # 1초 간격으로 확인
                
            except Exception as e:
                logger.debug(f"다운로드 대기 중 오류 (파일 시스템 접근 등): {str(e)}")
                time.sleep(1)
        
        logger.error(f"{timeout}초 내에 파일 다운로드가 완료되지 않았습니다.")
        return None

    def _parse_csv_file(self, csv_file_path):
        """
        다운로드된 CSV 파일에서 키워드를 추출합니다.
        
        Args:
            csv_file_path (str): CSV 파일의 전체 경로.
            
        Returns:
            list: 추출된 키워드 (각각 'keyword' 키를 가진 딕셔너리).
        """
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
                    logger.debug(f"'{encoding}' 인코딩 실패: {csv_file_path}")
                    continue
            
            if not csv_data:
                logger.error(f"CSV 파일을 읽을 수 없습니다: {csv_file_path}")
                return keywords
            
            # CSV 데이터 파싱
            lines = csv_data.strip().split('\n')
            logger.info(f"CSV 파일 '{os.path.basename(csv_file_path)}'에서 {len(lines)}줄 발견")
            
            # 헤더를 건너뛸지 결정
            skip_header = False
            if lines:
                header_patterns = ['검색어', 'keyword', 'term', '순위', 'rank', '키워드', 'title']
                # 첫 줄의 첫 번째 컬럼이 헤더 패턴 중 하나를 포함하는지 확인
                first_col = lines[0].strip().split(',')[0].strip('"').lower()
                if any(pattern in first_col for pattern in header_patterns):
                    skip_header = True
                    logger.info(f"헤더 발견, 건너뛰기: {lines[0].strip()}")
            
            start_index = 1 if skip_header else 0
            
            for i, line in enumerate(lines[start_index:]):
                # 빈 줄 건너뛰기
                if not line.strip():
                    continue
                
                # 키워드 추출 로직 개선 (쉼표로 분리된 경우 첫 번째 컬럼, 아니면 전체)
                line_clean = line.strip().strip('﻿"') # BOM 및 외부 따옴표 제거
                
                keyword = ''
                if ',' in line_clean:
                    # CSV 표준에 따라 따옴표로 감싸진 필드 처리
                    import csv
                    reader = csv.reader([line_clean])
                    try:
                        fields = next(reader)
                        if fields:
                            keyword = fields[0].strip()
                    except csv.Error as e:
                        logger.warning(f"CSV 파싱 오류 발생: {e} - 줄: {line_clean}")
                        keyword = line_clean.split(',')[0].strip().strip('"') # 오류 발생 시 쉼표로 강제 분리
                else:
                    keyword = line_clean.strip().strip('"')
                
                # 유효한 키워드인지 확인
                if keyword and not keyword.isdigit() and len(keyword) > 1:
                    keywords.append({'keyword': keyword}) # 일단 키워드 텍스트만 추출
            
            logger.info(f"CSV에서 {len(keywords)}개 키워드 추출 완료")
            
        except Exception as e:
            logger.error(f"CSV 파일 처리 중 오류: {str(e)}")
            
        return keywords

    def _get_trends_from_rss(self, geo='KR'):
        """
        Google Trends RSS 피드에서 트렌드 가져오기
        
        Args:
            geo (str): 국가 코드 (예: 'KR').
            
        Returns:
            list: RSS 피드에서 파싱된 트렌드 항목 리스트.
        """
        url = f"https://trends.google.co.kr/trending/rss?geo={geo}"
        
        try:
            response = requests.get(url, timeout=10) # 타임아웃 설정
            response.raise_for_status() # HTTP 오류 발생 시 예외 발생
            
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f"{geo} - XML 파싱 오류: {e}. 내용을 디버깅 목적으로 출력합니다.")
                # 유효하지 않은 XML 문자를 처리하고 다시 파싱 시도
                content = response.content.decode('utf-8', errors='ignore')
                # 추가로 XML 선언 부분 등을 정리할 수도 있음
                # content = re.sub(r'<\?xml[^>]*\?>', '', content)
                root = ET.fromstring(content.encode('utf-8'))
            
            trends = []
            channel = root.find('channel')
            if channel is None:
                logger.error(f"{geo} - RSS 피드에서 'channel' 요소를 찾을 수 없습니다. 피드 형식이 변경되었을 수 있습니다.")
                return []
                
            items = channel.findall('item')
            logger.debug(f"{geo} - 총 {len(items)}개의 RSS 항목을 찾았습니다.")
            
            for idx, item in enumerate(items):
                try:
                    title_elem = item.find('title')
                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else 'No Title'
                    
                    # 트래픽 정보 찾기 (RSS에서 제공하는 추가 정보 - 네임스페이스 포함)
                    traffic = None
                    # 구글 트렌드 RSS는 'ht:approxTraffic' 형태의 네임스페이스를 사용함
                    # {http://purl.org/rss/1.0/modules/traffic/}approxTraffic
                    for elem in item:
                        if 'approxTraffic' in elem.tag: # 간단하게 태그 이름만으로 찾기
                            traffic = elem.text.strip()
                            break
                        # 완전한 네임스페이스를 사용한 접근 (더 정확)
                        # if '}' in elem.tag and elem.tag.split('}')[1] == 'approxTraffic':
                        #     traffic = elem.text.strip()
                        #     break
                    
                    trends.append({
                        'index': idx,
                        'title': title,
                        'traffic': traffic if traffic else '' # None 대신 빈 문자열
                    })
                except Exception as e:
                    logger.error(f"{geo} - RSS 항목 {idx} 처리 중 오류: {e}. 항목 건너뜀.")
            
            return trends
        
        except requests.exceptions.RequestException as e:
            logger.error(f"{geo} - RSS 요청 오류: {e}")
            return []
        except Exception as e:
            logger.error(f"{geo} - RSS 전체 처리 중 알 수 없는 오류: {e}")
            return []

    def merge_with_user_preferences_for_gemini(self, trend_keywords):
        """수집된 트렌드 키워드와 사용자 선호 키워드를 결합하여 Gemini에 전달할 키워드 리스트 생성"""
        if not self.db:
            logger.warning("Firebase 연결이 없어 사용자 선호도를 로드할 수 없습니다.")
            return trend_keywords
        
        try:
            # 사용자 선호 키워드 로드
            user_keywords_ref = (self.db.collection('keywords')
                                .document('user_preferred')
                                .collection('keywords'))
            
            user_preferred_keywords = []
            for doc in user_keywords_ref.stream():
                data = doc.to_dict()
                keyword = data.get('keyword', '')
                user_count = data.get('user_count', 0)
                if keyword:
                    user_preferred_keywords.append({
                        'keyword': keyword,
                        'user_count': user_count,
                        'source': 'user_preferred'
                    })
            
            # 사용자 선호도 기준으로 정렬 (관심도 높은 순)
            user_preferred_keywords.sort(key=lambda x: x['user_count'], reverse=True)
            
            # 결합된 키워드 리스트 (사용자 선호 키워드를 먼저 추가)
            combined_keywords = []
            
            # 1. 사용자 선호 키워드 먼저 추가 (최고 우선순위)
            for item in user_preferred_keywords:
                combined_keywords.append({
                    'keyword': item['keyword'],
                    'source': 'user_preferred',
                    'priority': 'highest',  # 최고 우선순위
                    'user_count': item['user_count']
                })
            
            # 2. 트렌드 키워드 추가 (사용자 선호 키워드와 중복되지 않는 것만)
            user_preferred_keywords_set = set(item['keyword'].lower() for item in user_preferred_keywords)
            
            for keyword in trend_keywords:
                if keyword.lower() not in user_preferred_keywords_set:
                    combined_keywords.append({
                        'keyword': keyword,
                        'source': 'trend',
                        'priority': 'high'  # 높은 우선순위 (하지만 사용자 선호보다는 낮음)
                    })
            
            logger.info(f"키워드 결합 완료: 사용자선호 {len(user_preferred_keywords)}개 (최우선) + 트렌드 {len([k for k in combined_keywords if k['source'] == 'trend'])}개")
            return combined_keywords
            
        except Exception as e:
            logger.error(f"사용자 선호도 결합 실패: {e}")
            return [{'keyword': kw, 'source': 'trend', 'priority': 'high'} for kw in trend_keywords]

    def _group_with_gemini(self, combined_keywords):
        """사용자 선호도가 결합된 키워드를 Gemini로 그룹핑"""
        if not combined_keywords:
            logger.warning("Gemini 그룹핑을 위한 키워드가 없습니다.")
            return []
        
        # 키워드 텍스트와 메타데이터 분리
        trend_keywords = [item['keyword'] for item in combined_keywords if item['source'] == 'trend']
        user_keywords = [item['keyword'] for item in combined_keywords if item['source'] == 'user_preferred']
        
        # Gemini 프롬프트 생성
        prompt = f"""다음 키워드들을 분석해서 처리해주세요.

            **사용자 선호 키워드 (최우선 포함 - 반드시 포함해야 함)**:
            {chr(10).join([f"{i+1}. {kw}" for i, kw in enumerate(user_keywords)])}

            **📈 트렌드 키워드 (보조적 포함)**:
            {chr(10).join([f"{i+1}. {kw}" for i, kw in enumerate(trend_keywords)])}

            처리 요구사항:
            1. **사용자 선호 키워드를 최우선으로 포함** - 가능한 모든 사용자 선호 키워드를 포함
            2. 트렌드 키워드는 사용자 선호 키워드와 연관성이 있거나 특별히 중요한 것을 우선적으로 포함
            3. 유사하거나 의미상 같은 키워드들을 하나의 **키워드**로 그룹으로 묶기
            4. 날짜 관련 키워드는 한국의 **기념일** 또는 주요 **이벤트 명칭**으로 변환
            5. 한국어가 아닌 키워드는 제외 (단, 유명 브랜드/제품/인물은 포함)
            6. **트렌드 키워드에서 추가로 최대 30개** 선별

            출력 형식 (JSON):
            ```json
            {{
            "keywords": [
                {{"keyword": "인공지능", "source": "user_preferred", "priority": "highest"}},
                {{"keyword": "문학", "source": "user_preferred", "priority": "highest"}},
                {{"keyword": "현충일", "source": "trend", "priority": "high"}}
            ]
            }}
            ```"""

        try:
            logger.info("Gemini 모델에 사용자 선호도가 결합된 키워드 요청 전송 중...")
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSON 파싱
            json_start = result_text.find("```json")
            if json_start != -1:
                json_start += len("```json")
                json_end = result_text.find("```", json_start)
                if json_end != -1:
                    json_string = result_text[json_start:json_end].strip()
                else:
                    json_string = result_text
            else:
                json_string = result_text
            
            parsed_result = json.loads(json_string)
            
            if "keywords" in parsed_result:
                logger.info(f"Gemini 그룹핑 완료: {len(parsed_result['keywords'])}개 키워드")
                return parsed_result["keywords"]
            else:
                logger.error("Gemini 응답에 'keywords' 키가 없습니다.")
                return []
                
        except Exception as e:
            logger.error(f"Gemini 그룹핑 실패: {e}")
            return []
    
    def _print_summary(self, grouped_keywords):
        """
        그룹핑된 키워드 결과에 대한 요약을 콘솔에 출력합니다.
        
        Args:
            grouped_keywords (list): 그룹핑된 키워드 (딕셔너리 리스트).
        """
        if not grouped_keywords:
            print("그룹핑된 키워드가 없습니다.")
            return
        
        print("\n" + "="*70)
        print(f"🤖 완전한 키워드 처리 결과 ({len(grouped_keywords)}개)")
        print("="*70)
        
        print(f"📊 최종 그룹핑 키워드: {len(grouped_keywords)}개")
        print(f"\n🏆 전체 키워드 목록:")
        
        for i, item in enumerate(grouped_keywords, 1):
            keyword = item.get('keyword', '')
            print(f"  {i:2d}. {keyword}")
        
        print("\n💡 처리 과정:")
        print("  1️⃣ RSS 피드 및 Google Trends 자동 다운로드로 최신 키워드 수집")
        print("  2️⃣ Gemini AI를 활용하여 유사 키워드 그룹핑, 날짜 기념일 변환, 불필요 키워드 필터링")
        print("  3️⃣ 최종 키워드만 선별하여 CSV 파일로 저장")
        print("  4️⃣ Firebase keywords 컬렉션에 저장 완료")
        
        print("="*70)

    def _cleanup_temp_files(self):
        """임시 다운로드 파일 정리"""
        logger.info(f"임시 파일 {len(self.temp_files)}개 정리 시작.")
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"임시 파일 삭제: {temp_file}")
            except Exception as e:
                logger.warning(f"임시 파일 '{temp_file}' 삭제 실패: {e}")
        self.temp_files = [] # 정리 후 목록 초기화


def main():
    api_key = "AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs"
    firebase_config = "../csproject2025-cfcb7-firebase-adminsdk-fbsvc-6764c4a1fb.json"
    
    """메인 실행 함수"""
    print("🚀 완전한 키워드 수집 + 그룹핑 시스템 시작")
    print("="*60)
    
    # 실제 API 키를 여기에 입력하거나 환경 변수에서 로드하세요.
    # 예: os.environ.get("GEMINI_API_KEY")
    api_key = "AIzaSyD1hxIJlbglSksUxRyLZkMZHrWyqFEwpEs" # <<=== 여기에 실제 Gemini API 키를 넣어주세요.
    
    if api_key == "YOUR_GEMINI_API_KEY":
        logger.error("Gemini API 키가 설정되지 않았습니다. 'YOUR_GEMINI_API_KEY'를 실제 키로 교체해주세요.")
        return
        
    try:
        # 처리기 초기화
        processor = CompleteKeywordProcessor(api_key, firebase_config)
        
        # 전체 워크플로우 실행
        # geo_codes는 여러 국가를 지정할 수 있으나, 현재 자동 다운로드는 KR에 고정되어 있음.
        # headless=True: 브라우저 UI 없이 백그라운드에서 실행
        result_id = processor.run_complete_workflow(geo_codes=['KR'], headless=True, use_rss=True, use_auto_download=True)
    
        if result_id:
            print(f"\n✅ 완료! Firebase에 저장됨 (날짜 ID: {result_id})")
            print(f"📄 Firebase 경로: keywords/{result_id}")
        else:
            print("\n❌ 처리 실패: Firebase 저장이 완료되지 않았습니다.")
        
    except Exception as e:
        logger.exception(f"메인 실행 중 예측할 수 없는 오류: {e}")
        print("\n❌ 시스템 오류가 발생했습니다. 로그를 확인해주세요.")

if __name__ == "__main__":
    main()