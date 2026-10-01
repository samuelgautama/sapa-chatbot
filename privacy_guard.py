"""
privacy_guard.py
---------------
Guardrail ringan untuk mencegah data identitas/finansial sensitif masuk ke
riwayat chat atau dikirim ke LLM/retriever.

Guardrail ini bukan sistem DLP penuh. Ia hanya menangani pola yang cukup jelas
untuk konteks chatbot lapangan, sambil berusaha tidak menyensor nominal iuran
seperti Rp1.000.000.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SanitizationResult:
    text: str
    redacted: bool
    categories: tuple[str, ...]


# Kata kunci yang memberi konteks bahwa angka berikutnya kemungkinan identitas/
# rekening, bukan nominal iuran.
_IDENTITY_PATTERNS = (
    # NIK/KTP/KK umumnya 16 digit. Separator spasi/tanda hubung tetap ditoleransi.
    ("NIK", re.compile(r"\bnik\b\s*(?:saya\s*)?[:#-]?\s*(?:\d[ -]?){15}\d", re.IGNORECASE)),
    ("KTP", re.compile(r"\b(?:no(?:mor)?\s*)?ktp\b\s*(?:saya\s*)?[:#-]?\s*(?:\d[ -]?){15}\d", re.IGNORECASE)),
    ("KK", re.compile(r"\b(?:no(?:mor)?\s*)?kk\b\s*(?:saya\s*)?[:#-]?\s*(?:\d[ -]?){15}\d", re.IGNORECASE)),
    ("rekening", re.compile(r"\b(?:no(?:mor)?\s*)?(?:rekening|rek)\b\s*(?:saya\s*)?[:#-]?\s*\d(?:[\d -]{5,23})", re.IGNORECASE)),
)

# Nomor telepon/WhatsApp yang ditempelkan dengan label yang jelas.
_PHONE_PATTERN = re.compile(
    r"\b(?:nomor|no(?:mor)?|wa|whatsapp)\b[^\d]{0,32}(?:\+62|62|0)[0-9](?:[0-9 -]{7,14})",
    re.IGNORECASE,
)

# Email lebih aman untuk disensor karena tidak dibutuhkan untuk menghitung iuran.
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def sanitize_user_input(text: str) -> SanitizationResult:
    """Sensor data sensitif yang cukup jelas tanpa menyentuh nominal iuran biasa."""
    if not text:
        return SanitizationResult(text="", redacted=False, categories=())

    sanitized = str(text)
    categories: list[str] = []

    for category, pattern in _IDENTITY_PATTERNS:
        sanitized, replacements = pattern.subn(f"[{category} DISENSOR]", sanitized)
        if replacements and category not in categories:
            categories.append(category)

    sanitized, replacements = _PHONE_PATTERN.subn("[NOMOR TELEPON DISENSOR]", sanitized)
    if replacements:
        categories.append("nomor telepon")

    sanitized, replacements = _EMAIL_PATTERN.subn("[EMAIL DISENSOR]", sanitized)
    if replacements:
        categories.append("email")

    # Jika user menulis kalimat eksplisit bahwa data identitas/rekening ikut ditempel,
    # beri sinyal UI meski pola angkanya gagal dikenali.
    lowered = str(text).lower()
    identity_words = ("nik saya", "ktp saya", "kk saya", "nomor rekening saya", "rekening saya")
    if any(phrase in lowered for phrase in identity_words) and not categories:
        categories.append("data identitas/finansial")

    # Hilangkan duplikasi kategori sambil mempertahankan urutan.
    unique_categories = tuple(dict.fromkeys(categories))
    return SanitizationResult(
        text=sanitized,
        redacted=bool(unique_categories),
        categories=unique_categories,
    )


def privacy_warning(result: SanitizationResult) -> str:
    """Pesan singkat yang aman ditampilkan ketika data sensitif terdeteksi."""
    if not result.redacted:
        return ""

    categories = ", ".join(result.categories)
    return (
        f"⚠️ **Data pribadi disensor:** {categories}. "
        "Jangan masukkan NIK, KTP, KK, nomor rekening, nomor telepon, atau data identitas "
        "lainnya ke dalam chat. Gunakan formulir atau kanal resmi sesuai arahan petugas."
    )
