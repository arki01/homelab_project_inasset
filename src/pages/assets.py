import streamlit as st
from utils.db_handler import get_latest_assets

def render():
    st.header("📈 자산 조회")
    st.caption("현재 자산 분포와 시간에 따른 흐름을 시각적으로 확인합니다.")

    df_assets = get_latest_assets()

    if df_assets.empty:
        st.info("기록된 자산 스냅샷이 없습니다. 가계부 업로드 시 자산 정보도 함께 저장되도록 구현이 필요합니다.")
    else:
        # 업데이트 날짜 표시 (캡션 바로 아래)
        if not df_assets.empty:
            snapshot_date = df_assets['snapshot_date'].iloc[0]
            date_only = snapshot_date.split()[0] if snapshot_date else ""
            st.caption(f"📅 Updated: {date_only}")
        
        # 소유자별로 데이터 분리
        owners = df_assets['owner'].unique()
             
        # 소유자별 탭
        tab_names = ['전체'] + [f"{owner}님" for owner in sorted(owners)]
        tabs = st.tabs([f"{name}" for name in tab_names])
        
        for idx, tab_name in enumerate(tab_names):
            with tabs[idx]:
                if tab_name == '전체':
                    display_data = df_assets.copy()
                    display_data = display_data.drop(columns=['owner', 'snapshot_date'])
                    
                    # 전체 합계
                    total_asset = df_assets[df_assets['balance_type'] == '자산']['amount'].sum()
                    total_debt = df_assets[df_assets['balance_type'] == '부채']['amount'].sum()
                    
                    # 총 현금 계산
                    cash_asset = df_assets[df_assets['asset_type'] == '현금 자산']['amount'].sum()
                    reserve_account = df_assets[df_assets['account_name'] == '예비 계좌 (네이버)']['amount'].sum()
                    free_account = df_assets[df_assets['account_name'] == '자유입출금 자산']['amount'].sum()
                    total_cash = cash_asset + reserve_account + free_account
                    
                    net_worth = total_asset - total_debt
                    
                    metric_asset = total_asset
                    metric_debt = total_debt
                    metric_cash = total_cash
                    metric_net = net_worth
                else:
                    owner = tab_name.replace('님', '')
                    owner_data = df_assets[df_assets['owner'] == owner]
                    
                    display_data = owner_data.copy()
                    display_data = display_data.drop(columns=['owner', 'snapshot_date'])
                    
                    # 소유자별 합계
                    metric_asset = owner_data[owner_data['balance_type'] == '자산']['amount'].sum()
                    metric_debt = owner_data[owner_data['balance_type'] == '부채']['amount'].sum()
                    
                    # 소유자별 현금
                    cash_asset = owner_data[owner_data['asset_type'] == '현금 자산']['amount'].sum()
                    reserve_account = owner_data[owner_data['account_name'] == '예비 계좌 (네이버)']['amount'].sum()
                    free_account = owner_data[owner_data['account_name'] == '자유입출금 자산']['amount'].sum()
                    metric_cash = cash_asset + reserve_account + free_account
                    
                    metric_net = metric_asset - metric_debt
                
                # 메트릭 표시 (2열 x 2행)
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("총 자산", f"{metric_asset:,.0f}원")
                    st.metric("현금", f"{metric_cash:,.0f}원")
                with col2:
                    st.metric("총 부채", f"{metric_debt:,.0f}원", delta_color="inverse")
                    st.metric("순자산", f"{metric_net:,.0f}원")
                
                st.divider()
                
                # amount 포맷팅 (콤마 추가)
                display_data['amount'] = display_data['amount'].apply(lambda x: f"{x:,}")
                
                st.dataframe(display_data, use_container_width=True, hide_index=True)
