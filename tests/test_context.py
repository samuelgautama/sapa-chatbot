"""Regression tests untuk structured conversation context + follow-up calculation."""

from decimal import Decimal

from calculator import detect_calculation_request, extract_programs
from conversation_context import build_conversation_context
from retrieval_utils import needs_history_for_retrieval, build_retrieval_query


def test_follow_up_three_programs_uses_previous_income():
    history = [{"role": "user", "content": "Saya punya penghasilan 2 juta."}]
    ctx = build_conversation_context("Hitung iuran untuk 3 program", history)

    assert ctx.base_income == Decimal("2000000")
    assert ctx.programs == ("JKK", "JKM", "JHT")
    assert detect_calculation_request("Hitung iuran untuk 3 program") is True


def test_new_income_overrides_previous_income():
    history = [
        {"role": "user", "content": "Penghasilan saya 2 juta."},
        {"role": "user", "content": "Sekarang pakai penghasilan 3 juta."},
    ]
    ctx = build_conversation_context("Hitung iuran untuk JKK", history)

    assert ctx.base_income == Decimal("3000000")
    assert ctx.programs == ("JKK",)


def test_program_memory_is_inherited_when_follow_up_omits_program():
    history = [{"role": "user", "content": "Calon peserta ambil JKK dan JKM."}]
    ctx = build_conversation_context("Berapa iurannya?", history)

    assert ctx.programs == ("JKK", "JKM")


def test_latest_current_program_overrides_old_program_memory():
    history = [{"role": "user", "content": "Ambil JKK + JKM."}]
    ctx = build_conversation_context("Sekarang hitung JHT saja", history)

    assert ctx.programs == ("JHT",)


def test_retrieval_detects_common_follow_up_forms():
    assert needs_history_for_retrieval("Iurannya berapa?") is True
    assert needs_history_for_retrieval("Syaratnya apa saja?") is True
    assert needs_history_for_retrieval("Bagaimana dengan JHT?") is True


def test_retrieval_stitches_previous_user_question_for_follow_up():
    history = [
        {"role": "user", "content": "Bagaimana cara mendaftar BPU?"},
        {"role": "assistant", "content": "Jawaban sebelumnya."},
    ]
    query = build_retrieval_query("Syaratnya apa saja?", history)
    assert "Bagaimana cara mendaftar BPU?" in query
    assert "Syaratnya apa saja?" in query


if __name__ == "__main__":
    tests = [
        test_follow_up_three_programs_uses_previous_income,
        test_new_income_overrides_previous_income,
        test_program_memory_is_inherited_when_follow_up_omits_program,
        test_latest_current_program_overrides_old_program_memory,
        test_retrieval_detects_common_follow_up_forms,
        test_retrieval_stitches_previous_user_question_for_follow_up,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
