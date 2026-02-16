# TechFilings

快速定位科技公司财报信息，AI辅助分析。

## 功能

- 自动下载NVIDIA、AMD、Palantir的10-K和10-Q财报
- 用户输入问题，快速定位相关原文
- 提供原文出处，方便验证
- AI生成简短总结

## 项目结构

```
techfilings/
├── config.py           # 配置文件
├── build_index.py      # 构建向量索引
├── app.py              # Streamlit Web界面
├── requirements.txt    # Python依赖
├── modules/
│   ├── loader.py       # 下载财报
│   ├── parser.py       # 解析HTML
│   ├── chunker.py      # 文档分块
│   ├── embedder.py     # 生成向量
│   ├── searcher.py     # 搜索检索
│   └── retriever.py    # 生成回答
└── data/
    ├── raw/            # 原始财报文件
    └── processed/      # 处理后的数据
```

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置OpenAI API Key
```bash
export OPENAI_API_KEY="your-api-key"
```

3. 下载并构建索引
```bash
python build_index.py
```

4. 启动Web界面
```bash
streamlit run app.py
```

## 开发进度

- [x] 项目结构搭建
- [x] loader.py - 财报下载
- [ ] parser.py - 文档解析
- [ ] chunker.py - 文档分块
- [ ] embedder.py - 向量化
- [ ] searcher.py - 搜索
- [ ] retriever.py - 回答生成
- [ ] app.py - Web界面

## 技术栈

- Python
- OpenAI API (Embedding + GPT-4o-mini)
- ChromaDB (向量数据库)
- LlamaIndex (RAG框架)
- Streamlit (Web界面)
