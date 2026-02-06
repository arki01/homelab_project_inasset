import sqlite3
import pandas as pd
import os

DB_PATH = "data/money_vault.db"

# --- DB 함수 (보내주신 컬럼 기준) ---
def save_to_db(df):
    conn = sqlite3.connect(DB_PATH)
    try:
        # 컬럼 공백 제거
        df.columns = [c.strip() for c in df.columns]
        df.to_sql('temp_ledger', conn, if_exists='replace', index=False)
        
        # 실제 테이블 생성 (이미지 컬럼 기준)
        conn.execute("CREATE TABLE IF NOT EXISTS ledger AS SELECT * FROM temp_ledger WHERE 1=0")
        
        # [중복 제거 로직] 날짜, 시간, 내용, 금액 4가지를 대조
        query = """
        INSERT INTO ledger 
        SELECT * FROM temp_ledger 
        WHERE NOT EXISTS (
            SELECT 1 FROM ledger 
            WHERE ledger."날짜" = temp_ledger."날짜" 
              AND ledger."시간" = temp_ledger."시간" 
              AND ledger."내용" = temp_ledger."내용" 
              AND ledger."금액" = temp_ledger."금액"
        );
        """
        conn.execute(query)
        conn.commit()
    except Exception as e:
        st.error(f"DB 저장 오류: {e}")
    finally:
        conn.close()

def load_from_db():
    if not os.path.exists(DB_PATH): return None
    conn = sqlite3.connect(DB_PATH)
    try:
        # 날짜와 시간 순으로 정렬해서 가져오기
        df = pd.read_sql("SELECT * FROM ledger ORDER BY 날짜 DESC, 시간 DESC", conn)
        return df
    except: return None
    finally: conn.close()

# def get_expense_summary():
#     db_path = "data/money_vault.db"
#     conn = sqlite3.connect(DB_PATH)
    
#     # 1. 쿼리 단계에서 날짜와 시간을 포맷팅합니다.
#     # strftime을 써서 초 단위(.000000)를 날려버립니다.
#     query = """
#     SELECT 
#         strftime('%Y-%m-%d', 날짜) as 날짜, 
#         strftime('%H:%M', 시간) as 시간, 
#         대분류, 내용, 금액 
#     FROM ledger 
#     ORDER BY 날짜 DESC, 시간 DESC 
#     LIMIT 30
#     """
#     df = pd.read_sql_query(query, conn)
    
#     # 2. 전체 통계 요약 (GPT가 전체 흐름을 알게 함)
#     # 이번 달 총 지출액 같은 정보를 추가로 뽑습니다.
#     stat_query = "SELECT SUM(금액) as 총액 FROM ledger WHERE 날짜 >= date('now', 'start of month')"
#     total_month = pd.read_sql_query(stat_query, conn).iloc[0]['총액']
    
#     conn.close()
    
#     # GPT에게 줄 텍스트 구성
#     summary = f"--- 이번 달 총 지출: {total_month:,.0f}원 ---\n"
#     summary += df.to_string(index=False)
#     return summary

def get_ai_context():
    conn = sqlite3.connect("data/money_vault.db")
    
    # 카테고리별 합계 요약 (GPT가 전체 지출 구조를 파악하게 함)
    cat_query = """
    SELECT 대분류, SUM(금액) as 합계, COUNT(*) as 건수
    FROM ledger
    GROUP BY 대분류
    ORDER BY 합계 DESC
    """
    cat_df = pd.read_sql_query(cat_query, conn)
    
    # 최근 중요 내역
    recent_query = "SELECT 날짜, 내용, 금액 FROM ledger ORDER BY 날짜 DESC LIMIT 15"
    recent_df = pd.read_sql_query(recent_query, conn)
    
    conn.close()
    
    context = "[카테고리별 통계]\n" + cat_df.to_string(index=False)
    context += "\n\n[최근 상세 내역]\n" + recent_df.to_string(index=False)
    return context