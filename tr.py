from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import re 

def setup_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # 필요시 활성화
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def get_data_with_post(driver, page_index=500):
    url = "https://www.goe.go.kr/recruit/ad/func/pb/hnfpPbancList.do"
    
    payload = {
        "mi": "10502",
        "currPage": "1",
        "srchEcptDl": "Y",
        "srchTodayPb": "N",
        "srchOcptNm": "기간제/사립교원",
        "srchOcptCd": "A",
        "pageIndex": str(page_index),
        "orderbyType": "reg",
        "searchType": "sj"
    }

    driver.get(url)
    time.sleep(1)

    js_script = """
    var form = document.createElement("form");
    form.method = "POST";
    form.action = arguments[0];
    var params = arguments[1];

    for (var key in params) {
        if (params.hasOwnProperty(key)) {
            var hiddenField = document.createElement("input");
            hiddenField.type = "hidden";
            hiddenField.name = key;
            hiddenField.value = params[key];
            form.appendChild(hiddenField);
        }
    }
    document.body.appendChild(form);
    form.submit();
    """
    driver.execute_script(js_script, url, payload)
    time.sleep(3)

def parse_recruit_list(driver):
    """
    HTML 구조를 분석하여 데이터 정제 (pbancSn 추가 및 데이터 밀림 방지)
    """
    items = driver.find_elements(By.CSS_SELECTOR, ".recruit_list > ul > li")
    results = []

    for item in items:
        try:
            # 1. pbancSn 추출
            anchor = item.find_element(By.TAG_NAME, "a")
            href_value = anchor.get_attribute("href")
            pbanc_sn_match = re.search(r"goView\('(\d+)'\)", href_value)
            pbanc_sn = pbanc_sn_match.group(1) if pbanc_sn_match else ""

            # --- [수정된 부분] 2. 상단 정보 추출 (데이터 밀림 방지 로직) ---
            top_info = item.find_elements(By.CSS_SELECTOR, ".cont_top > span")
            
            # 기본값 초기화
            school = ""
            phone = ""
            reg_date = ""
            
            if top_info:
                # 첫 번째는 무조건 학교명이라고 가정
                school = top_info[0].text.strip()
                
                # 나머지 span들을 순회하며 내용을 확인
                for span in top_info[1:]:
                    text = span.text.strip()
                    
                    if "등록일" in text:
                        # "등록일 :" 문자열 제거 후 저장
                        reg_date = text.replace("등록일", "").replace(":", "").strip()
                    elif "조회수" in text:
                        # 조회수는 수집하지 않음 (필요하면 변수 추가)
                        continue
                    else:
                        # 등록일도 아니고 조회수도 아니면 -> 전화번호로 판단
                        phone = text
            # -------------------------------------------------------

            # 3. 제목 및 뱃지 처리
            title_area = item.find_element(By.CSS_SELECTOR, ".cont_tit")
            badge_text = ""
            badges = title_area.find_elements(By.CLASS_NAME, "krds-badge")
            if badges:
                badge_text = badges[0].text.strip()
            
            full_title = title_area.text.strip()
            pure_title = full_title.replace(badge_text, "").strip()

            # 4. 상세 정보
            btm_groups = item.find_elements(By.CSS_SELECTOR, ".cont_btm > div")
            group1_ps = btm_groups[0].find_elements(By.TAG_NAME, "p")
            recruit_info = group1_ps[0].find_element(By.TAG_NAME, "span").text.strip()
            recruit_count = group1_ps[1].text.replace("채용인원", "").strip()

            group2_ps = btm_groups[1].find_elements(By.TAG_NAME, "p")
            apply_period = group2_ps[0].text.replace("접수기간", "").strip()
            work_period = group2_ps[1].text.replace("채용기간", "").strip()

            job_field = item.find_element(By.CSS_SELECTOR, ".cont_btm > p").text.replace("직무분야", "").strip()

            results.append({
                "pbancSn": pbanc_sn,
                "school": school,
                "title": pure_title,
                "badge": badge_text,
                "job_field": job_field if job_field else "내용없음",
                "recruit_info": recruit_info,
                "recruit_count": recruit_count,
                "apply_period": apply_period,
                "work_period": work_period,
                "phone": phone,   # 없는 경우 빈 문자열("")로 들어감
                "reg_date": reg_date
            })
        except Exception as e:
            print(f"항목 파싱 에러 발생: {e}")
            continue

    return results

if __name__ == "__main__":
    driver = setup_driver()
    try:
        # 데이터가 많으므로 테스트 시 page_index를 줄여서 확인해보세요
        get_data_with_post(driver, page_index=500)
        final_data = parse_recruit_list(driver)
        
        file_name = "recruit_list.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        
        print(f"총 {len(final_data)}개의 데이터를 수집했습니다.")
        print(f"결과가 '{file_name}' 파일로 저장되었습니다.")
        
    finally:
        driver.quit()