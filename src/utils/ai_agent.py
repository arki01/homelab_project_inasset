from openai import OpenAI

def ask_gpt_finance(client: OpenAI, user_message: str, db_context: str, chat_history: list):
    """
    금융 데이터 컨텍스트를 포함하여 GPT에게 질문합니다.
    """
    system_prompt = f"""
    너는 꼼꼼한 자산 관리 비서야. 
    아래 제공된 [카테고리별 통계]를 먼저 보고 전체 흐름을 파악한 뒤, [최근 상세 내역]을 참고해서 답변해줘.
    
    [데이터 컨텍스트]
    {db_context}
    """
    
    # 메시지 조립
    messages = [
        {"role": "system", "content": system_prompt},
        *chat_history # 기존 대화 내역 포함
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 응답 중 오류가 발생했습니다: {str(e)}"