"""
Tests untuk L-16: Jawaban tetap untuk "cara klaim JHT lewat JMO"

Tujuan: pertanyaan persis tentang cara klaim JHT lewat JMO dijawab dengan teks tetap (bukan LLM).
"""

import pytest
from sapa.chatbot import _prepare_ask, CARA_KLAIM_JHT_JMO_ANSWER


class FakeRetriever:
    """Retriever palsu untuk testing tanpa vector store."""
    def similarity_search_with_score(self, query, k=8):
        return []
    
    def invoke(self, query):
        """Fallback untuk retriever tanpa scoring."""
        return []


def test_exact_triggers_return_static_answer():
    """L-16(a): Semua variasi pemicu menghasilkan static_answer dengan marker khas."""
    retriever = FakeRetriever()
    
    exact_questions = [
        "cara klaim JHT lewat JMO",
        "cara klaim JHT di JMO",
        "cara klaim JHT via JMO",
        "cara klaim JHT lewat aplikasi JMO",
        "bagaimana cara klaim JHT lewat JMO",
        "gimana cara klaim JHT lewat JMO",
        "langkah klaim JHT lewat JMO",
        "klaim JHT lewat JMO",
        "klaim JHT di JMO",
        # Dengan tanda baca
        "Cara klaim JHT lewat JMO?",
        "Bagaimana cara klaim JHT lewat JMO?",
    ]
    
    for q in exact_questions:
        plan = _prepare_ask(q, retriever, history=None)
        assert plan.static_answer is not None, f"Harus ada static_answer untuk: {q}"
        assert "3 centang hijau" in plan.static_answer, f"Harus ada '3 centang hijau' di jawaban untuk: {q}"
        assert "Tracking Klaim" in plan.static_answer, f"Harus ada 'Tracking Klaim' di jawaban untuk: {q}"


def test_non_triggers_do_not_return_static_answer():
    """L-16(b): Pertanyaan dengan detail tambahan atau topik lain TIDAK memicu jawaban tetap ini."""
    retriever = FakeRetriever()
    
    non_trigger_questions = [
        "Cara klaim JHT lewat JMO kalau saldo saya Rp15 juta?",
        "Dokumen klaim JHT resign",
        "Cara klaim JHT lewat Lapak Asik",
        "Cara klaim JHT lewat kantor cabang",
        "Cara klaim JHT",
        "Cara daftar JMO?",
        "Cara daftar BPU?",
    ]
    
    for q in non_trigger_questions:
        plan = _prepare_ask(q, retriever, history=None)
        # Jika ada static_answer, tidak boleh jawaban cara klaim JHT lewat JMO
        if plan.static_answer:
            assert "3 centang hijau" not in plan.static_answer or "Tracking Klaim" not in plan.static_answer, \
                f"Tidak boleh trigger jawaban klaim JHT JMO untuk: {q}"


def test_l13_bpu_still_works():
    """L-16(c): Jawaban tetap BPU (L-13) tetap bekerja dan tidak dibajak oleh L-16."""
    retriever = FakeRetriever()
    
    # Pertanyaan BPU tetap memicu jawaban BPU
    plan = _prepare_ask("cara daftar BPU", retriever, history=None)
    assert plan.static_answer is not None
    assert "Bukan Penerima Upah" in plan.static_answer
    assert "1×24 jam" in plan.static_answer
    
    # Jangan sampai memicu jawaban klaim JHT
    if plan.static_answer:
        assert "3 centang hijau" not in plan.static_answer


def test_static_answer_content_complete():
    """L-16(d): Jawaban tetap lengkap mencakup syarat, langkah, dan catatan."""
    retriever = FakeRetriever()
    
    plan = _prepare_ask("cara klaim JHT lewat JMO", retriever, history=None)
    assert plan.static_answer is not None
    
    # Harus ada syarat klaim
    assert "Rp15.000.000" in plan.static_answer
    assert "mengundurkan diri" in plan.static_answer.lower() or "PHK" in plan.static_answer
    assert "pengkinian data" in plan.static_answer
    
    # Harus ada 9 langkah
    assert "Langkah:" in plan.static_answer or "**Langkah:**" in plan.static_answer
    assert "1. Buka JMO" in plan.static_answer
    assert "9. Muncul layar Berhasil" in plan.static_answer
    
    # Harus ada catatan fallback
    assert "Lapak Asik" in plan.static_answer or "kantor cabang" in plan.static_answer.lower()
