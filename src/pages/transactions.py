import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from utils.db_handler import get_analyzed_transactions

def render():
    st.header("📊 수입/지출 현황")
    st.caption("표준화된 카테고리로 정리된 상세 내역입니다.")

    df_analyzed = get_analyzed_transactions()

    if df_analyzed.empty:
        st.info("데이터가 없습니다. 먼저 [1. 가계부 업로드] 메뉴에서 엑셀 파일을 저장해주세요.")
    else:
        # 1. 날짜 변환 및 기준일 설정
        df_analyzed_dt = df_analyzed.copy()
        df_analyzed_dt['date'] = pd.to_datetime(df_analyzed_dt['date'])
        
        # owner 변경 적용
        mask_yunhee = df_analyzed_dt['source'].str.contains('Mega|페이코', case=False, na=False)                          
        if mask_yunhee.any():
            df_analyzed_dt.loc[mask_yunhee, 'owner'] = '윤희'

        latest_date = df_analyzed_dt['date'].max() # 데이터상 가장 최근 날짜
        current_day = latest_date.day # 현재 진행된 일수 (예: 15일)
        
        # 이번 달 기준 (1일 ~ 최근 날짜)
        this_month_start = latest_date.replace(day=1)
        
        # [변경] 비교 기준: 최근 1년 (이번 달 제외)
        one_year_ago = this_month_start - relativedelta(years=1)
         
        st.caption(f"📅 Updated: {latest_date.strftime('%Y-%m-%d')}")
        st.subheader("총 내역")

        # 탭 설정
        owners = ['전체'] + sorted(df_analyzed_dt['owner'].unique().tolist())
        tabs = st.tabs([f"{owner}님" if owner != '전체' else '전체' for owner in owners])
        
        for idx, owner in enumerate(owners):
            with tabs[idx]:
                # Owner 필터링
                if owner == '전체':
                    display_owner_df = df_analyzed_dt.copy()
                else:
                    display_owner_df = df_analyzed_dt[df_analyzed_dt['owner'] == owner]
                
                # --- [A] 이번 달 데이터 집계 ---
                current_df = display_owner_df[
                    (display_owner_df['date'] >= this_month_start) & 
                    (display_owner_df['date'] <= latest_date)
                ]
                
                cur_income = current_df[current_df['amount'] > 0]['amount'].sum()
                cur_expense = current_df[current_df['amount'] < 0]['amount'].sum()
                cur_fixed = current_df[current_df['expense_type'] == '고정 지출']['amount'].sum()
                cur_variable = current_df[current_df['expense_type'] == '변동 지출']['amount'].sum()

                # --- [B] 최근 1년 동기간 평균 계산 (핵심 로직 변경) ---
                # 1. 기간 필터: 1년 전 ~ 이번 달 시작 전까지
                past_year_df = display_owner_df[
                    (display_owner_df['date'] >= one_year_ago) & 
                    (display_owner_df['date'] < this_month_start)
                ]

                # 2. 일자 필터: 매월 1일 ~ 현재 일수(current_day) 까지만 포함
                # 예: 오늘이 10일이면, 작년 5월달 데이터 중에서도 1일~10일 데이터만 살림
                past_year_filtered = past_year_df[past_year_df['date'].dt.day <= current_day]

                # 3. 평균 계산을 위한 분모(개월 수) 계산
                # 12로 고정하지 않고, 실제 데이터가 있는 월의 개수를 셉니다 (데이터가 3개월치 밖에 없을 수도 있으므로)
                unique_months = past_year_filtered['date'].dt.to_period('M').nunique()
                if unique_months == 0:
                    unique_months = 1 # 0으로 나누기 방지

                # 4. 항목별 평균 산출 (총합 / 개월 수)
                avg_income = past_year_filtered[past_year_filtered['amount'] > 0]['amount'].sum() / unique_months
                avg_expense = past_year_filtered[past_year_filtered['amount'] < 0]['amount'].sum() / unique_months
                avg_fixed = past_year_filtered[past_year_filtered['expense_type'] == '고정 지출']['amount'].sum() / unique_months
                avg_variable = past_year_filtered[past_year_filtered['expense_type'] == '변동 지출']['amount'].sum() / unique_months

                # --- [C] 델타 계산 함수 (기존 유지) ---
                def calc_delta(current, average):
                    if average == 0:
                        return None
                    diff = current - average
                    pct = (diff / abs(average)) * 100
                    return f"{diff:,.0f}원 ({pct:+.1f}%)"

                # --- [D] UI 렌더링 ---
                c1, c2 = st.columns(2)
                with c1:
                    st.metric(
                        label="이번 달 총 수입", 
                        value=f"{cur_income:,.0f}원", 
                        delta=calc_delta(cur_income, avg_income),
                        help=f"최근 1년 동기간 평균: {avg_income:,.0f}원"
                    )
                    st.metric(
                        label="이번 달 총 지출", 
                        value=f"{cur_expense:,.0f}원", 
                        delta=calc_delta(cur_expense, avg_expense),
                        help=f"최근 1년 동기간 평균: {avg_expense:,.0f}원"
                    )
                with c2:
                    st.metric(
                        label="이번 달 고정 지출", 
                        value=f"{cur_fixed:,.0f}원",
                        delta=calc_delta(cur_fixed, avg_fixed),
                        help=f"최근 1년 동기간 평균: {avg_fixed:,.0f}원"
                    )
                    st.metric(
                        label="이번 달 변동 지출", 
                        value=f"{cur_variable:,.0f}원",
                        delta=calc_delta(cur_variable, avg_variable),
                        help=f"최근 1년 동기간 평균: {avg_variable:,.0f}원"
                    )

                # --- [C] 하단 상세 내역 필터링 및 합계 (새로 추가된 기능) ---
                st.divider()
                st.subheader("상세 내역 조회")

                # 0. 기간 선택 필터 (새로 추가됨)
                period_options = ["이번 주", "이번 달", "전체"]
                selected_period = st.radio(
                    "조회 기간",
                    period_options,
                    index=1, # 기본값: 최근 1개월
                    horizontal=True,
                    key=f"period_radio_{owner}"
                )

                # 1. 필터 UI 구성 (3단 컬럼)
                f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1, 2])
                
                with f_col1:
                    # 카테고리 선택 (다중 선택 가능)
                    unique_tx = sorted(display_owner_df['tx_type'].dropna().unique())
                    selected_tx = st.multiselect(
                        "수입/지출", 
                        unique_tx,
                        placeholder="전체 선택",
                        key=f"tx_select_{owner}" 
                    )

                with f_col2:
                    # 카테고리 선택 (다중 선택 가능)
                    unique_cats = sorted(display_owner_df['category_1'].dropna().unique())
                    selected_cats = st.multiselect(
                        "대분류", 
                        unique_cats,
                        placeholder="전체 선택",
                        key=f"cat_select_{owner}" 
                    )
                
                with f_col3:
                    # 지출 유형 선택 (고정/변동)
                    unique_types = sorted(display_owner_df['expense_type'].dropna().unique())
                    selected_types = st.multiselect(
                        "지출 유형",
                        unique_types,
                        placeholder="전체 선택",
                        key=f"expense_select_{owner}" 
                    )

                with f_col4:
                    # 적요 검색 (텍스트 입력)
                    search_text = st.text_input(
                        "내용",
                        placeholder="예: 스타벅스, 편의점",
                        key=f"search_input_{owner}"
                    )

                # 2. 필터링 로직 적용
                filtered_df = display_owner_df.copy()

                # [Step 1] 기간 필터 적용 (캘린더 기준)
                if selected_period == "이번 주":
                    # latest_date가 포함된 주의 월요일 계산
                    # weekday(): 월(0) ~ 일(6)
                    days_to_subtract = latest_date.weekday() 
                    start_of_week = latest_date - pd.Timedelta(days=days_to_subtract)
                    # 시간까지 00:00:00으로 초기화하고 싶다면:
                    start_of_week = start_of_week.replace(hour=0, minute=0, second=0)
                    
                    filtered_df = filtered_df[filtered_df['date'] >= start_of_week]

                elif selected_period == "이번 달":
                    # latest_date가 포함된 달의 1일 계산
                    start_of_month = latest_date.replace(day=1, hour=0, minute=0, second=0)
                    filtered_df = filtered_df[filtered_df['date'] >= start_of_month]

                # [Step 2] 카테고리/유형/검색어 필터 적용
                if selected_tx:
                    filtered_df = filtered_df[filtered_df['tx_type'].isin(selected_tx)]

                if selected_cats:
                    filtered_df = filtered_df[filtered_df['category_1'].isin(selected_cats)]
                
                if selected_types:
                    filtered_df = filtered_df[filtered_df['expense_type'].isin(selected_types)]
                    
                if search_text:
                    # 대소문자 구분 없이 검색 (case=False), NaN 값은 제외 (na=False)
                    filtered_df = filtered_df[filtered_df['description'].str.contains(search_text, case=False, na=False)]

                # 3. 데이터프레임 표시

                # 날짜 포맷팅 후 표시
                show_df = filtered_df.copy()
                show_df['date'] = show_df['date'].dt.strftime('%Y-%m-%d')

                st.dataframe(
                    show_df.sort_values(by=['date', 'time'], ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "date": "일자",
                        "time": "시간",
                        "tx_type": "수입/지출",
                        "owner": "소유자",
                        "category_1": "대분류",
                        "description": "내용",
                        "expense_type": "유형",
                        "memo": "메모",
                        "source": "결제수단",
                        "amount": st.column_config.NumberColumn(
                            "금액", 
                            format="%d원" 
                        ),
                    }
                )

                # 합계 표시
                if not filtered_df.empty:
                    income_filtered = filtered_df[filtered_df['amount'] > 0]['amount'].sum()
                    expense_filtered = filtered_df[filtered_df['amount'] < 0]['amount'].sum()

                    st.markdown(
                        f"<div style='text-align: left; color: gray; font-size: 1rem; margin-top: -20px;'>"
                        f"총 수입: <b>{income_filtered:,.0f}원</b> / 지출: <b>{expense_filtered:,.0f}원</b>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("조건에 맞는 내역이 없습니다.")