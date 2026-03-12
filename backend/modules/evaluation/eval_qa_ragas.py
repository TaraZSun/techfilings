"""
TechFilings - RAG Evaluation (RAGAS version)
Evaluates numeric accuracy, faithfulness, and answer relevancy
using RAGAS as judge instead of raw OpenAI.

Install:
    pip install ragas

Usage:
    cd backend/
    python modules/evaluation/eval_qa_ragas.py
"""

import csv
import os
import sys
import re
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend"))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.retriever import DocumentRetriever
from config import TOP_K, INPUT_CSV, OUTPUT_CSV, OPENAI_CHAT_MODEL
from dotenv import load_dotenv
load_dotenv()

# ── RAGAS imports ──────────────────────────────────────────────────────────────
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from datasets import Dataset

# ── Numeric overlap (unchanged from original) ──────────────────────────────────

def normalize_number(text: str) -> set[float]:
    """Convert numbers to millions for comparison: $25.8B → 25800, $25785M → 25785"""
    results = set()
    patterns = re.findall(
        r'\$?([\d,]+\.?\d*)\s*(billion|million|B|M|%)?',
        text, re.IGNORECASE
    )
    for num_str, unit in patterns:
        try:
            val = float(num_str.replace(",", ""))
            unit = (unit or "").lower()
            if unit in ("billion", "b"):
                val *= 1000
            elif unit == "%":
                val = round(val, 1)
            results.add(round(val, 1))
        except ValueError:
            continue
    return results


def numeric_overlap(predicted: str, expected: str) -> float:
    exp_nums = normalize_number(expected)
    if not exp_nums:
        return 1.0
    pred_nums = normalize_number(predicted)
    matched = 0
    for e in exp_nums:
        for p in pred_nums:
            if e == 0 and p == 0:
                matched += 1
                break
            elif e != 0 and abs(e - p) / abs(e) < 0.02:
                matched += 1
                break
    return round(matched / len(exp_nums), 3)


# ── Helpers ────────────────────────────────────────────────────────────────────

def avg(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


# ── Main eval loop ─────────────────────────────────────────────────────────────

def run_eval():
    retriever = DocumentRetriever()

    with open(INPUT_CSV, "r") as f:
        questions = list(csv.DictReader(f))

    total = len(questions)
    print(f"Loaded {total} questions from {INPUT_CSV}")
    print(f"Starting evaluation at {datetime.now().strftime('%H:%M:%S')}\n")
    print("-" * 60)

    result_rows = []

    # Accumulate data for RAGAS batch evaluation
    ragas_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    # ── Step 1: Run retriever for all questions ────────────────────────────────
    for i, row in enumerate(questions):
        q              = row["question"]
        company        = row["company"]
        filter_company = None if "/" in company else company

        print(f"[{i+1}/{total}] {q[:70]}...")
        t0 = time.time()

        result = retriever.retrieve_and_answer(
            query=q,
            top_k=TOP_K,
            filter_company=filter_company,
        )

        elapsed  = round(time.time() - t0, 2)
        answer   = result["answer"]
        # RAGAS expects contexts as list[str] — use text field from citations
        contexts = [c.get("text", c.get("content", "")) for c in result.get("citations", [])]
        n_overlap = numeric_overlap(answer, row["answer"])

        print(f"  ✓ RAG: {elapsed}s | sources: {result.get('num_sources', 0)} | numeric_overlap: {n_overlap}")

        result_rows.append({
            "question":         q,
            "company":          company,
            "question_type":    row["question_type"],
            "expected_answer":  row["answer"],
            "system_answer":    answer,
            "num_sources":      result.get("num_sources", 0),
            "sources": ", ".join([
                f"{c.get('company','')} {c.get('form_type','')} {c.get('period','')}"
                for c in result.get("citations", [])
            ]),
            "numeric_overlap":  n_overlap,
            "faithfulness":     None,
            "answer_relevancy": None,
            "latency_sec":      elapsed,
        })

        ragas_data["question"].append(q)
        ragas_data["answer"].append(answer)
        ragas_data["contexts"].append(contexts if contexts else [""])
        ragas_data["ground_truth"].append(row["answer"])

    # ── Step 2: RAGAS batch evaluation ────────────────────────────────────────
    print(f"\nRunning RAGAS evaluation on {total} samples...")

    dataset = Dataset.from_dict(ragas_data)

    # Configure RAGAS to use the same OpenAI model
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    ragas_result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )

    # ragas_result.to_pandas() gives per-sample scores
    scores_df = ragas_result.to_pandas()

    for i, row in enumerate(result_rows):
        row["faithfulness"]     = round(float(scores_df.iloc[i]["faithfulness"]), 3)
        row["answer_relevancy"] = round(float(scores_df.iloc[i]["answer_relevancy"]), 3)
        print(f"  [{i+1}] faithfulness={row['faithfulness']} | relevancy={row['answer_relevancy']}")

    # ── Save CSV ───────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result_rows[0].keys())
        writer.writeheader()
        writer.writerows(result_rows)

    # ── Build + save JSON summary ──────────────────────────────────────────────
    types = sorted(set(r["question_type"] for r in result_rows))
    by_type = {}
    for qt in types:
        subset = [r for r in result_rows if r["question_type"] == qt]
        by_type[qt] = {
            "n":                len(subset),
            "numeric_overlap":  avg(subset, "numeric_overlap"),
            "faithfulness":     avg(subset, "faithfulness"),
            "answer_relevancy": avg(subset, "answer_relevancy"),
            "avg_latency_sec":  avg(subset, "latency_sec"),
        }

    summary = {
        "timestamp":        datetime.now().isoformat(),
        "model":            OPENAI_CHAT_MODEL,
        "judge":            "ragas (faithfulness + answer_relevancy)",
        "judge_llm":        "gpt-4o-mini",
        "judge_embeddings": "text-embedding-3-small",
        "total_questions":  total,
        "top_k":            TOP_K,
        "metrics": {
            "numeric_overlap":  avg(result_rows, "numeric_overlap"),
            "faithfulness":     avg(result_rows, "faithfulness"),
            "answer_relevancy": avg(result_rows, "answer_relevancy"),
            "avg_latency_sec":  avg(result_rows, "latency_sec"),
        },
        "by_question_type": by_type,
    }

    json_path = OUTPUT_CSV.replace(".csv", "_ragas.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    # ── Print summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"EVALUATION SUMMARY — RAGAS  ({total} questions)")
    print(f"{'='*60}")
    m = summary["metrics"]
    print(f"  Numeric Overlap    : {m['numeric_overlap']}")
    print(f"  Faithfulness       : {m['faithfulness']}")
    print(f"  Answer Relevancy   : {m['answer_relevancy']}")
    print(f"  Avg Latency (sec)  : {m['avg_latency_sec']}")
    print(f"\n  By question type:")
    for qt, bm in by_type.items():
        print(f"    {qt:<15} n={bm['n']}  numeric_overlap={bm['numeric_overlap']}  faithfulness={bm['faithfulness']}  relevancy={bm['answer_relevancy']}")
    print(f"\nCSV  → {OUTPUT_CSV}")
    print(f"JSON → {json_path}")


if __name__ == "__main__":
    run_eval()