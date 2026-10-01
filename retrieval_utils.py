"""
retrieval_utils.py
------------------
Helper murni-Python untuk retrieval tahap 8.

Fokus:
- query expansion hanya saat pertanyaan benar-benar bergantung pada konteks sebelumnya;
- lexical reranking ringan di atas semantic retrieval;
- diversifikasi hasil agar tidak seluruh TOP_K berasal dari chunk yang hampir sama.

Modul ini sengaja tidak mengimpor LangChain sehingga dapat diuji secara lokal tanpa
model embedding/vector store.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


DEFAULT_HISTORY_MESSAGE_LIMIT = 4
DEFAULT_MAX_CHUNKS_PER_SECTION = 2

# Stopword minimal untuk Bahasa Indonesia. Tidak ditujukan sebagai linguistic parser,
# hanya untuk mengurangi bobot kata fungsi ketika melakukan lexical overlap.
STOPWORDS = {
    "yang", "dan", "atau", "di", "ke", "dari", "untuk", "dengan", "pada", "dalam",
    "apa", "apakah", "berapa", "bagaimana", "bisa", "saya", "kami", "kamu", "ini",
    "itu", "ada", "jadi", "agar", "sebagai", "dapat", "akan", "nya", "ya", "kah",
    "saja", "lebih", "sudah", "belum", "jika", "kalau", "tentang", "dengan", "secara",
}

CONTEXT_DEPENDENT_PATTERNS = (
    r"\byang tadi\b",
    r"\btersebut\b",
    r"\bdi atas\b",
    r"\bsebelumnya\b",
    r"\bsetelah itu\b",
    r"\bkalau yang\b",
    r"\bkalau\b",
    r"\bkalau begitu\b",
    r"\bbagaimana dengan\b",
    r"\bberikutnya\b",
    r"\blalu\b",
    r"\bkemudian\b",
    r"\bselanjutnya\b",
    r"\b3 program\b",
    r"\b2 program\b",
)


def normalize_tokens(text: str) -> set[str]:
    """Mengubah teks menjadi token sederhana yang cukup stabil untuk Bahasa Indonesia."""
    raw_tokens = re.findall(r"\b[\w%]+\b", (text or "").lower(), flags=re.UNICODE)
    return {
        token
        for token in raw_tokens
        if (len(token) >= 2 or any(ch.isdigit() for ch in token)) and token not in STOPWORDS
    }


def needs_history_for_retrieval(question: str) -> bool:
    """Menentukan apakah query retrieval perlu konteks pertanyaan user sebelumnya."""
    normalized = (question or "").lower().strip()
    if not normalized:
        return False

    if any(re.search(pattern, normalized) for pattern in CONTEXT_DEPENDENT_PATTERNS):
        return True

    # Pertanyaan sangat pendek hanya memakai history bila bentuknya memang seperti
    # follow-up, bukan sekadar karena jumlah karakternya sedikit.
    first_word = normalized.split(maxsplit=1)[0] if normalized.split() else ""
    return len(normalized) <= 30 and first_word in {"dan", "terus", "lalu", "kemudian", "berikutnya"}


def build_retrieval_query(
    question: str,
    history: Iterable[dict[str, Any]] | None,
    max_history_messages: int = DEFAULT_HISTORY_MESSAGE_LIMIT,
) -> str:
    """Membuat query retrieval yang tidak mencampurkan history pada pertanyaan mandiri."""
    question = (question or "").strip()
    if not history or not needs_history_for_retrieval(question):
        return question

    recent = list(history)[-max_history_messages:]
    previous_user_questions = [
        str(message.get("content", "")).strip()
        for message in recent
        if isinstance(message, dict)
        and message.get("role") == "user"
        and str(message.get("content", "")).strip()
    ]

    if not previous_user_questions:
        return question

    previous = previous_user_questions[-1]
    return f"Konteks pertanyaan sebelumnya: {previous}\nPertanyaan lanjutan: {question}"


def lexical_overlap_score(query: str, document: Any) -> float:
    """Mengukur overlap token query terhadap section + isi dokumen, rentang 0-1."""
    query_tokens = normalize_tokens(query)
    if not query_tokens:
        return 0.0

    metadata = getattr(document, "metadata", {}) or {}
    section = str(metadata.get("section", ""))
    content = str(getattr(document, "page_content", ""))
    document_tokens = normalize_tokens(f"{section} {content}")

    if not document_tokens:
        return 0.0

    return len(query_tokens & document_tokens) / len(query_tokens)


def rerank_scored_documents(
    query: str,
    scored_documents: Iterable[tuple[Any, float | None]],
    *,
    top_k: int = 3,
    max_chunks_per_section: int = DEFAULT_MAX_CHUNKS_PER_SECTION,
) -> list[tuple[Any, float, float, float | None]]:
    """Rerank kandidat dengan semantic score + lexical overlap lalu diversifikasi per section.

    Return tuple: (document, combined_score, lexical_score, semantic_score).
    Semantic score tetap dipertahankan terpisah karena dipakai sebagai confidence gate.
    """
    candidates = []
    for order, (document, semantic_score) in enumerate(scored_documents):
        lexical_score = lexical_overlap_score(query, document)
        if semantic_score is None:
            combined_score = lexical_score
        else:
            # Clamp hanya untuk mencegah nilai aneh dari backend/vector metric tertentu.
            semantic_normalized = max(0.0, min(1.0, float(semantic_score)))
            combined_score = (0.75 * semantic_normalized) + (0.25 * lexical_score)

        candidates.append((document, combined_score, lexical_score, semantic_score, order))

    candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)

    selected: list[tuple[Any, float, float, float | None]] = []
    section_counts: dict[str, int] = {}

    # Pass 1: diversifikasi berdasarkan section.
    for document, combined, lexical, semantic, _order in candidates:
        metadata = getattr(document, "metadata", {}) or {}
        section_key = str(
            metadata.get("section_id")
            or metadata.get("section")
            or metadata.get("source_file")
            or "unknown"
        )
        if section_counts.get(section_key, 0) >= max_chunks_per_section:
            continue

        selected.append((document, combined, lexical, semantic))
        section_counts[section_key] = section_counts.get(section_key, 0) + 1
        if len(selected) >= top_k:
            break

    # Pass 2: isi slot jika semua kandidat berada pada section yang sama.
    if len(selected) < top_k:
        selected_ids = {id(item[0]) for item in selected}
        for document, combined, lexical, semantic, _order in candidates:
            if id(document) in selected_ids:
                continue
            selected.append((document, combined, lexical, semantic))
            if len(selected) >= top_k:
                break

    return selected
