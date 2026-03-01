import streamlit as st
import pandas as pd
import datetime
import calendar
import os
import io
import time

from utils.db_handler import (
    save_transactions, save_asset_snapshot, clear_all_data,
    sync_categories_from_transactions, mark_file_processed, get_processed_filenames,
    has_transactions_in_range,
)
from utils.file_handler import (
    process_uploaded_zip, process_uploaded_excel,
    extract_snapshot_date, extract_date_range, scan_docs_folder, detect_owner_from_filename, DOCS_DIR,
)

_OWNER_PASSWORDS = {'형준': '0979', '윤희': '1223'}


def _two_months_before(d: datetime.date) -> datetime.date:
    """end_date 기준 2개월 전 같은 날을 반환합니다. (월말 초과 시 해당 월 말일로 보정)"""
    month = d.month - 2
    year = d.year
    if month <= 0:
        month += 12
        year -= 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _resolve_date_range(
    owner: str, file_start: datetime.date, file_end: datetime.date
) -> tuple:
    """
    DB 데이터 유무에 따라 실제 적용할 처리 기간을 결정합니다.
      - 해당 기간에 데이터 없음 → 파일 전체 기간 (file_start ~ file_end)
      - 겹치는 데이터 있음     → 최근 2개월 (file_end - 2개월 ~ file_end)
    """
    if has_transactions_in_range(owner, str(file_start), str(file_end)):
        return _two_months_before(file_end), file_end
    return file_start, file_end


def _build_item(filename: str, file_obj=None) -> dict:
    """파일명에서 처리 메타데이터 추출"""
    start_str, snapshot_str = extract_date_range(filename)
    if start_str is None:
        start_str = str(
            datetime.date.fromisoformat(snapshot_str) - datetime.timedelta(days=30)
        )
    return {
        'file': file_obj,
        'filename': filename,
        'owner': detect_owner_from_filename(filename),
        'snapshot_date': snapshot_str,
        'start_date': start_str,
    }


def _process_single(file_obj, filename: str, owner: str, start_date, end_date):
    """단일 파일 파싱 및 저장. (tx_count, asset_count, error) 반환"""
    password = _OWNER_PASSWORDS.get(owner, '')
    if filename.lower().endswith('.zip'):
        tx_df, asset_df, error = process_uploaded_zip(
            file_obj, password, start_date=start_date, end_date=end_date
        )
    else:
        tx_df, asset_df, error = process_uploaded_excel(
            file_obj, start_date=start_date, end_date=end_date
        )

    if error:
        return 0, 0, error

    tx_count = 0
    if tx_df is not None and not tx_df.empty:
        tx_count = save_transactions(tx_df, owner=owner, filename=filename)

    asset_count = 0
    if asset_df is not None and not asset_df.empty:
        asset_count = save_asset_snapshot(
            asset_df, owner=owner, snapshot_date=extract_snapshot_date(filename)
        )

    return tx_count, asset_count, None


def _show_file_table(items: list):
    """파일 목록 요약 테이블 렌더링 (snapshot_date 오름차순)"""
    rows = [{
        '파일명': it['filename'],
        '소유자': it['owner'] or '⚠️ 미감지',
        '기준일': it['snapshot_date'],
        '처리 기간': f"{it['start_date']} ~ {it['snapshot_date']}",
    } for it in sorted(items, key=lambda x: x['snapshot_date'])]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _run_batch(items: list, is_docs: bool = False) -> list:
    """snapshot_date 오름차순으로 파일을 순차 처리. 결과 리스트를 반환."""
    sorted_items = sorted(items, key=lambda x: x['snapshot_date'])
    results = []
    progress_bar = st.progress(0, text="처리 중...")

    for i, item in enumerate(sorted_items):
        filename = item['filename']
        owner = item['owner']
        file_start = datetime.date.fromisoformat(item['start_date'])
        file_end = datetime.date.fromisoformat(item['snapshot_date'])

        actual_start, actual_end = _resolve_date_range(owner, file_start, file_end)

        if is_docs:
            with open(os.path.join(DOCS_DIR, filename), 'rb') as f:
                file_obj = io.BytesIO(f.read())
        else:
            file_obj = item['file']

        tx_count, asset_count, error = _process_single(
            file_obj, filename, owner, actual_start, actual_end
        )

        period_str = f"{actual_start} ~ {actual_end}"
        if error:
            results.append({'파일명': filename, '소유자': owner, '처리기간': period_str, '처리결과': f'❌ {error}'})
        else:
            results.append({'파일명': filename, '소유자': owner, '처리기간': period_str, '처리결과': f'✅ 거래 {tx_count}건  자산 {asset_count}건'})
            if is_docs:
                mark_file_processed(filename, owner, item['snapshot_date'])

        progress_bar.progress((i + 1) / len(sorted_items))

    sync_categories_from_transactions()
    progress_bar.empty()
    return results


def _show_results(results: list):
    """배치 처리 결과를 렌더링합니다."""
    success_count = sum(1 for r in results if '✅' in r['처리결과'])
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    st.success(f"✅ {success_count} / {len(results)}개 파일 처리 완료")


def render():
    st.header("📥 가계부 업로드")
    st.caption("우리 부부의 가계부 기록을 통합하는 첫 단계입니다.")

    # ── Section 1: 직접 업로드 ─────────────────────────────
    st.subheader("수동 업로드 처리")

    if st.session_state.get('upload_results') is None:
        with st.container(border=True):
            uploaded_files = st.file_uploader(
                "뱅크샐러드 ZIP 또는 Excel 파일 (여러 파일 동시 선택 가능)",
                type=["zip", "xlsx", "xls"],
                accept_multiple_files=True,
            )

        if uploaded_files:
            items = [_build_item(f.name, file_obj=f) for f in uploaded_files]
            _show_file_table(items)

            undetected = [it['filename'] for it in items if not it['owner']]
            if undetected:
                st.warning(f"⚠️ 소유자 미감지 파일은 처리에서 제외됩니다: {', '.join(undetected)}")

            processable = [it for it in items if it['owner']]
            if processable:
                if st.button("DB 업데이트", use_container_width=True):
                    results = _run_batch(processable, is_docs=False)
                    st.session_state['upload_results'] = results
                    st.rerun()
    else:
        _show_results(st.session_state['upload_results'])
        if st.button("↩ 다시 업로드", key="reset_upload_btn", use_container_width=True):
            st.session_state.pop('upload_results', None)
            st.rerun()

    st.divider()

    # ── Section 2: docs/ 폴더 자동 처리 ──────────────────
    st.subheader("메일 첨부파일 자동 처리")

    if st.button("메일 첨부파일 확인", use_container_width=True):
        all_docs = scan_docs_folder()
        processed = get_processed_filenames()
        pending = [f for f in all_docs if f['filename'] not in processed]
        st.session_state['docs_pending'] = sorted(pending, key=lambda x: x['snapshot_date'])
        st.session_state.pop('docs_results', None)  # 이전 결과 초기화
        st.rerun()

    pending = st.session_state.get('docs_pending')
    if pending is not None:
        if not pending:
            st.info("처리할 새 파일이 없습니다.")
        else:
            _show_file_table(pending)

            undetected = [it['filename'] for it in pending if not it['owner']]
            if undetected:
                st.warning(f"⚠️ 소유자 미감지 파일은 처리에서 제외됩니다: {', '.join(undetected)}")

            processable = [it for it in pending if it['owner']]
            if processable:
                if st.button("DB 업데이트", key="docs_batch_btn", use_container_width=True):
                    results = _run_batch(processable, is_docs=True)
                    st.session_state['docs_results'] = results
                    st.session_state['docs_pending'] = None
                    st.rerun()

    if st.session_state.get('docs_results') is not None:
        _show_results(st.session_state['docs_results'])

    st.divider()

    # ── Section 3: Admin ─────────────────────────────────
    if st.session_state.get('role') == 'admin':
        st.markdown("""
        <style>
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"] {
            background-color: #dc3545 !important;
            border-color: #dc3545 !important;
            color: white !important;
        }
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"]:hover {
            background-color: #c82333 !important;
            border-color: #bd2130 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        @st.dialog("데이터 초기화 확인")
        def open_delete_modal():
            st.write("이 작업은 되돌릴 수 없으며, 저장된 모든 가계부 내역과 자산 정보가 영구적으로 삭제됩니다. (테이블 구조는 유지)")
            col1, col2 = st.columns([1, 1])

            with col1:
                if st.button("네, 초기화합니다", type="primary", use_container_width=True):
                    try:
                        clear_all_data()
                        for _k in ['upload_results', 'docs_results', 'docs_pending', '_upload_filenames']:
                            st.session_state.pop(_k, None)
                        st.success("초기화 완료! 잠시 후 새로고침 됩니다.")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류: {e}")

            with col2:
                if st.button("아니오, 취소합니다", use_container_width=True):
                    st.rerun()

        if st.button("DB 데이터 초기화", type="primary", use_container_width=True):
            open_delete_modal()

    st.markdown("<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)
