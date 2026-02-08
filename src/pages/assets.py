import streamlit as st
from utils.db_handler import get_latest_assets

def render():
    st.header("📈 자산 조회")
    st.caption("현재 자산 분포와 시간에 따른 흐름을 시각적으로 확인합니다.")

    df_assets = get_latest_assets()

    if df_assets.empty:
        st.info("기록된 자산 스냅샷이 없습니다. 가계부 업로드 시 자산 정보도 함께 저장되도록 구현이 필요합니다.")
    else:
        total_asset = df_assets[df_assets['balance_type'] == '자산']['amount'].sum()
        total_debt = df_assets[df_assets['balance_type'] == '부채']['amount'].sum()
        net_worth = total_asset - total_debt

        c1, c2, c3 = st.columns(3)
        c1.metric("총 자산", f"{total_asset:,.0f}원")
        c2.metric("총 부채", f"{total_debt:,.0f}원", delta_color="inverse")
        c3.metric("순자산", f"{net_worth:,.0f}원", delta=f"{(total_asset/total_debt if total_debt > 0 else 0):.1f}x")

        st.divider()

        asset_tab1, asset_tab2 = st.tabs(["👤 소유자별", "📂 항목별"])
        
        with asset_tab1:
            owner_summary = df_assets.groupby(['owner', 'balance_type'])['amount'].sum().unstack(fill_value=0)
            st.table(owner_summary.style.format("{:,.0f}"))
            
        with asset_tab2:
            st.dataframe(df_assets, use_container_width=True, hide_index=True)
