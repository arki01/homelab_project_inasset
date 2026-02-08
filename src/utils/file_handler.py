import pyzipper
import pandas as pd
import io

def process_uploaded_zip(uploaded_file, password, start_date=None, end_date=None):
    """
    업로드된 뱅샐 ZIP 파일을 분석하여 '가계부 내역'과 '자산 현황' DataFrame을 반환합니다.
    
    Returns:
        tx_df (pd.DataFrame): 가계부 지출/수입 내역
        asset_df (pd.DataFrame): 자산 잔액 현황
        error (str): 에러 메시지 (없으면 None)
    """
    tx_df = None
    asset_df = None

    try:
        with pyzipper.AESZipFile(uploaded_file) as zf:
            zf.setpassword(password.encode('utf-8'))
            
            # 엑셀 파일 찾기
            target_files = [f for f in zf.namelist() if f.endswith(('.csv', '.xlsx'))]
            
            if not target_files:
                 return None, None, "ZIP 파일 내에 엑셀/CSV 파일이 없습니다."

            # ★ [수정 포인트 1] 리스트의 첫 번째 파일명(문자열)을 가져옵니다.
            target_filename = target_files[0]

            with zf.open(target_filename) as f:
                # ★ [수정 포인트 2] 파일을 메모리에 한 번 읽어옵니다. 
                # (스트림을 두 번 읽을 때 발생할 수 있는 오류 방지 및 속도 향상)
                file_content = f.read()
                excel_data = pd.ExcelFile(io.BytesIO(file_content))

                # --- [1. 자산 처리 로직 (Sheet 0)] ---
                try:
                    # 첫 번째 시트 읽기
                    raw_asset_df = pd.read_excel(excel_data, sheet_name=0)
                    asset_df = _preprocess_asset_df(raw_asset_df)
                except Exception as e:
                    print(f"자산 시트 읽기 실패: {e}") # 자산 시트가 없을 수도 있으므로 예외처리

                # --- [2. 수입/지출 처리 로직 (Sheet 1)] ---
                try:
                    # 두 번째 시트가 있는지 확인
                    if len(excel_data.sheet_names) > 1:
                        tx_df = pd.read_excel(excel_data, sheet_name=1)
                        
                        if '날짜' in tx_df.columns:
                            tx_df['날짜'] = pd.to_datetime(tx_df['날짜'])
                            
                            # 기간 필터링
                            if start_date and end_date:
                                mask = (tx_df['날짜'].dt.date >= start_date) & (tx_df['날짜'].dt.date <= end_date)
                                tx_df = tx_df.loc[mask].copy()
                    else:
                        return None, None, "엑셀 파일에 가계부 내역 시트(Sheet2)가 없습니다."
                        
                except Exception as e:
                     return None, None, f"가계부 내역 시트 처리 중 오류: {str(e)}"

            return tx_df, asset_df, None # 성공 시
                
    except RuntimeError:
        return None, None, "비밀번호가 틀렸거나 파일 형식이 잘못되었습니다."
    except Exception as e:
        return None, None, f"파일 처리 중 오류 발생: {str(e)}"

def _preprocess_asset_df(df):
    """
    복잡한 뱅크샐러드 자산 시트(좌:자산, 우:부채, 셀병합)를 표준 포맷으로 변환
    """
    try:
        # 디버깅: 전체 시트 구조 확인
        print("\n=== 자산 시트 구조 ===")
        print(f"DataFrame shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print("\n처음 20행:")
        print(df.head(20))
        print("\n")
        
        # 1. 헤더 위치 찾기 ('항목' 이라는 글자가 있는 행 찾기)
        start_row_idx = -1
        for i, row in df.iterrows():
            if str(row[1]).strip() == '3.재무현황':
                start_row_idx = i
                break
        
        if start_row_idx == -1:
            print("자산 시트에서 '3.재무현황' 섹션을 찾을 수 없습니다.")
            return None
        
        print(f"'3.재무현황' 발견 위치: {start_row_idx}")

        # 실제 데이터 헤더('항목', '상품명') 위치 찾기 (시작 행 이후 10줄 이내 검색)
        header_row_idx = -1
        for i in range(start_row_idx, start_row_idx + 10):
            row_values = [str(x).strip() for x in df.iloc[i].values]
            if '항목' in row_values and '상품명' in row_values:
                header_row_idx = i
                break
        
        if header_row_idx == -1:
            print("자산 시트에서 헤더(항목, 상품명)를 찾을 수 없습니다.")
            return None

        print(f"헤더 발견 위치: {header_row_idx}")
        print(f"헤더 행 내용: {df.iloc[header_row_idx].tolist()}")

        # 종료 행 찾기 ('총자산' 텍스트 위치 탐색)
        # 헤더 이후부터 검색 시작
        end_row_idx = len(df)
        for i in range(header_row_idx + 1, len(df)):
            # 해당 행의 모든 셀을 문자열로 합쳐서 확인 (어느 열에 있을지 모르므로)
            row_str = " ".join([str(x) for x in df.iloc[i] if pd.notna(x)])
            if '총자산' in row_str:
                end_row_idx = i
                break

        print(f"데이터 종료 위치: {end_row_idx}")

        # 2. 데이터 영역 슬라이싱 (헤더 다음 행부터 끝까지)
        data_df = df.iloc[header_row_idx + 1 : end_row_idx].copy()

        if data_df.empty:
            print("데이터 영역이 비어있습니다.")
            return None

        print(f"\n데이터 영역 (처음 10행):")
        print(data_df.head(10))
        print(f"데이터 컬럼 수: {len(data_df.columns)}\n")

        # =========================================================
        # 전략 1: 컬럼 이름으로 감지 (존재하면)
        # 컬럼 이름이 없으면 인덱스로 처리
        # =========================================================
        
        # 헤더 행에서 컬럼명 감지
        header_row = df.iloc[header_row_idx]
        print(f"헤더 행 전체: {header_row.tolist()}\n")
        
        # 자산과 부채를 구분하기 위해 중간점 찾기
        # "항목", "상품명", "금액" 이 반복되는 구조에서 첫 번째와 두 번째 "항목" 사이를 기준으로
        item_positions = []
        for i, val in enumerate(header_row):
            if str(val).strip() == '항목':
                item_positions.append(i)
        
        print(f"'항목' 컬럼 위치: {item_positions}")
        
        if len(item_positions) >= 2:
            # 좌측: 첫 번째 항목까지, 우측: 두 번째 항목부터
            left_end = item_positions[1]
            right_start = item_positions[1]
        elif len(item_positions) == 1:
            # 항목이 1개만 있으면 중간점을 기준으로 분할
            left_end = len(header_row) // 2
            right_start = left_end
        else:
            # 항목 컬럼을 찾을 수 없으면 기존 방식
            left_end = min(4, len(data_df.columns))
            right_start = max(5, len(data_df.columns) // 2)
        
        print(f"좌측 범위: 0 ~ {left_end}, 우측 범위: {right_start} ~ {len(data_df.columns)}\n")
        
        # =========================================================
        # [좌측] 자산 데이터 추출
        # =========================================================
        assets = data_df.iloc[:, :left_end].copy()
        
        # 컬럼명 설정 (헤더 행 기반)
        assets.columns = [str(header_row.iloc[i]).strip() if i < len(header_row) else f'col_{i}' 
                         for i in range(len(assets.columns))]
        
        print(f"자산 데이터 컬럼명: {assets.columns.tolist()}")
        print(f"자산 데이터 (처음 5행):\n{assets.head()}\n")
        
        # 컬럼명 정규화 (항목 -> asset_type, 상품명 -> account_name, 금액/잔액 -> amount)
        column_mapping = {}
        for col in assets.columns:
            col_lower = col.lower()
            if '항목' in col_lower:
                column_mapping[col] = 'asset_type'
            elif '상품명' in col_lower or '계좌' in col_lower:
                column_mapping[col] = 'account_name'
            elif '금액' in col_lower or '잔액' in col_lower:
                column_mapping[col] = 'amount'
        
        assets = assets.rename(columns=column_mapping)
        
        # 필요한 컬럼만 남기기
        required_cols = ['asset_type', 'account_name', 'amount']
        existing_cols = [col for col in required_cols if col in assets.columns]
        
        if not existing_cols:
            print("⚠️ 필요한 컬럼 (항목/상품명/금액)을 찾을 수 없습니다.")
            print(f"사용 가능한 컬럼: {assets.columns.tolist()}")
            return None
        
        assets = assets[existing_cols].copy()
        assets['balance_type'] = '자산'
        
        # (자산 전처리)
        if 'asset_type' in assets.columns:
            assets['asset_type'] = assets['asset_type'].ffill()
        
        if 'amount' in assets.columns:
            assets['amount'] = pd.to_numeric(assets['amount'], errors='coerce').fillna(0).astype(int)
        
        print(f"자산 금액 분포 (0이 아닌 것 제외):")
        if 'amount' in assets.columns:
            print(assets[assets['amount'] != 0]['amount'].describe())
        
        # 필터링: 상품명과 금액 중 하나라도 있으면 유지
        if 'account_name' in assets.columns and 'amount' in assets.columns:
            assets = assets[
                (assets['account_name'].notna() & (assets['account_name'].astype(str).str.strip() != '')) | 
                (assets['amount'] != 0)
            ].copy()
        
        # 상품명 채우기
        if 'account_name' in assets.columns and 'asset_type' in assets.columns:
            assets['account_name'] = assets['account_name'].fillna(assets['asset_type'])

        # =========================================================
        # [우측] 부채 데이터 추출  
        # =========================================================
        if right_start < len(data_df.columns):
            liabilities = data_df.iloc[:, right_start:].copy()
            
            # 컬럼명 설정 (헤더 행 기반)
            liabilities.columns = [str(header_row.iloc[i]).strip() if i < len(header_row) else f'col_{i}' 
                                  for i in range(right_start, min(right_start + len(liabilities.columns), len(header_row)))]
            
            # 컬럼명 정규화
            column_mapping = {}
            for col in liabilities.columns:
                col_lower = col.lower()
                if '항목' in col_lower:
                    column_mapping[col] = 'asset_type'
                elif '상품명' in col_lower or '계좌' in col_lower:
                    column_mapping[col] = 'account_name'
                elif '금액' in col_lower or '잔액' in col_lower:
                    column_mapping[col] = 'amount'
            
            liabilities = liabilities.rename(columns=column_mapping)
            
            # 필요한 컬럼만 남기기
            existing_cols = [col for col in ['asset_type', 'account_name', 'amount'] 
                           if col in liabilities.columns]
            
            if existing_cols:
                liabilities = liabilities[existing_cols].copy()
                liabilities['balance_type'] = '부채'
                
                # (부채 전처리)
                if 'asset_type' in liabilities.columns:
                    liabilities['asset_type'] = liabilities['asset_type'].ffill()
                
                if 'amount' in liabilities.columns:
                    liabilities['amount'] = pd.to_numeric(liabilities['amount'], errors='coerce').fillna(0).astype(int)
                
                # 필터링: 상품명이 있고 금액이 0이 아닌 것만
                if 'account_name' in liabilities.columns and 'amount' in liabilities.columns:
                    liabilities = liabilities.dropna(subset=['account_name'])
                    liabilities = liabilities[
                        (liabilities['account_name'].astype(str).str.strip() != '') & 
                        (liabilities['amount'] != 0)
                    ]
                
                print(f"\n부채 데이터 (처음 5행):\n{liabilities.head()}\n")
            else:
                print("⚠️ 우측 부채 데이터에서 필요한 컬럼을 찾을 수 없습니다.")
                liabilities = pd.DataFrame()
        else:
            print("⚠️ 우측 부채 데이터가 없습니다.")
            liabilities = pd.DataFrame()

        # 5. 합치기
        if not liabilities.empty:
            combined_df = pd.concat([assets, liabilities], ignore_index=True)
        else:
            combined_df = assets.copy()
        
        # 최종적으로 빈 데이터프레임 체크
        if combined_df.empty:
            print("자산 데이터 파싱 후 결과가 비어있습니다.")
            return None
        
        # 최종 컬럼 순서
        final_cols = ['balance_type', 'asset_type', 'account_name', 'amount']
        result = combined_df[final_cols]
        
        print(f"\n=== 최종 결과 ===")
        print(f"총 {len(result)}건의 자산 데이터 추출됨")
        print(f"자산: {len(result[result['balance_type'] == '자산'])}건")
        print(f"부채: {len(result[result['balance_type'] == '부채'])}건")
        print(result.head(10))
        
        return result

    except Exception as e:
        print(f"자산 데이터 전처리 중 오류: {e}")
        return None

def format_df_for_display(df):
    display_df = df.copy()
    
    # 날짜 포맷팅 (YYYY-MM-DD)
    if '날짜' in display_df.columns:
        display_df['날짜'] = pd.to_datetime(display_df['날짜']).dt.strftime('%Y-%m-%d')

    # 시간 포맷팅 (HH:MM)
    if '시간' in display_df.columns:
        display_df['시간'] = pd.to_datetime(display_df['시간'], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M:%S')
        display_df['시간'] = display_df['시간'].fillna('-')
    
    return display_df
