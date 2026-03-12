"""
TechFilings - RAG Evaluation with RAGAS
Evaluates Faithfulness, Answer Relevancy, and numeric accuracy
against a golden dataset (sample_qa_v2.csv).

Usage:
    cd backend/
    python modules/evaluation/eval_ragas.py

Requirements:
    pip install ragas datasets
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

# from ragas import evaluate
# from ragas.metrics import faithfulness, answer_relevancy
# from datasets import Dataset
from config import TOP_K, INPUT_CSV, OUTPUT_CSV, OPENAI_CHAT_MODEL


def extract_numbers(text: str) -> set[str]:
    raw = re.findall(r'\$[\d,.]+\s*(?:billion|million|B|M)?|\b\d+(?:\.\d+)?\s*(?:billion|million|%)', text, re.IGNORECASE)
    return set(r.strip().lower() for r in raw)


def numeric_overlap(predicted: str, expected: str) -> float:
    exp_nums = extract_numbers(expected)
    if not exp_nums:
        return 1.0
    pred_nums = extract_numbers(predicted)
    return len(exp_nums & pred_nums) / len(exp_nums)


def avg(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def run_eval():
    retriever = DocumentRetriever()

    with open(INPUT_CSV, "r") as f:
        questions = list(csv.DictReader(f))

    total = len(questions)
    print(f"Loaded {total} questions from {INPUT_CSV}")
    print(f"Starting evaluation at {datetime.now().strftime('%H:%M:%S')}\n")
    print("-" * 60)

    ragas_rows  = []
    result_rows = []

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

        elapsed   = round(time.time() - t0, 2)
        answer    = result["answer"]
        contexts  = [c.get("content", "") for c in result.get("citations", [])]
        n_overlap = round(numeric_overlap(answer, row["answer"]), 3)

        print(f"  ✓ {elapsed}s | sources: {result.get('num_sources', 0)} | numeric_overlap: {n_overlap}")

        ragas_rows.append({
            "question":     q,
            "answer":       answer,
            "contexts":     contexts if contexts else [""],
            "ground_truth": row["answer"],
        })

        result_rows.append({
            "question":        q,
            "company":         company,
            "question_type":   row["question_type"],
            "expected_answer": row["answer"],
            "system_answer":   answer,
            "num_sources":     result.get("num_sources", 0),
            "sources": ", ".join([
                f"{c.get('company','')} {c.get('form_type','')} {c.get('period','')}"
                for c in result.get("citations", [])
            ]),
            "numeric_overlap": n_overlap,
            "latency_sec":     elapsed,
            "faithfulness":    None,
            "answer_relevancy": None,
        })

    # # RAGAS scoring
    # print("\n" + "-" * 60)
    # print("Running RAGAS evaluation (faithfulness + answer_relevancy)...")
    # print("This may take a few minutes...\n")
    # dataset = Dataset.from_list(ragas_rows)

    # try:
    #     ragas_result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
    #     ragas_df     = ragas_result.to_pandas()
    #     for i, row in enumerate(result_rows):
    #         row["faithfulness"]     = round(float(ragas_df.loc[i, "faithfulness"]), 3)
    #         row["answer_relevancy"] = round(float(ragas_df.loc[i, "answer_relevancy"]), 3)
    #         print(f"  [{i+1}/{total}] faithfulness={row['faithfulness']} | relevancy={row['answer_relevancy']}")
    # except Exception as e:
    #     print(f"RAGAS scoring failed: {e}")
    # RAGAS skipped - run separately
    for row in result_rows:
        row["faithfulness"]     = None
        row["answer_relevancy"] = None
    # Save CSV
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result_rows[0].keys())
        writer.writeheader()
        writer.writerows(result_rows)

    # Build + save JSON summary
    types  = sorted(set(r["question_type"] for r in result_rows))
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

    json_path = OUTPUT_CSV.replace(".csv", ".json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

  
    print(f"EVALUATION SUMMARY  ({total} questions)")
    m = summary["metrics"]
    print(f"  Numeric Overlap    : {m['numeric_overlap']}")
    print(f"  Faithfulness       : {m['faithfulness']}")
    print(f"  Answer Relevancy   : {m['answer_relevancy']}")
    print(f"  Avg Latency (sec)  : {m['avg_latency_sec']}")
    print(f"\n  By question type:")
    for qt, bm in by_type.items():
        print(f"    {qt:<15} n={bm['n']}  numeric_overlap={bm['numeric_overlap']}  faithfulness={bm['faithfulness']}")
    print(f"\nCSV  → {OUTPUT_CSV}")
    print(f"JSON → {json_path}")


if __name__ == "__main__":
    run_eval()