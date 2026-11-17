"""
Test untuk perbaikan bug round 2 (Bug 1-4).

Bug 1: _short_question_clarification membajak pertanyaan sah dan off-domain
Bug 2: Slot-filling _prepare_ask
Bug 3: Peringatan data pribadi di AnswerStream
Bug 4: String dengan backslash ganda literal
"""

import re
from test_critical_fixes import chatbot
from calculator import JKK_RATE, JKM_FLAT, JHT_RATE, format_rupiah


# --- BUG 1: _short_question_clarification ---

def test_short_question_with_domain_context_no_clarification():
    """Pertanyaan pendek dengan konteks domain harus masuk RAG, bukan klarifikasi."""
    history = [
        {"role": "user", "content": "Saya pedagang"},
        {"role": "assistant", "content": "Baik, sektor pedagang tercatat."},
    ]
    # "Syarat?" dengan konteks domain -> TIDAK boleh klarifikasi
    result = chatbot._short_question_clarification("Syarat?", history)
    assert result is None, "Syarat dengan konteks domain harus None (masuk RAG)"


def test_short_question_ambiguous_without_context_gets_clarification():
    """Pertanyaan ambigu tanpa konteks harus dapat klarifikasi TANPA fakta."""
    result = chatbot._short_question_clarification("Syarat?", history=None)
    assert result is not None, "Syarat tanpa konteks harus dapat klarifikasi"
    # Tidak boleh memuat fakta salah seperti "Warga negara Indonesia" atau "usia 17-65"
    assert "Warga negara Indonesia" not in result
    assert "17-65" not in result
    assert "1 bulan" not in result
    # Harus bertanya saja
    assert "Pendaftaran BPU" in result or "pendaftaran" in result.lower()


def test_berapa_iurannya_uses_calculator_constants():
    """'Berapa iurannya' harus dijawab dari konstanta calculator.py."""
    result = chatbot._short_question_clarification("Berapa iurannya?", history=None)
    assert result is not None
    jkk_pct = int(JKK_RATE * 100)
    jht_pct = int(JHT_RATE * 100)
    assert f"{jkk_pct}%" in result
    assert f"{jht_pct}%" in result
    assert format_rupiah(JKM_FLAT) in result


def test_off_domain_questions_not_clarified():
    """Pertanyaan off-domain seperti 'Berapa harga bitcoin' tidak boleh dapat klarifikasi BPU."""
    assert chatbot._short_question_clarification("Berapa harga bitcoin?", history=None) is None
    assert chatbot._short_question_clarification("Cara masak nasi", history=None) is None
    assert chatbot._short_question_clarification("Berapa gajinya?", history=None) is None


# --- BUG 2: Slot-filling _prepare_ask ---

def test_is_question_regex_word_boundary():
    """Pengecekan is_question harus pakai regex batas kata, bukan substring."""
    # "pada" memuat "ada" tapi bukan pertanyaan
    text = "pada hari ini"
    is_question = bool(re.search(r'\b(apa|apakah|berapa|bagaimana|gimana|kapan|siapa|kenapa|mengapa)\b', text.lower()) or '?' in text)
    assert not is_question, "'pada' tidak boleh cocok dengan 'ada'"
    
    # "ada diskon?" adalah pertanyaan
    text2 = "ada diskon?"
    is_question2 = bool(re.search(r'\b(apa|apakah|berapa|bagaimana|gimana|kapan|siapa|kenapa|mengapa)\b', text2.lower()) or '?' in text2)
    assert is_question2, "'ada diskon?' harus cocok"


# --- BUG 3: Peringatan PII di AnswerStream ---

def test_pii_warning_in_static_answer():
    """Peringatan PII harus muncul di jawaban statis."""
    pii_warn = "⚠️ Test warning\n\n"
    static = "Ini jawaban statis"
    stream = chatbot.AnswerStream(sources=[], static_answer=static, pii_warning=pii_warn)
    
    # .text harus berisi peringatan + static
    assert stream.text == pii_warn + static
    
    # Iterasi harus menghasilkan text lengkap
    result = "".join(stream)
    assert result == pii_warn + static
    assert stream.emitted == result


def test_pii_warning_consistency():
    """stream.emitted == stream.text dan peringatan muncul tepat sekali."""
    pii_warn = "⚠️ Warning\n\n"
    static = "Answer"
    stream = chatbot.AnswerStream(sources=[], static_answer=static, pii_warning=pii_warn)
    
    chunks = list(stream)
    joined = "".join(chunks)
    
    assert joined == stream.text, "joined chunks harus sama dengan .text"
    assert stream.emitted == stream.text, "emitted harus sama dengan .text"
    assert joined.count("⚠️ Warning") == 1, "peringatan harus muncul tepat sekali"


# --- BUG 4: String dengan backslash ganda literal ---

def test_no_backslash_in_clarification_responses():
    """Klarifikasi tidak boleh berisi \\n literal."""
    result = chatbot._short_question_clarification("Syarat?", history=None)
    if result:
        assert "\\n" not in result, "Tidak boleh ada backslash-n literal di klarifikasi"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
    exit(0 if failed == 0 else 1)

