import streamlit as st
from dotenv import load_dotenv
from utils.db_handler import _init_db, init_category_rules
from pages import upload, assets, transactions, analysis, chatbot

# 1. 페이지 설정
st.set_page_config(page_title="InAsset MVP", layout="wide", page_icon="🏛️")

# 2. DB 및 환경변수 초기화
_init_db()
init_category_rules()
load_dotenv()

# 3. 미려한 디자인을 위한 CSS 주입 (다크/라이트 모드 유연 대응)
st.markdown("""
    <style>
    /* [핵심] 전체 사이드바 배경색: Streamlit 테마 변수 활용 */
    [data-testid="stSidebar"] {
        background-color: var(--secondary-background-color);
    }
    
    /* 메뉴 버튼 디자인 */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        /* 테두리도 명시적 색상 대신 반투명 회색으로 처리 */
        border: 1px solid rgba(128, 128, 128, 0.2); 
        /* 배경을 투명하게 해서 라이트/다크 테마 배경을 그대로 투과시킴 */
        background-color: transparent; 
        /* 글자색을 Streamlit 테마 글자색 변수로 지정 */
        color: var(--text-color); 
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
        text-align: left;
        display: flex;
        align-items: center;
        justify-content: flex-start;
    }

    /* 활성화된 메뉴 스타일 (Primary 버튼 스타일링) */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
        color: white; /* 짙은 그라데이션 위에는 항상 흰색 글씨가 어울림 */
        border: none;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }

    /* 호버 효과 */
    .stButton > button:hover {
        border-color: #2575fc;
        color: #2575fc;
        transform: translateY(-2px);
        background-color: rgba(37, 117, 252, 0.05); /* 호버 시 약간의 파란 배경 효과 */
    }
    
    /* 사이드바 하단 정보창 스타일 */
    .server-status {
        padding: 10px;
        border-radius: 8px;
        /* #e3f2fd 처럼 꽉 막힌 색 대신, 파란색(2196f3)에 투명도 10%를 줘서 테마에 스며들게 함 */
        background-color: rgba(33, 150, 243, 0.1); 
        border-left: 5px solid #2196f3;
        font-size: 0.8rem;
        /* 글자색 역시 테마에 맞게 변경 */
        color: var(--text-color); 
    }
    </style>
    """, unsafe_allow_html=True)

# 4. 세션 상태 초기화
if 'menu' not in st.session_state:
    st.session_state.menu = "💰 수입/지출 현황"

# 5. 사이드바 구성
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: #2575fc;'>🏛️ InAsset</h1>", unsafe_allow_html=True)
    # [수정] color: gray 대신 opacity(투명도)를 사용하여 다크모드에서도 자연스럽게 보이도록 조치
    st.markdown("<p style='text-align: center; font-size: 0.8rem; opacity: 0.7;'>우리 부부의 스마트 자산 관리자</p>", unsafe_allow_html=True)
    st.markdown("---")

    # 메뉴 구성 (이모지 포함)
    menu_options = {
        "💰 수입/지출 현황": "💰 수입/지출 현황",
        "🏦 자산 현황": "🏦 자산 현황",
        "📊 분석 리포트": "📊 분석 리포트",
        "🤖 컨설턴트 챗봇": "🤖 컨설턴트 챗봇",
        "📂 데이터 업로드": "📂 데이터 업로드"
    }

    for label in menu_options.keys():
        # 현재 선택된 메뉴라면 primary 스타일 적용
        is_active = st.session_state.menu == label
        if st.button(
            label, 
            key=f"menu_{label}",
            use_container_width=True, 
            type="primary" if is_active else "secondary"
        ):
            st.session_state.menu = label
            st.rerun()

    st.markdown("---")
    
    # N100 서버 상태 시각화
    st.markdown(f"""
        <div class="server-status">
            <strong>🏠 Homelab Server Status</strong><br>
            • Node: N100 Mini PC<br>
            • Status: <span style="color: #4caf50;">● Running</span>
        </div>
    """, unsafe_allow_html=True)

# 6. 현재 선택된 메뉴에 따른 화면 렌더링
current_menu = st.session_state.menu

# 실제 메뉴 이름과 매핑 (이모지 제외하고 처리하기 위함)
if "수입/지출 현황" in current_menu:
    transactions.render()
elif "자산 현황" in current_menu:
    assets.render()
elif "분석 리포트" in current_menu:
    analysis.render()
elif "챗봇" in current_menu:
    chatbot.render()
elif "업로드" in current_menu:
    upload.render()