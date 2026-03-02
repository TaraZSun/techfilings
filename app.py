"""
TechFilings - Web应用
Clean chat interface with citation support
"""

import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from modules.chat_storage import save_chat, load_chat, list_chats, generate_title, new_chat_id
from dotenv import load_dotenv
load_dotenv()

from modules.retriever import DocumentRetriever

st.set_page_config(
    page_title="TechFilings",
    page_icon="🦅",
    layout="centered"
)

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


@st.cache_resource
def get_retriever():
    return DocumentRetriever()

def render_message(role: str, content: str, citations: list = None):
    if role == "user":
        col1, col2 = st.columns([1, 2])
        with col2:
            st.markdown(f'<div class="user-message">{content}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-message">{content}</div>', unsafe_allow_html=True)
        if citations:
            st.markdown('<div class="citations-header">Sources</div>', unsafe_allow_html=True)
            for c in citations:
                with st.expander(f"[{c['index']}] {c['company']} · {c['form_type']} · {c['section']}"):
                    st.markdown(f'<div class="citation-text">{c["text"]}</div>', unsafe_allow_html=True)

def main():
    # 1. 渲染标题
    st.markdown('<div class="app-title">🦅 TechFilings</div>', unsafe_allow_html=True)

    # 2. 初始化对话历史，初始化 chat_id
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0
    if "chat_id" not in st.session_state:
        st.session_state.chat_id = new_chat_id()
    if "chat_title" not in st.session_state:
        st.session_state.chat_title = "New Chat"

    # 3. 渲染历史记录 (所有的对话都会在这个区域向上滚动)
    for msg in st.session_state.messages:
        render_message(msg["role"], msg["content"], msg.get("citations"))

    # 4. 固定的底部输入区域
    with st.form(key="chat_form", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        with col1:
            query = st.text_input(
                "Ask a question",
                placeholder="Ask a question about the filings......",
                label_visibility="collapsed",
            )
        with col2:
            send = st.form_submit_button("Send")

    # 5. 处理输入逻辑
    if send and query.strip():
        query = query.strip()
        if not st.session_state.get("pending_query"):
            st.session_state.messages.append({"role": "user", "content": query})
            st.session_state["pending_query"] = query
            
            # 第一条消息时生成标题
            if len(st.session_state.messages) == 1:
                title = generate_title(query)
                st.session_state.chat_title = title
            
            save_chat(st.session_state.chat_id, st.session_state.messages, st.session_state.chat_title)
            st.rerun()

    # 6. 处理待回答的问题
    if st.session_state.get("pending_query"):
        query = st.session_state.pop("pending_query")
        with st.spinner(""):
            retriever = get_retriever()
            result = retriever.retrieve_and_answer(query=query, top_k=5)

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "citations": result.get("citations", [])
        })
        
        # 保存完整对话
        save_chat(st.session_state.chat_id, st.session_state.messages, st.session_state.chat_title)
        st.rerun()


if __name__ == "__main__":
    main()