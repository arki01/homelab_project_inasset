import streamlit as st
import pandas as pd
import os
import math
from dotenv import load_dotenv
from openai import OpenAI

# ★ 모듈 임포트 (우리가 만든 도구들)
from utils.db_handler import load_from_db, save_to_db, get_ai_context  
from utils.file_handler import process_uploaded_zip, format_df_for_display
from utils.ai_agent import ask_gpt_finance

# 1. 설정 및 초기화
st.set_page_config(page_title="Money AI", page_icon="💰", layout="wide")
load_dotenv()

# 세션 상태 초기화
if 'cp' not in st.session_state: st.session_state.cp = 1
if "messages" not in st.session_state: st.session_state.messages = []

def reset_cp(): st.session_state.cp = 1

# 2. 사이드바 (데이터 관리)
with st.sidebar:
    st.title("📂 데이터 관리")
    up_file = st.file_uploader("뱅샐 ZIP 업로드", type=None)
    pw = st.text_input("비밀번호", type="password")
    
    # DB 초기화 버튼
    if st.button("DB 전체 삭제"):
        if os.path.exists("data/money_vault.db"): 
            os.remove("data/money_vault.db")
            st.rerun()
    
    st.divider()
    
    # API 키 확인 및 클라이언트 생성
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("API 키 미설정")
        client = None
    else:
        st.success("AI 엔진 가동 중")
        client = OpenAI(api_key=api_key)

# 3. 메인 탭 구조
tab_data, tab_ai = st.tabs(["📊 자산 장부", "💬 AI 비서에게 묻기"])

# --- [탭 1] 자산 장부 ---
with tab_data:
    st.title("💰 Money AI 장부")
    
    # 데이터 로드 (DB에서)
    df = load_from_db()
    
    # 파일 업로드 처리 로직 (file_handler 사용)
    if up_file and pw:
            new_df, error_msg = process_uploaded_zip(up_file, pw)
            
            if new_df is not None:
                try:
                    # ★ 여기서 DB 저장 호출
                    save_to_db(new_df) 
                    st.success("✅ 저장 성공! 중복된 데이터는 제외하고 등록했습니다.")
                    st.rerun()
                except RuntimeError as e:
                    # ★ DB가 던진 에러를 여기서 잡아서 화면에 표시
                    st.error(e) 
            elif error_msg:
                st.error(error_msg)

    # 데이터 표시 로직
    if df is not None and not df.empty:
        # 화면용 데이터 포맷팅 (file_handler 사용)
        display_df = format_df_for_display(df)
        
        # 필터 UI
        with st.expander("🔍 필터 설정", expanded=False):
            f_content = st.text_input("내용 검색", on_change=reset_cp)
            cats = sorted(display_df['대분류'].unique()) if '대분류' in display_df.columns else []
            f_cat = st.multiselect("대분류 필터", cats, on_change=reset_cp)

        # 필터링 적용
        if f_content: display_df = display_df[display_df['내용'].str.contains(f_content, na=False)]
        if f_cat: display_df = display_df[display_df['대분류'].isin(f_cat)]

        # 페이지네이션
        page_size = 15
        total_pages = max(1, math.ceil(len(display_df) / page_size))
        start = (st.session_state.cp - 1) * page_size

        # 테이블 출력
        st.dataframe(
            display_df.iloc[start:start+page_size], 
            use_container_width=True,
            hide_index=True,
            column_config={
                "금액": st.column_config.NumberColumn("금액(원)", format="%d"),
            }
        )

        # 페이지네이션 버튼
        c1, c2, c3, c4, c5 = st.columns(5)
        with c2: 
            if st.button("‹") and st.session_state.cp > 1: 
                st.session_state.cp -= 1; st.rerun()
        with c3: st.write(f"**{st.session_state.cp} / {total_pages}**")
        with c4: 
            if st.button("›") and st.session_state.cp < total_pages: 
                st.session_state.cp += 1; st.rerun()
    else:
        st.info("데이터를 업로드해주세요.")

# --- [탭 2] AI 비서 ---
with tab_ai:
    st.subheader("💬 무엇이든 물어보세요")
    chat_container = st.container(height=500)
    
    # 대화 기록 표시
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).markdown(msg["content"])

    # 입력 및 응답
    if prompt := st.chat_input("질문을 입력하세요"):
        if not client:
            st.error("OpenAI API 키가 필요합니다.")
        else:
            # 사용자 메시지 표시 및 저장
            st.session_state.messages.append({"role": "user", "content": prompt})
            with chat_container:
                st.chat_message("user").markdown(prompt)
            
            # AI 응답 생성 (ai_agent 사용)
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("분석 중..."):
                        # DB에서 컨텍스트 가져오기
                        db_context = get_ai_context()
                        # AI 함수 호출
                        answer = ask_gpt_finance(client, prompt, db_context, st.session_state.messages)
                        
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})