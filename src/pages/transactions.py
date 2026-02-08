import streamlit as st
import pandas as pd
import datetime
from utils.db_handler import get_analyzed_transactions

def render():
    st.header("📊 수입/지출현황 조회")
    st.caption("표준화된 카테고리로 정리된 상세 내역입니다.")

    df_analyzed = get_analyzed_transactions()

    if df_analyzed.empty:
        st.info("데이터가 없습니다. 먼저 [1. 가계부 업로드] 메뉴에서 엑셀 파일을 저장해주세요.")
    else:
        # date 컬럼을 datetime으로 변환 (계산용)
        df_analyzed_dt = df_analyzed.copy()
        df_analyzed_dt['date'] = pd.to_datetime(df_analyzed_dt['date'])
        
        # 데이터의 가장 최근 날짜 기준
        latest_date = df_analyzed_dt['date'].max()

        # 산정기준 날짜 표시 (캡션 바로 아래)
        st.caption(f"📅 Updated: {latest_date.strftime('%Y-%m-%d')}")
        
        # 해당 날짜 기준 월의 시작일과 주의 시작일
        month_start = latest_date.replace(day=1)
        week_start = latest_date - datetime.timedelta(days=latest_date.weekday())
         
        # 3. 데이터 탭 (전체, 형준, 윤희)
        owners = ['전체'] + sorted(df_analyzed_dt['owner'].unique().tolist())
        
        # 탭명 생성 (전체는 그대로, 나머지는 님 추가)
        tab_names = ['전체'] + [f"{owner}님" for owner in sorted(df_analyzed_dt['owner'].unique().tolist())]
        tabs = st.tabs([f"{name}" for name in tab_names])
        
        for idx, owner in enumerate(owners):
            with tabs[idx]:
                if owner == '전체':
                    display_owner_df = df_analyzed_dt.copy()
                    owner_label = "전체"
                else:
                    display_owner_df = df_analyzed_dt[df_analyzed_dt['owner'] == owner]
                    owner_label = f"{owner}님"
                
                # 해당 owner의 이번 달/주 지출
                owner_this_month = display_owner_df[
                    (display_owner_df['date'] >= month_start) & 
                    (display_owner_df['date'] <= latest_date)
                ]
                owner_this_week = display_owner_df[
                    (display_owner_df['date'] >= week_start) & 
                    (display_owner_df['date'] <= latest_date)
                ]
                
                owner_month_fixed = owner_this_month[owner_this_month['expense_type'] == '고정 지출']['amount'].sum()
                owner_month_variable = owner_this_month[owner_this_month['expense_type'] == '변동 지출']['amount'].sum()
                owner_week_fixed = owner_this_week[owner_this_week['expense_type'] == '고정 지출']['amount'].sum()
                owner_week_variable = owner_this_week[owner_this_week['expense_type'] == '변동 지출']['amount'].sum()
                
                # 소유자별 메트릭
                ocol1, ocol2 = st.columns(2)
                with ocol1:
                    st.metric(label=f"{owner_label} 이번 달 고정 지출", value=f"{owner_month_fixed:,.0f}원")
                    st.metric(label=f"{owner_label} 이번 주 고정 지출", value=f"{owner_week_fixed:,.0f}원")
                with ocol2:
                    st.metric(label=f"{owner_label} 이번 달 변동 지출", value=f"{owner_month_variable:,.0f}원")
                    st.metric(label=f"{owner_label} 이번 주 변동 지출", value=f"{owner_week_variable:,.0f}원")
                
               
                # 표시용으로 date를 문자열로 변환
                display_df = display_owner_df.copy()
                display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
                st.dataframe(display_df, use_container_width=True, hide_index=True)
