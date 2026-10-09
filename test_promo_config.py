"""Regression tests untuk temuan audit #21: periode promo satu sumber, tidak basi diam-diam."""

import pathlib
import sys
import tempfile
import types
from datetime import date

import promo_config
from calculator import PROMO_PERIODS as CALC_PERIODS, promo_status
from test_critical_fixes import chatbot
from test_retrieval_gate import Doc

DATA_DIR = pathlib.Path(__file__).with_name("data")


def states(on):
    return {item.sector: item.state for item in promo_config.promo_timeline(on)}


def test_single_source_of_truth():
    assert CALC_PERIODS is promo_config.PROMO_PERIODS
    assert not hasattr(chatbot, "PROMO_SOURCES")


def test_timeline_across_dates():
    assert states(date(2025, 12, 31)) == {"transportasi": "upcoming", "non_transportasi": "upcoming"}
    assert states(date(2026, 10, 7)) == {"transportasi": "active", "non_transportasi": "active"}
    assert states(date(2026, 12, 31))["non_transportasi"] == "active"      # hari terakhir masih aktif
    assert states(date(2027, 1, 1)) == {"transportasi": "active", "non_transportasi": "ended"}
    assert states(date(2027, 4, 1)) == {"transportasi": "ended", "non_transportasi": "ended"}


def test_calculator_stops_discount_after_expiry():
    assert promo_status(sector="non_transportasi", on_date=date(2026, 12, 31))[1] is True
    assert promo_status(sector="non_transportasi", on_date=date(2027, 1, 1))[1] is False
    assert promo_status(sector="transportasi", on_date=date(2027, 1, 1))[1] is True


def test_describe_period():
    assert promo_config.describe_period("non_transportasi") == "April 2026 – Desember 2026"
    assert promo_config.describe_period("transportasi") == "Januari 2026 – Maret 2027"


def test_maintenance_warnings():
    assert promo_config.maintenance_warnings(date(2026, 10, 7)) == []
    soon = promo_config.maintenance_warnings(date(2026, 12, 1))
    assert len(soon) == 1 and "non transportasi" in soon[0] and "30 hari" in soon[0]
    ended = promo_config.maintenance_warnings(date(2027, 1, 2))
    assert any("SUDAH BERAKHIR" in w and "non transportasi" in w for w in ended)
    assert len(promo_config.maintenance_warnings(date(2027, 4, 2))) == 2


def test_docs_match_config_today():
    assert promo_config.doc_period_mismatches(DATA_DIR) == []


def test_doc_drift_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "x.txt").write_text(
            "Periode: Januari 2026 – Juni 2027\nPeriode: April 2026 – Desember 2026\n", encoding="utf-8"
        )
        problems = promo_config.doc_period_mismatches(tmp)
    assert any("Juni 2027" in p for p in problems)                      # periode dokumen salah
    assert any("Maret 2027" in p and "tidak ditemukan" in p for p in problems)   # periode config hilang


def test_time_relative_claims_are_listed():
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "x.txt").write_text(
            "saat ini sedang berlaku diskon iuran 50%\nIuran JHT 2% dari penghasilan\n", encoding="utf-8"
        )
        claims = promo_config.time_relative_promo_claims(tmp)
    assert len(claims) == 1 and "x.txt:1" in claims[0]


def test_today_falls_back_to_wib_without_tzdata():
    class _NoTz(types.ModuleType):
        def ZoneInfo(self, key):          # meniru Windows tanpa paket tzdata
            raise KeyError(f"No time zone found with key {key}")

    original = sys.modules.get("zoneinfo")
    sys.modules["zoneinfo"] = _NoTz("zoneinfo")
    try:
        result = promo_config.today_jakarta()
        status = promo_status(sector="transportasi")      # jalur calculator juga tidak boleh error
    finally:
        if original is not None:
            sys.modules["zoneinfo"] = original
        else:
            del sys.modules["zoneinfo"]
    assert isinstance(result, date) and status[1] in (True, False)


# --- konteks tanggal di prompt ----------------------------------------------------------------

def test_temporal_context_not_needed_for_unrelated_question():
    text = chatbot._temporal_context("bagaimana cara daftar BPU?", [Doc("Langkah pendaftaran lewat formulir.")])
    assert "tidak diperlukan" in text


def test_temporal_context_injected_when_retrieved_doc_mentions_promo():
    docs = [Doc("Saat ini sedang berlaku diskon iuran JKK & JKM 50% untuk non-transportasi.")]
    text = chatbot._temporal_context("iuran JKK berapa?", docs, today=date(2027, 1, 5))
    assert "2027-01-05" in text
    assert "non transportasi sudah berakhir pada 2026-12-31" in text
    assert "transportasi sedang berada dalam periode berlaku sampai 2027-03-31" in text
    assert "IKUTI status di atas" in text


def test_temporal_context_still_triggers_on_promo_question():
    text = chatbot._temporal_context("ada promo?", [], today=date(2026, 10, 7))
    assert "2026-10-07" in text and "sedang berada dalam periode" in text


def test_load_retriever_logs_maintenance_warnings():
    import logging

    class _Cap(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.WARNING)
            self.messages = []

        def emit(self, record):
            self.messages.append(record.getMessage())

    original = chatbot.maintenance_warnings
    chatbot.maintenance_warnings = lambda: promo_config.maintenance_warnings(date(2027, 1, 2))
    handler = _Cap()
    chatbot.logger.addHandler(handler)
    try:
        chatbot._log_promo_maintenance()
    finally:
        chatbot.logger.removeHandler(handler)
        chatbot.maintenance_warnings = original
    assert any("SUDAH BERAKHIR" in m for m in handler.messages)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"{len(tests)} tests passed")