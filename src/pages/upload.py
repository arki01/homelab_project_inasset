import streamlit as st
import pandas as pd
import os
import datetime
import time
from utils.db_handler import DB_PATH, save_transactions, save_asset_snapshot
from utils.file_handler import process_uploaded_zip, format_df_for_display

def render():
    st.header("📥 가계부 업로드")
    st.caption("우리 부부의 가계부 기록을 통합하는 첫 단계입니다.")

    with st.container(border=True):
        uploaded_file = st.file_uploader("뱅크샐러드 ZIP 파일을 업로드하세요", type=None)
        extracted_owner = None
        default_password = None
          
        # 파일명에서 소유자 추출, 소유자별 기본 비밀번호 설정
        if uploaded_file:
            filename = uploaded_file.name  # 예: '조윤희님_2025-01-31~2026-01-31.zip'

            if '님_' in filename:
                full_name = filename.split('님_')[0]  # '조윤희님_...' -> '조윤희'
                # 성을 제외한 이름만 추출 (마지막 1글자 = 이름)
                extracted_owner = full_name[1:3] if len(full_name) > 0 else None

            default_password = ""
            if extracted_owner == "형준": 
                default_password = "0979"
            elif extracted_owner == "윤희": 
                default_password = "1223"
        
        password = st.text_input("ZIP 파일 비밀번호", type="password", value=default_password)

    if uploaded_file and password:
        # 파일명에서 소유자 추출
        filename = uploaded_file.name  # 예: '조윤희님_2025-01-31~2026-01-31.zip'
        extracted_owner = None
        
        if '님_' in filename:
            full_name = filename.split('님_')[0]  # '조윤희님_...' -> '조윤희'
            # 성을 제외한 이름만 추출 (마지막 1글자 = 이름)
            extracted_owner = full_name[1:3] if len(full_name) > 0 else None
        
        with st.container(border=True):
            # 추출된 소유자가 있으면 선택값으로 설정, 없으면 기본값
            owner_options = ["형준", "윤희"]
            default_index = 0
            
            if extracted_owner and extracted_owner in owner_options:
                default_index = owner_options.index(extracted_owner)
            elif extracted_owner:
                # 파일명의 이름이 선택지에 없으면 경고
                st.warning(f"⚠️ 파일명의 '{extracted_owner}'님이 선택지에 없습니다. 수동으로 선택해주세요.")
            
            owner = st.selectbox(
                "데이터 소유자 선택", 
                owner_options,
                index=default_index,
                help="파일명에서 자동으로 감지되었습니다. 필요시 수정하세요."
            )

            upload_mode = st.radio(
                "업로드 기간 설정",
                ["전체 기간", "특정 기간 (기본값: 현재 ~ 1개월 전)"],
                index=0, horizontal=True,
                help="파일 전체를 올릴지, 최근 내역만 골라 올릴지 선택하세요."
            )
            
            is_manual = (upload_mode == "특정 기간 (기본값: 현재 ~ 1개월 전)")
            today = datetime.date.today()
            one_month_ago = today - datetime.timedelta(days=30)
            
            upload_period = st.date_input(
                "",
                value=(one_month_ago, today),
                disabled=not is_manual,
                help="기간 업로드 모드에서만 활성화됩니다.")

            if st.button("파일 분석 시작", use_container_width=True):
                s_date, e_date = (None, None)
                if upload_mode == "특정 기간 (기본값: 현재 ~ 1개월 전)" and len(upload_period) == 2:
                    s_date, e_date = upload_period

                tx_df, asset_df, error = process_uploaded_zip(uploaded_file, password, start_date=s_date, end_date=e_date)

                if error:
                    st.error(f"❌ {error}")
                elif tx_df is None or tx_df.empty:
                    st.warning("⚠️ 해당 기간에 일치하는 데이터가 없습니다.")
                else:
                    st.session_state['temp_df'] = tx_df
                    st.session_state['temp_asset_df'] = asset_df
                    st.session_state['analysis_owner'] = owner
                    st.session_state['show_preview'] = True
                    st.rerun()

        # 분석 완료 후 미리보기 표시 (버튼 리런과 상관없이 유지)
        if st.session_state.get('show_preview', False):
            st.success(f"✅ {st.session_state.get('analysis_owner')}님의 가계부 정보를 성공적으로 불러왔습니다.\n- 자산 정보: {len(st.session_state.get('temp_asset_df', pd.DataFrame()))}건\n- 수입/지출 내역: {len(st.session_state['temp_df'])}건")
            
            if st.session_state.get('temp_asset_df') is not None and not st.session_state['temp_asset_df'].empty:
                with st.expander("📊 자산 내역 미리보기", expanded=True):
                    st.dataframe(st.session_state['temp_asset_df'], use_container_width=True)
                    st.markdown(
                        f"<div style='text-align: left; color: gray; font-size: 1rem; margin-top: -20px;'>"
                        f"총 {len(st.session_state['temp_asset_df']):,}건"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
            else:
                st.warning("⚠️ 자산 데이터를 찾을 수 없습니다.")

            with st.expander("💰 수입/지출 내역 미리보기", expanded=True):
                display_df = format_df_for_display(st.session_state['temp_df'])
                st.dataframe(display_df, use_container_width=True)
                st.markdown(
                    f"<div style='text-align: left; color: gray; font-size: 1rem; margin-top: -20px;'>"
                    f"총 {len(display_df):,}건"
                    f"</div>", 
                    unsafe_allow_html=True
                )

            if st.button(f"{owner}님 명의로 저장", type="secondary", use_container_width=True):
                try:
                    filename = st.session_state.get('uploaded_filename', 'unknown.zip')
                    owner = st.session_state.get('analysis_owner', '사용자')
                    
                    tx_count = save_transactions(
                        st.session_state['temp_df'], 
                        owner=owner, 
                        filename=filename
                    )
                    
                    asset_count = 0
                    if st.session_state.get('temp_asset_df') is not None and not st.session_state['temp_asset_df'].empty:
                        temp_asset = st.session_state['temp_asset_df']
                        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        asset_count = save_asset_snapshot(
                            temp_asset,
                            owner=owner,
                            snapshot_date=now_str
                        )

                    if tx_count > 0 or asset_count > 0:
                        min_d = st.session_state['temp_df']['날짜'].min().strftime('%Y-%m-%d')
                        max_d = st.session_state['temp_df']['날짜'].max().strftime('%Y-%m-%d')

                        st.balloons()
                        st.success(f"✅ {owner}님의 가계부 내역 {tx_count}건과 자산 정보 {asset_count}건이 저장되었습니다.\n(기간: {min_d} ~ {max_d})")
                        
                        # 풍선 애니메이션 완료 대기
                        time.sleep(5)
                        
                        # 세션 상태 초기화
                        st.session_state['show_preview'] = False
                        if 'temp_df' in st.session_state: 
                            del st.session_state['temp_df']
                        if 'temp_asset_df' in st.session_state: 
                            del st.session_state['temp_asset_df']
                        if 'analysis_owner' in st.session_state:
                            del st.session_state['analysis_owner']
                        
                        st.rerun()
                    else:
                        st.warning("⚠️ 저장된 데이터가 0건입니다.")

                except Exception as e:
                    st.error(f"❌ 저장 중 오류가 발생했습니다: {e}")

    st.divider()

    @st.dialog("DB 삭제 확인")
    def open_delete_modal():
        st.write("이 작업은 되돌릴 수 없으며, 저장된 모든 가계부 내역과 자산 정보가 영구적으로 사라집니다.")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("네, 삭제합니다", type="primary", use_container_width=True):
                if os.path.exists(DB_PATH):
                    try:
                        os.remove(DB_PATH)
                        st.success("삭제 완료! 잠시 후 새로고침 됩니다.")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류: {e}")
                else:
                    st.warning("삭제할 데이터베이스가 없습니다.")
                    time.sleep(1)
                    st.rerun()

        with col2:
            if st.button("아니오, 취소합니다", use_container_width=True):
                st.rerun()

    if st.button("DB 전체 삭제", type="primary", use_container_width=True):
        open_delete_modal()
        
    st.markdown("<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)
