from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import subprocess
import datetime
import os
import logging
import platform

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def initialize_driver(headless=False, profile_path=None):
    """Chrome 드라이버를 초기화합니다."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")  # 언어 설정 추가
    
    # 사용자 에이전트 설정
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 프로필 경로 설정
    if profile_path:
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(10)
    return driver

def wait_for_page_load(driver, timeout=30):
    """페이지가 완전히 로드될 때까지 대기합니다."""
    try:
        # 페이지 로드 완료 대기
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # 추가 인터랙티브 콘텐츠 로드 대기
        time.sleep(3)
        
        # 스크롤을 내려 동적 콘텐츠 로드
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        
        logger.info("페이지가 완전히 로드되었습니다.")
        return True
    except Exception as e:
        logger.warning(f"페이지 로드 대기 중 오류: {str(e)}")
        return False

def click_export_and_copy(driver, max_retries=3):
    """내보내기 버튼 클릭 후 클립보드에 복사합니다."""
    for retry in range(max_retries):
        try:
            # 1️⃣ 내보내기 버튼 찾기 및 클릭
            logger.info(f"🚀 내보내기 버튼 클릭 시도 중... (시도 {retry+1}/{max_retries})")
            
            # 다양한 방법으로 내보내기 버튼 검색
            export_button = None
            
            # 방법 1: JavaScript로 버튼 찾기
            driver.execute_script("""
                var buttons = document.querySelectorAll('button');
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
            
            # 방법 2: XPath로 버튼 찾기 (JavaScript가 실패한 경우)
            if not driver.execute_script("return window._exportButtonClicked === true;"):
                try:
                    logger.info("XPath로 내보내기 버튼 검색 중...")
                    export_xpath_patterns = [
                        "//button[contains(., '내보내기')]",
                        "//button[contains(., 'Export')]",
                        "//button[contains(., '다운로드')]",
                        "//button[contains(., 'Download')]",
                        "//div[contains(@role, 'button')][contains(., '내보내기')]",
                        "//div[contains(@role, 'button')][contains(., 'Export')]"
                    ]
                    
                    for xpath in export_xpath_patterns:
                        buttons = driver.find_elements(By.XPATH, xpath)
                        if buttons:
                            logger.info(f"XPath로 버튼 찾음: {buttons[0].text}")
                            export_button = buttons[0]
                            export_button.click()
                            break
                except Exception as e:
                    logger.warning(f"XPath 검색 중 오류: {str(e)}")
            
            # 내보내기 메뉴가 나타날 때까지 약간 대기
            time.sleep(2)
            
            # 2️⃣ 클립보드 복사 버튼 클릭
            logger.info("📋 클립보드 복사 버튼 클릭 중...")
            clipboard_clicked = driver.execute_script("""
                // 클립보드 복사 버튼 찾기 (여러 가능한 선택자 시도)
                var clipboardItems = document.querySelectorAll('li[data-action="clipboard"], [aria-label*="클립보드"], [aria-label*="Clipboard"]');
                if (clipboardItems.length > 0) {
                    console.log('클립보드 복사 버튼 찾음');
                    clipboardItems[0].click();
                    return true;
                }
                
                // 대체 방법: 텍스트로 검색
                var allItems = document.querySelectorAll('li, div[role="menuitem"]');
                for (var i = 0; i < allItems.length; i++) {
                    var item = allItems[i];
                    var text = item.textContent.toLowerCase();
                    if (text.includes('클립보드') || text.includes('clipboard') || text.includes('복사') || text.includes('copy')) {
                        console.log('텍스트로 클립보드 버튼 찾음: ' + text);
                        item.click();
                        return true;
                    }
                }
                
                return false;
            """)
            
            if not clipboard_clicked:
                logger.warning("클립보드 복사 버튼을 JavaScript로 찾지 못했습니다. XPath 시도...")
                try:
                    clipboard_xpath_patterns = [
                        "//li[contains(., '클립보드')]",
                        "//li[contains(., 'Clipboard')]",
                        "//li[contains(., '복사')]", 
                        "//li[contains(., 'Copy')]",
                        "//div[contains(@role, 'menuitem')][contains(., '클립보드')]",
                        "//div[contains(@role, 'menuitem')][contains(., 'Clipboard')]"
                    ]
                    
                    for xpath in clipboard_xpath_patterns:
                        items = driver.find_elements(By.XPATH, xpath)
                        if items:
                            logger.info(f"XPath로 클립보드 메뉴 찾음: {items[0].text}")
                            items[0].click()
                            clipboard_clicked = True
                            break
                except Exception as e:
                    logger.warning(f"클립보드 XPath 검색 중 오류: {str(e)}")
            
            # 복사 작업 완료 대기
            time.sleep(3)
            
            # 3️⃣ 클립보드 내용 가져오기 - 운영체제별 처리
            logger.info("🔄 클립보드 데이터 추출 중...")
            
            # 현재 운영체제 확인
            current_os = platform.system()
            clipboard_data = None
            
            if current_os == "Windows":
                # Windows 환경에서 직접 클립보드 접근
                try:
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    clipboard_data = win32clipboard.GetClipboardData()
                    win32clipboard.CloseClipboard()
                except ImportError:
                    logger.warning("win32clipboard 모듈을 찾을 수 없습니다. PowerShell 방식을 시도합니다.")
                    clipboard_data = get_clipboard_windows_powershell()
                except Exception as e:
                    logger.error(f"Windows 클립보드 접근 오류: {str(e)}")
                    clipboard_data = get_clipboard_windows_powershell()
            
            elif current_os == "Linux":
                # WSL 또는 일반 Linux 환경
                if os.path.exists("/proc/version") and "microsoft" in open("/proc/version").read().lower():
                    # WSL 환경
                    logger.info("WSL 환경 감지, PowerShell을 통한 클립보드 접근 시도...")
                    clipboard_data = get_clipboard_wsl()
                else:
                    # 일반 Linux 환경
                    try:
                        clipboard_data = get_clipboard_linux()
                    except Exception as e:
                        logger.error(f"Linux 클립보드 접근 오류: {str(e)}")
            
            elif current_os == "Darwin":  # macOS
                try:
                    clipboard_data = get_clipboard_macos()
                except Exception as e:
                    logger.error(f"macOS 클립보드 접근 오류: {str(e)}")
            
            # 클립보드 데이터 확인
            if clipboard_data and clipboard_data.strip():
                logger.info(f"✅ 클립보드 데이터 복사 성공: {clipboard_data[:50]}...")
                # CSV 포맷 확인
                if "," in clipboard_data and "\n" in clipboard_data:
                    logger.info("CSV 형식의 데이터가 감지되었습니다.")
                return clipboard_data
            else:
                logger.warning("클립보드에서 데이터를 찾을 수 없습니다.")
                if retry < max_retries - 1:
                    logger.info(f"{(retry + 1) * 3}초 후 재시도합니다...")
                    time.sleep((retry + 1) * 3)  # 점진적으로 대기 시간 증가
                    continue
                return None
                
        except Exception as e:
            logger.error(f"❌ 내보내기 및 클립보드 복사 중 오류 발생: {str(e)}")
            if retry < max_retries - 1:
                logger.info(f"{(retry + 1) * 3}초 후 재시도합니다...")
                time.sleep((retry + 1) * 3)
            else:
                return None
    
    return None

def get_clipboard_windows_powershell():
    """PowerShell을 사용하여 Windows 클립보드 내용을 가져옵니다."""
    try:
        logger.info("PowerShell을 사용하여 클립보드 내용 가져오기 시도...")
        
        # PowerShell 명령어: 클립보드 내용을 임시 파일에 저장
        ps_command = """
        $tempFile = "$env:TEMP\\clipboard_temp.txt";
        Set-Content -Path $tempFile -Value "" -Encoding UTF8;
        Add-Type -AssemblyName System.Windows.Forms;
        if ([System.Windows.Forms.Clipboard]::ContainsText()) {
            $clipboardText = [System.Windows.Forms.Clipboard]::GetText();
            Set-Content -Path $tempFile -Value $clipboardText -Encoding UTF8;
            Write-Host $tempFile;
        } else {
            Write-Host "CLIPBOARD_EMPTY";
        }
        """
        
        result = subprocess.run(['powershell.exe', '-Command', ps_command], 
                                capture_output=True, 
                                text=True, 
                                encoding='utf-8',
                                timeout=10)
        
        if result.returncode == 0 and "CLIPBOARD_EMPTY" not in result.stdout:
            temp_path = result.stdout.strip()
            logger.info(f"임시 파일 경로: {temp_path}")
            
            # 임시 파일에서 내용 읽기
            with open(temp_path, "r", encoding="utf-8") as f:
                clipboard_data = f.read()
                return clipboard_data
        else:
            logger.error(f"PowerShell 클립보드 접근 실패: {result.stderr}")
            return None
    
    except subprocess.TimeoutExpired:
        logger.error("PowerShell 명령어 실행 시간 초과")
        return None
    except Exception as e:
        logger.error(f"PowerShell 클립보드 접근 중 오류: {str(e)}")
        return None

def get_clipboard_wsl():
    """WSL 환경에서 Windows 클립보드 내용을 가져옵니다."""
    try:
        logger.info("WSL→Windows 클립보드 접근 시도...")
        
        # WSL에서 Windows PowerShell 호출
        ps_command = """
        $tempFile = "$env:TEMP\\clipboard_temp.txt";
        Set-Content -Path $tempFile -Value "" -Encoding UTF8;
        Add-Type -AssemblyName System.Windows.Forms;
        if ([System.Windows.Forms.Clipboard]::ContainsText()) {
            $clipboardText = [System.Windows.Forms.Clipboard]::GetText();
            Set-Content -Path $tempFile -Value $clipboardText -Encoding UTF8;
            $tempPath = $tempFile;
            $wslPath = wsl wslpath -u `"$tempPath`";
            Write-Host $wslPath;
        } else {
            Write-Host "CLIPBOARD_EMPTY";
        }
        """
        
        result = subprocess.run(['powershell.exe', '-Command', ps_command], 
                                capture_output=True, 
                                text=True, 
                                encoding='utf-8',
                                timeout=15)
        
        if result.returncode == 0 and "CLIPBOARD_EMPTY" not in result.stdout:
            wsl_path = result.stdout.strip()
            logger.info(f"WSL에서 접근 가능한 파일 경로: {wsl_path}")
            
            if os.path.exists(wsl_path):
                with open(wsl_path, "r", encoding="utf-8") as f:
                    clipboard_data = f.read()
                    return clipboard_data
            else:
                logger.error(f"WSL 경로를 찾을 수 없음: {wsl_path}")
                return None
        else:
            logger.error(f"WSL PowerShell 클립보드 접근 실패: {result.stderr}")
            return None
    
    except Exception as e:
        logger.error(f"WSL 클립보드 접근 중 오류: {str(e)}")
        return None

def get_clipboard_linux():
    """Linux 환경에서 클립보드 내용을 가져옵니다."""
    try:
        logger.info("Linux 클립보드(xclip) 접근 시도...")
        
        # xclip을 사용하여 클립보드 내용 가져오기
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                capture_output=True, 
                                text=True, 
                                encoding='utf-8',
                                timeout=5)
        
        if result.returncode == 0:
            return result.stdout
        else:
            logger.error(f"xclip 명령어 실패: {result.stderr}")
            
            # 대체 방법으로 xsel 시도
            logger.info("대체 방법(xsel)으로 시도...")
            result_xsel = subprocess.run(['xsel', '--clipboard', '--output'], 
                                        capture_output=True, 
                                        text=True, 
                                        encoding='utf-8',
                                        timeout=5)
            
            if result_xsel.returncode == 0:
                return result_xsel.stdout
            else:
                logger.error(f"xsel 명령어 실패: {result_xsel.stderr}")
                return None
    
    except FileNotFoundError:
        logger.error("xclip 또는 xsel이 설치되어 있지 않습니다.")
        return None
    except Exception as e:
        logger.error(f"Linux 클립보드 접근 중 오류: {str(e)}")
        return None

def get_clipboard_macos():
    """macOS 환경에서 클립보드 내용을 가져옵니다."""
    try:
        logger.info("macOS 클립보드(pbpaste) 접근 시도...")
        
        # pbpaste를 사용하여 클립보드 내용 가져오기
        result = subprocess.run(['pbpaste'], 
                                capture_output=True, 
                                text=True, 
                                encoding='utf-8',
                                timeout=5)
        
        if result.returncode == 0:
            return result.stdout
        else:
            logger.error(f"pbpaste 명령어 실패: {result.stderr}")
            return None
    
    except Exception as e:
        logger.error(f"macOS 클립보드 접근 중 오류: {str(e)}")
        return None

def get_google_trends_csv(headless=False, profile_path=None):
    """내보내기 버튼 클릭 방식으로 Google Trends 데이터를 CSV로 저장합니다."""
    driver = None
    
    try:
        logger.info("🌐 Google Trends 페이지 로딩 중...")
        driver = initialize_driver(headless=headless, profile_path=profile_path)
        
        # Google Trends 페이지 로드
        driver.get("https://trends.google.co.kr/trends/trendingsearches/daily?geo=KR&hl=ko")
        
        # 페이지 로딩 대기
        logger.info("페이지 로딩 대기 중...")
        wait_for_page_load(driver, timeout=30)
        
        # 쿠키 동의 창이 있으면 닫기
        try:
            cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), '동의') or contains(text(), 'Agree') or contains(text(), 'Accept')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                logger.info("쿠키 동의 창을 닫았습니다.")
                time.sleep(2)
        except Exception as e:
            logger.warning(f"쿠키 동의 창 처리 중 오류 (무시됨): {str(e)}")
        
        # 내보내기 버튼 클릭 및 클립보드 데이터 가져오기
        csv_data = click_export_and_copy(driver)
        
        if not csv_data:
            logger.error("클립보드에서 CSV 데이터를 가져오지 못했습니다.")
            return None
        
        # CSV 데이터 저장
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"google_trends_{timestamp}.csv"
        
        with open(csv_filename, 'w', encoding='utf-8') as csv_file:
            csv_file.write(csv_data)
        logger.info(f"CSV 데이터를 '{csv_filename}'에 저장했습니다.")
        
        return csv_filename
        
    except Exception as e:
        logger.exception(f"오류 발생: {str(e)}")
        return None
    
    finally:
        if driver:
            driver.quit()

def main():
    """메인 함수: CSV 형식으로 인기 트렌드 데이터 추출 실행"""
    logger.info("📊 Google Trends 인기 검색어 데이터 추출 시작...")
    
    # 프로필 경로 설정 (필요시)
    profile_path = "./chrome_profile"
    
    # CSV 형식으로 데이터 추출
    csv_filename = get_google_trends_csv(headless=False, profile_path=profile_path)
    
    if csv_filename:
        logger.info("✅ 데이터 추출 성공!")
        logger.info(f"결과 파일: {csv_filename}")
        
        # CSV 데이터 미리보기
        try:
            with open(csv_filename, 'r', encoding='utf-8') as f:
                preview = f.read(1000)
                print("\n" + "=" * 50)
                print("추출된 CSV 데이터 미리보기:")
                print("=" * 50)
                print(preview + ("..." if len(preview) >= 1000 else ""))
                print("\n" + "=" * 50)
        except:
            pass
    else:
        logger.error("❌ 데이터 추출 실패")

if __name__ == "__main__":
    main()