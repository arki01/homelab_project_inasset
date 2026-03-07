import calendar
import hashlib
import json
import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openai import OpenAI

from utils.ai_agent import STANDARD_CATEGORIES, generate_analysis_summary
from utils.db_handler import get_analyzed_transactions, get_asset_history, get_budgets


def render():
    st.markdown("""
        <style>
        .page-header {
            text-align: center; padding: 1rem 0 0.5rem;
            color: #000000; font-size: 2.5rem; font-weight: 700;
        }
        .page-subtitle {
            text-align: center; color: var(--text-color);
            opacity: 0.7; font-size: 1rem; margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="page-header">분석 리포트</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">과거 패턴을 분석하여 소비 현황과 자산 흐름을 파악합니다.</div>', unsafe_allow_html=True)

    df_all = get_analyzed_transactions()
    if df_all.empty:
        st.info("데이터가 없습니다. 먼저 데이터를 업로드해주세요.")
        return

    # 메트릭 계산 → GPT 요약 카드
    anomaly_metrics = _compute_anomaly_metrics(df_all)
    burnrate_metrics = _compute_burnrate_metrics(df_all)
    _render_summary_card(anomaly_metrics, burnrate_metrics)

    st.subheader("🚨 이상 지출")
    _render_anomaly(df_all)

    st.divider()

    st.subheader("💸 지출 예측")
    _render_burnrate(df_all)

    st.divider()

    st.subheader("📈 자산 트렌드")
    _render_asset_trend(owner="전체")


# ──────────────────────────────────────────────
# GPT 요약 카드
# ──────────────────────────────────────────────

def _compute_anomaly_metrics(df_all) -> dict | None:
    """이상 지출 계산. 데이터 부족(3개월 미만) 시 None 반환."""
    df = df_all[df_all['tx_type'] == '지출'].copy()
    if df.empty:
        return None

    df['amount_abs'] = df['amount'].abs()
    df['date'] = pd.to_datetime(df['date'])
    df['year_month'] = df['date'].dt.to_period('M')

    today = date.today()
    current_period = pd.Period(today, 'M')
    today_day = today.day

    past_df = df[
        (df['year_month'] < current_period) &
        (df['year_month'] >= current_period - 12)
    ].copy()
    current_df = df[df['year_month'] == current_period].copy()

    past_months = past_df['year_month'].nunique()
    if past_months < 3:
        return None

    past_same_period = past_df[past_df['date'].dt.day <= today_day].copy()
    past_monthly = (
        past_same_period.groupby(['year_month', 'category_1'])['amount_abs']
        .sum().reset_index()
    )
    past_stats = (
        past_monthly.groupby('category_1')['amount_abs']
        .agg(['mean', 'std']).reset_index()
    )
    past_stats.columns = ['category_1', 'mean', 'std']

    if current_df.empty:
        return {"anomalies": [], "past_months": past_months}

    current_monthly = (
        current_df.groupby('category_1')['amount_abs']
        .sum().reset_index()
        .rename(columns={'amount_abs': 'current_amount'})
    )
    merged = current_monthly.merge(past_stats, on='category_1', how='left').dropna(subset=['mean', 'std'])
    anomalies_df = merged[
        (merged['std'] > 0) &
        (abs(merged['current_amount'] - merged['mean']) > 2 * merged['std'])
    ].copy()

    anomalies = []
    for _, row in anomalies_df.iterrows():
        diff = row['current_amount'] - row['mean']
        pct = (diff / row['mean'] * 100) if row['mean'] > 0 else 0
        anomalies.append({
            "category": row['category_1'],
            "current": int(row['current_amount']),
            "mean": int(row['mean']),
            "diff": int(diff),
            "pct": round(pct, 1),
            "direction": "over" if diff > 0 else "under",
        })

    return {"anomalies": anomalies, "past_months": past_months}


def _compute_burnrate_metrics(df_all) -> dict | None:
    """Burn-rate 계산. 이번 달 지출 없으면 None 반환."""
    today = date.today()
    first_of_month = today.replace(day=1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    df = df_all.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['year_month'] = df['date'].dt.to_period('M')
    current_period = pd.Period(today, 'M')

    budgets_df = get_budgets()
    budget_total = int(budgets_df['monthly_amount'].sum()) if not budgets_df.empty else 0

    df_month = df[
        (df['tx_type'] == '지출') &
        (df['date'] >= pd.Timestamp(first_of_month)) &
        (df['date'] <= pd.Timestamp(today))
    ].copy()
    df_month['amount_abs'] = df_month['amount'].abs()

    daily = df_month.groupby('date')['amount_abs'].sum().reset_index()
    date_range = pd.date_range(start=first_of_month, end=today)
    daily = (
        daily.set_index('date').reindex(date_range, fill_value=0).reset_index()
        .rename(columns={'index': 'date', 'amount_abs': 'amount'})
    )
    daily['cumulative'] = daily['amount'].cumsum()
    current_total = int(daily['cumulative'].iloc[-1]) if not daily.empty else 0

    past_12_df = df[
        (df['tx_type'] == '지출') &
        (df['year_month'] < current_period) &
        (df['year_month'] >= current_period - 12)
    ].copy()
    past_12_df['amount_abs'] = past_12_df['amount'].abs()
    past_12_df['day_of_month'] = past_12_df['date'].dt.day

    past_daily_pattern = pd.Series(dtype=float)
    if not past_12_df.empty:
        n_months = past_12_df['year_month'].nunique()
        past_daily_pattern = (
            past_12_df.groupby(['year_month', 'day_of_month'])['amount_abs']
            .sum().reset_index()
            .groupby('day_of_month')['amount_abs']
            .sum()
            .div(n_months)
        )

    remaining_days = range(today.day + 1, days_in_month + 1)
    projected_total = current_total + int(sum(past_daily_pattern.get(d, 0) for d in remaining_days))

    if current_total == 0 and projected_total == 0:
        return None

    budget_pct = (current_total / budget_total * 100) if budget_total > 0 else 0
    will_exceed = (projected_total > budget_total) if budget_total > 0 else False

    return {
        "current_total": current_total,
        "projected_total": projected_total,
        "budget_total": budget_total,
        "budget_pct": round(budget_pct, 1),
        "will_exceed": will_exceed,
    }


def _render_summary_card(anomaly_metrics: dict | None, burnrate_metrics: dict | None):
    """GPT 기반 분석 요약 안내글 카드."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return

    # 데이터 해시 기반 세션 캐시 (같은 데이터 → 재호출 없음)
    metrics_hash = hashlib.md5(
        json.dumps([anomaly_metrics, burnrate_metrics], sort_keys=True, default=str).encode()
    ).hexdigest()[:10]
    cache_key = f"analysis_summary_{date.today().isoformat()}_{metrics_hash}"

    if cache_key not in st.session_state:
        with st.spinner("AI 요약 생성 중..."):
            try:
                client = OpenAI(api_key=api_key)
                summary = generate_analysis_summary(client, anomaly_metrics, burnrate_metrics)
            except Exception:
                summary = ""
        st.session_state[cache_key] = summary
    else:
        summary = st.session_state[cache_key]

    if summary:
        st.markdown(f"""
            <div style="background:var(--background-color);
                        border-left:4px solid #667eea;
                        padding:0.9rem 1.2rem;
                        border-radius:4px;
                        margin-bottom:1.5rem;
                        font-size:0.95rem;
                        line-height:1.75;">
                🤖 {summary}
            </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 이상 지출 탐지
# ──────────────────────────────────────────────

def _render_anomaly(df_all):
    df = df_all[df_all['tx_type'] == '지출'].copy()
    if df.empty:
        st.info("지출 데이터가 없습니다.")
        return

    df['amount_abs'] = df['amount'].abs()
    df['date'] = pd.to_datetime(df['date'])
    df['year_month'] = df['date'].dt.to_period('M')

    today = date.today()
    current_period = pd.Period(today, 'M')
    today_day = today.day

    past_df = df[
        (df['year_month'] < current_period) &
        (df['year_month'] >= current_period - 12)
    ].copy()
    current_df = df[df['year_month'] == current_period].copy()

    past_months = past_df['year_month'].nunique()
    if past_months < 3:
        st.info(f"최소 3개월 이상 과거 데이터가 필요합니다. (현재 {past_months}개월 보유)")
        return

    # 과거 데이터도 동일 구간(1일~당일)으로 한정하여 공정 비교
    past_same_period = past_df[past_df['date'].dt.day <= today_day].copy()

    past_monthly = (
        past_same_period.groupby(['year_month', 'category_1'])['amount_abs']
        .sum().reset_index()
    )
    past_stats = (
        past_monthly.groupby('category_1')['amount_abs']
        .agg(['mean', 'std']).reset_index()
    )
    past_stats.columns = ['category_1', 'mean', 'std']

    if current_df.empty:
        st.info("이번 달 지출 데이터가 없습니다.")
        return

    current_monthly = (
        current_df.groupby('category_1')['amount_abs']
        .sum().reset_index()
        .rename(columns={'amount_abs': 'current_amount'})
    )

    merged = current_monthly.merge(past_stats, on='category_1', how='left').dropna(subset=['mean', 'std'])
    anomalies = merged[
        (merged['std'] > 0) &
        (abs(merged['current_amount'] - merged['mean']) > 2 * merged['std'])
    ].copy()

    st.caption(f"비교 기준: 매월 1일~{today_day}일 누적 지출 / 과거 {past_months}개월 평균")

    if anomalies.empty:
        st.success("이번 달 이상 지출이 감지되지 않았습니다.")
        return

    for _, row in anomalies.iterrows():
        diff = row['current_amount'] - row['mean']
        pct = (diff / row['mean'] * 100) if row['mean'] > 0 else 0
        sign = "+" if diff > 0 else ""
        st.warning(
            f"🚨 **{row['category_1']}** — 이번 달 {today_day}일까지 {int(row['current_amount']):,}원 "
            f"(평균 대비 {sign}{pct:.0f}%, {sign}{int(diff):,}원)"
        )
        with st.expander("상세 내역 보기"):
            detail = (
                current_df[current_df['category_1'] == row['category_1']]
                [['date', 'description', 'amount_abs', 'source']].copy()
                .rename(columns={'date': '날짜', 'description': '내용',
                                 'amount_abs': '금액', 'source': '결제수단'})
            )
            detail['금액'] = detail['금액'].apply(lambda x: f"{int(x):,}원")
            detail['날짜'] = detail['날짜'].dt.strftime('%Y-%m-%d')
            st.dataframe(detail, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────
# 지출 예측 (Burn-rate)
# ──────────────────────────────────────────────

def _render_burnrate(df_all):
    today = date.today()
    first_of_month = today.replace(day=1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    end_of_month = date(today.year, today.month, days_in_month)

    df = df_all.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['year_month'] = df['date'].dt.to_period('M')
    current_period = pd.Period(today, 'M')

    # 카테고리 목록: STANDARD_CATEGORIES 기준 + 예산에 있는 추가 카테고리
    budgets_df = get_budgets()
    known_cats = set(budgets_df['category'].tolist()) if not budgets_df.empty else set()
    std_cats_available = [c for c in STANDARD_CATEGORIES if c in known_cats]
    extra_cats = sorted(known_cats - set(STANDARD_CATEGORIES))
    all_categories = ["전체"] + std_cats_available + extra_cats

    col_cat, _col2, _col3 = st.columns(3)
    with col_cat:
        selected_cat = st.selectbox("카테고리 선택", all_categories)

    exclude_yebibee = False
    if selected_cat == "전체":
        exclude_yebibee = st.checkbox("예비비 제외 (이벤트성 비용)", value=True)

    # 이번 달 지출 (1일~오늘)
    df_month = df[
        (df['tx_type'] == '지출') &
        (df['date'] >= pd.Timestamp(first_of_month)) &
        (df['date'] <= pd.Timestamp(today))
    ].copy()
    df_month['amount_abs'] = df_month['amount'].abs()
    if selected_cat != "전체":
        df_month = df_month[df_month['category_1'] == selected_cat]
    elif exclude_yebibee:
        df_month = df_month[df_month['category_1'] != '예비비']

    # 일별 합산 → 누적합
    daily = df_month.groupby('date')['amount_abs'].sum().reset_index()
    date_range = pd.date_range(start=first_of_month, end=today)
    daily = (
        daily.set_index('date').reindex(date_range, fill_value=0).reset_index()
        .rename(columns={'index': 'date', 'amount_abs': 'amount'})
    )
    daily['cumulative'] = daily['amount'].cumsum()
    current_total = int(daily['cumulative'].iloc[-1]) if not daily.empty else 0

    # 과거 12개월 일별 평균 패턴으로 비선형 예측
    past_12_df = df[
        (df['tx_type'] == '지출') &
        (df['year_month'] < current_period) &
        (df['year_month'] >= current_period - 12)
    ].copy()
    past_12_df['amount_abs'] = past_12_df['amount'].abs()
    past_12_df['day_of_month'] = past_12_df['date'].dt.day
    if selected_cat != "전체":
        past_12_df = past_12_df[past_12_df['category_1'] == selected_cat]
    elif exclude_yebibee:
        past_12_df = past_12_df[past_12_df['category_1'] != '예비비']

    past_daily_pattern = pd.Series(dtype=float)
    if not past_12_df.empty:
        n_months = past_12_df['year_month'].nunique()
        past_daily_pattern = (
            past_12_df.groupby(['year_month', 'day_of_month'])['amount_abs']
            .sum().reset_index()
            .groupby('day_of_month')['amount_abs']
            .sum()
            .div(n_months)
        )

    remaining_days = range(today.day + 1, days_in_month + 1)
    projected_total = current_total + int(sum(past_daily_pattern.get(d, 0) for d in remaining_days))

    # 지난달 실제 지출
    last_period = current_period - 1
    last_month_df = df[
        (df['tx_type'] == '지출') &
        (df['year_month'] == last_period)
    ].copy()
    last_month_df['amount_abs'] = last_month_df['amount'].abs()
    last_month_df['day_of_month'] = last_month_df['date'].dt.day
    if selected_cat != "전체":
        last_month_df = last_month_df[last_month_df['category_1'] == selected_cat]
    elif exclude_yebibee:
        last_month_df = last_month_df[last_month_df['category_1'] != '예비비']

    last_month_total = int(last_month_df[last_month_df['day_of_month'] <= today.day]['amount_abs'].sum())

    last_month_dates = []
    last_month_values = []
    if not last_month_df.empty:
        last_daily = last_month_df.groupby('day_of_month')['amount_abs'].sum()
        running_last = 0.0
        for d in range(1, days_in_month + 1):
            running_last += float(last_daily.get(d, 0))
            last_month_dates.append(pd.Timestamp(date(today.year, today.month, d)))
            last_month_values.append(round(running_last))

    # 예산
    if selected_cat == "전체":
        budget_total = int(budgets_df['monthly_amount'].sum()) if not budgets_df.empty else 0
    else:
        row = budgets_df[budgets_df['category'] == selected_cat]
        budget_total = int(row['monthly_amount'].iloc[0]) if not row.empty else 0

    budget_pct = (current_total / budget_total * 100) if budget_total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("현재 누적 지출", f"{current_total:,}원")
    with col2:
        last_diff = current_total - last_month_total if last_month_total > 0 else None
        st.metric(
            "지난달 누적 지출 (현재 기준)",
            f"{last_month_total:,}원" if last_month_total > 0 else "데이터 없음",
            delta=f"{last_diff:+,}원" if last_diff is not None else None,
            delta_color="inverse",
        )
    with col3:
        if budget_total > 0:
            budget_diff = projected_total - budget_total
            sign = "+" if budget_diff > 0 else ""
            st.metric(
                "예상 월말 지출",
                f"{projected_total:,}원",
                delta=f"{sign}{budget_diff:,}원 (예산 대비)",
                delta_color="inverse",
                help=f"설정 예산: {budget_total:,}원",
            )
        else:
            st.metric("예상 월말 지출", f"{projected_total:,}원", help="설정된 예산이 없습니다.")
    with col4:
        st.metric("예산 대비 소진율", f"{budget_pct:.1f}%" if budget_total > 0 else "예산 미설정")

    if current_total == 0 and projected_total == 0:
        st.info("이번 달 지출 데이터가 없습니다.")
        return

    # 예측 곡선 구성 (오늘 지점부터 연결)
    pred_dates = [pd.Timestamp(today)]
    pred_values = [current_total]
    running = float(current_total)
    for d in remaining_days:
        running += float(past_daily_pattern.get(d, 0))
        pred_dates.append(pd.Timestamp(date(today.year, today.month, d)))
        pred_values.append(round(running))

    past_months_count = past_12_df['year_month'].nunique() if not past_12_df.empty else 0
    subtitle = f"과거 {past_months_count}개월 패턴 기반" if past_months_count > 0 else "과거 데이터 없음"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily['date'], y=daily['cumulative'],
        mode='lines', name='현재 누적 지출',
        line=dict(color='#667eea', width=2),
    ))
    if last_month_dates:
        fig.add_trace(go.Scatter(
            x=last_month_dates, y=last_month_values,
            mode='lines', name='지난달 지출',
            line=dict(color='#cccccc', width=1.5),
        ))
    fig.add_trace(go.Scatter(
        x=pred_dates, y=pred_values,
        mode='lines', name='지출 예측 (과거 12개월 기준)',
        line=dict(color='#999999', width=2, dash='dot'),
    ))
    if budget_total > 0:
        all_dates = pd.date_range(start=first_of_month, end=end_of_month)
        fig.add_trace(go.Scatter(
            x=all_dates, y=[budget_total] * len(all_dates),
            mode='lines', name='예산',
            line=dict(color='#e74c3c', width=1.5, dash='dash'),
        ))

    fig.update_layout(
        title=f'{today.year}년 {today.month}월 지출 예측 ({selected_cat}) — {subtitle}',
        xaxis_title='날짜', yaxis_title='금액 (원)',
        yaxis_tickformat=',', hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


# ──────────────────────────────────────────────
# 자산 트렌드
# ──────────────────────────────────────────────

def _fill_combined_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 소유자 합산 트렌드를 계산합니다.
    특정 날짜에 데이터가 없는 소유자는 가장 가까운 과거 스냅샷으로 보정 후 합산합니다.
    """
    df = df.sort_values('snapshot_date')
    owners = df['owner'].unique()
    all_dates = sorted(df['snapshot_date'].unique())

    rows = []
    for d in all_dates:
        total_net, total_asset, total_debt = 0.0, 0.0, 0.0
        for owner in owners:
            past = df[(df['owner'] == owner) & (df['snapshot_date'] <= d)]
            if not past.empty:
                latest = past.iloc[-1]
                total_net += float(latest['net_worth'])
                total_asset += float(latest['total_asset'])
                total_debt += float(latest['total_debt'])
        rows.append({'snapshot_date': d, 'net_worth': total_net,
                     'total_asset': total_asset, 'total_debt': total_debt})
    return pd.DataFrame(rows)


def _render_asset_trend(owner: str):
    df = get_asset_history()
    if df.empty:
        st.info("자산 스냅샷 데이터가 없습니다. 먼저 자산 데이터를 업로드해주세요.")
        return

    df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])

    if owner == "전체":
        trend = _fill_combined_trend(df)
        trend['snapshot_date'] = pd.to_datetime(trend['snapshot_date'])
    else:
        trend = df[df['owner'] == owner].copy()

    if trend.empty or len(trend) < 2:
        st.info("자산 트렌드를 표시하려면 2개 이상의 스냅샷이 필요합니다.")
        return

    trend = trend.sort_values('snapshot_date')
    trend['ma3'] = trend['net_worth'].rolling(3, min_periods=1).mean().round().astype('Int64')

    # 2년 예측 (스냅샷 3개 이상일 때만)
    # - 근 2년치 데이터만 피팅하여 최근 트렌드 반영
    # - 오늘(today_ts)부터 24개월 앞까지 예측
    forecast_dates = []
    forecast_values = []
    if len(trend) >= 3:
        today_ts = pd.Timestamp(date.today())
        cutoff = today_ts - pd.DateOffset(years=2)
        trend_fit = trend[trend['snapshot_date'] >= cutoff]
        if len(trend_fit) < 3:
            trend_fit = trend  # 2년치 3개 미만이면 전체 사용

        origin = trend_fit['snapshot_date'].min()
        x = np.array([(d - origin).days for d in trend_fit['snapshot_date']])
        y = trend_fit['net_worth'].values
        slope_per_day = np.polyfit(x, y, 1)[0]  # 기울기(원/일)만 사용, 절편 버림

        # 시작점을 실제 최신 순자산으로 고정 후 기울기 적용
        base_value = float(trend.iloc[-1]['net_worth'])
        forecast_dates = [today_ts + pd.DateOffset(months=i) for i in range(0, 25)]
        days_from_today = np.array([(d - today_ts).days for d in forecast_dates])
        forecast_values = np.round(base_value + slope_per_day * days_from_today).astype(int)

    latest = trend.iloc[-1]
    prev = trend.iloc[-2]
    delta = latest['net_worth'] - prev['net_worth']

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 자산", f"{int(latest['total_asset']):,}원")
    with col2:
        st.metric("총 부채", f"{int(latest['total_debt']):,}원")
    with col3:
        st.metric("순 자산", f"{int(latest['net_worth']):,}원", delta=f"{int(delta):,}원")

    owner_note = "전체 (보정 합산)" if owner == "전체" else owner
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend['snapshot_date'], y=trend['net_worth'],
        mode='lines+markers', name='순자산',
        opacity=0.6, line=dict(color='#667eea', width=1.5), marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=trend['snapshot_date'], y=trend['ma3'],
        mode='lines', name='3개월 이동평균',
        line=dict(color='#764ba2', width=3),
    ))
    if forecast_dates:
        fig.add_trace(go.Scatter(
            x=forecast_dates, y=forecast_values,
            mode='lines', name='2년 예측 (선형 추세)',
            line=dict(color='#999999', width=2, dash='dot'),
        ))
    fig.update_layout(
        title=f'자산 트렌드 — {owner_note}',
        xaxis_title='날짜', yaxis_title='금액 (원)',
        yaxis_tickformat=',', hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
