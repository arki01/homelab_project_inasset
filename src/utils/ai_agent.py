import json
from datetime import date
from openai import OpenAI

DB_SCHEMA = """
[DB 스키마 — SQLite]

테이블: transactions (거래 내역)
  - date TEXT        : 날짜 (YYYY-MM-DD)
  - time TEXT        : 시간 (HH:MM)
  - tx_type TEXT     : 타입 — 수입 / 지출 / 이체
  - category_1 TEXT  : 대분류 (식비, 교통비, 고정비, 주거비, 금융, 보험, 생활비, 활동비, 친목비, 꾸밈비, 차량비, 여행비, 의료비, 기여비, 양육비, 예비비, 미분류)
  - category_2 TEXT  : 소분류
  - description TEXT : 내용/상호명
  - amount INTEGER   : 금액 (원 단위)
  - currency TEXT    : 화폐
  - source TEXT      : 결제수단
  - memo TEXT        : 메모
  - owner TEXT       : 소유자 — 형준 / 윤희 / 공동

테이블: asset_snapshots (자산 스냅샷)
  - snapshot_date TEXT : 스냅샷 날짜 (YYYY-MM-DD HH:MM:SS)
  - balance_type TEXT  : 구분 — 자산 / 부채
  - asset_type TEXT    : 항목 (현금 자산, 투자성 자산 등)
  - account_name TEXT  : 상품명
  - amount INTEGER     : 금액 (원 단위, 부채는 음수)
  - owner TEXT         : 소유자 — 형준 / 윤희 / 공동

테이블: category_rules (고정비/변동비 분류)
  - category_name TEXT : 대분류명 (transactions.category_1 과 동일)
  - expense_type TEXT  : 지출 유형 — 고정 지출 / 변동 지출
"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "SQLite DB에서 SELECT 쿼리로 데이터를 조회합니다. "
                "분석에 필요한 데이터만 정확히 쿼리하세요. "
                "이체(tx_type='이체')는 항상 제외하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "실행할 SELECT SQL 쿼리 (SELECT 또는 WITH 로 시작해야 함)"
                    }
                },
                "required": ["sql"]
            }
        }
    }
]


def ask_gpt_finance(client: OpenAI, chat_history: list) -> str:
    """
    Function Calling으로 GPT가 필요한 쿼리를 직접 작성·실행하고 답변을 생성합니다.

    Args:
        client      : OpenAI 클라이언트
        chat_history: 대화 이력 (최신 user 메시지 포함)

    Returns:
        str: GPT 최종 답변
    """
    from utils.db_handler import execute_query_safe

    today = date.today().strftime('%Y-%m-%d')

    system_prompt = f"""너는 꼼꼼한 가계부 분석 비서야. 부부(형준/윤희)의 가계 데이터를 분석한다.

오늘 날짜: {today}

{DB_SCHEMA}

[규칙]
- 질문에 답하기 위해 반드시 query_database 도구로 필요한 데이터를 먼저 조회해
- 질문 범위에 딱 맞는 쿼리를 작성해 (불필요한 데이터 로딩 금지)
- 이체(tx_type='이체')는 항상 WHERE 조건에서 제외해
- 기간이 명시되지 않으면 이번 달 기준으로 조회해
- 금액은 원 단위 정수야
- 답변은 친근하고 명확하게 한국어로 해줘
"""

    messages = [
        {"role": "system", "content": system_prompt},
        *chat_history
    ]

    try:
        # 1차 호출: GPT가 필요한 쿼리 결정
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto"
        )

        response_message = response.choices[0].message

        # Function Call 없이 바로 답변한 경우 반환
        if not response_message.tool_calls:
            return response_message.content

        # Function Call 루프: 쿼리 실행 후 결과 전달
        messages.append(response_message)

        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "query_database":
                args = json.loads(tool_call.function.arguments)
                sql = args.get("sql", "")
                query_result = execute_query_safe(sql)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": query_result
                })

        # 2차 호출: 쿼리 결과를 바탕으로 최종 답변 생성
        final_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        return final_response.choices[0].message.content

    except Exception as e:
        return f"AI 응답 중 오류가 발생했습니다: {str(e)}"
