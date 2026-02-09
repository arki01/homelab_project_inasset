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
        
        latest_date = df_analyzed_dt['date'].max() # 데이터상 가장 최근 날짜
        
        # 이번 달 기준 (1일 ~ 최근 날짜)
        this_month_start = latest_date.replace(day=1)
        
        # 지난 달 동기간 기준 (지난달 1일 ~ 지난달 최근 날짜와 같은 날)
        last_month_start = this_month_start - relativedelta(months=1)
        last_month_end = latest_date - relativedelta(months=1)
         
        st.caption(f"📅 Updated: {latest_date.strftime('%Y-%m-%d')} (전월 동기간 {last_month_end.strftime('%m-%d')} 대비)")
        st.subheader("총 내역")

        # 탭 설정
        owners = ['전체'] + sorted(df_analyzed_dt['owner'].unique().tolist())
        tabs = st.tabs([f"{owner}님" if owner != '전체' else '전체' for owner in owners])
        
        for idx, owner in enumerate(owners):
            with tabs[idx]:
                # Owner 필터링
                if owner == '전체':
                    display_owner_df = df_analyzed_dt.copy()
                    label_prefix = "전체"
                else:
                    display_owner_df = df_analyzed_dt[df_analyzed_dt['owner'] == owner]
                    label_prefix = f"{owner}님"
                
                # --- 데이터 집계 로직 시작 ---
                
                # A. 이번 달 데이터 필터링
                current_df = display_owner_df[
                    (display_owner_df['date'] >= this_month_start) & 
                    (display_owner_df['date'] <= latest_date)
                ]
                
                # B. 지난 달 데이터 필터링 (동기간)
                past_df = display_owner_df[
                    (display_owner_df['date'] >= last_month_start) & 
                    (display_owner_df['date'] <= last_month_end)
                ]

                # C. 금액 집계 함수 (중복 제거를 위해 함수형태 혹은 간단히 변수 처리)
                # 이번 달
                cur_income = current_df[current_df['amount'] > 0]['amount'].sum()
                cur_expense = current_df[current_df['amount'] < 0]['amount'].sum() # 음수 값
                cur_fixed = current_df[current_df['expense_type'] == '고정 지출']['amount'].sum()
                cur_variable = current_df[current_df['expense_type'] == '변동 지출']['amount'].sum()

                # 지난 달
                prev_income = past_df[past_df['amount'] > 0]['amount'].sum()
                prev_expense = past_df[past_df['amount'] < 0]['amount'].sum()
                prev_fixed = past_df[past_df['expense_type'] == '고정 지출']['amount'].sum()
                prev_variable = past_df[past_df['expense_type'] == '변동 지출']['amount'].sum()

                # D. 증감률 계산 헬퍼 함수
                def calc_delta(current, previous):
                    if previous == 0:
                        return None # 지난달 데이터가 0이면 비교 불가
                    diff = current - previous
                    pct = (diff / abs(previous)) * 100
                    return f"{diff:,.0f}원 ({pct:+.1f}%)"

                # --- UI 렌더링 ---
                
                c1, c2 = st.columns(2)
                with c1:
                    st.metric(
                        label="이번 달 총 수입", 
                        value=f"{cur_income:,.0f}원", 
                        delta=calc_delta(cur_income, prev_income)
                    )
                    # 지출은 음수이므로, 절댓값으로 보여주거나 로직에 유의해야 함 (여기서는 원본 값 유지하되 delta 색상 반전)
                    st.metric(
                        label="이번 달 총 지출", 
                        value=f"{cur_expense:,.0f}원", 
                        delta=calc_delta(cur_expense, prev_expense),
                        delta_color="inverse" # 지출이 늘어나면 빨간색(Bad)이 아니라 초록색? 통상 지출 증가는 Bad(Red)
                    )
                with c2:
                    st.metric(
                        label="이번 달 고정 지출", 
                        value=f"{cur_fixed:,.0f}원",
                        delta=calc_delta(cur_fixed, prev_fixed),
                        delta_color="inverse"
                    )
                    st.metric(
                        label="이번 달 변동 지출", 
                        value=f"{cur_variable:,.0f}원",
                        delta=calc_delta(cur_variable, prev_variable),
                        delta_color="inverse"
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
                f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
                
                with f_col1:
                    # 카테고리 선택 (다중 선택 가능)
                    unique_cats = sorted(display_owner_df['category_1'].dropna().unique())
                    selected_cats = st.multiselect(
                        "대분류", 
                        unique_cats,
                        placeholder="전체 선택",
                        key=f"cat_select_{owner}" 
                    )
                
                with f_col2:
                    # 지출 유형 선택 (고정/변동)
                    unique_types = sorted(display_owner_df['expense_type'].dropna().unique())
                    selected_types = st.multiselect(
                        "지출 유형",
                        unique_types,
                        placeholder="전체 선택",
                        key=f"type_select_{owner}" 
                    )

                with f_col3:
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
                    show_df.sort_values(by='date', ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "amount": st.column_config.NumberColumn("금액", format="%d원"),
                        "date": "일자",
                        "time": "시간",
                        "owner": "소유자",
                        "category_1": "대분류",
                        "description": "내용",
                        "expense_type": "유형"
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