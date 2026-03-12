"""
TechFilings - RAG Evaluation
Evaluates numeric accuracy, faithfulness, and answer relevancy
using OpenAI as judge.

Usage:
    cd backend/
    python modules/evaluation/eval_qa.py
"""

import csv
import os
import sys
import re
import time
import json
from datetime import datetime
import yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend"))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.retriever import DocumentRetriever
from openai import OpenAI
from config import TOP_K, INPUT_CSV, OUTPUT_CSV, OPENAI_CHAT_MODEL
from dotenv import load_dotenv
load_dotenv()
_eval_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt", "eval_prompts.yaml")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ── Numeric overlap ────────────────────────────────────────────────────────────

def normalize_number(text: str) -> set[float]:
    """Convert numbers to millions for comparison: $25.8B → 25800, $25785M → 25785"""
    results = set()
    # Match patterns like $25.8 billion, $25785M, 73%, 1.5B etc.
    patterns = re.findall(
        r'\$?([\d,]+\.?\d*)\s*(billion|million|B|M|%)?',
        text, re.IGNORECASE
    )
    for num_str, unit in patterns:
        try:
            val = float(num_str.replace(",", ""))
            unit = (unit or "").lower()
            if unit in ("billion", "b"):
                val *= 1000  # convert to millions
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
    # Allow 2% tolerance for rounding differences
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


# ── OpenAI judge ───────────────────────────────────────────────────────────────

def llm_judge(question: str, answer: str, ground_truth: str, contexts: list[str]) -> dict:
    """Use gpt-4o-mini to evaluate faithfulness and answer relevancy."""
    context_str = "\n---\n".join(contexts[:3]) if contexts else "No context available"
    
    with open(_eval_path) as f:
        _eval_prompts = yaml.safe_load(f)
    JUDGE_PROMPT = _eval_prompts["judge_prompt"]
    prompt = JUDGE_PROMPT.format(
            question=question,
            context_str=context_str[:2000],
            answer=answer,
            ground_truth=ground_truth,
        )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        raw = response.choices[0].message.content.strip()
        scores = json.loads(raw)
        return {
            "faithfulness":     round(float(scores.get("faithfulness", 0)), 3),
            "answer_relevancy": round(float(scores.get("answer_relevancy", 0)), 3),
        }
    except Exception as e:
        print(f"    [!] LLM judge failed: {e}")
        return {"faithfulness": None, "answer_relevancy": None}


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
        contexts = [c.get("content", "") for c in result.get("citations", [])]
        n_overlap = numeric_overlap(answer, row["answer"])

        print(f"  ✓ RAG: {elapsed}s | sources: {result.get('num_sources', 0)} | numeric_overlap: {n_overlap}")

        # LLM judge
        scores = llm_judge(q, answer, row["answer"], contexts)
        print(f"  ✓ Judge: faithfulness={scores['faithfulness']} | relevancy={scores['answer_relevancy']}")

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
            "faithfulness":     scores["faithfulness"],
            "answer_relevancy": scores["answer_relevancy"],
            "latency_sec":      elapsed,
        })

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
        "judge_model":      "gpt-4o-mini",
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

    # ── Print summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"EVALUATION SUMMARY  ({total} questions)")
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