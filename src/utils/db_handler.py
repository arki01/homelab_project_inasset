import sqlite3
import pandas as pd
import os

# 설정: 경로는 절대경로로 잡거나 환경변수로 빼는 것이 좋으나, 현재는 상대경로 유지
DB_PATH = "data/money_vault.db"

def _init_check():
    """내부 함수: DB 폴더가 존재하는지 확인하고 없으면 생성"""
    directory = os.path.dirname(DB_PATH)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def save_to_db(df):
    """
    데이터프레임을 저장하고 중복을 제거합니다.
    에러 발생 시 UI에 출력하지 않고, 호출한 곳으로 에러를 던집니다(Raise).
    """
    _init_check()
    
    # DB 연결 (with 구문을 쓰면 자동으로 close 됩니다)
    with sqlite3.connect(DB_PATH) as conn:
        try:
            # 1. 컬럼 공백 제거 (방어적 코딩)
            df.columns = [c.strip() for c in df.columns]
            
            # 2. 임시 테이블에 일단 몽땅 저장
            df.to_sql('temp_ledger', conn, if_exists='replace', index=False)
            
            # 3. 실제 테이블이 없으면 생성 (스키마 복사)
            conn.execute("CREATE TABLE IF NOT EXISTS ledger AS SELECT * FROM temp_ledger WHERE 1=0")
            
            # 4. 중복 제거 INSERT (핵심 로직)
            # 날짜+시간+내용+금액+대분류가 모두 같으면 중복으로 간주
            query = """
            INSERT INTO ledger 
            SELECT * FROM temp_ledger 
            WHERE NOT EXISTS (
                SELECT 1 FROM ledger 
                WHERE ledger."날짜" = temp_ledger."날짜" 
                  AND ledger."시간" = temp_ledger."시간" 
                  AND ledger."내용" = temp_ledger."내용" 
                  AND ledger."금액" = temp_ledger."금액"
                  AND ledger."대분류" = temp_ledger."대분류"
            );
            """
            conn.execute(query)
            conn.commit()
            
        except Exception as e:
            # 여기서 st.error를 쓰지 않고 에러를 상위로 던집니다.
            raise RuntimeError(f"DB 저장 중 문제 발생: {str(e)}")

def load_from_db():
    if not os.path.exists(DB_PATH):
        return None
    
    with sqlite3.connect(DB_PATH) as conn:
        try:
            query = "SELECT * FROM ledger ORDER BY 날짜 DESC, 시간 DESC"
            df = pd.read_sql(query, conn)
            return df
        except Exception:
            return None

def get_ai_context():
    """
    GPT에게 전달할 통계 및 최근 내역 요약본 생성
    """
    if not os.path.exists(DB_PATH):
        return "아직 데이터가 없습니다."

    with sqlite3.connect(DB_PATH) as conn:
        try:
            # 1. 카테고리별 지출 합계 (수입은 제외하거나, 양수/음수 표기 필요)
            # 보통 지출 분석이 목적이므로 금액 < 0 인 것만 분석하는 경우도 많음
            # 여기서는 전체 합계를 구하되, 보기 좋게 정렬
            cat_query = """
            SELECT 대분류, SUM(금액) as 합계
            FROM ledger
            GROUP BY 대분류
            ORDER BY 합계 ASC
            """
            cat_df = pd.read_sql_query(cat_query, conn)
            
            # 2. 최근 10건의 상세 내역 (토큰 절약을 위해 15 -> 10건으로 축소 추천)
            recent_query = """
            SELECT 날짜, 대분류, 내용, 금액 
            FROM ledger 
            ORDER BY 날짜 DESC, 시간 DESC 
            LIMIT 10
            """
            recent_df = pd.read_sql_query(recent_query, conn)
            
            # 문자열로 변환
            context = "[카테고리별 누적 합계 (단위:원)]\n" + cat_df.to_string(index=False)
            context += "\n\n[최근 소비 내역 10건]\n" + recent_df.to_string(index=False)
            
            return context
            
        except Exception as e:
            return f"데이터 조회 중 오류 발생: {str(e)}"