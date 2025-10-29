import os
import time
import json
from dotenv import load_dotenv
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

# --- 설정 (Configuration) ---
# 환경 변수 로드 (config/.env)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / "config" / ".env")

# .env 파일에서 정보 로드
tv_username = os.getenv('TRADINGVIEW_USERNAME')
tv_password = os.getenv('TRADINGVIEW_PASSWORD')

# 본인의 차트 레이아웃 URL로 반드시 변경하세요.
CHART_URL = "https://www.tradingview.com/chart/4RRD64C4/" 

# 캡처할 시간 프레임 목록 (트레이딩뷰 내부 data-value 값과 일치)
TIME_FRAMES = {
    '5m': '5',
    '15m': '15',
    '1H': '60',
    '1D': '1D' # 일봉은 'D'
}
# -----------------------------

def capture_charts_robust(url, timeframes, output_dir=None, symbol="SOLANAUSDT.P"):
    if output_dir is None:
        # 프로젝트 루트의 data/screenshots 폴더로 자동 설정
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "screenshots")
    driver = None
    try:
        print("--- 자동화 브라우저 설정 시작 ---")
        service = ChromeService(executable_path=ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') # 실제 서버 운영 시 주석 해제
        # options.add_argument('--no-sandbox')
        # options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1920, 1080)
        wait = WebDriverWait(driver, 30) # 대기 시간을 30초로 늘려 안정성 확보

        print("--- 트레이딩뷰 접속 및 쿠키 주입 ---")
        driver.get("https://www.tradingview.com")
        
        # cookies.json 파일이 있는지 확인
        cookie_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'cookies.json')
        if not os.path.exists(cookie_path):
            raise FileNotFoundError(f"cookies.json 파일을 찾을 수 없습니다: {cookie_path}")
            
        with open(cookie_path, 'r') as f:
            cookies = json.load(f)
        for cookie in cookies:
            driver.add_cookie(cookie)
        
        print(f"--- 목표 차트 페이지로 이동: {url} ---")
        driver.get(url)

        print("--- 로그인 세션 확인 중... ---")
        time.sleep(5)
        
        # 로그인 페이지로 리디렉션되었는지 확인하여 세션 만료 체크
        if "log in" in driver.title.lower() or "sign in" in driver.title.lower():
            raise Exception("로그인 세션이 만료되었습니다. cookies.json 파일을 다시 생성해주세요.")

        print("--- 차트 로딩 대기... ---")
        # 차트의 핵심 컨테이너가 로드될 때까지 기다림
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "chart-markup-table")))
        time.sleep(5) # 차트 로딩 시간
        
        # 심볼 변경 시도
        print(f"--- 심볼을 SOLUSDT.P로 변경 시도 ---")
        try:
            # 심볼 버튼 클릭 (제공된 XPath 사용)
            symbol_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div[3]/div/div/div[3]/div[1]/div/div/div/div/div[2]/button[1]")))
            symbol_button.click()
            time.sleep(2)
            
            # 검색 입력 필드 찾기 - 더 안정적인 방법
            time.sleep(1)  # 검색창이 완전히 열릴 때까지 대기
            
            # 활성화된 input 필드 찾기
            search_inputs = driver.find_elements(By.TAG_NAME, "input")
            search_input = None
            
            for inp in search_inputs:
                if inp.is_displayed() and inp.is_enabled():
                    try:
                        inp.click()
                        search_input = inp
                        break
                    except:
                        continue
            
            if not search_input:
                raise Exception("검색 입력 필드를 찾을 수 없습니다")
            
            time.sleep(0.5)
            search_input.clear()
            search_input.send_keys("SOLUSDT.P")
            time.sleep(4)  # 검색 결과가 로드될 충분한 시간
            
            # SOLUSDT.P 항목 클릭 - 가장 간단한 방법
            print("--- 검색 결과 클릭 시도 ---")
            
            # 방법 1: 제공된 XPath 시도
            clicked = False
            try:
                solana_item = driver.find_element(By.XPATH, "/html/body/div[7]/div[2]/div/div[1]/div/div[5]/div/div/div[2]")
                if solana_item.is_displayed():
                    solana_item.click()
                    clicked = True
                    print("--- XPath로 클릭 성공 ---")
            except:
                pass
            
            # 방법 2: 키보드로 선택
            if not clicked:
                try:
                    print("--- 엔터키로 첫 번째 결과 선택 ---")
                    search_input.send_keys(Keys.ENTER)
                    clicked = True
                except:
                    pass
            
            # 방법 3: 클릭 가능한 요소 찾기
            if not clicked:
                try:
                    clickable_divs = driver.find_elements(By.CSS_SELECTOR, "div[data-role='list-item']")
                    for div in clickable_divs:
                        if "SOLUSDT" in div.text:
                            div.click()
                            clicked = True
                            print("--- 리스트 아이템 클릭 성공 ---")
                            break
                except:
                    pass
            
            if not clicked:
                print("⚠️ 검색 결과를 클릭할 수 없습니다")
            
            print("--- 심볼 SOLUSDT.P로 변경 완료 ---")
            time.sleep(5) # 차트가 새로 로드될 시간
            
        except Exception as e:
            print(f"⚠️ 심볼 변경 실패: {str(e)}")
            print("--- 현재 차트 심볼 그대로 사용하여 진행 ---")
        
        # 차트가 완전히 로드될 때까지 추가 대기
        time.sleep(5)

        # 스크린샷 저장 폴더 생성
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for frame_label, frame_value in timeframes.items():
            print(f"--- {frame_label} 시간 프레임으로 변경 중... ---")
            
            # 시간 프레임 변경 버튼 클릭 (ID를 사용하여 더 안정적으로 찾기)
            interval_button = wait.until(EC.element_to_be_clickable((By.ID, "header-toolbar-intervals")))
            interval_button.click()
            
            # 원하는 시간 프레임 선택 (data-value 속성을 사용하여 정확히 클릭)
            timeframe_option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"div[data-value='{frame_value}']")))
            timeframe_option.click()
            
            print(f"--- {frame_label} 차트 로딩 대기... 5초 ---")
            time.sleep(5)
            
            output_filename = f"{output_dir}/chart_{frame_label}.png"
            print(f"--- {frame_label} 차트 캡처 및 '{output_filename}'으로 저장 ---")
            
            # 특정 요소가 아닌, 보이는 전체 화면을 캡처하여 안정성 극대화
            driver.save_screenshot(output_filename)
            print(f"--- {frame_label} 캡처 성공! ---")

    except Exception as e:
        print(f"오류 발생: {e}")

    finally:
        if driver:
            driver.quit()
            print("--- 브라우저 종료 ---")

if __name__ == "__main__":
    import sys
    # Windows 환경에서의 UTF-8 인코딩 문제 해결
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # SOLANAUSDT.P 심볼로 차트 캡처
    capture_charts_robust(CHART_URL, TIME_FRAMES)