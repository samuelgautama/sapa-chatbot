"""
privacy_guard.py
---------------
Guardrail ringan untuk mencegah data identitas/finansial sensitif masuk ke
riwayat chat atau dikirim ke LLM/retriever.

Guardrail ini bukan sistem DLP penuh. Ia hanya menangani pola yang cukup jelas
untuk konteks chatbot lapangan, sambil berusaha tidak menyensor nominal iuran
seperti Rp1.000.000 atau Rp16.800.

Dua sinyal terpisah pada hasilnya:
- redacted : teks BENAR-BENAR berubah (ada nilai yang disensor).
- flagged  : ada indikasi data pribadi, termasuk kasus yang tidak bisa disensor
             otomatis (mis. user menulis "NIK saya ada di KTP" tanpa angka).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SanitizationResult:
    text: str
    redacted: bool
    categories: tuple[str, ...]
    flagged: bool = False


# Celah antara label dan angka: "saya", "adalah", ":", nama bank, dsb. Tanpa digit dan
# tanpa baris baru supaya tidak "melompat" ke angka di kalimat lain.
_GAP = r"[^\d\n]{0,30}?"

# 16 digit dengan pemisah opsional (spasi, titik, atau tanda hubung) di antara digit.
_SIXTEEN_DIGITS = r"(?:\d[ .-]?){15}\d(?!\d)"

# Label identitas + 16 digit. NIK, nomor KTP, dan nomor KK memang 16 digit.
_IDENTITY_PATTERNS = (
    ("NIK", re.compile(rf"\b(?:nik|nomor\s+induk\s+kependudukan)\b{_GAP}{_SIXTEEN_DIGITS}", re.IGNORECASE)),
    ("KTP", re.compile(rf"\b(?:no(?:mor)?\s*)?ktp\b{_GAP}{_SIXTEEN_DIGITS}", re.IGNORECASE)),
    ("KK", re.compile(rf"\b(?:no(?:mor)?\s*)?(?:kk|kartu\s+keluarga)\b{_GAP}{_SIXTEEN_DIGITS}", re.IGNORECASE)),
    # Rekening: 8-20 digit (spasi/tanda hubung boleh). Titik tidak diterima sebagai pemisah,
    # sehingga nominal seperti "1.000.000" tidak pernah terbaca sebagai nomor rekening.
    ("rekening", re.compile(
        r"\b(?:no(?:mor)?\.?\s*)?(?:rekening|rek)\b[^\d\n]{0,40}?\d(?:[ -]?\d){7,19}(?!\d)",
        re.IGNORECASE,
    )),
)

# 16 digit tanpa label (kemungkinan besar NIK/KK): contiguous atau berkelompok 4-4-4-4.
# Nominal rupiah memakai kelompok 3 digit sehingga tidak ikut tertangkap.
_BARE_SIXTEEN = re.compile(r"(?<![\d.,])(?:\d{4}[ .-]?){3}\d{4}(?![\d])")

# Nomor telepon/WhatsApp dengan label yang jelas (format apa pun).
_PHONE_PATTERN = re.compile(
    r"\b(?:nomor|no(?:mor)?|wa|whatsapp|hp|telepon|telp)\b[^\d]{0,32}(?:\+62|62|0)[0-9](?:[0-9 -]{7,14})",
    re.IGNORECASE,
)

# Nomor seluler Indonesia tanpa label: 08xx / +62 8xx / 628xx, 10-13 digit.
_MOBILE_PATTERN = re.compile(r"(?<![\d.,])(?:\+?62|0)[ -]?8\d{1,2}[ .-]?\d{3,4}[ .-]?\d{3,5}(?!\d)")

# Email lebih aman untuk disensor karena tidak dibutuhkan untuk menghitung iuran.
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

_IDENTITY_WORDS = ("nik saya", "ktp saya", "kk saya", "nomor rekening saya", "rekening saya")


def sanitize_user_input(text: str) -> SanitizationResult:
    """Sensor data sensitif yang cukup jelas tanpa menyentuh nominal iuran biasa."""
    if not text:
        return SanitizationResult(text="", redacted=False, categories=(), flagged=False)

    original = str(text)
    sanitized = original
    categories: list[str] = []

    for category, pattern in _IDENTITY_PATTERNS:
        sanitized, replacements = pattern.subn(f"[{category} DISENSOR]", sanitized)
        if replacements:
            categories.append(category)

    sanitized, replacements = _BARE_SIXTEEN.subn("[NOMOR IDENTITAS DISENSOR]", sanitized)
    if replacements:
        categories.append("nomor identitas")

    sanitized, replacements = _PHONE_PATTERN.subn("[NOMOR TELEPON DISENSOR]", sanitized)
    if replacements:
        categories.append("nomor telepon")

    sanitized, replacements = _MOBILE_PATTERN.subn("[NOMOR TELEPON DISENSOR]", sanitized)
    if replacements and "nomor telepon" not in categories:
        categories.append("nomor telepon")

    sanitized, replacements = _EMAIL_PATTERN.subn("[EMAIL DISENSOR]", sanitized)
    if replacements:
        categories.append("email")

    redacted = sanitized != original

    # User menyebut data identitas/rekening miliknya tetapi tidak ada pola angka yang dikenali:
    # beri sinyal ke UI, tetapi JANGAN mengaku sudah menyensor (redacted tetap False).
    lowered = original.lower()
    if not categories and any(phrase in lowered for phrase in _IDENTITY_WORDS):
        categories.append("data identitas/finansial")

    unique_categories = tuple(dict.fromkeys(categories))
    return SanitizationResult(
        text=sanitized,
        redacted=redacted,
        categories=unique_categories,
        flagged=bool(unique_categories),
    )


def privacy_warning(result: SanitizationResult) -> str:
    """Pesan singkat yang aman ditampilkan ketika data sensitif terdeteksi."""
    if not result.flagged:
        return ""

    categories = ", ".join(result.categories)
    if result.redacted:
        return (
            f"⚠️ **Data pribadi disensor:** {categories}. "
            "Jangan masukkan NIK, KTP, KK, nomor rekening, nomor telepon, atau data identitas "
            "lainnya ke dalam chat. Gunakan formulir atau kanal resmi sesuai arahan petugas."
        )
    return (
        f"⚠️ **Data pribadi terdeteksi:** {categories}, tetapi tidak dapat disensor otomatis. "
        "Jangan tulis NIK, KTP, KK, nomor rekening, nomor telepon, atau data identitas lainnya "
        "di chat. Gunakan formulir atau kanal resmi sesuai arahan petugas."
    )