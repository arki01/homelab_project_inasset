import streamlit as st
import pyzipper
import pandas as pd
import os
import math
from dotenv import load_dotenv
from openai import OpenAI
import database

# 1. 페이지 설정 (가장 상단)
st.set_page_config(page_title="Money AI", page_icon="💰", layout="wide")

# 2. 초기화
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if 'cp' not in st.session_state: st.session_state.cp = 1
if "messages" not in st.session_state: st.session_state.messages = []

def reset_cp(): st.session_state.cp = 1

# --- 사이드바: 데이터 관리 전용 ---
with st.sidebar:
    st.title("📂 데이터 관리")
    up_file = st.file_uploader("뱅샐 ZIP 업로드", type=None)
    pw = st.text_input("비밀번호", type="password")
    
    if st.button("DB 전체 삭제"):
        if os.path.exists("data/money_vault.db"): os.remove("data/money_vault.db")
        st.rerun()
    
    st.divider()
    if not os.getenv("OPENAI_API_KEY"):
        st.error("API 키 미설정")
    else:
        st.success("AI 엔진 가동 중")

# --- 메인 화면: 탭 구조 ---
tab_data, tab_ai = st.tabs(["📊 자산 장부", "💬 AI 비서에게 묻기"])

# --- [탭 1] 자산 장부 화면 ---
with tab_data:
    st.title("💰 Money AI 장부")
    df = database.load_from_db()
    
    if up_file and pw:
        try:
            with pyzipper.AESZipFile(up_file) as zf:
                zf.setpassword(pw.encode('utf-8'))
                target = [f for f in zf.namelist() if f.endswith(('.csv', '.xlsx'))][0]
                with zf.open(target) as f:
                    new_df = pd.read_csv(f) if target.endswith('.csv') else pd.read_excel(f, sheet_name=1)
                    if '금액' in new_df.columns:
                        new_df['금액'] = pd.to_numeric(new_df['금액'], errors='coerce').fillna(0)
                    database.save_to_db(new_df)
                    st.success("✅ 저장 성공!")
                    st.rerun()
        except Exception as e:
            st.error(f"오류: {e}")

    if df is not None and not df.empty:
        # --- 데이터 전처리 (표시용) ---
        # 날짜 포맷팅 (YYYY-MM-DD)
        df['날짜'] = pd.to_datetime(df['날짜']).dt.strftime('%Y-%m-%d')
        
        # 시간 포맷팅 (HH:MM) - 소수점 및 초 단위 제거
        df['시간'] = pd.to_datetime(df['시간'], format='%H:%M:%S.%f', errors='coerce').dt.strftime('%H:%M')
        df['시간'] = df['시간'].fillna('-')

        # 상세 필터링
        with st.expander("🔍 필터 설정", expanded=False):
            f_content = st.text_input("내용 검색", on_change=reset_cp)
            cats = sorted(df['대분류'].unique()) if '대분류' in df.columns else []
            f_cat = st.multiselect("대분류 필터", cats, on_change=reset_cp)

        f_df = df.copy()
        if f_content: f_df = f_df[f_df['내용'].str.contains(f_content, na=False)]
        if f_cat: f_df = f_df[f_df['대분류'].isin(f_cat)]

        # --- 페이지네이션 변수 정의 ---
        page_size = 15
        total_pages = max(1, math.ceil(len(f_df) / page_size))
        start = (st.session_state.cp - 1) * page_size

        # --- 데이터 출력 (고급 설정 적용) ---
        st.dataframe(
            f_df.iloc[start:start+page_size], 
            use_container_width=True,
            hide_index=True,  # 왼쪽의 인덱스(0, 1, 2...)를 숨겨서 장부처럼 보이게 함
            column_config={
                "날짜": st.column_config.TextColumn("날짜"),
                "시간": st.column_config.TextColumn("시간"),
                "금액": st.column_config.NumberColumn(
                    "금액(원)",
                    format="%d",  # 천 단위 쉼표 추가
                    help="지출액은 마이너스로 표시됩니다"
                )
            }
        )

        # 하단 페이지네이션 버튼
        p_cols = st.columns([1, 1, 1, 1, 1])
        with p_cols[1]:
            if st.button("‹") and st.session_state.cp > 1: st.session_state.cp -= 1; st.rerun()
        with p_cols[2]:
            st.write(f"**{st.session_state.cp} / {total_pages}**")
        with p_cols[3]:
            if st.button("›") and st.session_state.cp < total_pages: st.session_state.cp += 1; st.rerun()
            
    else:
        st.info("데이터를 업로드해주세요.")

# --- [탭 2] AI 비서 화면 ---
with tab_ai:
    st.subheader("💬 무엇이든 물어보세요")
    
    chat_container = st.container(height=500)
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("질문을 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        with chat_container:
            with st.chat_message("assistant"):
                db_context = database.get_ai_context()
                messages = [
                    {
                        "role": "system", 
                        "content": f"너는 꼼꼼한 자산 관리 비서야. 아래 제공된 [카테고리별 통계]를 먼저 보고 전체 흐름을 파악한 뒤, [최근 상세 내역]을 참고해서 답변해줘.\n\n{db_context}"
                    },
                    *st.session_state.messages
                ]
                
                response = client.chat.completions.create(model="gpt-4o", messages=messages)
                answer = response.choices[0].message.content
                
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})