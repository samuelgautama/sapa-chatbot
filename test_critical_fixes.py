"""Regression tests untuk 4 temuan kritis audit (kalkulator, slot percakapan).

Dijalankan dengan `pytest test_critical_fixes.py` atau `python test_critical_fixes.py`.
chatbot.py butuh LangChain/FAISS; bila paket itu tidak terpasang (mis. CI ringan), modul
dibuat stub supaya logika deterministik tetap bisa diuji.
"""

import sys
import types
from decimal import Decimal

from calculator import detect_calculation_request, extract_base_income, extract_programs
from conversation_context import build_conversation_context


def _import_chatbot():
    try:
        import chatbot
        return chatbot
    except ImportError:
        class _Msg:
            def __init__(self, content):
                self.content = content

        stubs = {
            "dotenv": {"load_dotenv": lambda *a, **k: None},
            "langchain_huggingface": {"HuggingFaceEmbeddings": object},
            "langchain_community": {},
            "langchain_community.vectorstores": {"FAISS": object},
            "langchain_groq": {"ChatGroq": object},
            "langchain_core": {},
            "langchain_core.messages": {
                "SystemMessage": _Msg, "HumanMessage": _Msg, "AIMessage": _Msg,
            },
        }
        for name, attrs in stubs.items():
            module = types.ModuleType(name)
            module.__dict__.update(attrs)
            sys.modules[name] = module
        import chatbot
        return chatbot


chatbot = _import_chatbot()


def H(*user_messages):
    return [{"role": "user", "content": m} for m in user_messages]


def answer(question, *history):
    ctx = build_conversation_context(question, H(*history))
    return chatbot._try_deterministic_calculation(question, ctx)


# --- Temuan 1: negasi & frasa jumlah program -------------------------------------------

def test_negation_excludes_program():
    assert extract_programs("hitung iuran 1 juta tanpa JHT") == ("JKK", "JKM")
    assert extract_programs("tanpa JHT dan JKM") == ("JKK",)
    assert extract_programs("2 program tanpa JHT") == ("JKK", "JKM")


def test_program_count_phrase_beats_single_mention():
    assert extract_programs("3 program termasuk JHT") == ("JKK", "JKM", "JHT")
    assert extract_programs("2 program JKK dan JHT") == ("JKK", "JHT")


def test_ambiguous_program_phrase_does_not_guess():
    assert extract_programs("2 program termasuk JHT") == ()
    assert extract_programs("hitung iuran") == ()


def test_negation_end_to_end_total():
    r = answer("hitung iuran penghasilan 1 juta tanpa JHT")
    assert "Rp16.800" in r and "JHT" not in r


# --- Temuan 2: penghasilan di bawah minimum --------------------------------------------

def test_below_minimum_is_rejected_not_replaced_by_old_income():
    r = answer("hitung iuran penghasilan 800.000 per bulan", "hitung iuran penghasilan 2 juta")
    assert "minimum" in r and "Rp800.000" in r
    assert "Rp2.000.000" not in r and "Rp20.000" not in r


def test_below_minimum_without_history_explains_minimum():
    r = answer("hitung iuran penghasilan 800.000 per bulan")
    assert "Rp1.000.000" in r and "Rp800.000" in r


def test_money_marker_required_for_attempt():
    # tahun/angka polos bukan percobaan penghasilan
    assert chatbot.extract_income_attempt("hitung iuran 3 program tahun 2026") is None
    assert extract_base_income("hitung iuran 1jt") == Decimal("1000000")


def test_minimum_flag_default_behaviour_unchanged():
    assert extract_base_income("penghasilan 800.000") is None
    assert extract_base_income("penghasilan 800.000", enforce_minimum=False) == Decimal("800000")


# --- Temuan 3: slot stale antar calon peserta ------------------------------------------

def test_inherited_slots_are_reported():
    ctx = build_conversation_context("Hitung iuran untuk 3 program", H("Penghasilan saya 2 juta."))
    assert ctx.inherited_slots == ("base_income",)


def test_inherited_note_is_shown_to_user():
    r = answer("hitung iuran penghasilan 2 juta", "JKK saja berapa?")
    assert "pilihan program dipakai dari pesan sebelumnya" in r


def test_reset_phrase_drops_old_slots():
    history = H("Penghasilan 2 juta, ambil JKK saja", "ok", "calon peserta baru, pedagang")
    ctx = build_conversation_context("hitung iuran", history)
    assert ctx.base_income is None and ctx.programs == ()
    assert ctx.sector == "non_transportasi"


def test_slots_expire_outside_window():
    filler = ["pertanyaan biasa"] * 6
    ctx = build_conversation_context("hitung iuran 3 program", H("penghasilan 2 juta", *filler))
    assert ctx.base_income is None


def test_current_message_is_never_marked_inherited():
    ctx = build_conversation_context("hitung iuran JKK penghasilan 3 juta", H("penghasilan 2 juta"))
    assert ctx.base_income == Decimal("3000000") and ctx.inherited_slots == ()


# --- Temuan 4: pembajakan pertanyaan umum ----------------------------------------------

def test_informational_questions_not_hijacked():
    assert detect_calculation_request("berapa iuran JKK untuk penerima upah?") is False
    assert detect_calculation_request("berapa iuran JHT?") is False
    assert detect_calculation_request("hitung jumlah peserta di Kota Terpercaya") is False
    assert answer("berapa iuran JHT?") is None


def test_real_calculation_requests_still_detected():
    assert detect_calculation_request("Hitung iuran JKK + JKM untuk penghasilan Rp1.000.000")
    assert detect_calculation_request("Berapa total 3 program untuk penghasilan Rp1.000.000?")
    assert detect_calculation_request("hitung iuran 1 juta")
    assert detect_calculation_request("hitung iuran 1jt")
    assert detect_calculation_request("Berapa iuran JKK + JKM untuk penghasilan Rp1 juta?")


def test_eval_dataset_phrasings_detected():
    for q in (
        "Kalau penghasilan Rp2 juta, berapa JKK dan JKM?",
        "Kalau 3 program promo untuk pedagang Rp1.000.000, berapa totalnya?",
    ):
        assert detect_calculation_request(q), q


def test_bpu_wording_is_not_mistaken_for_penerima_upah():
    assert detect_calculation_request("berapa iuran JKK bukan penerima upah penghasilan Rp1.000.000?")
    assert not detect_calculation_request("berapa iuran JKK perusahaan dengan upah Rp5.000.000?")


def test_follow_up_uses_income_context():
    assert detect_calculation_request("kalau 3 program?") is False
    assert detect_calculation_request("kalau 3 program?", has_income_context=True) is True
    r = answer("kalau 3 program?", "hitung iuran penghasilan 1 juta")
    assert r is not None and "Rp36.800" in r


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"{len(tests)} tests passed")