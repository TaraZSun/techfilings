# TechFilings

> **Query SEC filings in plain English.** Vector search over iXBRL-parsed 10-K and 10-Q filings — grounded answers with inline citations, in seconds.

## What This Project Does
SEC filings are dense. A single 10-K can run 200+ pages of financial data, risk disclosures, and management commentary — all in iXBRL format, where structured financial tags are embedded directly in HTML alongside layout artifacts and footnotes.
TechFilings makes these documents queryable. Ask a question in plain English, get an answer grounded in the source filing, with a citation back to the exact section. No scrolling, no manual cross-referencing.
The core engineering challenge is the parsing layer: iXBRL documents can't be treated as plain text. TechFilings implements an iXBRL-aware parser that separates financial content from structural noise, and routes table extraction through a complexity classifier — BeautifulSoup for simple tables, LLM-based extraction for complex nested structures.

**What TechFilings returns in seconds:**

> NVIDIA identified U.S. export control regulations as a significant risk, citing restrictions on A100 and H100 chip sales to China. The filing notes these restrictions could materially impact data center revenue — approximately 78% of total revenue in FY2024. Risk language has intensified across successive 10-Q filings, with new references to "further tightening" affecting future product generations.
>
> *Sources: NVIDIA 10-K FY2024 · Item 1A · [1], NVIDIA 10-Q Q3 2024 · Item 1A · [2]*


## Features

- **iXBRL-aware parsing** — distinguishes financial data from layout artifacts in SEC filings
- **Complexity-based table routing** — BeautifulSoup for simple tables, LLM fallback for complex structures
- **Section-aware chunking** — every chunk carries its filing section for precise citation
- **Source-grounded answers** — every response cites the exact filing, form type, and section
- **Collapsible citations** — expandable source passages in the chat UI
- **User feedback collection** — stored in Supabase after every 3 questions

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Llama 3.2 (Ollama) |
| Embeddings | text-embedding-ada-002 (OpenAI) |
| Vector DB | ChromaDB |
| Data Source | SEC EDGAR / iXBRL |
| Backend | Python / FastAPI |
| Frontend | HTML / CSS / JS |
| Feedback Storage | Supabase |

## Coverage

**Companies:** NVDA · AMD · PLTR

**Filings:** 10-K (annual) and 10-Q (quarterly), FY2024

## Project Structure

```
techfilings/
├── backend/
│   ├── main.py                  # FastAPI app, API endpoints
│   ├── modules/
│   │   ├── parser/              # iXBRL parsing, table extraction, chunking
│   │   ├── retrieval/           # Embedding generation, ChromaDB vector search
│   │   └── generation/          # LLM answer generation, prompt construction
│   ├── prompts.py               # Prompt templates
│   └── data_storage.py         # Supabase feedback storage
└── frontend/
    ├── index.html               # Landing page
    ├── chat.html                # Chat interface
    ├── style.css                # Shared styles
    └── app.js                   # Chat logic, citation rendering
```

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) with `llama3.2` model pulled
- OpenAI API key (for embeddings)

### Installation

```bash
git clone https://github.com/TaraZSun/techfilings.git
cd techfilings
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in `backend/`:

```env
OPENAI_API_KEY=your_openai_key
SUPABASE_URL=your_supabase_url       # optional
SUPABASE_KEY=your_supabase_key       # optional
```

### Run

```bash
cd backend
uvicorn main:app --reload --port 8001
```

Serve the frontend via Live Server or any static file server, then open `frontend/index.html`.

## Example Queries

- "What was NVIDIA's R&D spend in FY2024?"
- "AMD gross margin trend across 2023–2024 quarterly filings"
- "Palantir revenue breakdown by segment"
- "What export control risks did NVIDIA disclose in their latest 10-K?"
- "How did AMD describe competition risks in their most recent 10-Q?"

## License

MIT