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
BankSalad ZIP/Excel 업로드
  → file_handler.py  (ZIP 해제, Excel 파싱, 파일명 날짜 추출)
  → ai_agent.py      (GPT-4o 카테고리 매핑)
  → db_handler.py    (SQLite upsert)
  → pages/           (Streamlit 화면)
  → ai_agent.py      (GPT-4o 챗봇 — Function Calling)
```

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `src/app.py` | 진입점, 사이드바 라우팅, DB 초기화, 인증/승인 |
| `src/pages/budget.py` | 🎯 목표 예산 설정 |
| `src/pages/transactions.py` | 💰 수입/지출 현황 |
| `src/pages/assets.py` | 🏦 자산 현황 |
| `src/pages/chatbot.py` | 🤖 AI 챗봇 |
| `src/pages/data_management.py` | 📂 데이터 관리 — 수동 업로드 / docs/ 자동처리 / 카테고리 정규화 / DB 초기화 |
| `src/pages/analysis.py` | 📊 분석 리포트 — AI 요약 / 이상 지출 / Burn-rate / 자산 트렌드 |
| `src/utils/db_handler.py` | 모든 SQLite 작업 |
| `src/utils/file_handler.py` | ZIP/Excel 파싱, 파일명 메타데이터 추출 |
| `src/utils/ai_agent.py` | OpenAI API 래퍼 (카테고리 매핑 / 분석 요약 / 챗봇) |

## 데이터베이스 스키마

**DB 경로:** `data/inasset_v1.db` (gitignore 됨)

```sql
-- 거래 내역
transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT,                 -- YYYY-MM-DD
  time TEXT,                 -- HH:MM
  tx_type TEXT,              -- 수입 / 지출 / 이체
  category_1 TEXT,           -- 원본 대분류 (뱅크샐러드 그대로)
  category_2 TEXT,           -- 소분류
  refined_category_1 TEXT,   -- 표준화 대분류 (GPT 매핑값, NULL·빈값이면 category_1 사용)
  refined_category_2 TEXT,   -- 미사용
  description TEXT,          -- 내용/상호명
  amount INTEGER,            -- 금액(원). 지출은 음수(-50000), 수입은 양수(+3000000)
  currency TEXT,
  source TEXT,               -- 결제수단
  memo TEXT,
  owner TEXT,                -- 형준 / 윤희 / 공동
  created_at TIMESTAMP
)

-- 자산 스냅샷 (동일 snapshot_date+owner → DELETE+INSERT)
asset_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_date TEXT,        -- YYYY-MM-DD
  balance_type TEXT,         -- 자산 / 부채
  asset_type TEXT,           -- 현금 자산, 투자성 자산 등
  account_name TEXT,
  amount INTEGER,            -- 원 단위, 부채는 양수로 저장(부호 반전 없음)
  owner TEXT,
  created_at TIMESTAMP
)

-- 카테고리별 월 예산
budgets (
  category       TEXT PRIMARY KEY,  -- transactions의 실효 대분류와 동일
  monthly_amount INTEGER,           -- 월 예산 (원 단위, 0=미설정)
  is_fixed_cost  INTEGER,           -- 1=고정 지출, 0=변동 지출
  sort_order     INTEGER
)

-- docs/ 폴더 자동처리 이력
processed_files (
  filename      TEXT PRIMARY KEY,
  owner         TEXT,
  snapshot_date TEXT,
  processed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**카테고리 조회 규칙:** `refined_category_1`이 있으면 우선 사용, 없으면 `category_1` fallback.
```sql
COALESCE(NULLIF(refined_category_1, ''), category_1)
```

## 주요 함수

### db_handler.py
- `_init_db()` — 테이블 생성 + migration (category_rules DROP, budgets sort_order ADD)
- `save_transactions(df, owner, filename)` — 데이터 기간 내 해당 소유자 DELETE 후 INSERT
- `save_asset_snapshot(df, owner, snapshot_date)` — 동일 날짜+소유자 DELETE+INSERT
- `get_analyzed_transactions()` — transactions LEFT JOIN budgets, tx_type!='이체', COALESCE 카테고리
- `get_latest_assets()` — 소유자별 최신 스냅샷
- `get_previous_assets(target_date, owner)` — target_date에 가장 근접한 스냅샷 (delta 계산용)
- `init_budgets()` — budgets 비어있을 때 형준 거래내역 카테고리로 seed
- `sync_categories_from_transactions()` — 업로드 후 신규 카테고리를 budgets에 자동 추가
- `get_budgets()` — budgets 전체 반환 (비어있으면 init_budgets 선실행)
- `save_budgets(df)` — budgets 전체 교체 저장
- `get_category_avg_monthly(months)` — 최근 N개월 카테고리별 월평균 지출
- `get_few_shot_examples(months, tx_type)` — GPT 매핑용 few-shot 예시 (형준 최근 N개월)
- `get_transactions_for_reclassification(start_date, end_date)` — 기간별 고유 description 목록 (재분류용)
- `update_refined_categories(mapping, start_date, end_date)` — refined_category_1 일괄 업데이트
- `has_transactions_in_range(owner, start_date, end_date)` — 기간 내 데이터 존재 여부
- `get_processed_filenames()` — `{filename: processed_at}` dict 반환 (set 아님)
- `mark_file_processed(filename, owner, snapshot_date)` — 처리 완료 기록
- `clear_all_data()` — transactions / asset_snapshots / processed_files 전체 삭제
- `get_asset_history()` — snapshot_date × owner 기준 집계 (total_asset, total_debt, net_worth)
- `execute_query_safe(sql, max_rows=200)` — 챗봇용 SELECT 전용 안전 실행기

### file_handler.py
- `detect_owner_from_filename(filename)` — ZIP: 님_ 패턴 / Excel: _나·_내사랑 suffix
- `scan_docs_folder()` — docs/ 스캔, `{filename, owner, snapshot_date, start_date, mtime}` 반환
- `extract_date_range(filename)` — `(start_date, end_date)` 추출, 없으면 `(None, 오늘)`
- `extract_snapshot_date(filename)` — end_date만 추출
- `process_uploaded_zip(uploaded_file, password, start_date, end_date)` — ZIP 해제 + Excel 파싱
- `process_uploaded_excel(uploaded_file, start_date, end_date)` — Excel 직접 파싱
- `_parse_excel_sheets(excel_data, start_date, end_date)` — Sheet0(자산) / Sheet1(거래) 파서
- `_parse_asset_sheet(df)` — BankSalad 병합셀 처리

### ai_agent.py
- `map_categories(client, pairs_df, few_shot_df, categories)` — GPT few-shot 카테고리 매핑, `(result_df, usage_dict)` 반환
- `generate_analysis_summary(client, anomaly_metrics, burnrate_metrics)` — 이상지출·Burn-rate 메트릭을 받아 친근한 한국어 요약 2~3문장 생성
- `ask_gpt_finance(client, chat_history)` — Function Calling 멀티턴 루프 (최대 5회 반복). GPT가 tool_call 없을 때 최종 답변 반환

## 환경변수

`.env` 파일 (gitignore됨):
```
OPENAI_API_KEY=sk-...
```

## 코드 컨벤션

- **언어**: UI·주석 모두 한국어
- **금액**: INTEGER (원 단위). 지출 = 음수, 수입 = 양수. 집계 시 `ABS(amount)` 또는 `-amount` 사용
- **카테고리**: `COALESCE(NULLIF(refined_category_1, ''), category_1)` 패턴으로 항상 실효값 사용
- **날짜**: TEXT `YYYY-MM-DD`, 시간 TEXT `HH:MM`
- **소유자**: 형준 / 윤희 / 공동
- **페이지 구조**: 각 페이지 파일에 `render()` 함수 하나
- **DB 연결**: `with sqlite3.connect(DB_PATH) as conn:` 컨텍스트 매니저 사용
- **이체 제외**: `get_analyzed_transactions()`에서 `tx_type != '이체'` 필터링됨

## Docker

```yaml
image: python:3.11-slim
ports: "3101:8501"
env_file: .env
TZ: Asia/Seoul
restart: always
```

볼륨 마운트(`.:/app`) — 코드 수정 후 컨테이너 재시작 필요.

## 구현 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| Step 0 | 기술 부채 정리 | ✅ |
| Step 1 | 로그인/인증 (streamlit-authenticator, admin/user 역할) | ✅ |
| Step 2 | 목표 예산 설정 (budgets 테이블, 카테고리 자동 동기화) | ✅ |
| Step 3 | 멀티 포맷 업로더 + 파일명 날짜 자동 감지 | ✅ |
| Step 4 | GPT 카테고리 자동 매핑 + 검수 UI | ✅ |
| Step 5 | 이상 지출 탐지 (2σ 기준, 드릴다운) | ✅ |
| Step 6 | Burn-rate 분석 (과거 패턴 기반 월말 예측) | ✅ |
| Step 7 | 자산 트렌드 MVP (선형 회귀, Prophet은 마이그레이션 후) | ✅ |
| Step 8 | NL-to-SQL 멀티턴 고도화 | 🔄 진행 중 |
| Step 9 | 동적 시각화 (챗봇 Plotly 차트) | ❌ |

## 알려진 이슈

- `data_management.py`에 ZIP 비밀번호 하드코딩 (형준=0979, 윤희=1223)
- `transactions.py`에 owner 보정 로직 하드코딩 (`Mega/페이코` → 윤희)
- `transactions` 스키마에 `refined_category_2` 컬럼 정의되어 있으나 미활용
- Step 7 자산 트렌드: 현재 선형 회귀(numpy) MVP. 데이터 마이그레이션 후 Prophet으로 교체 예정
- `asset_snapshots`의 부채 `amount`는 양수로 저장됨 (net_worth 계산 시 차감 필요)

## 다음 단계

### 데이터 마이그레이션 (Step 8 이전 권장)

2022~2025년 4년치 과거 데이터 일괄 업로드. Step 5~7 분석 신뢰도 확보 및 Prophet 교체 조건 충족.

- `data_management.py` 수동 업로드 탭에서 Excel 일괄 업로드
- `save_transactions()`의 날짜 범위 삭제-재삽입 로직이 연도별로 정확히 동작하는지 사전 검증 필요
- `asset_snapshots`는 동일 날짜+소유자 덮어쓰기 — 중복 업로드 시 자동 교체됨

### Step 8 — NL-to-SQL 에이전트 고도화

멀티턴 쿼리 루프는 완료 (`ask_gpt_finance` 최대 5회 반복). 잔여 작업:
- 슬라이딩 윈도우: `chat_history[-N:]` 적용으로 장기 대화 토큰 초과 방지
- 시스템 프롬프트에 예산 데이터 동적 주입 (budgets 테이블 조회 후 컨텍스트 추가)

### Step 9 — 동적 시각화

챗봇 응답에서 Plotly 차트 렌더링. 보안 원칙: GPT는 `render_chart(chart_type, labels, values, title)` 파라미터만 결정, Python이 허용된 chart_type(`pie`, `bar`, `line`)으로 직접 생성.

**수정 대상:** `ai_agent.py` (Tool 추가), `chatbot.py` (차트 렌더링 분기)
