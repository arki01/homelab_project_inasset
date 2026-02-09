import streamlit as st
from utils.db_handler import get_latest_assets

def render():
    st.header("📈 자산 현황")
    st.caption("현재 자산 분포와 시간에 따른 흐름을 시각적으로 확인합니다.")

    df_assets = get_latest_assets()

    if df_assets.empty:
        st.info("기록된 자산 스냅샷이 없습니다. 가계부 업로드 시 자산 정보도 함께 저장되도록 구현이 필요합니다.")
    else:
        # [핵심 변경 1] 부채 데이터를 음수(-)로 변환
        # 이렇게 하면 이후 모든 계산(합계, 시각화)에서 자동으로 차감됩니다.
        mask_debt = df_assets['balance_type'] == '부채'
        df_assets.loc[mask_debt, 'amount'] = df_assets.loc[mask_debt, 'amount'] * -1

        # 업데이트 날짜 표시 (캡션 바로 아래)
        if not df_assets.empty:
            snapshot_date = df_assets['snapshot_date'].iloc[0]
            date_only = snapshot_date.split()[0] if snapshot_date else ""
            st.caption(f"📅 Updated: {date_only}")
        st.subheader("총 내역")
        
        # 소유자별로 데이터 분리
        owners = df_assets['owner'].unique()
             
        # 소유자별 탭
        tab_names = ['전체'] + [f"{owner}님" for owner in sorted(owners)]
        tabs = st.tabs([f"{name}" for name in tab_names])
        
        for idx, tab_name in enumerate(tab_names):
            with tabs[idx]:
                if tab_name == '전체':
                    owner = '전체'
                    
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
                    
                    net_worth = total_asset + total_debt
                    
                    # 소유자별 주식
                    stock_asset = df_assets[df_assets['asset_type'] == '투자성 자산']['amount'].sum()
                    stock_asset_net = stock_asset - reserve_account

                    metric_asset = total_asset
                    metric_debt = total_debt
                    metric_cash = total_cash
                    metric_stock = stock_asset_net
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
                    
                    metric_net = metric_asset + metric_debt

                    # 소유자별 주식
                    stock_asset = owner_data[owner_data['asset_type'] == '투자성 자산']['amount'].sum()
                    stock_asset_net = stock_asset - reserve_account
                    metric_stock = stock_asset_net
                
                # 메트릭 표시 (2열 x 2행)
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("총 자산", f"{metric_asset:,.0f}원")
                    st.metric("순 자산", f"{metric_net:,.0f}원")
                with col2:
                    st.metric("현금", f"{metric_cash:,.0f}원")
                    st.metric("주식", f"{metric_stock:,.0f}원")

                st.divider()
                st.subheader("상세 내역 조회")
                
                # 1. 필터 UI 구성 (3단 컬럼)
                f_col1, f_col2 = st.columns([1, 2])
                
                with f_col1:
                    # 카테고리 선택 (다중 선택 가능)
                    unique_cats = sorted(display_data['asset_type'].dropna().unique())
                    selected_cats = st.multiselect(
                        "자산 분류", 
                        unique_cats,
                        placeholder="전체 선택",
                        key=f"cat_asset_{owner}" 
                    )
                
                with f_col2:
                    # 적요 검색 (텍스트 입력)
                    search_text = st.text_input(
                        "자산명",
                        placeholder="예: 보증금, 소비 계좌",
                        key=f"search_asset_{owner}"
                    )

                # 2. 필터링 로직 적용
                filtered_df = display_data.copy()

                if selected_cats:
                    filtered_df = filtered_df[filtered_df['asset_type'].isin(selected_cats)]
                                  
                if search_text:
                    # 대소문자 구분 없이 검색 (case=False), NaN 값은 제외 (na=False)
                    filtered_df = filtered_df[filtered_df['account_name'].str.contains(search_text, case=False, na=False)]

                # 3. 데이터프레임 표시
                show_df = filtered_df.copy()

                st.dataframe(
                    show_df.sort_values(by='amount', ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "amount": st.column_config.NumberColumn("금액", format="%d원"),
                        "blance_type": "자산/부채",
                        "asset_type": "자산 분류",
                        "account_name": "자산명"
                    }
                )

                # 4. 필터링된 결과 합계 계산
                if not filtered_df.empty:
                    aseet_filtered = filtered_df[filtered_df['amount'] > 0]['amount'].sum()
                    
                    # 합계 보여주기 (강조 박스)
                    st.markdown(
                        f"<div style='text-align: left; color: gray; font-size: 1rem; margin-top: -20px;'>"
                        f"총 자산: <b>{aseet_filtered:,.0f}원</b>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("조건에 맞는 내역이 없습니다.")