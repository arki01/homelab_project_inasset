import streamlit as st
from dotenv import load_dotenv
from utils.db_handler import _init_db, init_category_rules
from pages import upload, assets, transactions, analysis, chatbot

# 1. 페이지 설정 및 DB 초기화
st.set_page_config(page_title="InAsset MVP", layout="wide", page_icon="🏛️")
_init_db()
init_category_rules()

# 모바일 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 4rem; padding-bottom: 0rem; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; padding-top: 0.5rem; padding-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

load_dotenv()

# 2. 세션 상태 초기화
if 'menu' not in st.session_state:
    st.session_state.menu = "1. 가계부 업로드"

# 3. 사이드바 커스텀 메뉴
st.sidebar.title("🏛️ InAsset")
st.sidebar.markdown("---")

menu_items = [
    "1. 가계부 업로드",
    "2. 자산 조회",
    "3. 수입/지출현황 조회",
    "4. 분석 리포트",
    "5. 컨설턴트 챗봇"
]

for item in menu_items:
    if st.sidebar.button(
        item, 
        use_container_width=True, 
        type="primary" if st.session_state.menu == item else "secondary"
    ):
        st.session_state.menu = item
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("N100 HomeLab Server Running")

# 4. 현재 선택된 메뉴에 따른 화면 렌더링
current_menu = st.session_state.menu

if current_menu == "1. 가계부 업로드":
    upload.render()
elif current_menu == "2. 자산 조회":
    assets.render()
elif current_menu == "3. 수입/지출현황 조회":
    transactions.render()
elif current_menu == "4. 분석 리포트":
    analysis.render()
elif current_menu == "5. 컨설턴트 챗봇":
    chatbot.render()