import pyzipper
import pandas as pd
import io

def process_uploaded_zip(uploaded_file, password, start_date=None, end_date=None):
    """
    업로드된 뱅샐 ZIP 파일을 메모리상에서 해제하고 DataFrame으로 변환합니다.
    """
    try:
        with pyzipper.AESZipFile(uploaded_file) as zf:
            zf.setpassword(password.encode('utf-8'))
            # CSV 또는 Excel 파일 찾기
            target_files = [f for f in zf.namelist() if f.endswith(('.csv', '.xlsx'))]
            
            if not target_files:
                return None, "ZIP 파일 내에 엑셀/CSV 파일이 없습니다."
                
            target = target_files[0]
            
            with zf.open(target) as f:
                df = pd.read_excel(f, sheet_name=1) # 뱅샐 표준 시트 위치

                # 데이터 정제 및 기간 필터링 로직
                if '날짜' in df.columns:
                    df['날짜'] = pd.to_datetime(df['날짜'])
                    
                    # 시작일과 종료일이 인자로 들어왔을 때만 필터링 수행
                    if start_date and end_date:
                        mask = (df['날짜'].dt.date >= start_date) & (df['날짜'].dt.date <= end_date)
                        df = df.loc[mask].copy()

                return df, None # 성공 시 df 반환, 에러 메시지 None
                
    except RuntimeError:
        return None, "비밀번호가 틀렸거나 파일 형식이 잘못되었습니다."
    except Exception as e:
        return None, f"파일 처리 중 오류 발생: {str(e)}"

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
