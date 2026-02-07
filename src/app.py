import streamlit as st
import pandas as pd
import os
import datetime
import time

from dotenv import load_dotenv
from utils.db_handler import DB_PATH, _init_db, save_transactions
from utils.file_handler import process_uploaded_zip, format_df_for_display

# 1. 페이지 설정 및 DB 초기화
st.set_page_config(page_title="InAsset MVP", layout="wide", page_icon="🏛️")
_init_db()

# 모바일 최적화 및 PWA 설정 메타 태그
st.markdown("""
    <style>
    .block-container { padding-top: 4rem; padding-bottom: 0rem; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; padding-top: 0.5rem; padding-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

load_dotenv()

# 2. 세션 상태 초기화 (현재 선택된 메뉴 저장)
if 'menu' not in st.session_state:
    st.session_state.menu = "1. 가계부 업로드"

# 3. 사이드바 커스텀 메뉴 (목록 형태)
st.sidebar.title("🏛️ InAsset")
st.sidebar.markdown("---")

# 메뉴 리스트 정의
menu_items = [
    "1. 가계부 업로드",
    "2. 자산 조회",
    "3. 수입/지출현황 조회",
    "4. 분석 리포트",
    "5. 컨설턴트 챗봇"
]

# 버튼을 리스트 형태로 나열하여 직접 선택하게 함
for item in menu_items:
    # 현재 선택된 메뉴는 강조(primary) 버튼으로 표시하여 시각적 인지 향상
    if st.sidebar.button(
        item, 
        use_container_width=True, 
        type="primary" if st.session_state.menu == item else "secondary"
    ):
        st.session_state.menu = item
        st.rerun() # 메뉴 클릭 시 화면 즉시 갱신

st.sidebar.markdown("---")
st.sidebar.caption("N100 HomeLab Server Running")


# 4. 현재 선택된 메뉴에 따른 화면 렌더링
current_menu = st.session_state.menu

if current_menu == "1. 가계부 업로드":
    st.header("📥 가계부 데이터 업로드")
    st.write("우리 부부의 가계부 기록을 통합하는 첫 단계입니다.")

    with st.container(border=True):
        uploaded_file = st.file_uploader("뱅크샐러드 ZIP 파일을 업로드하세요", type=None)
        password = st.text_input("ZIP 파일 비밀번호", type="password")

    if uploaded_file and password:
        with st.container(border=True):
            # 데이터 소유자 선택
            owner = st.selectbox(
                "데이터 소유자 선택", 
                ["형준", "윤희"], 
                help="해당 가계부 내역의 주인을 선택하세요. 저장 시 이 값이 일괄 적용됩니다."
            )

            # 1. 라디오 버튼으로 업로드 모드 설정 (가로 배열)
            upload_mode = st.radio(
                "업로드 기간 설정",
                ["전체 기간", "특정 기간 (기본값: 현재 ~ 1개월 전)"],
                index=1, horizontal=True,
                help="파일 전체를 올릴지, 최근 내역만 골라 올릴지 선택하세요."
            )
            
            # 2. 날짜 설정 (라디오 버튼 상태에 따라 잠금/해제)
            is_manual = (upload_mode == "특정 기간 (기본값: 현재 ~ 1개월 전)")
            
            today = datetime.date.today()
            one_month_ago = today - datetime.timedelta(days=30)
            
            upload_period = st.date_input(
                "",
                value=(one_month_ago, today),
                disabled=not is_manual,  # '전체 기간' 선택 시 비활성화
                help="기간 업로드 모드에서만 활성화됩니다.")

        if st.button("파일 분석 시작", use_container_width=True):

            # 라디오 버튼이 '특정 기간'일 때만 날짜를 넘기고, '전체'일 때는 None을 넘깁니다.
            s_date, e_date = (None, None)
            if upload_mode == "특정 기간 (기본값: 현재 ~ 1개월 전)" and len(upload_period) == 2:
                s_date, e_date = upload_period

            df, error = process_uploaded_zip(uploaded_file, password, start_date=s_date, end_date=e_date)
            if error:
                st.error(f"❌ {error}")
            elif df is None or df.empty:
                st.warning("⚠️ 해당 기간에 일치하는 데이터가 없습니다.")
            else:
                st.session_state['temp_df'] = df
                st.success(f"✅ {owner}님의 가계부 내역을 성공적으로 불러왔습니다. 아래 내역을 확인 후 저장하기를 눌러주세요.")

        # 분석된 데이터가 세션에 있을 때만 저장 버튼 표시
        if 'temp_df' in st.session_state:
            display_df = format_df_for_display(st.session_state['temp_df'])
            st.dataframe(display_df, use_container_width=True)
            
            #  데이터프레임 우측 하단 건수 표시
            st.markdown(
                f"<div style='text-align: right; color: gray; font-size: 1rem; margin-top: -30px;'>"
                f"총 {len(display_df):,}건"
                f"</div>", 
                unsafe_allow_html=True
            )

            # 저장 버튼 클릭 시 선택한 owner 값을 함께 전달
            if st.button(f"{owner}님 명의로 저장", type="secondary",use_container_width=True):
                save_transactions(display_df, owner=owner)

                # 결과 메시지 계산을 위해 날짜 추출
                min_d = st.session_state['temp_df']['날짜'].min().strftime('%Y-%m-%d')
                max_d = st.session_state['temp_df']['날짜'].max().strftime('%Y-%m-%d')

                st.balloons()
                st.success(f"{owner}님의 {min_d}부터 {max_d}까지의 내역이 DB에 안전하게 저장되었습니다.")
                del st.session_state['temp_df'] # 저장 후 캐시 삭제
    
    st.divider()

    # --- [1. 팝업창 함수 정의] ---
    # @st.dialog 데코레이터를 붙이면 이 함수는 실행 시 팝업으로 뜹니다.
    @st.dialog("DB 삭제 확인")
    def open_delete_modal():
        st.write("이 작업은 되돌릴 수 없으며, 저장된 모든 가계부 내역과 자산 정보가 영구적으로 사라집니다.")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # 팝업 내에서 삭제 버튼 클릭
            if st.button("네, 삭제합니다", type="primary", use_container_width=True):
                if os.path.exists(DB_PATH):
                    try:
                        os.remove(DB_PATH)
                        st.success("삭제 완료! 잠시 후 새로고침 됩니다.")
                        time.sleep(1.5)
                        st.rerun() # 페이지 새로고침 (팝업도 같이 닫힘)
                    except Exception as e:
                        st.error(f"오류: {e}")
                else:
                    st.warning("삭제할 데이터베이스가 없습니다.")
                    time.sleep(1)
                    st.rerun()

        with col2:
            # 취소 버튼 클릭 시 팝업 닫기
            if st.button("아니오, 취소합니다", use_container_width=True):
                st.rerun() # 리런하면 팝업이 닫힙니다.

    # --- [2. 메인 화면의 트리거 버튼] ---
    # 복잡한 if session_state 로직이 필요 없습니다. 버튼 누르면 함수만 호출하면 끝!
    if st.button("DB 전체 삭제", type="primary", use_container_width=True):
        open_delete_modal() # 이 함수를 호출하면 팝업이 뜹니다.
        
    st.markdown("<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)

elif current_menu == "2. 자산 조회":
    st.header("📈 자산 조회")
    st.info("현재 자산 분포와 시간에 따른 흐름을 시각적으로 확인합니다.")
    # 여기에 차트 라이브러리(Plotly/Altair) 연동 예정

elif current_menu == "3. 수입/지출현황 조회":
    st.header("📊 수입/지출현황 조회")
    st.write("표준화된 카테고리로 정리된 상세 내역입니다.")
    # DB 조회 로직 구현부

elif current_menu == "4. 분석 리포트":
    st.header("📋 AI 분석 리포트")
    st.caption("과거 패턴을 분석하여 미래 소비를 예측합니다. (준비 중)")

elif current_menu == "5. 컨설턴트 챗봇":
    st.header("🤖 지능형 자산 컨설턴트")
    st.caption("자연어로 질문하고 시각화 답변을 받는 공간입니다. (준비 중)")


# import streamlit as st
# import pandas as pd
# import os
# import math
# from dotenv import load_dotenv
# from openai import OpenAI
# import plotly.express as px

# # 커스텀 모듈
# from utils.db_handler import load_from_db, save_to_db, get_ai_context  
# from utils.file_handler import process_uploaded_zip, format_df_for_display
# from utils.ai_agent import ask_gpt_finance

# # 1. 설정 및 초기화
# st.set_page_config(page_title="Money AI", page_icon="💰", layout="wide")

# # 모바일에서 '앱'처럼 보이게 하는 메타 태그 주입
# st.markdown("""
#     <link rel="manifest" href="app/static/manifest.json">
    
#     <style>
#     /* 상단 여백 확보 (안드로이드 상태바 가림 방지) */
#     .block-container {
#         padding-top: 4rem; 
#         padding-bottom: 0rem;
#     }
#     .stTabs [data-baseweb="tab"] {
#         font-size: 1.1rem;
#         padding-top: 0.5rem;
#         padding-bottom: 0.5rem;
#     }
#     </style>
    
#     <meta name="theme-color" content="#ffffff">
#     <meta name="mobile-web-app-capable" content="yes">
#     <meta name="apple-mobile-web-app-capable" content="yes">
#     <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
#     """, unsafe_allow_html=True)

# load_dotenv()

# # 세션 상태 초기화
# if 'cp' not in st.session_state: st.session_state.cp = 1
# if "messages" not in st.session_state: st.session_state.messages = []

# def reset_cp(): st.session_state.cp = 1

# def main():
#     # 2. 사이드바 (데이터 관리)
#     with st.sidebar:
#         st.title("📂 데이터 관리")
#         up_file = st.file_uploader("뱅샐 ZIP 업로드", type=None)
#         pw = st.text_input("비밀번호", type="password")
        
#         # DB 초기화 버튼
#         if st.button("DB 전체 삭제"):
#             if os.path.exists("data/money_vault.db"): 
#                 os.remove("data/money_vault.db")
#                 st.rerun()
        
#         st.divider()
        
#         # API 키 확인 및 클라이언트 생성
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             st.error("API 키 미설정")
#             client = None
#         else:
#             st.success("AI 엔진 가동 중")
#             client = OpenAI(api_key=api_key)

#     # 데이터 로드를 탭 생성 전으로 이동
#     df = load_from_db()

# #     # 2. 탭 구성 (리포트 탭 추가)
# #     tab1, tab2, tab3 = st.tabs(["📊 장부", "💬 AI 비서", "📈 리포트"])

# #     # --- [탭 1] 자산 장부 ---
# #     with tab1:
# #         st.title("💰 Money AI 장부")
        
# #         # 파일 업로드 처리
# #         if up_file and pw:
# #             new_df, error_msg = process_uploaded_zip(up_file, pw)
            
# #             if new_df is not None:
# #                 try:
# #                     save_to_db(new_df) 
# #                     st.success("✅ 저장 성공! 중복된 데이터는 제외하고 등록했습니다.")
# #                     st.rerun()
# #                 except RuntimeError as e:
# #                     st.error(e) 
# #             elif error_msg:
# #                 st.error(error_msg)

# #         # 데이터 표시
# #         if df is not None and not df.empty:
# #             display_df = format_df_for_display(df)
            
# #             # 필터 UI
# #             with st.expander("🔍 필터 설정", expanded=False):
# #                 f_content = st.text_input("내용 검색", on_change=reset_cp)
# #                 cats = sorted(display_df['대분류'].unique()) if '대분류' in display_df.columns else []
# #                 f_cat = st.multiselect("대분류 필터", cats, on_change=reset_cp)

# #             # 필터링 적용
# #             if f_content: display_df = display_df[display_df['내용'].str.contains(f_content, na=False)]
# #             if f_cat: display_df = display_df[display_df['대분류'].isin(f_cat)]

# #             # 페이지네이션
# #             page_size = 15
# #             total_pages = max(1, math.ceil(len(display_df) / page_size))
# #             start = (st.session_state.cp - 1) * page_size

# #             # 테이블 출력
# #             st.dataframe(
# #                 display_df.iloc[start:start+page_size], 
# #                 use_container_width=True,
# #                 hide_index=True,
# #                 column_config={
# #                     "금액": st.column_config.NumberColumn("금액(원)", format="%d"),
# #                 }
# #             )

# #             # 페이지네이션 버튼
# #             c1, c2, c3, c4, c5 = st.columns(5)
# #             with c2: 
# #                 if st.button("‹") and st.session_state.cp > 1: 
# #                     st.session_state.cp -= 1; st.rerun()
# #             with c3: st.write(f"**{st.session_state.cp} / {total_pages}**")
# #             with c4: 
# #                 if st.button("›") and st.session_state.cp < total_pages: 
# #                     st.session_state.cp += 1; st.rerun()
# #         else:
# #             st.info("데이터를 업로드해주세요.")

# #     # --- [탭 2] AI 비서 ---
# #     with tab2:
# #         st.title("🤖 Money AI 비서")
# #         st.subheader("💬 무엇이든 물어보세요")
# #         chat_container = st.container(height=500)
        
# #         # 대화 기록 표시
# #         with chat_container:
# #             for msg in st.session_state.messages:
# #                 st.chat_message(msg["role"]).markdown(msg["content"])

# #         # 입력 및 응답
# #         if prompt := st.chat_input("질문을 입력하세요"):
# #             if not client:
# #                 st.error("OpenAI API 키가 필요합니다.")
# #             else:
# #                 st.session_state.messages.append({"role": "user", "content": prompt})
# #                 with chat_container:
# #                     st.chat_message("user").markdown(prompt)
                
# #                 with chat_container:
# #                     with st.chat_message("assistant"):
# #                         with st.spinner("분석 중..."):
# #                             db_context = get_ai_context()
# #                             answer = ask_gpt_finance(client, prompt, db_context, st.session_state.messages)
# #                             st.markdown(answer)
# #                             st.session_state.messages.append({"role": "assistant", "content": answer})

# # # --- [탭 3] 리포트 ---
# #     with tab3:
# #         st.header("이번 달 소비 분석")

# #         # 데이터가 있는지 확인
# #         if df is not None and not df.empty:
            
# #             # (1) 데이터 전처리: 금액을 숫자로 변환 (오류 방지)
# #             df['금액_수치'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0)
            
# #             # --- [핵심 수정 로직] ---
# #             # 1. '지출' 데이터만 필터링 (수입, 이체 제외)
# #             # 만약 '타입' 컬럼이 없다면(구형 엑셀 등), 전체 데이터를 씁니다.
# #             if '타입' in df.columns:
# #                 # .copy()를 써야 원본 df에 영향을 주지 않고 안전하게 가공합니다.
# #                 expense_df = df[df['타입'] == '지출'].copy()
# #             else:
# #                 expense_df = df.copy()

# #             # 2. 금액을 절대값(양수)으로 변환 (마이너스 부호 제거)
# #             # -15000 -> 15000
# #             expense_df['금액_수치'] = expense_df['금액_수치'].abs()
# #             # -----------------------

# #             # (2) 카테고리별 집계 (Group By)
# #             # 필터링된 'expense_df'를 사용합니다.
# #             category_sum = expense_df.groupby('대분류')['금액_수치'].sum().reset_index()
            
# #             # 금액이 0보다 큰 것만 남김 (0원짜리 카테고리 제거)
# #             category_sum = category_sum[category_sum['금액_수치'] > 0]
            
# #             # 금액이 큰 순서대로 정렬 (시각화 예쁘게 하기 위해)
# #             category_sum = category_sum.sort_values(by='금액_수치', ascending=False)

# #             # (3) 파이 차트 그리기
# #             st.subheader("💳 카테고리별 지출 비중")
            
# #             if not category_sum.empty:
# #                 fig_pie = px.pie(
# #                     category_sum, 
# #                     values='금액_수치', 
# #                     names='대분류',
# #                     hole=0.4, # 도넛 차트 스타일
# #                     title='지출 카테고리 분포'
# #                 )
# #                 # 차트 안에 퍼센트와 라벨 표시
# #                 fig_pie.update_traces(textposition='inside', textinfo='percent+label')
# #                 st.plotly_chart(fig_pie, use_container_width=True)
# #             else:
# #                 st.warning("표시할 '지출' 데이터가 없습니다.")

# #             # (4) 막대 차트 (일별 지출 흐름)
# #             st.subheader("📅 일별 지출 흐름")
# #             daily_sum = expense_df.groupby('날짜')['금액_수치'].sum().reset_index()
            
# #             if not daily_sum.empty:
# #                 fig_bar = px.bar(
# #                     daily_sum, 
# #                     x='날짜', 
# #                     y='금액_수치',
# #                     title='일자별 지출 추이',
# #                     color='금액_수치', # 금액에 따라 색상 진하게
# #                     color_continuous_scale='Bluyl' # 깔끔한 파란색 계열
# #                 )
# #                 st.plotly_chart(fig_bar, use_container_width=True)
# #             else:
# #                 st.warning("표시할 데이터가 없습니다.")

# #         else:
# #             st.info("데이터가 없습니다. 엑셀 파일을 업로드해주세요.")

# # 스크립트 실행 진입점
# if __name__ == "__main__":
#     main()