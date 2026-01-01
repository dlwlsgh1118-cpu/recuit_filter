import streamlit as st
import pandas as pd
import json
import os
import re

# 1. 페이지 설정
st.set_page_config(page_title="경기도교육청 채용 알림이", layout="wide")

# --- [핵심 로직] 직무 정제 및 대표 단어(Root) 추출 함수 ---
def get_clean_tokens(text):
    """
    텍스트에서 '정보-컴퓨터', '영어(1)' 등을 '정보컴퓨터', '영어'로 변환하여 리스트로 반환
    """
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

# 2. 데이터 로드 함수
@st.cache_data
def load_data():
    file_path = "recruit_list.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            df = pd.DataFrame(data)
            
            # (1) 링크 생성
            base_url = "https://www.goe.go.kr/recruit/ad/func/pb/hnfpPbancInfoView.do?pbancSn="
            if not df.empty and 'pbancSn' in df.columns:
                df['원본링크'] = base_url + df['pbancSn']
            
            # (2) 지역(Region) 추출
            def get_region(info_text):
                if "|" in str(info_text):
                    # "시급... | 안산시" -> 안산시
                    return str(info_text).split("|")[-1].strip()
                return "지역미기재" # 분류 실패 시 명시적 표시
            
            if not df.empty and 'recruit_info' in df.columns:
                df['region'] = df['recruit_info'].apply(get_region)
                
            # (3) 직무(Job) 데이터 클렌징 (빈값 처리)
            if not df.empty and 'job_field' in df.columns:
                df['job_field'] = df['job_field'].fillna("내용없음")
                df['job_field'] = df['job_field'].replace("", "내용없음")

            return df
    return pd.DataFrame()

df = load_data()

# 3. 화면 구성
st.title("🍎 경기도교육청 채용 공고 대시보드")

if df.empty:
    st.error("데이터를 찾을 수 없습니다. 'recruit_list.json' 파일이 있는지 확인해주세요.")
else:
    # --- 사이드바 필터 영역 ---
    st.sidebar.header("🔍 검색 및 필터")
    
    # 1. 텍스트 검색
    search_term = st.sidebar.text_input("학교명 또는 제목 검색", "")
    
    # 2. 지역 필터 (다중 선택)
    # "지역미기재"는 필터 목록에서는 빼거나 맨 아래로 보냄 (선택사항)
    unique_regions = sorted(df['region'].unique().tolist())
    if "지역미기재" in unique_regions:
        unique_regions.remove("지역미기재")
        unique_regions.append("지역미기재") # 맨 뒤로
        
    selected_regions = st.sidebar.multiselect("지역 선택", unique_regions)
    
    # 3. 직무 필터
    subject_roots = extract_root_subjects(df)
    selected_subjects = st.sidebar.multiselect("직무(과목) 선택", subject_roots)

    # 4. 공고 상태
    badges = ["전체"] + sorted(df['badge'].unique().tolist())
    selected_badge = st.sidebar.selectbox("공고 상태", badges)

    # ==========================
    # [메인 필터링 로직]
    # ==========================
    filtered_df = df.copy()

    # (1) 텍스트 검색
    if search_term:
        filtered_df = filtered_df[
            filtered_df['school'].str.contains(search_term, na=False) | 
            filtered_df['title'].str.contains(search_term, na=False)
        ]
    
    # (2) 지역 필터
    if selected_regions:
        filtered_df = filtered_df[filtered_df['region'].isin(selected_regions)]

    # (3) 직무 필터 (스마트 매칭)
    if selected_subjects:
        def check_subject_match(row_text):
            row_tokens = get_clean_tokens(row_text)
            for token in row_tokens:
                for selected in selected_subjects:
                    if token.startswith(selected):
                        return True
            return False
        filtered_df = filtered_df[filtered_df['job_field'].apply(check_subject_match)]

    # (4) 상태 필터
    if selected_badge != "전체":
        filtered_df = filtered_df[filtered_df['badge'] == selected_badge]

    # --- 상단 요약 표시 ---
    conditions = []
    if search_term: conditions.append(f"검색어: '{search_term}'")
    if selected_regions: conditions.append(f"지역: {', '.join(selected_regions)}")
    if selected_subjects: conditions.append(f"직무: {', '.join(selected_subjects)}")
    if selected_badge != "전체": conditions.append(f"상태: {selected_badge}")

    summary_text = " / ".join(conditions) if conditions else "전체 공고 조회 중"
    st.info(f"📋 **검색 조건:** {summary_text}")

    # --- 결과 출력 ---
    st.write(f"✅ 조건에 맞는 공고: **{len(filtered_df)}** 건")

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
                
                # 카드 내부 UI
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
                    st.write("") # 여백
                    st.link_button("공고 바로가기", row['원본링크'])
                st.divider()

    # ==========================
    # [🚨 누락/분류 불가 공고 섹션]
    # ==========================
    st.markdown("---") # 구분선
    st.subheader("🚨 정보 누락 및 분류 불가 공고 (Check List)")
    st.markdown("""
    <div style='background-color: #fff5f5; padding: 10px; border-radius: 5px; border: 1px solid #ffcccc;'>
    💡 <b>작성자의 실수</b>로 지역이나 직무가 비어있는 공고들입니다.<br>
    위의 필터 설정과 상관없이(단, <b>검색어</b>는 포함), <b>놓치기 쉬운 공고</b>를 이곳에 모아두었습니다.
    </div>
    """, unsafe_allow_html=True)

    # 1. 전체 데이터(df)에서 누락된 애들만 찾음
    # 조건: (지역이 '지역미기재') OR (직무가 '내용없음')
    missing_condition = (df['region'] == "지역미기재") | (df['job_field'] == "내용없음")
    missing_df = df[missing_condition].copy()

    # 2. 단, '검색어(학교명)' 필터는 적용해줌 (전혀 엉뚱한 학교는 안 나오게)
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
                "recruit_info": "상세정보(참고용)",
                "원본링크": st.column_config.LinkColumn("링크", display_text="확인하기")
            }
        )

# 새로고침 버튼
if st.sidebar.button("데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()