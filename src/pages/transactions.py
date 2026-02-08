import streamlit as st
from utils.db_handler import get_analyzed_transactions

def render():
    st.header("📊 수입/지출현황 조회")
    st.caption("표준화된 카테고리로 정리된 상세 내역입니다.")

    df_analyzed = get_analyzed_transactions()

    if df_analyzed.empty:
        st.info("데이터가 없습니다. 먼저 [1. 가계부 업로드] 메뉴에서 엑셀 파일을 저장해주세요.")
    else:
        col1, col2 = st.columns(2)
        
        fixed_cost = df_analyzed[df_analyzed['expense_type'] == '고정 지출']['amount'].sum()
        with col1:
            st.metric(label="이번 달 고정 지출 (예상)", value=f"{fixed_cost:,.0f}원")

        variable_cost = df_analyzed[df_analyzed['expense_type'] == '변동 지출']['amount'].sum()
        with col2:
            st.metric(label="이번 달 변동 지출", value=f"{variable_cost:,.0f}원")

        st.divider()

        tab1, tab2 = st.tabs(["📝 상세 내역", "📈 지출 구조"])
        
        with tab1:
            st.dataframe(df_analyzed, use_container_width=True, hide_index=True)
            
        with tab2:
            st.caption("고정비 vs 변동비 비중")
            chart_data = df_analyzed.groupby('expense_type')['amount'].sum()
            st.bar_chart(chart_data)
