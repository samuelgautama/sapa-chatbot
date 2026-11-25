"""
Tests untuk L-18: Jawaban tetap untuk "cara klaim JHT" umum

Tujuan: pertanyaan umum tentang cara klaim JHT (termasuk "untuk PU"/"untuk BPU") 
dijawab dengan teks tetap yang menjelaskan tiga cara mengajukan klaim (bukan LLM).
"""

import pytest
from sapa.chatbot import _prepare_ask, CARA_KLAIM_JHT_UMUM_ANSWER


class FakeRetriever:
    """Retriever palsu untuk testing tanpa vector store."""
    def similarity_search_with_score(self, query, k=8):
        return []
    
    def invoke(self, query):
        """Fallback untuk retriever tanpa scoring."""
        return []


def test_exact_triggers_return_static_answer():
    """L-18(a): Semua variasi pemicu menghasilkan static_answer dengan marker khas."""
    retriever = FakeRetriever()
    
    exact_questions = [
        "cara klaim jht",
        "klaim jht",
        "bagaimana cara klaim jht",
        "gimana cara klaim jht",
        "cara mengajukan klaim jht",
        "prosedur klaim jht",
        "cara klaim jht untuk pu",
        "cara klaim jht untuk bpu",
        "cara klaim jht untuk penerima upah",
        "cara klaim jht untuk bukan penerima upah",
        "cara klaim jht pu",
        "cara klaim jht bpu",
        "cara klaim jht peserta pu",
        "cara klaim jht peserta bpu",
        # Dengan huruf besar
        "Cara Klaim JHT",
        "Bagaimana Cara Klaim JHT?",
        "Gimana Cara Klaim JHT untuk PU?",
        "CARA KLAIM JHT UNTUK BPU",
    ]
    
    for q in exact_questions:
        plan = _prepare_ask(q, retriever, history=None)
        assert plan.static_answer is not None, f"Harus ada static_answer untuk: {q}"
        assert "tiga cara" in plan.static_answer.lower(), f"Harus ada 'tiga cara' di jawaban untuk: {q}"
        assert "Tracking Klaim" in plan.static_answer, f"Harus ada 'Tracking Klaim' di jawaban untuk: {q}"


def test_non_triggers_do_not_return_static_answer():
    """L-18(b): Pertanyaan dengan detail tambahan TIDAK memicu jawaban tetap ini."""
    retriever = FakeRetriever()
    
    non_trigger_questions = [
        "Cara klaim JHT lewat JMO",  # Spesifik: harus gunakan L-16
        "Dokumen klaim JHT kalau resign",
        "Cara klaim JHT lewat Lapak Asik",
        "Cara klaim JHT lewat kantor cabang",
        "Saldo klaim JHT berapa?",
        "Berapa saldo JHT saya?",
        "Cara daftar BPU?",  # L-13
    ]
    
    for q in non_trigger_questions:
        plan = _prepare_ask(q, retriever, history=None)
        # Jika ada static_answer, tidak boleh jawaban cara klaim JHT umum
        if plan.static_answer:
            # Cek apakah ini bukan jawaban L-18 (harus NOT memiliki marker "tiga cara")
            is_l18 = "tiga cara" in plan.static_answer.lower() and "Tracking Klaim" in plan.static_answer
            if q.lower().startswith("cara klaim jht lewat jmo"):
                # Ini L-16, harus ada "3 centang hijau"
                assert "3 centang hijau" in plan.static_answer, f"Seharusnya L-16 untuk: {q}"
            elif q.lower().startswith("cara daftar bpu"):
                # Ini L-13, harus ada "Bukan Penerima Upah"
                assert "Bukan Penerima Upah" in plan.static_answer, f"Seharusnya L-13 untuk: {q}"
            else:
                # Pertanyaan lainnya sebaiknya NOT trigger L-18
                assert not is_l18, f"Tidak boleh trigger L-18 untuk: {q}"


def test_l16_jmo_still_works():
    """L-18(c): Jawaban L-16 (JMO) masih bekerja, tidak diganggu L-18."""
    retriever = FakeRetriever()
    
    # Pertanyaan spesifik JMO tetap memicu L-16
    plan = _prepare_ask("cara klaim JHT lewat JMO", retriever, history=None)
    assert plan.static_answer is not None
    assert "3 centang hijau" in plan.static_answer
    
    # Jangan sampai memicu L-18 marker
    assert not ("tiga cara" in plan.static_answer.lower() and "Aplikasi JMO" in plan.static_answer and "Lapak Asik" in plan.static_answer)


def test_l13_bpu_still_works():
    """L-18(d): Jawaban L-13 (BPU) masih bekerja, tidak diganggu L-18."""
    retriever = FakeRetriever()
    
    # Pertanyaan BPU tetap memicu L-13
    plan = _prepare_ask("cara daftar BPU", retriever, history=None)
    assert plan.static_answer is not None
    assert "Bukan Penerima Upah" in plan.static_answer
    
    # Jangan sampai memicu L-18 marker
    assert "tiga cara" not in plan.static_answer.lower()


def test_static_answer_content_complete():
    """L-18(e): Jawaban tetap lengkap mencakup tiga cara, tracking klaim, dan catatan BPU."""
    retriever = FakeRetriever()
    
    plan = _prepare_ask("cara klaim jht", retriever, history=None)
    assert plan.static_answer is not None
    
    # Harus ada judul
    assert "### Cara Klaim JHT" in plan.static_answer
    
    # Harus menyebutkan berlaku untuk PU dan BPU
    assert "Penerima Upah" in plan.static_answer or "PU" in plan.static_answer
    assert "BPU" in plan.static_answer
    
    # Harus ada tiga cara
    assert "1. **Aplikasi JMO**" in plan.static_answer
    assert "2. **Lapak Asik**" in plan.static_answer
    assert "3. **Kantor Cabang" in plan.static_answer
    
    # Harus ada link Lapak Asik
    assert "https://lapakasik.bpjsketenagakerjaan.go.id" in plan.static_answer
    
    # Harus ada tracking klaim
    assert "Tracking Klaim" in plan.static_answer
    assert "Cek Status Klaim" in plan.static_answer
    
    # Harus ada catatan BPU tentang masa tunggu
    assert "BPU" in plan.static_answer
    assert "masa tunggu 1 bulan" in plan.static_answer or "berhenti bekerja/usaha" in plan.static_answer


def test_exact_match_normalization():
    """L-18(f): Pemeriksaan exact match bekerja setelah normalisasi."""
    retriever = FakeRetriever()
    
    # Variasi dengan tanda baca dan spasi
    questions_should_match = [
        "cara klaim jht?",
        "Cara Klaim JHT!",
        "CARA  KLAIM  JHT",
        "cara  klaim  jht  untuk  pu?",
        "GIMANA CARA KLAIM JHT UNTUK BPU?",
        "Bagaimana Cara Klaim JHT untuk Penerima Upah??",
    ]
    
    for q in questions_should_match:
        plan = _prepare_ask(q, retriever, history=None)
        assert plan.static_answer is not None, f"Harus match (normalized): {q}"
        assert "tiga cara" in plan.static_answer.lower(), f"Harus ada 'tiga cara' untuk: {q}"


def test_sources_empty_for_static_answer():
    """L-18(g): Static answer tidak memiliki sources (bukan dari retrieval)."""
    retriever = FakeRetriever()
    
    plan = _prepare_ask("cara klaim jht untuk pu", retriever, history=None)
    assert plan.static_answer is not None
    assert plan.sources == [], f"Static answer harus tidak memiliki sources, got: {plan.sources}"

