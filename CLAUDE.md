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
| `src/app.py` | 진입점, 사이드바 라우팅, DB 초기화, 인증/승인 |
| `src/pages/budget.py` | 🎯 목표 예산 설정 |
| `src/pages/transactions.py` | 💰 수입/지출 현황 |
| `src/pages/assets.py` | 🏦 자산 현황 |
| `src/pages/chatbot.py` | 🤖 AI 챗봇 |
| `src/pages/upload.py` | 📂 ZIP/Excel 업로드 + docs/ 자동처리 |
| `src/pages/analysis.py` | 📊 분석 리포트 (이상 지출 탐지 / Burn-rate / 자산 트렌드) |
| `src/utils/db_handler.py` | 모든 SQLite 작업 |
| `src/utils/file_handler.py` | ZIP/Excel 파싱, 파일명 메타데이터 추출 |
| `src/utils/ai_agent.py` | OpenAI API 래퍼 |

## 데이터베이스 스키마

**DB 경로:** `data/inasset_v1.db` (gitignore 됨)

```sql
-- 거래 내역
transactions (
  id, date TEXT, time TEXT,
  tx_type TEXT,              -- 수입/지출/이체
  category_1 TEXT,           -- 대분류
  category_2 TEXT,           -- 소분류
  refined_category_1 TEXT,   -- 표준화 대분류 (분석용, 현재 미사용)
  refined_category_2 TEXT,   -- 표준화 소분류 (분석용, 현재 미사용)
  description TEXT, amount INTEGER, currency TEXT,
  source TEXT,               -- 결제수단
  memo TEXT, owner TEXT,     -- 형준/윤희/공동
  created_at TIMESTAMP
)

-- 자산 스냅샷 (동일 snapshot_date+owner 조합은 DELETE+INSERT)
asset_snapshots (
  id, snapshot_date TEXT,
  balance_type TEXT,      -- 자산/부채
  asset_type TEXT,        -- 항목 (현금 자산, 투자성 자산 등)
  account_name TEXT, amount INTEGER,
  owner TEXT, created_at TIMESTAMP
)

-- 카테고리별 예산 (category_rules 통합 대체)
budgets (
  category       TEXT PRIMARY KEY,  -- transactions.category_1과 동일
  monthly_amount INTEGER,           -- 월 예산 (원 단위)
  is_fixed_cost  INTEGER            -- 1=고정, 0=변동
)

-- docs/ 폴더 자동처리 이력
processed_files (
  filename      TEXT PRIMARY KEY,
  owner         TEXT,
  snapshot_date TEXT,
  processed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## 주요 함수

### db_handler.py
- `_init_db()` — 앱 시작 시 테이블 생성 (migration: category_rules DROP 포함)
- `save_transactions(df, owner, filename)` — 해당 기간 삭제 후 재삽입 (UPSERT)
- `save_asset_snapshot(df, owner, snapshot_date)` — 동일 날짜+소유자 DELETE+INSERT
- `init_budgets()` — transactions(owner='형준')에서 카테고리 추출해 budgets 초기화
- `sync_categories_from_transactions()` — 업로드 후 신규 카테고리를 budgets에 자동 추가
- `get_analyzed_transactions()` — transactions LEFT JOIN budgets (expense_type 포함)
- `get_latest_assets()` — 소유자별 최신 스냅샷
- `get_previous_assets(target_date, owner)` — target_date에 가장 근접한 스냅샷 조회 (delta 계산용)
- `has_transactions_in_range(owner, start_date, end_date)` — 기간 내 데이터 존재 여부
- `get_processed_filenames()` — docs/ 처리 이력 파일명 set 반환
- `mark_file_processed(filename, owner, snapshot_date)` — 처리 완료 기록
- `clear_all_data()` — transactions, asset_snapshots, processed_files 전체 삭제
- `get_asset_history()` — 전체 자산 스냅샷 이력을 snapshot_date × owner 기준 집계 (total_asset, total_debt, net_worth)
- `execute_query_safe(sql, max_rows)` — 챗봇 Function Calling용 SELECT 쿼리 안전 실행기

### file_handler.py
- `detect_owner_from_filename(filename)` — 파일명 패턴으로 소유자 추출 (ZIP: 님_ / Excel: _나·_내사랑)
- `scan_docs_folder()` — docs/ 폴더 스캔, 메타데이터 목록 반환
- `extract_date_range(filename)` — 파일명에서 (start_date, end_date) 추출
- `extract_snapshot_date(filename)` — 파일명에서 end_date 추출
- `process_uploaded_zip(uploaded_file, password, start_date, end_date)` — ZIP 해제 + Excel 파싱
- `process_uploaded_excel(uploaded_file, start_date, end_date)` — Excel 직접 파싱
- `_parse_excel_sheets(excel_data, start_date, end_date)` — Sheet0(자산)/Sheet1(거래) 공통 파서
- `_parse_asset_sheet(df)` — BankSalad Sheet 0의 병합셀 처리 (구 _preprocess_asset_df)

### ai_agent.py
- `ask_gpt_finance(client, chat_history)` — Function Calling 방식으로 GPT가 `query_database` 도구를 직접 호출해 쿼리를 작성·실행하고 답변 생성
  - 내부적으로 `_TOOLS`(query_database 함수 정의)와 `DB_SCHEMA` 문자열을 시스템 프롬프트에 주입
  - 1차 호출 → GPT가 쿼리 결정 → `execute_query_safe()` 실행 → 2차 호출로 최종 답변 생성

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

- ✅ Step 0: 기술 부채 정리 (debug print 제거, f-string SQL 수정, 미사용 코드 정리, requirements 정비)
- ✅ Step 1: 로그인 및 보안 강화 (streamlit-authenticator, admin/user 역할, 승인 대기 관리)
- ✅ Step 2: 목표 예산 설정 (budgets 테이블, budget.py, 카테고리 자동 동기화)
- ✅ Step 3: 멀티 포맷 업로더 + 파일명 날짜 자동 감지 (Excel 직접 업로드, docs/ 자동처리, 스마트 날짜 범위)
- ✅ Step 4: GPT 카테고리 자동 매핑 (map_categories, STANDARD_CATEGORIES, 검수 UI)
- ✅ Step 5: 이상 지출 탐지 (2 표준편차 기준, 카테고리 드릴다운, analysis.py)
- ✅ Step 6: Burn-rate 분석 (과거 12개월 일별 패턴 기반 월말 예측, 예산선, analysis.py)
- ✅ Step 7: 자산 트렌드 MVP (순자산 추이 + 3개월 이동평균 + 2년 선형 예측, Prophet 미적용)
- ❌ 미구현: NL-to-SQL 멀티턴(Step 8), 동적 시각화(Step 9)

### 최근 주요 변경 이력

| 항목 | 변경 내용 |
|------|----------|
| Step 7: 자산 트렌드 예측 | `_render_asset_trend()`에 2년 선형 예측 추가. 최근 2년치 회귀 기울기 사용, 시작점을 실제 최신 순자산으로 고정, 오늘부터 24개월 외삽 |
| Step 6: Burn-rate 버그 수정 | `past_daily_pattern` 계산에서 `.mean()` → `.sum().div(n_months)` 로 수정 (지출 있는 달만 분모로 쓰던 과대 추정 문제 해결) |
| 전체 페이지 헤더 스타일 | 보라 그라디언트 → 검정(`#000000`), 상단 padding `2rem` → `1rem` (모든 pages/*.py, chatbot.py) |
| 이동평균 툴팁 정수화 | `ma3` `.round().astype('Int64')`, 예측값 `np.round().astype(int)` |
| Step 5~7: analysis.py 구현 | `_render_anomaly()`, `_render_burnrate()`, `_fill_combined_trend()`, `_render_asset_trend()` 신규 구현 |
| Step 4: 카테고리 매핑 | STANDARD_CATEGORIES 정의, map_categories() GPT 매핑, 검수 UI (st.data_editor 드롭다운), refined_category_1 저장 |
| Step 4: upload.py | 3단계 플로우 (파일선택→GPT검수→저장), _parse_batch_only, _build_mapping_df, _apply_mapping_and_save 분리 |
| Step 3: 업로드 | ZIP+Excel 멀티포맷, docs/ 폴더 자동처리, 파일명 날짜 추출, 스마트 날짜 범위 |
| Step 2: 예산 | budgets 테이블, category_rules 통합 제거, sync_categories_from_transactions() |
| Step 1: 인증 | streamlit-authenticator 로그인, admin/user 역할, 승인 대기 계정 관리 |
| 챗봇 아키텍처 | 하드코딩 컨텍스트 주입 → GPT Function Calling으로 전환 |

## 알려진 이슈

- `upload.py`에 ZIP 비밀번호 하드코딩 (형준=0979, 윤희=1223)
- `transactions.py`에 owner 보정 로직 하드코딩 (`Mega/페이코` → 윤희)
- `transactions` 스키마에 `refined_category_2` 컬럼 정의되어 있으나 미활용
- Step 7 자산 트렌드: 현재 선형 회귀(numpy) MVP. 데이터 마이그레이션 후 Prophet으로 교체 예정

---

## 개발 로드맵

> **InAsset의 장기 비전:** 사후 정산 방식에서 벗어나 실시간 지출 통제 및 미래 자산 예측이 가능한 개인화 지능형 자산 관리 서비스

### ✅ Step 0 - 착수 전 선행 기술 부채 정리

| 항목 | 조치 | 상태 |
|------|------|------|
| debug print 제거 | `_parse_asset_sheet()`, `save_transactions()` print문 삭제 | ✅ |
| f-string SQL 수정 | `get_previous_assets()`, `get_chatbot_context()` 파라미터 바인딩(`?`)으로 교체 | ✅ |
| 미사용 코드 정리 | `get_chatbot_context()` 제거, `langchain-community` requirements에서 제거 | ✅ |
| requirements 정비 | `streamlit-authenticator` 추가, `langchain-community` 제거 | ✅ |

---

### ✅ Step 1 — 로그인 및 보안 강화

**목표:** Cloudflare Tunnel을 통해 외부에 노출된 앱에 인증 레이어를 추가한다. 모든 기능 개발 전 선행 완료.

**구현 범위**
- `streamlit-authenticator` 라이브러리로 로그인 화면 구현
- 관리자(admin) / 사용자(user) 역할 분리: 관리자는 DB 삭제·계정 관리 가능, 사용자는 조회·업로드만 가능
- 로그인 전 모든 페이지 접근 차단 (`app.py` 최상단에서 인증 상태 확인)

**기술 검토**
- `streamlit-authenticator`가 requirements.txt에 없음 → 추가 필요
- 사용자 정보(아이디, bcrypt 해시 비밀번호, 역할)는 `config.yaml`에 저장 — 볼륨 마운트(`.:/app`) 환경이므로 컨테이너 재시작 없이 파일 수정 가능
- `st.secrets` 대신 `config.yaml` + 볼륨 마운트 방식 사용 (Docker 환경에 적합)
- 역할(role) 기반 UI 분기는 `st.session_state["role"]` 값으로 처리

**수정 대상 파일:** `app.py`, `requirements.txt`, `config.yaml` (신규)

---

### ✅ Step 2 — 목표 예산 설정

**목표:** AI 분석의 기준점이 될 예산 데이터를 확보한다. Step 6(Burn-rate)의 필수 선행 조건.

**구현 범위**
- 사이드바 메뉴 최상단에 `🎯 목표 예산` 항목 추가 (`app.py` `menu_options` 수정)
- `st.data_editor`로 카테고리별 월 예산 입력 UI
- 신규 페이지: `src/pages/budget.py`

**기술 검토**
- `_init_db()`에 `budgets` 테이블 CREATE TABLE 추가 필요
- `category_rules` 테이블의 카테고리 목록을 seed 데이터로 활용하여 기본 예산 행 자동 초기화 (사용자가 빈 화면 보지 않도록)
- `st.data_editor` 편집 후 별도 저장 버튼 트리거 필요 (Streamlit 특성상 편집이 자동 저장되지 않음)
- 예산은 카테고리당 단일 월 예산 값으로 단순하게 설계 (연도/월 구분 없음)

**DB 스키마 (신규)**
```sql
budgets (
  category       TEXT PRIMARY KEY,  -- category_rules.category_name과 동일
  monthly_amount INTEGER,           -- 월 예산 (원 단위)
  is_fixed_cost  INTEGER            -- 1=고정, 0=변동 (category_rules와 연동)
)
```

**수정 대상 파일:** `db_handler.py` (`_init_db()` 수정 + 예산 CRUD 함수 추가), `app.py` (메뉴 추가), `src/pages/budget.py` (신규)

---

### ✅ Step 3 — 멀티 포맷 업로더 + 파일명 기반 날짜 자동 감지

**목표:** ZIP 외 Excel 직접 업로드를 지원하고, 파일명에서 기준 날짜를 추출하여 데이터 정확성을 높인다.

**구현 범위**
- `st.file_uploader`에 `.xlsx`, `.xls` 확장자 추가 (ZIP과 동시 지원)
- ZIP: 기존 `process_uploaded_zip()` 유지
- Excel 직접 업로드: `file_handler.py`에 `process_uploaded_excel()` 함수 신규 작성
- **파일명에서 날짜 자동 추출:** 파일명 패턴에서 기준 날짜(end_date)를 파싱하여 `snapshot_date`로 사용
- docs 폴더에서 등록된 최신 파일에 대해 자동 업데이트 로직 추가 (신규 이메일 Event 기반 자동 수신됨)

**날짜 추출 규칙**
```
파일명 패턴 예시:
  ZIP:   '조윤희님_2024-02-01~2025-02-01.zip'  → 기준일: 2025-02-01
  Excel: '2024-02-01~2025-02-01_나.xlsx'       → 기준일: 2025-02-01

추출: regex r'(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})' 로 두 날짜 포착,
      오른쪽 날짜를 snapshot_date로 사용
      패턴 없는 파일명은 datetime.now() fallback
```

**기술 검토**
- **현재 문제:** `upload.py` line 138에서 `snapshot_date`를 `datetime.datetime.now()`로 생성. 업로드 시점이 아닌 파일이 나타내는 날짜로 저장해야 `get_previous_assets()`의 30일 델타 계산이 정확해짐. ZIP도 동일 문제 → 파일명 기반으로 통일
- `_preprocess_asset_df()`는 뱅크샐러드 고유 구조(병합셀, `3.재무현황` 헤더)에 강하게 결합되어 있어, Excel 직접 업로드 시 Sheet 구조가 동일한 경우에만 재사용 가능 — 불일치 시 별도 파싱 로직 분기

**수정 대상 파일:** `file_handler.py` (함수 추가 + 날짜 파싱), `upload.py` (분기 처리 + 날짜 전달)

---

### Step 4 — GPT 기반 카테고리 자동 매핑 (ETL)

**목표:** 업로드된 거래내역을 GPT가 자동으로 표준 카테고리로 분류하고, 사용자가 검수한다.

**구현 범위**
- 업로드된 거래내역의 `(category_1, description)` 조합을 GPT에 전달하여 `refined_category_1` 자동 매핑
- **분류 기준:** DB에 저장된 형준의 최근 3개월 `(description → category_1)` 실제 분류 패턴을 few-shot 예시로 GPT 프롬프트에 주입
- Human-in-the-loop 검수 UI: `st.data_editor`로 매핑 결과 확인·수정 후 저장

**기술 검토**
- **ML 분류기 대신 GPT few-shot 방식 채택:** 데이터 규모로는 scikit-learn 분류기 훈련에 필요한 레이블 데이터가 부족함. GPT few-shot in-context learning이 현실적이고 정확도도 높음
- **구현 방식:** `SELECT DISTINCT description, category_1 FROM transactions WHERE owner='형준' AND date >= (최근 3개월)` → GPT 시스템 프롬프트에 few-shot 주입 → 신규 데이터의 `description` 배치 전송 → `refined_category_1` 매핑 딕셔너리 반환
- **비용 최적화:** 고유 `(category_1, description)` 조합만 추출하여 GPT에 전송 (중복 제거). 100건 업로드 시 실제 고유값은 20~30개 수준으로 GPT 호출 1~2회면 충분 (토큰 사용량 검증 로직 필요)
- **현재 문제:** `save_transactions()`의 `valid_columns` 리스트에 `refined_category_1`이 없어 저장 불가 → `db_handler.py` 수정 필요
- 업로드 플로우(업로드 → 파싱 → **카테고리 검수** → 저장)로 단계 추가 — `upload.py` 세션 상태 흐름 재설계 필요
- `langchain-community` 의존성 불필요 — `openai` SDK만으로 구현 가능, 제거 권장

**수정 대상 파일:** `ai_agent.py` (함수 추가), `db_handler.py` (`valid_columns` 수정), `upload.py` (검수 단계 삽입), `requirements.txt`

---

### [ 데이터 마이그레이션 — Step 4 완료 후 ]

> Step 1~4 완료 후 **2022~2025년 4년치 과거 데이터를 일괄 마이그레이션**한다.
> 이 시점부터 Step 5~7의 분석 기능이 실질적인 의미를 갖는다.

**마이그레이션 범위**
- 2022~2025년 뱅크샐러드 Excel 파일 (연도별 또는 분기별) 일괄 업로드
- Step 3에서 구현된 Excel 직접 업로드 + 파일명 날짜 추출 기능 활용
- Step 4의 GPT 카테고리 매핑으로 4년치 `refined_category_1` 일괄 정규화

**기술적 고려사항**
- 4년치 거래내역 업로드 시 `save_transactions()`의 날짜 범위 삭제-재삽입 로직이 연도별로 정확히 동작하는지 사전 검증 필요
- 운영 중에 기존 입력된 데이터들도 업데이트가 필요할 수 있기 때문에, 기존 데이터들도 업데이트하는 화면을 구성 필요
- `asset_snapshots`는 APPEND only이므로 중복 스냅샷 업로드 주의 — 동일 날짜 스냅샷 중복 여부 체크 로직 검토
- 마이그레이션 완료 후 Step 7(자산 트렌드)에서 **Prophet 바로 적용 가능** (4년 = 48개월치 데이터 확보)

---

### Step 5 — 이상 지출 탐지 (Anomaly Detection)

**목표:** `분석 리포트`에 과거 평균 대비 이상 지출을 감지하고 원인 항목을 드릴다운으로 표시한다.

**구현 범위**
- 카테고리별 이번 달 지출이 과거 평균 대비 2 표준편차 초과 시 이상 지출로 분류
- `analysis.py` 상단에 인사이트 카드 렌더링: "이번 달 **식비**가 평소보다 **43%** 높습니다"
- 이상 카테고리별로 주요 원인 항목(`description`) 드릴다운 표시

**기술 검토**
- NumPy/Pandas만으로 구현 가능 — 추가 의존성 없음
- **계산 방식:** `category_1`별 월 지출 합계 집계 → 과거 N개월 평균·표준편차 계산 → 이번 달과 비교
- 마이그레이션 이후 48개월 데이터 기반으로 신뢰도 높은 평균·표준편차 계산 가능 (마이그레이션 전에는 최소 3개월 데이터 필요 조건 안내)
- 드릴다운: `st.expander` 내 `st.dataframe`으로 description별 금액 합계 상세 표시

**수정 대상 파일:** `src/pages/analysis.py`

---

### Step 6 — 실시간 소비 속도(Burn-rate) 분석

**목표:** 이번 달 지출 속도를 기반으로 월말 예상 지출을 예측하고, 예산 대비 현황을 시각화한다.

**구현 범위**
- 이번 달 누적 지출 기반으로 월말 예상 지출 계산 및 시각화
- **Total 뷰:** 전체 지출 누적 곡선 + 월말 예측선 + 예산선 (Plotly)
- **카테고리 뷰:** `st.selectbox`로 category_1 선택 시 해당 카테고리 단위 차트로 전환

**기술 검토**
- **Step 2(예산 설정) 완료 후 착수** — 예산선 렌더링에 `budgets` 테이블 데이터 필요
- 계산식: `월말 예상 = (현재까지 누적 지출 / 경과 일수) × 해당 월 전체 일수`
- `get_analyzed_transactions()`으로 이번 달 일별 데이터 조회 후 `groupby('date').sum()`으로 누적 계산
- Plotly `go.Scatter`로 3개 선 렌더링: 실제 누적(실선), 예측(점선), 예산(수평선). `plotly` 이미 requirements에 존재

**수정 대상 파일:** `src/pages/analysis.py`, `db_handler.py` (예산 조회 함수 추가)

---

### ✅ Step 7 — 자산 트렌드 분석

**목표:** 누적 자산 스냅샷 데이터로 자산 성장 추세를 시각화하고 향후 2년을 예측한다.

**구현 현황 (MVP 완성)**
- 소유자별/전체 합산 순자산 추이 차트 (실제값 + 3개월 이동평균)
- 2년 선형 예측: 최근 2년치 데이터로 회귀 기울기 계산 → 오늘부터 24개월 외삽
  - 시작점 = 실제 최신 순자산값 고정 (절편 버리고 기울기만 사용)
  - 스냅샷 3개 이상일 때만 예측선 표시

**Prophet 고도화 (마이그레이션 후)**
- 4년치 데이터 확보 후 `prophet` 패키지로 교체
- N100 환경에서 pystan 컴파일 20~40분 소요 → Docker 이미지 재빌드 일정 고려

**관련 함수:** `_render_asset_trend()`, `_fill_combined_trend()`, `get_asset_history()`

---

### Step 8 — NL-to-SQL 에이전트 고도화

**목표:** 챗봇이 복잡한 질문에도 여러 번 쿼리를 실행하여 정확한 답변을 생성하도록 개선한다.

**구현 범위**
- 멀티턴 쿼리 루프: 단일 tool_call → `while` 루프 확장 (GPT가 필요한 만큼 반복 쿼리)
- 시스템 프롬프트에 예산 정보 동적 주입 (Step 2 완료 후)
- 장기 대화 토큰 초과 방지를 위한 슬라이딩 윈도우 적용 (최근 N턴만 유지)

**기술 검토**
- **LangChain 전환 불필요:** 현재 OpenAI Function Calling 방식이 `SQLDatabaseChain`보다 더 유연하고 디버깅이 쉬움. LangChain은 복잡성만 추가 → `langchain-community` 패키지 제거
- **현재 구현의 실질 한계:**
  - `response_message.tool_calls` 처리가 단일 루프 — 복잡한 질문(예: "이번 달 식비 중 카드사별 비교해줘")에서 여러 쿼리가 필요한 경우 대응 불가
  - `chat_history` 전체를 매 요청마다 전송 — 대화가 길어지면 토큰 초과 가능
- **개선 방향:** `while response_message.tool_calls:` 루프 + `chat_history[-N:]` 슬라이싱

**수정 대상 파일:** `src/utils/ai_agent.py`, `requirements.txt` (`langchain-community` 제거)

---

### Step 9 — 동적 시각화 피드백

**목표:** 챗봇 응답에서 데이터 조회 결과를 텍스트와 Plotly 차트로 함께 표시한다.

**구현 범위**
- GPT가 `render_chart` 도구를 호출하면 Python이 Plotly로 안전하게 렌더링
- 예: "이번 달 외식비 비중 보여줘" → `query_database` 실행 → `render_chart` 호출 → 파이 차트 + 텍스트 응답

**기술 검토**
- **보안 설계 원칙:** GPT가 Plotly 코드를 직접 생성하고 `exec()`로 실행하는 방식은 코드 인젝션 위험 → 반드시 Tool 방식으로 제한
- **안전한 구현:** `_TOOLS`에 `render_chart(chart_type, labels, values, title)` 도구 추가. GPT는 파라미터만 결정하고, Python 측에서 허용된 `chart_type`(`pie`, `bar`, `line`)에 대한 Plotly 코드를 직접 생성
- `chatbot.py`에서 tool_call 결과가 `render_chart`인 경우 `st.plotly_chart()` 렌더링 분기 추가

**수정 대상 파일:** `src/utils/ai_agent.py` (Tool 추가), `src/pages/chatbot.py` (차트 렌더링 분기)

---

### 전체 구현 순서 한눈에 보기

```
[✅완료] Step 0: 기술 부채 정리
[✅완료] Step 1: 로그인/인증
[✅완료] Step 2: 목표 예산 설정
[✅완료] Step 3: 멀티 포맷 업로더 + 파일명 날짜 자동 감지
[✅완료] Step 4: GPT 카테고리 자동 매핑
[✅완료] Step 5: 이상 지출 탐지
[✅완료] Step 6: Burn-rate 분석
[✅완료] Step 7: 자산 트렌드 MVP (선형 회귀, Prophet은 마이그레이션 후)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [ 데이터 마이그레이션: 22~25년 4년치 일괄 업로드 ]
    → Step 5~7 분석 기능의 신뢰도 확보
    → Prophet(Step 7) 교체 조건 충족
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 8 → NL-to-SQL 멀티턴 고도화    ← 다음 단계
Step 9 → 동적 시각화 (Tool 방식)
```

### 의존성 변경 계획

```
# 추가
streamlit-authenticator   # Step 1
prophet                   # Step 7

# 제거
langchain-community       # 미사용, Function Calling으로 대체됨
```
