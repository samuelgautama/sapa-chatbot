"""
evaluate.py
-----------
Evaluation harness untuk Asisten Akuisisi BPU.

Menjalankan evaluasi:
1. Retrieval hit@k berdasarkan sumber/section yang diharapkan dan pipeline reranking tahap 8.
2. Fallback gate untuk pertanyaan di luar domain.
3. Privacy guard untuk penyensoran data sensitif.
4. Deterministic calculator untuk angka iuran.
5. (Opsional) answer generation smoke test dengan LLM melalui --with-llm.

Contoh:
    python evaluate.py
    python evaluate.py --dataset evaluation_dataset.json
    python evaluate.py --with-llm

Catatan:
- Retrieval evaluation membutuhkan vector_store yang sudah dibuat lewat ingest.py.
- LLM answer evaluation bersifat smoke test; evaluasi semantik mendalam tetap perlu
  review manusia atau evaluator terpisah.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from calculator import calculate_bpu_contribution, extract_base_income, extract_programs, detect_discount_request, detect_sector, promo_status
from privacy_guard import sanitize_user_input

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "evaluation_dataset.json"
RESULTS_PATH = ROOT / "evaluation_results.json"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _metadata_matches(doc: Any, expected: dict[str, str]) -> bool:
    metadata = getattr(doc, "metadata", {}) or {}
    filename = Path(str(metadata.get("source_file", metadata.get("source", "")))).name
    source_name = str(metadata.get("source_name", ""))
    section = str(metadata.get("section", ""))

    file_ok = filename == expected.get("file", filename) if expected.get("file") else True
    section_needle = expected.get("section_contains")
    section_ok = section_needle.lower() in section.lower() if section_needle else True

    # Fallback untuk index lama tanpa metadata section: cari di page_content.
    if section_needle and not section_ok:
        content = str(getattr(doc, "page_content", ""))
        section_ok = section_needle.lower() in content.lower()

    return file_ok and section_ok and bool(source_name or filename or section)


def retrieval_test_case(case: dict[str, Any], retriever: Any, top_k: int) -> dict[str, Any]:
    from chatbot import retrieve_documents

    question = case["question"]
    history = case.get("history", [])
    docs, retrieval_query, retrieval_details = retrieve_documents(
        question,
        retriever,
        history=history,
    )

    expected_sources = case.get("expected_sources", [])

    def matches(doc: Any) -> bool:
        return any(_metadata_matches(doc, expected) for expected in expected_sources) if expected_sources else True

    # Evaluasi dilakukan pada dokumen yang benar-benar akan dipakai chatbot, bukan retriever mentah.
    hit_at_1 = bool(docs and matches(docs[0]))
    hit_at_3 = any(matches(doc) for doc in docs[:3])

    reciprocal_rank = 0.0
    for index, doc in enumerate(docs, start=1):
        if matches(doc):
            reciprocal_rank = 1.0 / index
            break

    return {
        "id": case["id"],
        "question": question,
        "retrieval_query": retrieval_query,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "reciprocal_rank": reciprocal_rank,
        "top_k": top_k,
        "retrieval_details": retrieval_details,
        "retrieved": [
            {
                "rank": index,
                "source_file": (getattr(doc, "metadata", {}) or {}).get("source_file"),
                "source_name": (getattr(doc, "metadata", {}) or {}).get("source_name"),
                "section": (getattr(doc, "metadata", {}) or {}).get("section"),
                "section_id": (getattr(doc, "metadata", {}) or {}).get("section_id"),
                "chunk_index": (getattr(doc, "metadata", {}) or {}).get("chunk_index"),
                "content_preview": str(getattr(doc, "page_content", ""))[:160].replace("\n", " "),
            }
            for index, doc in enumerate(docs, start=1)
        ],
    }

def privacy_test_case(case: dict[str, Any]) -> dict[str, Any]:
    result = sanitize_user_input(case["question"])
    # Data-sensitive tests must redact at least one pattern and must preserve ordinary money values.
    passed = bool(result.redacted) if case.get("expected_privacy_redaction") else not result.redacted
    return {
        "id": case["id"],
        "question": case["question"],
        "passed": passed,
        "redacted": result.redacted,
        "sanitized_text": result.text,
    }


def calculator_test_case(case: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected_calculation"]
    income = extract_base_income(case["question"])
    programs = extract_programs(case["question"])

    # Promo test only applies the discount when the deterministic domain rule says it is eligible.
    discount = False
    if detect_discount_request(case["question"]):
        sector = detect_sector(case["question"])
        _, discount = promo_status(sector=sector)

    errors: list[str] = []
    if income != expected["income"]:
        errors.append(f"income={income}, expected={expected['income']}")
    if tuple(programs) != tuple(expected["programs"]):
        errors.append(f"programs={programs}, expected={tuple(expected['programs'])}")

    if income is not None:
        result = calculate_bpu_contribution(income, programs, discount_jkk_jkm=discount)
        if result.total != expected["total"]:
            errors.append(f"total={result.total}, expected={expected['total']}")
        if bool(discount) != bool(expected["discount"]):
            errors.append(f"discount={discount}, expected={expected['discount']}")
        actual = result.as_dict()
    else:
        actual = None

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": not errors,
        "errors": errors,
        "actual": actual,
        "expected": expected,
    }


def fallback_test_case(case: dict[str, Any], retriever: Any, min_score: float) -> dict[str, Any]:
    # Menguji behavior yang sama seperti tahap 4 tanpa memanggil LLM.
    try:
        scored = retriever.similarity_search_with_relevance_scores(case["question"], k=5)
    except (AttributeError, TypeError):
        return {
            "id": case["id"],
            "question": case["question"],
            "passed": False,
            "reason": "Retriever tidak menyediakan similarity_search_with_relevance_scores; fallback gate tidak dapat diverifikasi.",
        }

    normalized = [(doc, float(score)) for doc, score in scored if not math.isnan(float(score))]
    best_score = max((score for _, score in normalized), default=None)
    would_fallback = best_score is None or best_score < min_score

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": would_fallback,
        "best_score": best_score,
        "threshold": min_score,
        "would_fallback": would_fallback,
    }


def answer_smoke_test(cases: list[dict[str, Any]], retriever: Any, llm: Any) -> list[dict[str, Any]]:
    from chatbot import ask

    results = []
    for case in cases:
        if case.get("category") not in {"retrieval", "context"}:
            continue
        history = case.get("history", [])
        answer, sources = ask(case["question"], retriever, llm, history=history)
        answer_lower = answer.lower()
        keyword_hits = [k for k in case.get("expected_keywords", []) if k.lower() in answer_lower]
        keyword_pass = len(keyword_hits) == len(case.get("expected_keywords", []))
        results.append({
            "id": case["id"],
            "question": case["question"],
            "keyword_pass": keyword_pass,
            "keyword_hits": keyword_hits,
            "expected_keywords": case.get("expected_keywords", []),
            "answer_preview": answer[:800],
            "source_count": len(sources),
        })
    return results


def summarize(section: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if not section:
        return {"total": 0, "passed": 0, "rate": None}
    passed = sum(1 for item in section if item.get(key))
    return {"total": len(section), "passed": passed, "rate": round(passed / len(section), 4)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Asisten Akuisisi BPU")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.30)
    parser.add_argument("--with-llm", action="store_true", help="Run smoke tests through the configured LLM")
    args = parser.parse_args()

    dataset = load_dataset(Path(args.dataset))
    results: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "dataset": str(Path(args.dataset).resolve()),
        "top_k": args.top_k,
        "min_score": args.min_score,
        "retrieval": [],
        "privacy": [],
        "calculator": [],
        "fallback": [],
        "answer_smoke": [],
    }

    # Unit-like tests that do not require external model/index.
    for case in dataset:
        if case.get("category") == "privacy":
            results["privacy"].append(privacy_test_case(case))
        elif case.get("category") == "calculator":
            results["calculator"].append(calculator_test_case(case))

    retrieval_cases = [c for c in dataset if c.get("category") in {"retrieval", "context"}]
    fallback_cases = [c for c in dataset if c.get("category") == "fallback"]

    vector_store_path = ROOT / "vector_store"
    retriever = None
    llm = None

    if retrieval_cases or fallback_cases or args.with_llm:
        try:
            from chatbot import load_retriever, load_llm
            retriever = load_retriever()
        except Exception as exc:
            results["environment_error"] = f"Tidak dapat memuat retriever/vector_store: {exc}"
            retriever = None

    if retriever is not None:
        for case in retrieval_cases:
            results["retrieval"].append(retrieval_test_case(case, retriever, args.top_k))
        for case in fallback_cases:
            results["fallback"].append(fallback_test_case(case, retriever, args.min_score))

        if args.with_llm:
            try:
                llm = load_llm()
                results["answer_smoke"] = answer_smoke_test(dataset, retriever, llm)
            except Exception as exc:
                results["llm_error"] = f"Tidak dapat menjalankan LLM smoke test: {exc}"

    results["summary"] = {
        "retrieval_hit_at_1": summarize(results["retrieval"], "hit_at_1"),
        "retrieval_hit_at_3": summarize(results["retrieval"], "hit_at_3"),
        "retrieval_mrr": (
            round(sum(item["reciprocal_rank"] for item in results["retrieval"]) / len(results["retrieval"]), 4)
            if results["retrieval"] else None
        ),
        "privacy": summarize(results["privacy"], "passed"),
        "calculator": summarize(results["calculator"], "passed"),
        "fallback": summarize(results["fallback"], "passed"),
        "answer_smoke": summarize(results["answer_smoke"], "keyword_pass"),
    }

    with RESULTS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print("=" * 72)
    print("ASISTEN AKUISISI BPU — EVALUATION REPORT")
    print("=" * 72)
    print(json.dumps(results["summary"], ensure_ascii=False, indent=2))
    print(f"\nHasil lengkap: {RESULTS_PATH}")

    if "environment_error" in results:
        print("\nPERINGATAN:", results["environment_error"])
        print("Jalankan `python ingest.py` terlebih dahulu untuk membuat vector_store.")

    # Exit non-zero hanya untuk deterministic unit tests yang gagal.
    deterministic_failed = any(not x["passed"] for x in results["privacy"] + results["calculator"])
    return 1 if deterministic_failed else 0


if __name__ == "__main__":
    sys.exit(main())
