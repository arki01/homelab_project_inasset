import streamlit as st
import os
from openai import OpenAI
from utils.ai_agent import ask_gpt_finance

def render():
    # ChatGPT 스타일 CSS
    st.markdown("""
        <style>
        /* 전체 채팅 컨테이너 스타일 */
        .stChatMessage {
            padding: 1rem 0.5rem !important;
            border-radius: 12px !important;
            margin-bottom: 1rem !important;
            animation: fadeIn 0.3s ease-in;
        }
        
        /* 아바타 숨기기 */
        .stChatMessage [data-testid="chatAvatarIcon-user"],
        .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
            display: none !important;
        }
        
        /* 사용자 메시지 스타일 */
        .stChatMessage[data-testid="user-message"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        }
        
        .stChatMessage[data-testid="user-message"] p {
            color: white !important;
        }
        
        /* AI 메시지 스타일 */
        .stChatMessage[data-testid="assistant-message"] {
            background-color: var(--secondary-background-color) !important;
            border: 1px solid rgba(128, 128, 128, 0.1);
        }
        
        /* 채팅 입력창 스타일 */
        .stChatInputContainer {
            border-top: 1px solid rgba(128, 128, 128, 0.1);
            padding-top: 1rem;
        }
        
        .stChatInput > div {
            border-radius: 24px !important;
            border: 2px solid rgba(128, 128, 128, 0.2) !important;
            transition: all 0.3s ease;
        }
        
        .stChatInput > div:focus-within {
            border-color: #667eea !important;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
        }
        
        /* 예시 질문 버튼 스타일 */
        .example-button {
            background: var(--background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            transition: all 0.3s ease;
            cursor: pointer;
            text-align: left;
            width: 100%;
        }
        
        .example-button:hover {
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        
        /* 헤더 스타일 */
        .chat-header {
            text-align: center;
            padding: 2rem 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .chat-subtitle {
            text-align: center;
            color: var(--text-color);
            opacity: 0.7;
            font-size: 1rem;
            margin-bottom: 2rem;
        }
        
        /* 애니메이션 */
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* 스피너 스타일 */
        .stSpinner > div {
            border-color: #667eea !important;
        }
        
        /* 초기화 버튼 스타일 */
        .reset-button button {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.5rem 1.5rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .reset-button button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(245, 87, 108, 0.3);
        }
        
        /* 메시지 카운터 스타일 */
        .message-counter {
            background: var(--secondary-background-color);
            border-radius: 20px;
            padding: 0.5rem 1rem;
            display: inline-block;
            font-size: 0.9rem;
            border: 1px solid rgba(128, 128, 128, 0.1);
        }
        
        /* 에러 메시지 스타일 개선 */
        .stAlert {
            border-radius: 12px;
            border-left: 4px solid;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 헤더
    st.markdown('<div class="chat-header">AI 자산 컨설턴트</div>', unsafe_allow_html=True)
    st.markdown('<div class="chat-subtitle">자연어로 질문하고 AI가 데이터를 분석하여 답변합니다</div>', unsafe_allow_html=True)
    
    # 1. OpenAI API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        st.error("⚠️ OPENAI_API_KEY가 설정되지 않았습니다.")
        st.info("`.env` 파일에 `OPENAI_API_KEY=sk-...` 형식으로 추가해주세요.")
        st.stop()
    
    # 2. OpenAI 클라이언트 초기화
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
        st.stop()
    
    # 3. 세션 상태 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # 4. 예시 질문 (대화가 비어있을 때만 표시)
    if len(st.session_state.messages) == 0:
        
        example_questions = [
            "💰 이번 달 지출 현황은?",
            "📊 가장 많이 쓴 카테고리는?",
            "💡 고정비 비중이 적절한가요?",
            "📈 저축률을 높이려면?",
            "🎯 이번 달 예산 추천해줘",
            "⚠️ 불필요한 지출이 있나요?"
        ]
        
        cols = st.columns(3)
        for idx, question in enumerate(example_questions):
            with cols[idx % 3]:
                if st.button(question, key=f"example_{idx}", use_container_width=True):
                    st.session_state.example_question = question
                    st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
    
    # 5. 채팅 컨테이너
    chat_container = st.container()
    
    with chat_container:
        # 기존 메시지 표시
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # 6. 사용자 입력 처리
    user_input = None
    
    # 예시 질문 버튼 클릭 시
    if "example_question" in st.session_state:
        user_input = st.session_state.example_question
        del st.session_state.example_question
    
    # 채팅 입력
    if prompt := st.chat_input("💬 궁금한 것을 물어보세요...", key="chat_input"):
        user_input = prompt
    
    # 7. 사용자 입력이 있을 때 처리
    if user_input:
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("🔍 AI가 데이터를 분석하고 있습니다..."):
                try:
                    # AI가 필요한 쿼리를 직접 생성·실행 후 답변
                    response = ask_gpt_finance(
                        client=client,
                        chat_history=st.session_state.chat_history
                    )
                    
                    # 응답 표시
                    st.markdown(response)
                    
                    # 응답 저장
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    error_message = f"⚠️ 오류가 발생했습니다: {str(e)}"
                    st.error(error_message)
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
        
        # 새 메시지 후 리런
        st.rerun()
    
    # 8. 하단 컨트롤 (대화가 있을 때만 표시)
    if len(st.session_state.messages) > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(
                f'<div class="message-counter">💬 대화 메시지: {len(st.session_state.messages)}개</div>', 
                unsafe_allow_html=True
            )
        
        with col3:
            st.markdown('<div class="reset-button">', unsafe_allow_html=True)
            if st.button("🔄 대화 초기화", use_container_width=True, key="reset_chat"):
                st.session_state.messages = []
                st.session_state.chat_history = []
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
