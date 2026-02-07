import sqlite3
import pandas as pd
import os

# DB 경로 및 파일명 변경 (InAsset의 아이덴티티 반영)
DB_PATH = "data/inasset_v1.db"

def _init_db():
    directory = os.path.dirname(DB_PATH)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        # 뱅크샐러드 엑셀 구조를 반영한 신규 테이블 스키마
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,          -- 날짜는 필수 (YYYY-MM-DD)
                time TEXT,          -- 시간 (HH:MM)
                tx_type TEXT,       -- 타입 (수입/지출)
                category_1 TEXT,    -- 대분류
                category_2 TEXT,    -- 소분류
                description TEXT,   -- 내용
                amount INTEGER,     -- 금액
                currency TEXT,      -- 화폐
                source TEXT,        -- 결제수단
                memo TEXT,          -- 메모
                owner TEXT,         -- 소유자 (남편/아내/공동)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # # 2. 자산 스냅샷 테이블 (Asset Snapshots)
        # conn.execute("""
        #     CREATE TABLE IF NOT EXISTS asset_snapshots (
        #         id INTEGER PRIMARY KEY AUTOINCREMENT,
        #         base_date TEXT,     -- 기준 일자
        #         asset_type TEXT,    -- 자산 종류 (예적금, 주식, 현금)
        #         asset_name TEXT,    -- 자산명 (신한은행, 삼성전자)
        #         balance INTEGER,    -- 잔액
        #         owner TEXT          -- 소유자
        #     )
        # """)

def save_transactions(df, owner="공동"):
    """
    지정된 기간과 소유자에 해당하는 기존 데이터를 삭제한 후, 새로운 데이터를 저장합니다.
    """
    _init_db()
    
    # 1. 한글 컬럼 -> 영문 컬럼 매핑 사전
    mapping = {
        '날짜': 'date',
        '시간': 'time',
        '타입': 'tx_type',
        '대분류': 'category_1',
        '소분류': 'category_2',
        '내용': 'description',
        '금액': 'amount',
        '화폐': 'currency',
        '결제수단': 'source',
        '메모': 'memo'
    }
    
    rename_df = df.rename(columns=mapping).copy()
    rename_df['owner'] = owner
    rename_df['date'] = pd.to_datetime(rename_df['date']).dt.strftime('%Y-%m-%d')
    rename_df['time'] = pd.to_datetime(rename_df['time'], errors='coerce').dt.strftime('%H:%M')
    rename_df['time'] = rename_df['time'].fillna('00:00')

    # 4. DB에 저장할 최종 컬럼 리스트 정의
    valid_columns = list(mapping.values()) + ['owner']

    # 5. 데이터프레임에 해당 컬럼들이 있는지 확인 후 필터링
    # (혹시라도 매핑되지 않은 컬럼이 있을 경우를 대비해 존재하는 것만 추림)
    final_df = rename_df[[col for col in valid_columns if col in rename_df.columns]]

    # 사용자가 기간을 선택했든 전체를 선택했든, 실제 들어가는 데이터의 양끝을 찾습니다.
    min_date = final_df['date'].min()
    max_date = final_df['date'].max()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 2. "감지된 기간" 내의 "해당 소유자" 데이터만 삭제
        print(f"Update Range: {min_date} ~ {max_date} (Owner: {owner})") # 디버깅용 로그
        
        delete_query = "DELETE FROM transactions WHERE owner = ? AND date >= ? AND date <= ?"
        cursor.execute(delete_query, (owner, min_date, max_date))
        
        # 3. 새로운 데이터 삽입 (Bulk Insert)
        final_df.to_sql('transactions', conn, if_exists='append', index=False)
        conn.commit()

    
# def save_asset_snapshot(date, asset_data_list):
#     """특정 시점의 전체 자산 상태 저장"""
#     # asset_data_list: [{'asset_name': '신한', 'balance': 5000, 'owner': '남편'}, ...]
#     df = pd.DataFrame(asset_data_list)
#     df['base_date'] = date
#     with sqlite3.connect(DB_PATH) as conn:
#         df.to_sql('asset_snapshots', conn, if_exists='append', index=False)



# ## 변경전 정의 함수
# def load_from_db():
#     if not os.path.exists(DB_PATH):
#         return None
    
#     with sqlite3.connect(DB_PATH) as conn:
#         try:
#             query = "SELECT * FROM ledger ORDER BY 날짜 DESC, 시간 DESC"
#             df = pd.read_sql(query, conn)
#             return df
#         except Exception:
#             return None

# def get_ai_context():
#     """
#     GPT에게 전달할 통계 및 최근 내역 요약본 생성
#     """
#     if not os.path.exists(DB_PATH):
#         return "아직 데이터가 없습니다."

#     with sqlite3.connect(DB_PATH) as conn:
#         try:
#             # 1. 카테고리별 지출 합계 (수입은 제외하거나, 양수/음수 표기 필요)
#             # 보통 지출 분석이 목적이므로 금액 < 0 인 것만 분석하는 경우도 많음
#             # 여기서는 전체 합계를 구하되, 보기 좋게 정렬
#             cat_query = """
#             SELECT 대분류, SUM(금액) as 합계
#             FROM ledger
#             GROUP BY 대분류
#             ORDER BY 합계 ASC
#             """
#             cat_df = pd.read_sql_query(cat_query, conn)
            
#             # 2. 최근 10건의 상세 내역 (토큰 절약을 위해 15 -> 10건으로 축소 추천)
#             recent_query = """
#             SELECT 날짜, 대분류, 내용, 금액 
#             FROM ledger 
#             ORDER BY 날짜 DESC, 시간 DESC 
#             LIMIT 10
#             """
#             recent_df = pd.read_sql_query(recent_query, conn)
            
#             # 문자열로 변환
#             context = "[카테고리별 누적 합계 (단위:원)]\n" + cat_df.to_string(index=False)
#             context += "\n\n[최근 소비 내역 10건]\n" + recent_df.to_string(index=False)
            
#             return context
            
#         except Exception as e:
#             return f"데이터 조회 중 오류 발생: {str(e)}"