import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from uuid import uuid4
import src.langchain_bot.agent as agent
from src.langchain_bot.rag_tool import initialize_vector_store
from src.langchain_bot.auth import authenticate_user
from src.langchain_bot.context import SessionContext
from src.langchain_bot.hitl_utils import (
    handle_interrupt,
    has_pending_action_for_thread,
)
def get_llm():
    load_dotenv()
    model=ChatOpenAI(model="gpt-5.4-mini", temperature=0.3)
    return model

def build_chain(llm):
    system_message= SystemMessage(content="You are a concise, helpful assistant. Use prior chat history to stay on context")
    prompt= ChatPromptTemplate.from_messages([system_message, MessagesPlaceholder("history"), ("human", "{input}") ])
    return prompt | llm

def init_session():
    # st.session_state.setdefault("conversations",{})
    # st.session_state.setdefault("messages",[])
    st.session_state.setdefault("user_email", None)
    st.session_state.setdefault("user_role", None)
    st.session_state.setdefault("conversation_id", None)
    st.session_state.setdefault("vector_store_ready", False)
    st.session_state.setdefault("pending_notice", None)

def render_history():
    config = agent.get_thread_config(
        st.session_state.user_email,
        st.session_state.conversation_id)
    state = agent.get_agent().get_state(config)
    for msg in state.values.get("messages", []):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if content.startswith("Logged-in user email:"):
                content = content.split("User request:", 1)[-1].strip()
            st.chat_message("user").markdown(content)
        elif isinstance(msg, AIMessage) and msg.content:
            st.chat_message("assistant").markdown(msg.content)

def chat_round(user_input):
    config = agent.get_thread_config(
        st.session_state.user_email,
        st.session_state.conversation_id,
    )

    context = SessionContext(
        user_email=st.session_state.user_email,
        role=st.session_state.user_role,
        conversation_id=st.session_state.conversation_id
    )
    thread_id = config["configurable"]["thread_id"]
    if has_pending_action_for_thread(thread_id):
        st.session_state.pending_notice = (
            "### Approval already pending\n\n"
            "Please approve or reject the existing request before creating "
            "another cancellation or return."
        )
        return

    result = agent.get_agent().invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Logged-in user email: {context.user_email}\n"
                        f"User request: {user_input}"
                    ),
                }
            ]
        },
        config,
        context=context,
    )
    notice = handle_interrupt(
        result,
        thread_id,
        st.session_state.user_email,
    )
    if notice:
        st.session_state.pending_notice = notice
def start_conversation():
    conversation_id = str(uuid4())
    agent.add_thread(st.session_state.user_email, conversation_id)
    st.session_state.conversation_id = conversation_id
    st.rerun()

# def load_conversation(conv_id):
#     if conv_id in st.session_state.conversations:
#         st.session_state.messages=st.session_state.conversations[conv_id]
def main():
    st.set_page_config(page_title="Langchain Bot", page_icon="🤖")
    st.title("Langchain Bot")
    st.caption("A helpful assistant powered by Langchain")
    load_dotenv()
    init_session()
    user_email = st.session_state.user_email
    if not st.session_state.vector_store_ready:
        try:
            with st.spinner("Initializing vector store..."):
                initialize_vector_store()
                st.session_state.vector_store_ready = True
                st.success("Vector store initialized successfully.")

        except Exception as e:
            st.error("Failed to initialize vector store.")
            st.stop()

    if user_email is None:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password")
            role = st.selectbox("Role", ["customer", "admin"])
            submitted = st.form_submit_button("Login")
            if submitted:
                user = authenticate_user(email, password, role)
                if user:
                    st.session_state.user_email=user["email"]
                    st.session_state.user_role=user["role"]
                    threads=agent.load_threads(st.session_state.user_email)
                    if threads:
                        st.session_state.conversation_id = threads[0]
                    else:
                        conversation_id = str(uuid4())
                        agent.add_thread(
                            st.session_state.user_email,
                            conversation_id,
                        )
                        st.session_state.conversation_id = conversation_id
                    st.success(f"Logged in as {user['full_name']} ({user['role']})")
                    st.rerun() 
                else:
                    st.error("Invalid credentials or role. Please try again.")
        st.info("Please log in to access the assistant.")
    else:
        st.sidebar.header("Conversations")
        st.sidebar.button("Start New Conversation", on_click=start_conversation)
        st.sidebar.selectbox(
            "Select a conversation",
            options=agent.load_threads(st.session_state.user_email),
            key="conversation_id",
        )
        st.info(f"Logged in as: {st.session_state.user_email} ({st.session_state.user_role}) (conversation_id:{st.session_state.conversation_id})")
        
        render_history()
        if st.session_state.pending_notice:
            st.chat_message("assistant").markdown(
                st.session_state.pending_notice
            )
            st.session_state.pending_notice = None

        prompt=st.chat_input("Ask a question")
        if prompt:
            # llm=get_llm()
            st.chat_message("assistant").markdown("Thinking...")
            chat_round(prompt)
            st.rerun()

if __name__=="__main__":
    main()
