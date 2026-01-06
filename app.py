import streamlit as st
import pandas as pd
import json
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# 1. [크롤러 로직] Selenium 기능 함수화
# ==========================================
def setup_driver():
    chrome_options = Options()
    # Streamlit에서 실행 시 브라우저 창이 뜨지 않도록 Headless 모드 사용 권장
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
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
        "pageIndex": str(page_index), # 가져올 게시물 수
        "orderbyType": "reg",
        "searchType": "sj"
    }

    driver.get(url)
    time.sleep(1) # 페이지 로딩 대기

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
    time.sleep(3) # 데이터 로딩 대기 (인터넷 속도에 따라 조절 필요)

def parse_recruit_list(driver):
    items = driver.find_elements(By.CSS_SELECTOR, ".recruit_list > ul > li")
    results = []

    for item in items:
        try:
            # 1. pbancSn 추출
            anchor = item.find_element(By.TAG_NAME, "a")
            href_value = anchor.get_attribute("href")
            pbanc_sn_match = re.search(r"goView\('(\d+)'\)", href_value)
            pbanc_sn = pbanc_sn_match.group(1) if pbanc_sn_match else ""

            # 2. 상단 정보 추출
            top_info = item.find_elements(By.CSS_SELECTOR, ".cont_top > span")
            school = ""
            phone = ""
            reg_date = ""
            
            if top_info:
                school = top_info[0].text.strip()
                for span in top_info[1:]:
                    text = span.text.strip()
                    if "등록일" in text:
                        reg_date = text.replace("등록일", "").replace(":", "").strip()
                    elif "조회수" in text:
                        continue
                    else:
                        phone = text

            # 3. 제목 및 뱃지
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
                "phone": phone,
                "reg_date": reg_date
            })
        except Exception:
            continue
    return results

def crawl_and_save():
    """실제 크롤링을 수행하고 파일을 저장하는 함수"""
    driver = setup_driver()
    try:
        # 데이터 수집 (500개 기준)
        get_data_with_post(driver, page_index=500)
        final_data = parse_recruit_list(driver)
        
        # 파일 저장
        file_name = "recruit_list.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        
        return len(final_data)
    except Exception as e:
        st.error(f"크롤링 중 에러가 발생했습니다: {e}")
        return 0
    finally:
        driver.quit()

# ==========================================
# 2. [Streamlit UI] 페이지 설정 및 로직
# ==========================================
st.set_page_config(page_title="경기도교육청 채용 알림이", layout="wide")

# --- 직무 정제 함수 ---
def get_clean_tokens(text):
    tokens = []
    if not isinstance(text, str):
        return tokens
    parts = text.split(',')
    for part in parts:
        clean = re.sub(r'\(.*?\)|[0-9]+|명', '', part)
        clean = re.sub(r'[^가-힣a-zA-Z]', '', clean)
        if clean:
            tokens.append(clean)
    return tokens

def extract_root_subjects(df):
    all_tokens = set()
    if df.empty or 'job_field' not in df.columns:
        return []
    for text in df['job_field']:
        tokens = get_clean_tokens(text)
        all_tokens.update(tokens)
    sorted_tokens = sorted(list(all_tokens), key=len)
    roots = []
    for token in sorted_tokens:
        is_covered = False
        for root in roots:
            if token.startswith(root):
                is_covered = True
                break
        if not is_covered:
            roots.append(token)
    return sorted(roots)

# --- 데이터 로드 함수 ---
@st.cache_data
def load_data():
    file_path = "recruit_list.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                df = pd.DataFrame(data)
                
                base_url = "https://www.goe.go.kr/recruit/ad/func/pb/hnfpPbancInfoView.do?pbancSn="
                if not df.empty and 'pbancSn' in df.columns:
                    df['원본링크'] = base_url + df['pbancSn']
                
                def get_region(info_text):
                    if "|" in str(info_text):
                        return str(info_text).split("|")[-1].strip()
                    return "지역미기재"
                
                if not df.empty and 'recruit_info' in df.columns:
                    df['region'] = df['recruit_info'].apply(get_region)
                    
                if not df.empty and 'job_field' in df.columns:
                    df['job_field'] = df['job_field'].fillna("내용없음")
                    df['job_field'] = df['job_field'].replace("", "내용없음")

                return df
            except json.JSONDecodeError:
                return pd.DataFrame()
    return pd.DataFrame()

# ==========================================
# 3. 화면 구성 및 실행
# ==========================================

# 사이드바: 새로고침 버튼 (가장 위에 배치)
st.sidebar.header("⚙️ 데이터 관리")
if st.sidebar.button("🔄 최신 공고 가져오기 (크롤링)"):
    with st.spinner('경기도교육청 사이트에서 최신 공고를 가져오는 중입니다... (약 10~15초 소요)'):
        # 크롤링 실행
        count = crawl_and_save()
        
    if count > 0:
        st.success(f"성공! {count}개의 공고를 업데이트했습니다.")
        # 캐시 비우고 페이지 리로드
        st.cache_data.clear()
        time.sleep(1) # 사용자가 메시지를 볼 수 있게 잠시 대기
        st.rerun()
    else:
        st.warning("데이터를 가져오지 못했거나 공고가 없습니다.")

# 메인 로직 시작
df = load_data()

st.title("🍎 경기도교육청 채용 공고 대시보드 (업데이트 성공!)")

if df.empty:
    st.warning("현재 저장된 데이터가 없습니다. 사이드바의 '최신 공고 가져오기' 버튼을 눌러주세요.")
else:
    # --- 사이드바 필터 영역 ---
    st.sidebar.header("🔍 검색 및 필터")
    
    search_term = st.sidebar.text_input("학교명 또는 제목 검색", "")
    
    unique_regions = sorted(df['region'].unique().tolist())
    if "지역미기재" in unique_regions:
        unique_regions.remove("지역미기재")
        unique_regions.append("지역미기재")
    selected_regions = st.sidebar.multiselect("지역 선택", unique_regions)
    
    subject_roots = extract_root_subjects(df)
    selected_subjects = st.sidebar.multiselect("직무(과목) 선택", subject_roots)

    badges = ["전체"] + sorted(df['badge'].unique().tolist())
    selected_badge = st.sidebar.selectbox("공고 상태", badges)

    # 필터링
    filtered_df = df.copy()

    if search_term:
        filtered_df = filtered_df[
            filtered_df['school'].str.contains(search_term, na=False) | 
            filtered_df['title'].str.contains(search_term, na=False)
        ]
    
    if selected_regions:
        filtered_df = filtered_df[filtered_df['region'].isin(selected_regions)]

    if selected_subjects:
        def check_subject_match(row_text):
            row_tokens = get_clean_tokens(row_text)
            for token in row_tokens:
                for selected in selected_subjects:
                    if token.startswith(selected):
                        return True
            return False
        filtered_df = filtered_df[filtered_df['job_field'].apply(check_subject_match)]

    if selected_badge != "전체":
        filtered_df = filtered_df[filtered_df['badge'] == selected_badge]

    # 요약 정보
    conditions = []
    if search_term: conditions.append(f"검색어: '{search_term}'")
    if selected_regions: conditions.append(f"지역: {', '.join(selected_regions)}")
    if selected_subjects: conditions.append(f"직무: {', '.join(selected_subjects)}")
    if selected_badge != "전체": conditions.append(f"상태: {selected_badge}")

    summary_text = " / ".join(conditions) if conditions else "전체 공고 조회 중"
    st.info(f"📋 **검색 조건:** {summary_text}")
    st.write(f"✅ 조건에 맞는 공고: **{len(filtered_df)}** 건 (총 데이터: {len(df)}건)")

    # 결과 테이블
    st.dataframe(
        filtered_df, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "pbancSn": None,
            "recruit_info": None,
            "recruit_count": None,
            "region": "지역",
            "school": "학교명",
            "title": "공고 제목",
            "job_field": "직무(과목)",
            "badge": "상태",
            "apply_period": "접수 기간",
            "reg_date": "등록일",
            "원본링크": st.column_config.LinkColumn("링크", display_text="공고 보기")
        }
    )
    
    # 상세 보기 (Expander)
    if len(filtered_df) > 0:
        with st.expander("🔽 상세 공고 리스트 열기/닫기", expanded=False):
            for i, (index, row) in enumerate(filtered_df.iterrows()):
                title_header = f"[{row['region']}] {row['school']} - {row['title']}"
                if row['badge']: title_header += f" ({row['badge']})"
                
                st.markdown(f"#### {title_header}")
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.caption("상세정보")
                    st.write(f"{row['recruit_info']}")
                    st.write(f"**직무:** {row['job_field']}")
                with c2:
                    st.caption("일정")
                    st.write(f"접수: {row['apply_period']}")
                    st.write(f"채용: {row['work_period']}")
                with c3:
                    st.write("")
                    st.link_button("공고 바로가기", row['원본링크'])
                st.divider()

    # 정보 누락 섹션
    st.markdown("---")
    st.subheader("🚨 정보 누락 및 분류 불가 공고 (Check List)")
    
    missing_condition = (df['region'] == "지역미기재") | (df['job_field'] == "내용없음")
    missing_df = df[missing_condition].copy()

    if search_term:
        missing_df = missing_df[
            missing_df['school'].str.contains(search_term, na=False) | 
            missing_df['title'].str.contains(search_term, na=False)
        ]

    if missing_df.empty:
        st.success("🎉 현재 데이터에는 정보가 누락된 공고가 없습니다.")
    else:
        st.error(f"총 **{len(missing_df)}** 건의 정보 불충분 공고가 발견되었습니다.")
        st.dataframe(
            missing_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "pbancSn": None,
                "recruit_count": None,
                "region": st.column_config.TextColumn("지역", help="지역 정보가 없습니다."),
                "job_field": st.column_config.TextColumn("직무", help="직무 정보가 없습니다."),
                "school": "학교명",
                "title": "공고 제목",
                "recruit_info": "상세정보",
                "원본링크": st.column_config.LinkColumn("링크", display_text="확인하기")
            }
        )