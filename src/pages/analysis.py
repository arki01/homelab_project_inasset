import streamlit as st

def render():
    st.markdown("""
        <style>
        .page-header {
            text-align: center; padding: 2rem 0 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text; font-size: 2.5rem; font-weight: 700;
        }
        .page-subtitle {
            text-align: center; color: var(--text-color);
            opacity: 0.7; font-size: 1rem; margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="page-header">분석 리포트</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">과거 패턴을 분석하여 미래 소비를 예측합니다. (준비 중)</div>', unsafe_allow_html=True)
