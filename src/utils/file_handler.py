import pyzipper
import pandas as pd
import io

def process_uploaded_zip(uploaded_file, password):
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
                if target.endswith('.csv'):
                    df = pd.read_csv(f)
                else:
                    df = pd.read_excel(f, sheet_name=1) # 뱅샐 표준 시트 위치
                
                # 금액 숫자 변환
                if '금액' in df.columns:
                    df['금액'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0)
                
                return df, None # 성공 시 df 반환, 에러 메시지 None
                
    except RuntimeError:
        return None, "비밀번호가 틀렸거나 파일 형식이 잘못되었습니다."
    except Exception as e:
        return None, f"파일 처리 중 오류 발생: {str(e)}"

def format_df_for_display(df):
    """
    화면 출력용으로 데이터를 깔끔하게 다듬습니다. (원본 데이터 변경 X)
    """
    display_df = df.copy()
    
    # 날짜 포맷팅 (YYYY-MM-DD)
    if '날짜' in display_df.columns:
        display_df['날짜'] = pd.to_datetime(display_df['날짜']).dt.strftime('%Y-%m-%d')
    
    # 시간 포맷팅 (HH:MM)
    if '시간' in display_df.columns:
        display_df['시간'] = pd.to_datetime(display_df['시간'], format='%H:%M:%S.%f', errors='coerce').dt.strftime('%H:%M')
        display_df['시간'] = display_df['시간'].fillna('-')
        
    return display_df