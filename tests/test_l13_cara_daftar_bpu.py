"""
Tests untuk L-13: Jawaban tetap untuk "cara daftar BPU"

Tujuan: pertanyaan persis "cara daftar BPU" dijawab dengan teks tetap (bukan LLM)
agar tidak ada langkah karangan.
"""

import pytest
from sapa.chatbot import _prepare_ask, CARA_DAFTAR_BPU_ANSWER


class FakeRetriever:
    """Retriever palsu untuk testing tanpa vector store."""
    def similarity_search_with_score(self, query, k=8):
        return []
    
    def invoke(self, query):
        """Fallback untuk retriever tanpa scoring."""
        return []


def test_exact_triggers_return_static_answer():
    """L-13(a): Semua variasi pemicu menghasilkan static_answer dengan marker khas."""
    retriever = FakeRetriever()
    
    exact_questions = [
        "cara daftar BPU",
        "cara mendaftar BPU",
        "bagaimana cara daftar BPU",
        "bagaimana cara mendaftar BPU",
        "cara daftar peserta BPU",
        "gimana cara daftar BPU",
        "daftar BPU gimana",
        "daftar BPU bagaimana",
        # Dengan tanda baca
        "Cara daftar BPU?",
        "Bagaimana cara daftar BPU?",
        "Daftar BPU gimana?",
    ]
    
    for q in exact_questions:
        plan = _prepare_ask(q, retriever, history=None)
        assert plan.static_answer is not None, f"Harus ada static_answer untuk: {q}"
        assert "1×24 jam" in plan.static_answer, f"Harus ada '1×24 jam' di jawaban untuk: {q}"
        assert "Bukan Penerima Upah" in plan.static_answer, f"Harus ada 'Bukan Penerima Upah' di jawaban untuk: {q}"


def test_non_triggers_do_not_return_static_answer():
    """L-13(b): Pertanyaan yang mengandung topik lain TIDAK memicu jawaban tetap ini."""
    retriever = FakeRetriever()
    
    non_trigger_questions = [
        "Cara daftar JMO?",
        "Cara daftar BPU untuk ojol?",
        "Cara klaim JHT",
        "Syarat daftar BPU",
        "Dokumen daftar BPU",
        "Berapa iuran BPU?",
        "Apa itu BPU?",
        "BPU ikut program apa?",
    ]
    
    for q in non_trigger_questions:
        plan = _prepare_ask(q, retriever, history=None)
        # Jika ada static_answer, tidak boleh jawaban cara daftar BPU
        if plan.static_answer:
            assert "1×24 jam" not in plan.static_answer or "mahasiswa magang" not in plan.static_answer, \
                f"Tidak boleh trigger jawaban daftar BPU untuk: {q}"


def test_slot_filling_still_works():
    """L-13(c): Nominal/slot-filling tetap berjalan seperti sebelumnya."""
    retriever = FakeRetriever()
    
    # Slot filling: nominal tanpa kata tanya
    plan = _prepare_ask("Penghasilan 2 juta", retriever, history=None)
    assert plan.static_answer is not None, "Harus ada konfirmasi slot"
    assert "2.000.000" in plan.static_answer or "2 juta" in plan.static_answer
    
    # Ambiguous nominal masih terdeteksi
    plan = _prepare_ask("Penghasilan 1 juta 500", retriever, history=None)
    assert plan.static_answer is not None, "Harus ada klarifikasi nominal ambigu"
    assert "1 juta 500" in plan.static_answer or "1.000.500" in plan.static_answer


def test_static_answer_content_complete():
    """L-13(d): Jawaban tetap lengkap mencakup mahasiswa magang dan kanal lain."""
    retriever = FakeRetriever()
    
    plan = _prepare_ask("cara daftar BPU", retriever, history=None)
    assert plan.static_answer is not None
    
    # Harus ada langkah lewat mahasiswa magang
    assert "mahasiswa magang" in plan.static_answer.lower()
    assert "Formulir" in plan.static_answer
    assert "1×24 jam" in plan.static_answer
    
    # Harus menyebut kanal lain
    assert "JMO" in plan.static_answer or "Jamsostek Mobile" in plan.static_answer
    assert "website" in plan.static_answer.lower() or "kanal pendaftaran lain" in plan.static_answer.lower()
    
    # Harus ada catatan program
    assert "JKK" in plan.static_answer and "JKM" in plan.static_answer and "JHT" in plan.static_answer
