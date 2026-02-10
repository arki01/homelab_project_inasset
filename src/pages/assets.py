import streamlit as st
from utils.db_handler import get_latest_assets, get_previous_assets

def render():
    st.header("📈 자산 현황")
    st.caption("현재 자산 분포와 시간에 따른 흐름을 시각적으로 확인합니다.")

    # 1. 최신 데이터 가져오기
    df_assets = get_latest_assets()

    if df_assets.empty:
        st.info("기록된 자산 스냅샷이 없습니다. 가계부 업로드 시 자산 정보도 함께 저장되도록 구현이 필요합니다.")
        return

    # [핵심 1] 현재 데이터 전처리 (부채 -> 음수)
    mask_debt = df_assets['balance_type'] == '부채'
    df_assets.loc[mask_debt, 'amount'] = df_assets.loc[mask_debt, 'amount'] * -1

    # 2. 과거 데이터 가져오기 및 전처리
    current_date = df_assets['snapshot_date'].iloc[0]
    df_prev = get_previous_assets(current_date)
    
    prev_date_str = ""
    if not df_prev.empty:
        # [핵심 2] 과거 데이터도 똑같이 전처리 (부채 -> 음수)
        mask_debt_prev = df_prev['balance_type'] == '부채'
        df_prev.loc[mask_debt_prev, 'amount'] = df_prev.loc[mask_debt_prev, 'amount'] * -1
        
        # 과거 날짜 표시용
        prev_snapshot_date = df_prev['snapshot_date'].iloc[0]
        prev_date_str = prev_snapshot_date.split()[0] if prev_snapshot_date else ""

    # 업데이트 날짜 표시
    date_only = current_date.split()[0]
    diff_msg = f"({prev_date_str} 대비)" if prev_date_str else "(비교 대상 없음)"
    st.caption(f"📅 Updated: {date_only} {diff_msg}")
    
    st.subheader("총 내역")
    
    owners = df_assets['owner'].unique()
    tab_names = ['전체'] + [f"{owner}님" for owner in sorted(owners)]
    tabs = st.tabs([f"{name}" for name in tab_names])
    
    for idx, tab_name in enumerate(tab_names):
        with tabs[idx]:
            # --- [A] 현재 데이터 필터링 ---
            if tab_name == '전체':
                owner = '전체'
                display_data = df_assets.copy()
                
                # 현재 계산
                cur_asset = df_assets[df_assets['amount'] > 0]['amount'].sum()
                cur_debt = df_assets[df_assets['amount'] < 0]['amount'].sum()
                cur_net = df_assets['amount'].sum() # 자산+부채(음수)
                
                cash_asset = df_assets[df_assets['asset_type'] == '현금 자산']['amount'].sum()
                reserve_account = df_assets[df_assets['account_name'] == '예비 계좌 (네이버)']['amount'].sum()
                free_account = df_assets[df_assets['asset_type'] == '자유입출금 자산']['amount'].sum()
                cur_cash = cash_asset + reserve_account + free_account
                
                stock_asset = df_assets[df_assets['asset_type'] == '투자성 자산']['amount'].sum()
                cur_stock = stock_asset - reserve_account

                # --- [B] 과거 데이터 필터링 및 계산 ---
                if not df_prev.empty:
                    prev_data_all = df_prev.copy()
                    prev_asset = prev_data_all[prev_data_all['amount'] > 0]['amount'].sum()
                    prev_debt = prev_data_all[prev_data_all['amount'] < 0]['amount'].sum()
                    prev_net = prev_data_all['amount'].sum()
                    
                    p_cash = prev_data_all[prev_data_all['asset_type'] == '현금 자산']['amount'].sum()
                    p_reserve = prev_data_all[prev_data_all['account_name'] == '예비 계좌 (네이버)']['amount'].sum()
                    p_free = prev_data_all[prev_data_all['asset_type'] == '자유입출금 자산']['amount'].sum()
                    prev_cash = p_cash + p_reserve + p_free
                    
                    p_stock = prev_data_all[prev_data_all['asset_type'] == '투자성 자산']['amount'].sum()
                    prev_stock = p_stock - p_reserve
                else:
                    prev_asset = prev_debt = prev_net = prev_cash = prev_stock = 0

            else:
                owner = tab_name.replace('님', '')
                owner_data = df_assets[df_assets['owner'] == owner]
                display_data = owner_data.copy()
                
                # 현재 계산
                cur_asset = owner_data[owner_data['amount'] > 0]['amount'].sum()
                cur_debt = owner_data[owner_data['amount'] < 0]['amount'].sum()
                cur_net = owner_data['amount'].sum()
                
                cash_asset = owner_data[owner_data['asset_type'] == '현금 자산']['amount'].sum()
                reserve_account = owner_data[owner_data['account_name'] == '예비 계좌 (네이버)']['amount'].sum()
                free_account = owner_data[owner_data['asset_type'] == '자유입출금 자산']['amount'].sum()
                cur_cash = cash_asset + reserve_account + free_account
                
                stock_asset = owner_data[owner_data['asset_type'] == '투자성 자산']['amount'].sum()
                cur_stock = stock_asset - reserve_account

                # 과거 계산
                if not df_prev.empty:
                    prev_owner_data = df_prev[df_prev['owner'] == owner]
                    if not prev_owner_data.empty:
                        prev_asset = prev_owner_data[prev_owner_data['amount'] > 0]['amount'].sum()
                        prev_debt = prev_owner_data[prev_owner_data['amount'] < 0]['amount'].sum()
                        prev_net = prev_owner_data['amount'].sum()
                        
                        p_cash = prev_owner_data[prev_owner_data['asset_type'] == '현금 자산']['amount'].sum()
                        p_reserve = prev_owner_data[prev_owner_data['account_name'] == '예비 계좌 (네이버)']['amount'].sum()
                        p_free = prev_owner_data[prev_owner_data['asset_type'] == '자유입출금 자산']['amount'].sum()
                        prev_cash = p_cash + p_reserve + p_free
                        
                        p_stock = prev_owner_data[prev_owner_data['asset_type'] == '투자성 자산']['amount'].sum()
                        prev_stock = p_stock - p_reserve
                    else:
                        prev_asset = prev_debt = prev_net = prev_cash = prev_stock = 0
                else:
                    prev_asset = prev_debt = prev_net = prev_cash = prev_stock = 0

            # --- [C] Delta 계산 헬퍼 함수 ---
            def calc_delta(current, previous):
                if df_prev.empty or previous == 0:
                    return None
                diff = current - previous
                return f"{diff:,.0f}원"

            # --- [D] 메트릭 표시 (Help 추가) ---
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "총 자산 (부채 제외)", 
                    f"{cur_asset:,.0f}원",
                    delta=calc_delta(cur_asset, prev_asset),
                    help=f"직전 기록({prev_date_str}): {prev_asset:,.0f}원" # [추가] 툴팁
                )
                st.metric(
                    "순 자산 (부채 포함)", 
                    f"{cur_net:,.0f}원", 
                    delta=calc_delta(cur_net, prev_net),
                    help=f"직전 기록({prev_date_str}): {prev_net:,.0f}원" # [추가] 툴팁
                )
                if cur_debt != 0:
                    st.caption(f" ㄴ 부채: {cur_debt:,.0f}원")
            with col2:
                st.metric(
                    "현금", 
                    f"{cur_cash:,.0f}원",
                    delta=calc_delta(cur_cash, prev_cash),
                    help=f"직전 기록({prev_date_str}): {prev_cash:,.0f}원" # [추가] 툴팁
                )
                st.metric(
                    "주식", 
                    f"{cur_stock:,.0f}원",
                    delta=calc_delta(cur_stock, prev_stock),
                    help=f"직전 기록({prev_date_str}): {prev_stock:,.0f}원" # [추가] 툴팁
                )

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