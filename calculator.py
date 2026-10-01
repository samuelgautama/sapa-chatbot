"""
calculator.py
-------------
Perhitungan deterministik iuran BPU BPJS Ketenagakerjaan.

Sumber tarif yang dipakai aplikasi:
- JKK: 1% dari dasar penghasilan yang dilaporkan
- JKM: Rp6.800/bulan
- JHT: 2% dari dasar penghasilan yang dilaporkan
- Promo 50% hanya untuk JKK + JKM dan hanya jika promo secara eksplisit
  diaktifkan oleh caller setelah memastikan sektor/periode yang berlaku.

Modul ini sengaja tidak menggunakan LLM agar aritmetika tidak bergantung
pada model generatif.
"""

from __future__ import annotations

import re
from datetime import date
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

JKK_RATE = Decimal("0.01")
JKM_FLAT = Decimal("6800")
JHT_RATE = Decimal("0.02")
MIN_INCOME = Decimal("1000000")

SUPPORTED_PROGRAMS = ("JKK", "JKM", "JHT")

PROMO_PERIODS = {
    "transportasi": (date(2026, 1, 1), date(2027, 3, 31)),
    "non_transportasi": (date(2026, 4, 1), date(2026, 12, 31)),
}

TRANSPORT_KEYWORDS = ("ojek online", "ojol", "kurir", "sopir angkutan", "transportasi")
NON_TRANSPORT_KEYWORDS = ("pedagang", "petani", "nelayan", "umkm", "usaha kecil", "usaha mandiri")


def _money(value: Decimal) -> int:
    """Pembulatan rupiah ke bilangan bulat terdekat."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_rupiah(value: int | Decimal) -> str:
    """Format angka menjadi format rupiah sederhana."""
    amount = _money(Decimal(value))
    return f"Rp{amount:,}".replace(",", ".")


@dataclass(frozen=True)
class ContributionResult:
    base_income: Decimal
    programs: tuple[str, ...]
    discount_jkk_jkm: bool
    jkk: int
    jkm: int
    jht: int
    total: int

    def as_dict(self) -> dict:
        return {
            "base_income": str(self.base_income),
            "programs": list(self.programs),
            "discount_jkk_jkm": self.discount_jkk_jkm,
            "jkk": self.jkk,
            "jkm": self.jkm,
            "jht": self.jht,
            "total": self.total,
        }


def calculate_bpu_contribution(
    base_income: int | Decimal,
    programs: Iterable[str],
    *,
    discount_jkk_jkm: bool = False,
) -> ContributionResult:
    """Hitung iuran BPU berdasarkan tarif sumber yang dikonfigurasi di atas."""
    income = Decimal(str(base_income))
    if income < MIN_INCOME:
        raise ValueError(
            f"Dasar penghasilan yang didaftarkan minimal {format_rupiah(MIN_INCOME)} per bulan."
        )

    normalized = tuple(dict.fromkeys(p.upper().strip() for p in programs))
    invalid = [p for p in normalized if p not in SUPPORTED_PROGRAMS]
    if invalid:
        raise ValueError(f"Program tidak didukung: {', '.join(invalid)}")
    if not normalized:
        raise ValueError("Minimal satu program harus dipilih.")

    jkk = _money(income * JKK_RATE) if "JKK" in normalized else 0
    jkm = _money(JKM_FLAT) if "JKM" in normalized else 0
    jht = _money(income * JHT_RATE) if "JHT" in normalized else 0

    # Promo hanya boleh memengaruhi JKK dan JKM; JHT selalu tarif normal.
    if discount_jkk_jkm:
        jkk = _money(Decimal(jkk) / Decimal("2")) if "JKK" in normalized else 0
        jkm = _money(Decimal(jkm) / Decimal("2")) if "JKM" in normalized else 0

    total = jkk + jkm + jht
    return ContributionResult(
        base_income=income,
        programs=normalized,
        discount_jkk_jkm=discount_jkk_jkm,
        jkk=jkk,
        jkm=jkm,
        jht=jht,
        total=total,
    )


def _parse_money(raw: str) -> Decimal:
    """Parse beberapa format umum nominal Indonesia: 1.000.000 / 1000000 / 1 juta."""
    text = raw.lower().strip()
    text = text.replace("rp", "").replace("idr", "").strip()

    # Bentuk: 1,5 juta / 1.5 juta / 1 juta
    million_match = re.fullmatch(r"([0-9]+(?:[\.,][0-9]+)?)\s*juta", text)
    if million_match:
        number = million_match.group(1).replace(",", ".")
        return Decimal(number) * Decimal("1000000")

    cleaned = text.replace(".", "").replace(",", "")
    digits = re.sub(r"[^0-9]", "", cleaned)
    if not digits:
        raise ValueError("Nominal tidak dapat dibaca.")
    return Decimal(digits)


def extract_base_income(question: str) -> Optional[Decimal]:
    """Mencoba menemukan nominal dasar penghasilan dari pertanyaan user."""
    text = question.lower()

    patterns = [
        r"(?:rp\s*)?[0-9][0-9\.,]*\s*juta",
        r"(?:rp\s*)?[0-9][0-9\.]{3,}(?:\s*(?:per\s*bulan|/\s*bulan|sebulan))?",
        r"(?:penghasilan|pendapatan|dasar\s+penghasilan)(?:\s+sekitar|\s+sebesar|\s*=|\s*:)?\s*(?:rp\s*)?[0-9][0-9\.,]*",
    ]

    # Prioritaskan frasa setelah kata penghasilan/pendapatan.
    contextual = re.search(
        r"(?:penghasilan|pendapatan|dasar\s+penghasilan)[^0-9]{0,30}((?:rp\s*)?[0-9][0-9\.,]*(?:\s*juta)?)",
        text,
    )
    if contextual:
        try:
            value = _parse_money(contextual.group(1))
            if value >= MIN_INCOME:
                return value
        except ValueError:
            pass

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(0)
        try:
            value = _parse_money(raw)
            if value >= MIN_INCOME:
                return value
        except ValueError:
            continue

    return None


def extract_programs(question: str) -> tuple[str, ...]:
    """Deteksi program yang disebut user tanpa menebak ketika tidak ada penyebutan."""
    text = question.lower()
    programs: list[str] = []

    if re.search(r"\bjkk\b|kecelakaan kerja", text):
        programs.append("JKK")
    if re.search(r"\bjkm\b|kematian", text):
        programs.append("JKM")
    if re.search(r"\bjht\b|hari tua", text):
        programs.append("JHT")

    # Ungkapan jumlah program yang umum pada materi magang.
    if not programs:
        if re.search(r"\b3\s*(program|jaminan)\b|tiga\s*(program|jaminan)", text):
            return ("JKK", "JKM", "JHT")
        if re.search(r"\b2\s*(program|jaminan)\b|dua\s*(program|jaminan)", text):
            return ("JKK", "JKM")

    return tuple(programs)


def detect_calculation_request(question: str) -> bool:
    """Cek apakah pertanyaan cukup jelas merupakan permintaan hitung iuran."""
    text = question.lower()
    calculation_words = (
        "hitung", "berapa iuran", "simulasi iuran", "total iuran",
        "berapa bayar", "bayar per bulan", "biaya per bulan", "iuran per bulan",
    )
    has_calculation_word = any(word in text for word in calculation_words)
    has_program_or_income = any(token in text for token in ("jkk", "jkm", "jht", "penghasilan", "pendapatan", "rp", "per bulan"))
    return has_calculation_word and has_program_or_income


def build_calculation_response(
    result: ContributionResult,
    *,
    include_both_2_and_3_program_options: bool = False,
) -> str:
    """Bangun jawaban numerik deterministik yang siap ditampilkan ke user."""
    lines = [
        "### Simulasi Iuran BPU",
        f"Dasar penghasilan: **{format_rupiah(result.base_income)}/bulan**",
        "",
    ]

    if "JKK" in result.programs:
        if result.discount_jkk_jkm:
            lines.append("- **JKK:** " + f"{format_rupiah(result.jkk)} (setelah diskon 50%)")
        else:
            lines.append("- **JKK:** " + format_rupiah(result.jkk))
    if "JKM" in result.programs:
        if result.discount_jkk_jkm:
            lines.append("- **JKM:** " + f"{format_rupiah(result.jkm)} (setelah diskon 50%)")
        else:
            lines.append("- **JKM:** " + format_rupiah(result.jkm))
    if "JHT" in result.programs:
        lines.append("- **JHT:** " + format_rupiah(result.jht))

    lines.extend([
        "",
        f"**Total: {format_rupiah(result.total)}/bulan**",
    ])

    if result.discount_jkk_jkm:
        lines.append("\n*Catatan: diskon diterapkan hanya pada JKK dan JKM; JHT tidak didiskon.*")

    return "\n".join(lines)


def detect_sector(question: str) -> Optional[str]:
    """Deteksi sektor yang disebut user untuk keperluan validasi promo."""
    text = question.lower()
    if any(keyword in text for keyword in TRANSPORT_KEYWORDS):
        return "transportasi"
    if any(keyword in text for keyword in NON_TRANSPORT_KEYWORDS):
        return "non_transportasi"
    return None


def detect_discount_request(question: str) -> bool:
    """Cek apakah user secara eksplisit meminta simulasi dengan promo/diskon."""
    text = question.lower()
    return any(word in text for word in ("diskon", "promo", "potongan 50", "setelah diskon"))


def promo_status(*, sector: Optional[str], on_date: Optional[date] = None) -> tuple[str, bool]:
    """Validasi promo berdasarkan periode sumber; mengembalikan (status, eligible)."""
    if on_date is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        current = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    else:
        current = on_date

    if sector is None:
        active = []
        for name, (start, end) in PROMO_PERIODS.items():
            if start <= current <= end:
                active.append(name)
        if active:
            return "Sektor belum ditentukan; jangan menerapkan diskon secara otomatis.", False
        return "Tidak ada periode promo yang aktif berdasarkan tanggal sistem.", False

    period = PROMO_PERIODS.get(sector)
    if period is None:
        return "Sektor tidak dikenali untuk validasi promo.", False

    start, end = period
    if start <= current <= end:
        return f"Promo aktif untuk sektor {sector} sampai {end.isoformat()}.", True
    return f"Promo tidak aktif untuk sektor {sector} pada {current.isoformat()}.", False
