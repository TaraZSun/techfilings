"""
TechFilings - Web应用
Streamlit界面，用户查询财报信息
"""

import streamlit as st
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from modules.retriever import DocumentRetriever


# 页面配置
st.set_page_config(
    page_title="TechFilings",
    page_icon="📊",
    layout="wide"
)

# 初始化retriever（使用缓存避免重复初始化）
@st.cache_resource
def get_retriever():
    return DocumentRetriever()


def main():
    # 标题
    st.title("📊 TechFilings")
    st.markdown("快速定位科技公司财报信息，AI辅助分析")
    st.markdown("---")
    
    # 侧边栏 - 筛选选项
    with st.sidebar:
        st.header("筛选条件")
        
        # 公司筛选
        company_options = ["全部公司", "NVDA (NVIDIA)", "AMD", "PLTR (Palantir)"]
        selected_company = st.selectbox("选择公司", company_options)
        
        # 转换为ticker
        ticker_map = {
            "全部公司": None,
            "NVDA (NVIDIA)": "NVDA",
            "AMD": "AMD",
            "PLTR (Palantir)": "PLTR"
        }
        filter_ticker = ticker_map[selected_company]
        
        # 文件类型筛选
        filing_options = ["全部类型", "10-K (年报)", "10-Q (季报)"]
        selected_filing = st.selectbox("文件类型", filing_options)
        
        filing_map = {
            "全部类型": None,
            "10-K (年报)": "10-K",
            "10-Q (季报)": "10-Q"
        }
        filter_filing_type = filing_map[selected_filing]
        
        # 结果数量
        top_k = st.slider("返回结果数量", min_value=3, max_value=10, value=5)
        
        st.markdown("---")
        st.markdown("**支持的公司**")
        st.markdown("- NVIDIA (NVDA)")
        st.markdown("- AMD")
        st.markdown("- Palantir (PLTR)")
    
    # 主区域 - 查询输入
    query = st.text_input(
        "输入你的问题",
        placeholder="例如：What is NVIDIA's data center revenue?"
    )
    
    # 查询按钮
    if st.button("🔍 搜索", type="primary") or (query and st.session_state.get("last_query") != query):
        if query:
            st.session_state["last_query"] = query
            
            with st.spinner("正在搜索和分析..."):
                retriever = get_retriever()
                result = retriever.retrieve_and_answer(
                    query=query,
                    top_k=top_k,
                    filter_ticker=filter_ticker,
                    filter_filing_type=filter_filing_type
                )
            
            # 显示AI回答
            st.markdown("### 💡 AI分析")
            st.markdown(result["answer"])
            
            # 显示引用来源
            st.markdown("---")
            st.markdown(f"### 📄 原文引用 ({result['num_sources']}个来源)")
            
            for citation in result["citations"]:
                with st.expander(
                    f"**引用 {citation['index']}** | {citation['ticker']} | {citation['filing_type']} ({citation['filing_date']}) | 相似度: {citation['similarity']:.2f}"
                ):
                    st.markdown(f"**章节:** {citation['section']}")
                    st.markdown("**原文内容:**")
                    st.text_area(
                        label="原文",
                        value=citation["text"],
                        height=200,
                        disabled=True,
                        label_visibility="collapsed",
                        key=f"citation_{citation['index']}"
                    )
        else:
            st.warning("请输入问题")
    
    # 示例查询
    st.markdown("---")
    st.markdown("### 💬 示例问题")
    
    example_queries = [
        "What is NVIDIA's data center revenue?",
        "What are AMD's main risk factors?",
        "How does Palantir generate revenue from government contracts?",
        "What is NVIDIA's gross margin?",
        "How has AMD's revenue changed year over year?"
    ]
    
    cols = st.columns(2)
    for i, example in enumerate(example_queries):
        col = cols[i % 2]
        if col.button(example, key=f"example_{i}"):
            st.session_state["last_query"] = example
            st.rerun()


if __name__ == "__main__":
    main()