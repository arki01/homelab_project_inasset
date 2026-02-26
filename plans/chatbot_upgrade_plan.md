# 🤖 InAsset 챗봇 기능 업데이트 계획서

## 📋 현재 상태 분석

### 기존 구현 현황
- **[`chatbot.py`](../Projects/InAsset/src/pages/chatbot.py:1)**: 기본 헤더만 있는 준비 중 상태
- **[`ai_agent.py`](../Projects/InAsset/src/utils/ai_agent.py:1)**: GPT-4o 연동 함수 구현됨 (`ask_gpt_finance`)
- **[`db_handler.py`](../Projects/InAsset/src/utils/db_handler.py:1)**: transactions, asset_snapshots 테이블 관리 함수 존재
- **환경 설정**: `.env`에 OPENAI_API_KEY 저장됨 (docker-compose.yml 연동 필요)

### 요구사항 정리
1. **기본적인 챗봇 UI 구현** (Streamlit 채팅 인터페이스)
2. **현재 ai_agent.py 활용** (추후 고도화 가능한 구조)
3. **데이터 컨텍스트**: transactions 테이블의 최근 데이터 + 카테고리별 통계 요약
4. **대화 히스토리 유지** (세션 상태 관리)

---

## 🏗️ 설계 방안

### 1. DB 컨텍스트 생성 함수 설계

#### [`db_handler.py`](../Projects/InAsset/src/utils/db_handler.py:1)에 추가할 함수

```python
def get_chatbot_context(limit_recent=20, period_months=3):
    """
    챗봇에게 전달할 금융 데이터 컨텍스트를 생성합니다.
    
    Args:
        limit_recent: 최근 거래 내역 개수 (기본 20건)
        period_months: 통계 집계 기간 (기본 3개월)
    
    Returns:
        str: 포맷팅된 컨텍스트 문자열
    """
```

**생성할 컨텍스트 구조:**
1. **기간별 수입/지출 요약** (최근 3개월)
   - 총 수입, 총 지출, 순자산 변화
   - 소유자별(남편/아내/공동) 집계

2. **카테고리별 지출 통계** (대분류 기준)
   - 상위 5개 카테고리 + 금액 + 비중

3. **고정비/변동비 분석**
   - 고정 지출 vs 변동 지출 비율

4. **최근 거래 내역** (20건)
   - 날짜, 카테고리, 내용, 금액, 소유자

---

### 2. 챗봇 UI 구조 설계

#### Streamlit 채팅 인터페이스 구성

```
┌─────────────────────────────────────────┐
│  🤖 지능형 자산 컨설턴트                │
│  자연어로 질문하고 인사이트를 받으세요  │
├─────────────────────────────────────────┤
│                                         │
│  [채팅 메시지 영역]                     │
│  - st.chat_message 활용                 │
│  - 사용자/AI 메시지 구분                │
│  - 대화 히스토리 표시                   │
│                                         │
├─────────────────────────────────────────┤
│  [입력 영역]                            │
│  - st.chat_input 활용                   │
│  - 예시 질문 버튼 (선택 사항)           │
└─────────────────────────────────────────┘
```

#### 세션 상태 관리
- `st.session_state.chat_history`: 대화 내역 저장
- `st.session_state.messages`: UI 표시용 메시지 리스트

---

### 3. AI 에이전트 통합 방안

#### 기존 [`ai_agent.py`](../Projects/InAsset/src/utils/ai_agent.py:1) 활용

**현재 함수 구조:**
```python
ask_gpt_finance(client: OpenAI, user_message: str, db_context: str, chat_history: list)
```

**통합 플로우:**
```mermaid
graph LR
    A[사용자 질문] --> B[get_chatbot_context 호출]
    B --> C[DB에서 컨텍스트 생성]
    C --> D[ask_gpt_finance 호출]
    D --> E[GPT-4o 응답]
    E --> F[UI에 표시]
    F --> G[세션 히스토리 저장]
```

**개선 사항:**
- OpenAI 클라이언트 초기화를 [`chatbot.py`](../Projects/InAsset/src/pages/chatbot.py:1)에서 처리
- 에러 핸들링 강화 (API 키 누락, 네트워크 오류 등)
- 로딩 상태 표시 (`st.spinner` 활용)

---

### 4. 환경 설정 보완

#### [`docker-compose.yml`](../Projects/InAsset/docker-compose.yml:1) 수정

**추가할 내용:**
```yaml
services:
  inasset-app:
    env_file:
      - .env  # OPENAI_API_KEY 자동 로드
```

#### `.env` 파일 구조 (참고용)
```
OPENAI_API_KEY=sk-...
```

---

## 📝 단계별 구현 로드맵

### Step 1: DB 컨텍스트 함수 구현
**파일**: [`db_handler.py`](../Projects/InAsset/src/utils/db_handler.py:1)

- [ ] `get_chatbot_context()` 함수 추가
  - 최근 3개월 수입/지출 요약 쿼리
  - 카테고리별 지출 통계 (상위 5개)
  - 고정비/변동비 비율 계산
  - 최근 거래 내역 20건 조회
  - 포맷팅된 문자열 반환

**예상 출력 형식:**
```
=== 최근 3개월 재무 현황 ===
• 총 수입: 10,500,000원
• 총 지출: 7,200,000원
• 순자산 변화: +3,300,000원

=== 카테고리별 지출 TOP 5 ===
1. 식비: 1,800,000원 (25%)
2. 주거비: 1,500,000원 (21%)
3. 교통비: 900,000원 (12%)
...

=== 고정비 vs 변동비 ===
• 고정 지출: 3,000,000원 (42%)
• 변동 지출: 4,200,000원 (58%)

=== 최근 거래 내역 (20건) ===
[날짜] [카테고리] [내용] [금액] [소유자]
...
```

---

### Step 2: 챗봇 UI 구현
**파일**: [`chatbot.py`](../Projects/InAsset/src/pages/chatbot.py:1)

- [ ] 세션 상태 초기화
  - `messages`: UI 표시용 메시지 리스트
  - `chat_history`: API 전달용 대화 히스토리

- [ ] OpenAI 클라이언트 초기화
  - `os.getenv("OPENAI_API_KEY")` 확인
  - API 키 누락 시 경고 메시지 표시

- [ ] 채팅 인터페이스 구현
  - 기존 메시지 표시 (`st.chat_message` 활용)
  - 사용자 입력 처리 (`st.chat_input`)
  - AI 응답 생성 및 표시

- [ ] 예시 질문 버튼 (선택 사항)
  - "이번 달 지출 현황은?"
  - "가장 많이 쓴 카테고리는?"
  - "고정비 비중이 적절한가요?"

---

### Step 3: AI 에이전트 연동
**파일**: [`chatbot.py`](../Projects/InAsset/src/pages/chatbot.py:1)

- [ ] 사용자 질문 입력 시 처리 플로우
  1. `get_chatbot_context()` 호출하여 DB 컨텍스트 생성
  2. `ask_gpt_finance()` 호출하여 AI 응답 생성
  3. 응답을 UI에 표시
  4. 세션 히스토리에 저장

- [ ] 에러 핸들링
  - API 키 누락
  - 네트워크 오류
  - DB 조회 실패
  - 각 상황별 사용자 친화적 메시지 표시

- [ ] 로딩 상태 표시
  - `st.spinner("AI가 분석 중입니다...")` 활용

---

### Step 4: 환경 설정 업데이트
**파일**: [`docker-compose.yml`](../Projects/InAsset/docker-compose.yml:1)

- [ ] `env_file` 추가
  ```yaml
  env_file:
    - .env
  ```

- [ ] 컨테이너 재시작 후 환경변수 로드 확인

---

### Step 5: 테스트 및 검증

- [ ] 기본 대화 테스트
  - "안녕하세요" → 인사 응답 확인
  - "이번 달 지출은?" → 컨텍스트 기반 응답 확인

- [ ] 데이터 컨텍스트 정확성 검증
  - DB 실제 데이터와 AI 응답 비교

- [ ] 대화 히스토리 유지 확인
  - 이전 대화 내용 참조하는 질문 테스트

- [ ] 에러 상황 테스트
  - API 키 제거 후 동작 확인
  - DB 비어있을 때 동작 확인

---

## 🚀 향후 고도화 방향 (Phase 3 대비)

### 1. NL-to-SQL 전환 경로

현재 구현은 **"DB 컨텍스트를 텍스트로 전달"** 방식이지만, Phase 3에서는 **"AI가 직접 SQL 쿼리 생성"** 방식으로 전환합니다.

#### 현재 방식 (Phase 2)
```
사용자 질문 → DB 컨텍스트 생성 (고정) → GPT에 전달 → 응답
```

#### 고도화 방식 (Phase 3)
```
사용자 질문 → GPT가 SQL 생성 → DB 실행 → 결과를 GPT에 전달 → 응답
```

#### 전환 시 필요한 작업

**1단계: LangChain SQL Database Chain 도입**
```python
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI

# DB 연결
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

# SQL 생성 체인
llm = ChatOpenAI(model="gpt-4o", temperature=0)
chain = create_sql_query_chain(llm, db)

# 사용자 질문 → SQL 생성
sql_query = chain.invoke({"question": "이번 달 식비 지출은?"})
```

**2단계: Self-Correction 메커니즘**
```python
try:
    result = db.run(sql_query)
except Exception as e:
    # 오류 메시지를 AI에게 전달하여 쿼리 수정
    corrected_query = chain.invoke({
        "question": original_question,
        "error": str(e),
        "previous_query": sql_query
    })
```

**3단계: 동적 시각화 연동**
```python
# AI가 생성한 데이터를 Plotly로 시각화
if "추이" in user_question or "그래프" in user_question:
    fig = px.line(df, x='date', y='amount', title='지출 추이')
    st.plotly_chart(fig)
```

---

### 2. 기능 확장 로드맵

#### Phase 2.5 (중간 단계)
- [ ] 자주 묻는 질문(FAQ) 템플릿 추가
- [ ] 응답에 간단한 표 형식 지원 (Markdown 테이블)
- [ ] 대화 내보내기 기능 (텍스트 파일)

#### Phase 3 (완전한 NL-to-SQL)
- [ ] LangChain SQL Database Chain 통합
- [ ] 동적 SQL 쿼리 생성 및 실행
- [ ] Self-Correction 메커니즘
- [ ] 쿼리 결과 자동 시각화 (Plotly)

#### Phase 4 (고급 분석)
- [ ] 예측 모델 연동 (Prophet)
  - "다음 달 예상 지출은?"
  - "이 속도면 연말 자산은?"
- [ ] 비교 분석
  - "작년 같은 달과 비교하면?"
  - "우리 부부 평균 대비 우리는?"
- [ ] 맞춤형 인사이트
  - "절약 가능한 항목 추천"
  - "목표 달성을 위한 조언"

---

## 🎯 구현 우선순위

### 🔴 필수 (MVP)
1. DB 컨텍스트 생성 함수
2. 기본 채팅 UI
3. AI 에이전트 연동
4. 환경 설정 보완

### 🟡 권장 (사용성 향상)
1. 예시 질문 버튼
2. 로딩 상태 표시
3. 에러 핸들링 강화

### 🟢 선택 (추후 개선)
1. 대화 내보내기
2. FAQ 템플릿
3. 응답 포맷팅 고도화

---

## 📊 예상 파일 변경 사항

### 수정할 파일
1. **[`db_handler.py`](../Projects/InAsset/src/utils/db_handler.py:1)** (+50줄)
   - `get_chatbot_context()` 함수 추가

2. **[`chatbot.py`](../Projects/InAsset/src/pages/chatbot.py:1)** (+100줄)
   - 전체 UI 및 로직 구현

3. **[`docker-compose.yml`](../Projects/InAsset/docker-compose.yml:1)** (+2줄)
   - `env_file` 설정 추가

### 수정하지 않을 파일
- **[`ai_agent.py`](../Projects/InAsset/src/utils/ai_agent.py:1)**: 현재 구조 그대로 활용
- **[`app.py`](../Projects/InAsset/src/app.py:1)**: 이미 챗봇 메뉴 연동됨

---

## 🔍 기술적 고려사항

### 1. 토큰 사용량 최적화
- 컨텍스트 길이 제한 (최근 3개월, 20건)
- 불필요한 컬럼 제외 (created_at, id 등)
- 금액 포맷팅 (천 단위 구분)

### 2. 응답 속도 개선
- DB 쿼리 최적화 (인덱스 활용)
- 컨텍스트 캐싱 (세션 내 재사용)
- 스트리밍 응답 (추후 고려)

### 3. 보안 및 프라이버시
- API 키 환경변수 관리
- 민감 정보 마스킹 (계좌번호 등)
- 대화 내역 로컬 저장 (외부 전송 없음)

### 4. 확장성 고려
- 함수 모듈화 (재사용 가능하게)
- 설정값 외부화 (기간, 건수 등)
- 로깅 추가 (디버깅 용이)

---

## ✅ 완료 기준

### 기능 요구사항
- [x] 사용자가 자연어로 질문 입력 가능
- [x] AI가 DB 컨텍스트 기반으로 응답 생성
- [x] 대화 히스토리 유지 (세션 내)
- [x] 에러 상황 처리 (API 키 누락 등)

### 비기능 요구사항
- [x] 응답 시간 5초 이내 (일반적인 질문)
- [x] 모바일 환경에서도 사용 가능
- [x] Docker 환경에서 정상 동작
- [x] 코드 가독성 및 유지보수성 확보

---

## 📚 참고 자료

### Streamlit 채팅 관련
- [Streamlit Chat Elements](https://docs.streamlit.io/library/api-reference/chat)
- [Build a basic LLM chat app](https://docs.streamlit.io/knowledge-base/tutorials/build-conversational-apps)

### LangChain SQL (Phase 3 대비)
- [SQL Database Chain](https://python.langchain.com/docs/use_cases/sql/)
- [Self-Querying Retriever](https://python.langchain.com/docs/modules/data_connection/retrievers/self_query/)

### OpenAI API
- [Chat Completions API](https://platform.openai.com/docs/guides/chat)
- [Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)

---

## 🎬 다음 단계

이 계획서를 검토하신 후, 다음 중 하나를 선택해주세요:

1. **즉시 구현 시작** → Code 모드로 전환하여 단계별 구현
2. **계획 수정** → 특정 부분 조정 후 재검토
3. **추가 질문** → 불명확한 부분 명확화

---

**작성일**: 2026-02-24  
**버전**: 1.0  
**상태**: 검토 대기 중
