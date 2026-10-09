"""Regression tests untuk privacy_guard (temuan audit #5)."""

import json
import pathlib

from privacy_guard import privacy_warning, sanitize_user_input

NIK = "3271234567890123"

MUST_REDACT = [
    f"NIK: {NIK}",
    f"NIK saya adalah {NIK}",          # sebelumnya lolos
    f"nomor induk kependudukan saya {NIK}",
    f"ini ktp saya {NIK}",
    f"no KK {NIK}",
    f"kartu keluarga kami nomor {NIK}",
    "NIK 3271.2345.6789.0123",          # sebelumnya lolos
    "NIK 3271 2345 6789 0123",
    NIK,                                # 16 digit tanpa label, sebelumnya lolos
    "3271-2345-6789-0123",
    "nomor rekening BRI saya 1234567890123",   # sebelumnya lolos
    "rek 1234567890",
    "no. rekening 1234 5678 9012",
    "hubungi saya 0812-3456-7890",      # sebelumnya lolos
    "hubungi 081234567890",
    "kontaknya +62 812-3456-7890",
    "WA 081234567890",
    "wa saya: 0812 3456 7890",
    "No. HP 081234567890",
    "email budi@mail.com",
]

MUST_KEEP = [
    "hitung iuran penghasilan Rp1.000.000",
    "penghasilan Rp1.000.000 rek 1.000.000",
    "iurannya Rp16.800 per bulan",
    "total Rp36.800, JKK Rp10.000, JHT Rp20.000",
    "penghasilan 1500000 per bulan",
    "penghasilan 10.000.000, rekening bank mana yang bisa?",
    "hitung iuran 3 program tahun 2026",
    "promo April 2026 - Desember 2026",
    "Rp 1.000.000.000.000",
    "JKK 1% dan JHT 2% untuk Rp2.000.000",
]


def test_sensitive_values_are_removed():
    for text in MUST_REDACT:
        result = sanitize_user_input(text)
        digits = "".join(ch for ch in result.text if ch.isdigit())
        assert result.redacted and result.flagged, text
        assert len(digits) < 8 and "@" not in result.text, (text, result.text)


def test_money_and_ordinary_numbers_are_untouched():
    for text in MUST_KEEP:
        result = sanitize_user_input(text)
        assert result.text == text and not result.redacted and not result.flagged, (text, result.text)


def test_sanitization_is_idempotent():
    for text in MUST_REDACT:
        once = sanitize_user_input(text).text
        assert sanitize_user_input(once).text == once


def test_redacted_means_text_changed():
    # Menyebut "NIK saya" tanpa angka: ditandai, tetapi tidak mengaku sudah menyensor.
    result = sanitize_user_input("NIK saya ada di KTP, tolong cek")
    assert result.flagged and not result.redacted
    assert "tidak dapat disensor otomatis" in privacy_warning(result)


def test_warning_text():
    assert privacy_warning(sanitize_user_input("hitung iuran Rp1.000.000")) == ""
    assert "disensor" in privacy_warning(sanitize_user_input(f"NIK {NIK}"))


def test_eval_dataset_privacy_cases_still_pass():
    path = pathlib.Path(__file__).with_name("evaluation_dataset.json")
    cases = [c for c in json.loads(path.read_text(encoding="utf-8")) if c["category"] == "privacy"]
    assert cases
    for case in cases:
        assert sanitize_user_input(case["question"]).redacted, case["id"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"{len(tests)} tests passed")