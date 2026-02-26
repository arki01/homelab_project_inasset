import sqlite3
import pandas as pd
import os
import re

# DB 경로 및 파일명 변경 (InAsset의 아이덴티티 반영)
DB_PATH = "data/inasset_v1.db"

def _init_db():
    directory = os.path.dirname(DB_PATH)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # 1. 뱅크샐러드 엑셀 구조를 반영한 신규 테이블 스키마
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,          -- 날짜는 필수 (YYYY-MM-DD)
                time TEXT,          -- 시간 (HH:MM)
                tx_type TEXT,       -- 타입 (수입/지출)
                category_1 TEXT,    -- 대분류
                category_2 TEXT,    -- 소분류
                refined_category_1 TEXT, -- 표준화 대분류 (분석용)
                refined_category_2 TEXT, -- 표준화 소분류 (분석용)
                description TEXT,   -- 내용
                amount INTEGER,     -- 금액
                currency TEXT,      -- 화폐
                source TEXT,        -- 결제수단
                memo TEXT,          -- 메모
                owner TEXT,         -- 소유자 (남편/아내/공동)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. 자산 스냅샷 테이블 (Asset Snapshots)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT, 
                balance_type TEXT,  -- 구분 (자산/부채)
                asset_type TEXT,    -- 항목 (예: 자유입출금 자산, 신탁 자산, 저축성 자산 등)
                account_name TEXT,  -- 상품명 (예: 신한 주거래 우대통장)
                amount INTEGER,     -- 금액
                owner TEXT,         
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_connection():
    """데이터베이스 연결 객체를 반환합니다."""
    # DB 파일이 존재하는지 체크 (선택 사항)
    if not os.path.exists(DB_PATH):
        # 만약 data 폴더가 없다면 생성
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    return conn

def save_transactions(df, owner=None, filename="unknown.xlsx"):
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
    rename_df['source_file'] = filename
    rename_df['date'] = pd.to_datetime(rename_df['date']).dt.strftime('%Y-%m-%d')
    
    # 시간은 그대로 유지 (이미 HH:mm:ss 형식)
    if 'time' in rename_df.columns:
        rename_df['time'] = rename_df['time'].astype(str).str.strip()
    else:
        rename_df['time'] = '00:00:00'

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

    return len(final_df)    

def init_category_rules():
    """
    고정비/변동비 규칙 테이블을 생성하고 데이터를 정의합니다.
    """
    # DB 경로가 올바른지 확인 (현재 db_handler.py 위치 기준 상대 경로 보정)
    # 실행 위치에 따라 경로 에러가 날 수 있어 절대 경로로 보정하는 것이 안전합니다.
    base_dir = os.path.dirname(os.path.abspath(__file__)) # utils 폴더
    db_path_fixed = os.path.join(base_dir, '../../data/inasset_v1.db')
    
    with sqlite3.connect(db_path_fixed) as conn:
        cursor = conn.cursor()

        # 1. 규칙 테이블 생성
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_rules (
            category_name TEXT PRIMARY KEY, 
            expense_type TEXT
        )
        ''')

        # 2. 분류 규칙 정의 (엑셀 기준)
        rules = [
            # [고정 지출]
            ('고정비', '고정 지출'), ('주거비', '고정 지출'), 
            ('금융', '고정 지출'), ('보험', '고정 지출'),
            # [변동 지출]
            ('식비', '변동 지출'), ('생활비', '변동 지출'),
            ('활동비', '변동 지출'), ('친목비', '변동 지출'),
            ('꾸밈비', '변동 지출'), ('차량비', '변동 지출'),
            ('교통비', '변동 지출'), ('여행비', '변동 지출'),
            ('의료비', '변동 지출'), ('기여비', '변동 지출'),
            ('양육비', '변동 지출'), ('예비비', '변동 지출'),
            ('미분류', '변동 지출'),
        ]

        # 규칙 업데이트 (이미 있으면 무시하거나 덮어쓰기)
        cursor.executemany('INSERT OR REPLACE INTO category_rules VALUES (?, ?)', rules)
        conn.commit()

def get_analyzed_transactions():
    """
    transactions 테이블과 category_rules를 조인하여 
    고정비/변동비가 마킹된 데이터를 반환합니다.
    """
    # 경로 보정
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path_fixed = os.path.join(base_dir, '../../data/inasset_v1.db')

    if not os.path.exists(db_path_fixed):
        return pd.DataFrame() # 빈 데이터프레임 반환

    with sqlite3.connect(db_path_fixed) as conn:
        # JOIN 쿼리: 원본 transactions 테이블은 건드리지 않고 읽어올 때만 합칩니다.
        # category_1 (대분류)을 기준으로 규칙을 찾습니다.
        query = '''
        SELECT 
            T.date,
            T.time,
            T.tx_type,
            T.category_1,
            T.description,
            T.amount,
            T.memo,
            T.owner,
            T.source,
            IFNULL(R.expense_type, '미분류') as expense_type
        FROM transactions T
        LEFT JOIN category_rules R ON T.category_1 = R.category_name
        WHERE T.tx_type != '이체'
        ORDER BY T.date DESC, T.time DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        return df

def save_asset_snapshot(df, owner=None, snapshot_date=None):
    """
    추출된 자산 데이터를 asset_snapshots 테이블에 저장합니다.
    
    Args:
        df: 자산 데이터프레임 (owner 컬럼 포함 권장)
        owner: 소유자 (df에 owner가 없을 때만 사용)
        snapshot_date: 스냅샷 날짜 (YYYY-MM-DD HH:MM:SS 형식)
    """
    _init_db() # 테이블이 없으면 생성
    
    df = df.copy()
    
    # 1. 데이터프레임에 공통 정보(소유자, 날짜) 추가
    # df에 owner가 없을 때만 파라미터 값 사용
    if 'owner' not in df.columns or df['owner'].isna().all():
        df['owner'] = owner
    
    # snapshot_date는 항상 파라미터로부터 사용 (최신 날짜로)
    if snapshot_date:
        df['snapshot_date'] = snapshot_date
    
    # 2. DB 저장
    with sqlite3.connect(DB_PATH) as conn:
        # 데이터가 많지 않으므로 append 방식으로 계속 누적 (스냅샷이므로)
        df.to_sql('asset_snapshots', conn, if_exists='append', index=False)
        conn.commit()
    
    return len(df)

def get_latest_assets():
    """
    각 소유자별 가장 최근 날짜의 자산 스냅샷 정보를 가져옵니다.
    """
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. asset_snapshots 테이블이 있는지 먼저 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_snapshots'")
    if not cursor.fetchone():
        conn.close()
        return pd.DataFrame() # 테이블이 없으면 빈 DF 반환

    # 2. 소유자별 가장 최근 스냅샷 날짜 찾기
    query_latest = """
    SELECT owner, MAX(snapshot_date) as latest_date
    FROM asset_snapshots
    GROUP BY owner
    """
    latest_dates = pd.read_sql_query(query_latest, conn)
    
    if latest_dates.empty:
        conn.close()
        return pd.DataFrame()

    # 3. 각 소유자의 최신 날짜 데이터 모두 조회
    placeholders = ','.join(['?' for _ in latest_dates])
    owners = latest_dates['owner'].tolist()
    dates = latest_dates['latest_date'].tolist()
    
    # owner와 date 쌍으로 조회
    query = """
    SELECT 
        owner, 
        balance_type, 
        asset_type, 
        account_name, 
        amount,
        snapshot_date
    FROM asset_snapshots 
    WHERE (owner, snapshot_date) IN (
        SELECT owner, snapshot_date FROM (
            SELECT owner, snapshot_date,
                   ROW_NUMBER() OVER (PARTITION BY owner ORDER BY snapshot_date DESC) as rn
            FROM asset_snapshots
        )
        WHERE rn = 1
    )
    ORDER BY owner DESC, balance_type DESC, amount DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# utils/db_handler.py 에 추가

def get_previous_assets(target_date, owner):
    """
    특정 소유자의 데이터 중 target_date와 가장 가까운 snapshot_date의 데이터를 가져옵니다.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. 해당 소유자의 snapshot_date들 중 target_date와 차이(절대값)가 가장 작은 날짜 1개를 찾습니다.
        # strftime('%s', ...)는 날짜를 초 단위 타임스탬프로 변환하여 계산 가능하게 합니다.
        find_date_query = f"""
            SELECT snapshot_date 
            FROM asset_snapshots 
            WHERE owner = '{owner}'
            ORDER BY ABS(strftime('%s', snapshot_date) - strftime('%s', '{target_date}')) ASC
            LIMIT 1
        """
        closest_date_df = pd.read_sql(find_date_query, conn)
        
        if closest_date_df.empty:
            return pd.DataFrame()
            
        closest_date = closest_date_df.iloc[0]['snapshot_date']
        
        # 2. 찾은 '가장 근사한 날짜'에 해당하는 그 소유자의 모든 자산 내역을 가져옵니다.
        query = f"""
            SELECT * FROM asset_snapshots  
            WHERE owner = '{owner}' 
              AND snapshot_date = '{closest_date}'
        """
        df = pd.read_sql(query, conn)
        return df
        
    finally:
        conn.close()

def get_chatbot_context(limit_recent=20, period_months=3):
    """
    챗봇에게 전달할 금융 데이터 컨텍스트를 생성합니다.
    
    Args:
        limit_recent: 최근 거래 내역 개수 (기본 20건)
        period_months: 통계 집계 기간 (기본 3개월)
    
    Returns:
        str: 포맷팅된 컨텍스트 문자열
    """
    if not os.path.exists(DB_PATH):
        return "아직 데이터가 없습니다. 먼저 데이터를 업로드해주세요."
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 1. 기간 계산 (최근 N개월)
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_months * 30)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            # 2. 기간별 수입/지출 요약
            summary_query = f"""
            SELECT
                tx_type,
                owner,
                SUM(amount) as total
            FROM transactions
            WHERE date >= '{start_date_str}'
            GROUP BY tx_type, owner
            ORDER BY tx_type DESC, owner
            """
            summary_df = pd.read_sql_query(summary_query, conn)
            
            # 3. 카테고리별 지출 통계 (지출만, 상위 5개)
            category_query = f"""
            SELECT
                category_1,
                SUM(amount) as total,
                COUNT(*) as count
            FROM transactions
            WHERE date >= '{start_date_str}' AND tx_type = '지출'
            GROUP BY category_1
            ORDER BY total DESC
            LIMIT 5
            """
            category_df = pd.read_sql_query(category_query, conn)
            
            # 4. 고정비/변동비 분석
            expense_type_query = f"""
            SELECT
                IFNULL(R.expense_type, '미분류') as expense_type,
                SUM(T.amount) as total
            FROM transactions T
            LEFT JOIN category_rules R ON T.category_1 = R.category_name
            WHERE T.date >= '{start_date_str}' AND T.tx_type = '지출'
            GROUP BY expense_type
            """
            expense_type_df = pd.read_sql_query(expense_type_query, conn)
            
            # 5. 최근 거래 내역
            recent_query = f"""
            SELECT
                date,
                category_1,
                description,
                amount,
                owner,
                tx_type
            FROM transactions
            ORDER BY date DESC, time DESC
            LIMIT {limit_recent}
            """
            recent_df = pd.read_sql_query(recent_query, conn)
            
            # 6. 컨텍스트 문자열 생성
            context = f"=== 최근 {period_months}개월 재무 현황 ===\n\n"
            
            # 수입/지출 요약
            if not summary_df.empty:
                total_income = summary_df[summary_df['tx_type'] == '수입']['total'].sum()
                total_expense = summary_df[summary_df['tx_type'] == '지출']['total'].sum()
                net_change = total_income - total_expense
                
                context += f"• 총 수입: {total_income:,}원\n"
                context += f"• 총 지출: {total_expense:,}원\n"
                context += f"• 순자산 변화: {net_change:+,}원\n\n"
                
                # 소유자별 세부 내역
                context += "소유자별 내역:\n"
                for _, row in summary_df.iterrows():
                    context += f"  - {row['owner']} {row['tx_type']}: {row['total']:,}원\n"
                context += "\n"
            
            # 카테고리별 지출 TOP 5
            if not category_df.empty:
                context += "=== 카테고리별 지출 TOP 5 ===\n"
                total_expense = category_df['total'].sum()
                for idx, row in category_df.iterrows():
                    percentage = (row['total'] / total_expense * 100) if total_expense > 0 else 0
                    context += f"{idx+1}. {row['category_1']}: {row['total']:,}원 ({percentage:.1f}%, {row['count']}건)\n"
                context += "\n"
            
            # 고정비/변동비 분석
            if not expense_type_df.empty:
                context += "=== 고정비 vs 변동비 ===\n"
                total = expense_type_df['total'].sum()
                for _, row in expense_type_df.iterrows():
                    percentage = (row['total'] / total * 100) if total > 0 else 0
                    context += f"• {row['expense_type']}: {row['total']:,}원 ({percentage:.1f}%)\n"
                context += "\n"
            
            # 최근 거래 내역
            if not recent_df.empty:
                context += f"=== 최근 거래 내역 ({limit_recent}건) ===\n"
                for _, row in recent_df.iterrows():
                    context += f"[{row['date']}] {row['tx_type']} | {row['category_1']} | {row['description']} | {row['amount']:,}원 | {row['owner']}\n"
            
            return context
            
    except Exception as e:
        return f"데이터 조회 중 오류가 발생했습니다: {str(e)}"

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