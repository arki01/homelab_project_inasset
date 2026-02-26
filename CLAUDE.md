# CLAUDE.md — InAsset

InAsset은 부부(형준/윤희)의 가계부 앱이다. BankSalad Excel 내보내기를 SQLite에 저장하고 Streamlit으로 시각화하며, GPT-4o 챗봇으로 자연어 질의를 지원한다.

## 앱 실행

```bash
# Docker (권장) — http://localhost:3101
docker-compose up -d

# 로컬 직접 실행
pip install -r requirements.txt
streamlit run src/app.py
```

## 아키텍처

```
BankSalad ZIP 업로드
  → file_handler.py  (ZIP 해제, Excel 파싱)
  → db_handler.py    (SQLite upsert)
  → pages/           (Streamlit 화면)
  → ai_agent.py      (GPT-4o 챗봇)
```

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `src/app.py` | 진입점, 사이드바 라우팅, DB 초기화 |
| `src/pages/transactions.py` | 💰 수입/지출 현황 |
| `src/pages/assets.py` | 🏦 자산 현황 |
| `src/pages/chatbot.py` | 🤖 AI 챗봇 |
| `src/pages/upload.py` | 📂 BankSalad ZIP 업로드 |
| `src/pages/analysis.py` | 📊 분석 리포트 (stub) |
| `src/utils/db_handler.py` | 모든 SQLite 작업 |
| `src/utils/file_handler.py` | ZIP/Excel 파싱 |
| `src/utils/ai_agent.py` | OpenAI API 래퍼 |

## 데이터베이스 스키마

**DB 경로:** `data/inasset_v1.db` (gitignore 됨)

```sql
-- 거래 내역
transactions (
  id, date TEXT, time TEXT,
  tx_type TEXT,           -- 수입/지출/이체
  category_1 TEXT,        -- 대분류
  category_2 TEXT,        -- 소분류
  description TEXT, amount INTEGER, currency TEXT,
  source TEXT,            -- 결제수단
  memo TEXT, owner TEXT,  -- 형준/윤희/공동
  created_at TIMESTAMP
)

-- 자산 스냅샷
asset_snapshots (
  id, snapshot_date TEXT,
  balance_type TEXT,      -- 자산/부채
  asset_type TEXT,        -- 항목 (현금 자산, 투자성 자산 등)
  account_name TEXT, amount INTEGER,
  owner TEXT, created_at TIMESTAMP
)

-- 카테고리별 고정/변동 분류
category_rules (
  category_name TEXT PRIMARY KEY,
  expense_type TEXT       -- 고정 지출/변동 지출
)
```

## 주요 함수

### db_handler.py
- `_init_db()` — 앱 시작 시 테이블 생성
- `init_category_rules()` — 고정/변동 분류 룰 초기화
- `save_transactions(df, owner)` — 해당 기간 삭제 후 재삽입 (UPSERT)
- `save_asset_snapshot(df, owner)` — 자산 스냅샷 추가 (APPEND only)
- `get_analyzed_transactions()` — transactions LEFT JOIN category_rules
- `get_latest_assets()` — 소유자별 최신 스냅샷
- `get_previous_assets(target_date, owner)` — 30일 전 스냅샷 (delta 계산용)
- `get_chatbot_context(limit_recent, period_months)` — GPT 컨텍스트용 요약 문자열

### file_handler.py
- `process_uploaded_zip(uploaded_file, password, start_date, end_date)` — ZIP 해제 + Excel 파싱, (tx_df, asset_df, error) 반환
- `_preprocess_asset_df(df)` — BankSalad Sheet 0의 복잡한 병합셀 처리

### ai_agent.py
- `ask_gpt_finance(client, user_message, db_context, chat_history)` — GPT-4o 호출, DB 컨텍스트 주입

## 환경변수

`.env` 파일 (gitignore됨):
```
OPENAI_API_KEY=sk-...
```

## 코드 컨벤션

- **언어**: UI·주석 모두 한국어
- **금액**: INTEGER (원 단위), 부채는 음수
- **날짜**: TEXT "YYYY-MM-DD", 시간 TEXT "HH:MM"
- **소유자**: 형준 / 윤희 / 공동
- **페이지 구조**: 각 페이지 파일에 `render()` 함수 하나
- **DB 연결**: try/finally로 항상 conn.close()
- **이체(이체) 제외**: `get_analyzed_transactions()`에서 필터링됨

## Docker

```yaml
image: python:3.11-slim
ports: "3101:8501"
env_file: .env
TZ: Asia/Seoul
restart: always
```

볼륨 마운트(`.:/app`)로 코드 수정이 즉시 반영되지 않음 — 컨테이너 재시작 필요.

## 현재 상태

- ✅ 완성: 업로드, 거래내역, 자산현황, AI 챗봇
- 🟡 미완성: 분석 리포트 (`analysis.py`는 stub)
- ❌ 미구현: 사용자 인증, 예측 모델, 차트 시각화 내보내기

## 알려진 이슈

- `get_previous_assets()`에서 f-string SQL 사용 → 파라미터 바인딩 권장
- `upload.py`에 ZIP 비밀번호 하드코딩 (형준=0979, 윤희=1223)
- `file_handler.py`에 debug print문 다수 존재
- `langchain-community`, `plotly`는 requirements에 있으나 미사용 (Phase 3 대비)
