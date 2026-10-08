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
    """Parse format nominal Indonesia: 1.000.000 / 1000000 / 1 juta / 1,5jt / 800 ribu."""
    text = raw.lower().strip()
    text = text.replace("rp", "").replace("idr", "").strip()

    # Bentuk: 1,5 juta / 1.5 juta / 1 juta / 1jt
    million_match = re.fullmatch(r"([0-9]+(?:[\.,][0-9]+)?)\s*(?:juta|jt)", text)
    if million_match:
        number = million_match.group(1).replace(",", ".")
        return Decimal(number) * Decimal("1000000")

    # Bentuk: 800 ribu / 800rb
    thousand_match = re.fullmatch(r"([0-9]+(?:[\.,][0-9]+)?)\s*(?:ribu|rb)", text)
    if thousand_match:
        number = thousand_match.group(1).replace(",", ".")
        return Decimal(number) * Decimal("1000")

    cleaned = text.replace(".", "").replace(",", "")
    digits = re.sub(r"[^0-9]", "", cleaned)
    if not digits:
        raise ValueError("Nominal tidak dapat dibaca.")
    return Decimal(digits)


# Penanda bahwa sebuah angka dimaksudkan sebagai nominal uang (bukan tahun, jumlah, dsb).
_MONEY_MARKER = re.compile(
    r"rp\s*[0-9]"                                  # Rp800.000
    r"|[0-9][0-9\.,]*\s*(?:juta|jt|ribu|rb)\b"      # 1 juta, 800 ribu
    r"|\b[0-9]{1,3}(?:\.[0-9]{3})+\b"               # 800.000
)
_INCOME_CONTEXT = re.compile(
    r"(?:penghasilan|pendapatan|dasar\s+penghasilan|gaji)[^0-9]{0,30}"
    r"((?:rp\s*)?[0-9][0-9\.,]*(?:\s*(?:juta|jt|ribu|rb))?)"
)
_INCOME_PATTERNS = (
    r"(?:rp\s*)?[0-9][0-9\.,]*\s*(?:juta|jt)\b",
    r"(?:rp\s*)?[0-9][0-9\.]{3,}(?:\s*(?:per\s*bulan|/\s*bulan|sebulan))?",
)
_INCOME_ATTEMPT_PATTERNS = _INCOME_PATTERNS + (
    r"(?:rp\s*)?[0-9][0-9\.,]*\s*(?:ribu|rb)\b",
    r"rp\s*[0-9][0-9\.,]*",
)


def _first_money(text: str, patterns, *, require_marker: bool) -> Optional[Decimal]:
    """Nilai pertama yang terbaca dari pola-pola `patterns` (tanpa cek minimum)."""
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(0)
            if require_marker and not _MONEY_MARKER.search(raw):
                continue
            try:
                return _parse_money(raw)
            except ValueError:
                continue
    return None


def extract_base_income(question: str, *, enforce_minimum: bool = True) -> Optional[Decimal]:
    """Mencoba menemukan nominal dasar penghasilan dari pertanyaan user.

    enforce_minimum=True (default, perilaku lama): hanya nominal >= MIN_INCOME yang
    dikembalikan; nominal lebih kecil diabaikan.

    enforce_minimum=False: nominal yang JELAS disebut sebagai penghasilan (didahului kata
    penghasilan/pendapatan/gaji) dikembalikan walau di bawah minimum, supaya pemanggil bisa
    menolak secara eksplisit alih-alih diam-diam memakai angka lama dari percakapan.
    """
    text = question.lower()

    # Prioritaskan frasa setelah kata penghasilan/pendapatan.
    contextual = _INCOME_CONTEXT.search(text)
    if contextual:
        try:
            value = _parse_money(contextual.group(1))
            if value >= MIN_INCOME or (not enforce_minimum and value > 0):
                return value
        except ValueError:
            pass

    for pattern in _INCOME_PATTERNS:
        for match in re.finditer(pattern, text):
            try:
                value = _parse_money(match.group(0))
            except ValueError:
                continue
            if value >= MIN_INCOME:
                return value

    return None


def extract_income_attempt(question: str) -> Optional[Decimal]:
    """Nominal uang apa pun yang disebut user (berpenanda Rp/juta/ribu/titik ribuan), tanpa cek minimum.

    Dipakai HANYA pada permintaan hitung untuk mendeteksi percobaan memasukkan penghasilan di
    bawah minimum. Angka polos seperti tahun (2026) tidak dihitung.
    """
    value = _first_money(question.lower(), _INCOME_ATTEMPT_PATTERNS, require_marker=True)
    return value if value is not None and value > 0 else None


_PROGRAM_REGEX = {
    "JKK": r"\bjkk\b|kecelakaan\s+kerja",
    "JKM": r"\bjkm\b|kematian",
    "JHT": r"\bjht\b|hari\s+tua",
}
_PROGRAM_ANY = r"(?:jkk|jkm|jht|kecelakaan\s+kerja|kematian|hari\s+tua)"
_NEGATION = re.compile(
    r"\b(?:tanpa|selain|kecuali|bukan|tidak\s+(?:termasuk|usah|perlu|pakai|ikut|mau|ambil|dengan))"
    r"\s+(?:program\s+|jaminan\s+)?"
    r"((?:" + _PROGRAM_ANY + r"\b(?:\s*(?:,|\+|&|dan|atau)\s*)?)+)"
)
_THREE_PROGRAMS = re.compile(r"\b3\s*(?:program|jaminan)\b|tiga\s*(?:program|jaminan)")
_TWO_PROGRAMS = re.compile(r"\b2\s*(?:program|jaminan)\b|dua\s*(?:program|jaminan)")


def _programs_in(text: str) -> list[str]:
    return [name for name in SUPPORTED_PROGRAMS if re.search(_PROGRAM_REGEX[name], text)]


def extract_programs(question: str) -> tuple[str, ...]:
    """Deteksi program yang diminta user, termasuk negasi ("tanpa JHT") dan frasa jumlah.

    Aturan:
    - program yang didahului tanpa/selain/kecuali/bukan/tidak termasuk dikeluarkan;
    - "3 program" berarti ketiganya (kecuali ada pengecualian);
    - "2 program" tanpa nama program berarti JKK + JKM;
    - kombinasi yang ambigu mengembalikan () agar pemanggil menampilkan opsi 2 dan 3 program;
    - tidak ada penyebutan sama sekali -> () (tidak menebak).
    """
    text = question.lower()

    excluded: set[str] = set()

    def _collect(match: re.Match) -> str:
        excluded.update(_programs_in(match.group(1)))
        return " "

    positive_text = _NEGATION.sub(_collect, text)
    named = _programs_in(positive_text)

    count = 3 if _THREE_PROGRAMS.search(text) else 2 if _TWO_PROGRAMS.search(text) else None

    if count == 3 and not excluded:
        return SUPPORTED_PROGRAMS
    if count == 2:
        if len(named) == 2:
            return tuple(named)
        if not named:
            return tuple(p for p in ("JKK", "JKM") if p not in excluded)
        if len(named) < 2:
            return ()  # mis. "2 program termasuk JHT": ambigu, jangan menebak

    if named:
        result = named
    elif excluded:
        result = list(SUPPORTED_PROGRAMS)
    else:
        return ()

    return tuple(p for p in result if p not in excluded)


_EXPLICIT_CALC_WORDS = ("hitung", "simulasi", "total iuran")
_QUESTION_CALC_WORDS = (
    "berapa iuran", "berapa bayar", "bayar per bulan", "biaya per bulan", "iuran per bulan",
)
_NON_BPU_CONTEXT = re.compile(
    r"\b(?:penerima\s+upah|pemberi\s+kerja|perusahaan|pekerja\s+formal|klaim|santunan)\b"
)
_BPU_MENTION = re.compile(r"\bbpu\b|bukan\s+penerima\s+upah")
_PROGRAM_COUNT = re.compile(r"\b(?:2|3|dua|tiga)\s*(?:program|jaminan)\b")


def detect_calculation_request(question: str, *, has_income_context: bool = False) -> bool:
    """Cek apakah pertanyaan cukup jelas merupakan permintaan hitung iuran BPU.

    Pertanyaan informasional ("berapa iuran JHT?", "berapa iuran JKK untuk penerima upah?")
    TIDAK dianggap simulasi kecuali ada nominal penghasilan, penyebutan jumlah program, atau
    kata kerja hitung/simulasi yang eksplisit. `has_income_context=True` berarti percakapan
    sudah punya dasar penghasilan, sehingga follow-up seperti "kalau 3 program?" cukup.
    """
    text = question.lower()

    # Pertanyaan tentang Penerima Upah / klaim / perusahaan bukan simulasi iuran BPU.
    if _NON_BPU_CONTEXT.search(text) and not _BPU_MENTION.search(text):
        return False

    explicit = any(word in text for word in _EXPLICIT_CALC_WORDS)
    question_form = any(word in text for word in _QUESTION_CALC_WORDS)
    has_count = bool(_PROGRAM_COUNT.search(text))
    has_money = bool(_MONEY_MARKER.search(text))
    has_amount = has_money or bool(re.search(r"\b(?:penghasilan|pendapatan)\b", text))
    has_program = bool(re.search(r"\b(?:jkk|jkm|jht)\b", text))
    asks_value = "berapa" in text or "total" in text

    if explicit:
        return has_amount or has_count or has_program or "per bulan" in text
    # "Berapa total 3 program untuk penghasilan Rp1.000.000?", "Rp2 juta, berapa JKK dan JKM?"
    if asks_value and has_money and (has_program or has_count or "iuran" in text or "total" in text):
        return True
    if question_form:
        return has_amount or has_count
    # Follow-up pendek di percakapan yang sudah punya penghasilan: "kalau 3 program?"
    return has_income_context and has_count


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