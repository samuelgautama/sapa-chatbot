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
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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


# ---------------------------------------------------------------------------
# Parsing nominal uang (format baku maupun slang Indonesia)
# ---------------------------------------------------------------------------
# Didukung, antara lain:
#   1.000.000 | 1000000 | Rp 1.500.000 | 1 juta | 1,5 juta | 1.5 juta
#   1,5jt | 2.5 jt | 1.2juta | 300rb | 500 ribu
#   sejuta | satu setengah juta | 2 setengah juta | tiga ratus ribu
#   dua juta lima ratus ribu | sejuta lima ratus | 1 juta 500 ribu
#   Singkatan & slang: 5k | 1500k | 2jt | 2 jta | 2 jutaan | 2 juta-an | 3 ribuan
#   2 jeti | 5 rebu | 1,5 milyar | seratus ceban | Rp1.500.000,- | Rp1.500.000,00

_UNIT_WORDS = {
    "nol": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
}
_SCALE_WORDS = {
    "ribu": Decimal(1000),
    "juta": Decimal(1000000),
    "miliar": Decimal(1000000000),
}
# Singkatan dan bentuk "se-" dinormalisasi dulu: sejuta -> satu juta, jt -> juta, dst.
_ALIASES = {
    "jt": ("juta",),
    "jta": ("juta",),
    "jeti": ("juta",),          # slang
    "rb": ("ribu",),
    "rebu": ("ribu",),          # slang
    "k": ("ribu",),             # 5k = 5 ribu, 1500k = 1,5 juta
    "milyar": ("miliar",),
    "semilyar": ("satu", "miliar"),
    "sejuta": ("satu", "juta"),
    "seribu": ("satu", "ribu"),
    "seratus": ("satu", "ratus"),
    "sepuluh": ("satu", "puluh"),
    "sebelas": ("satu", "belas"),
    "semiliar": ("satu", "miliar"),
}
# Slang pecahan uang: seceng = Rp1.000, goceng = Rp5.000, ceban = Rp10.000, gocap = Rp50.000.
_COIN_WORDS = {
    "seceng": Decimal(1000),
    "goceng": Decimal(5000),
    "ceban": Decimal(10000),
    "gocap": Decimal(50000),
}
# Akhiran "-an" (jutaan, ribuan, juta-an, jtan, sejutaan) hanya penanda "kira-kira": diabaikan.
_AN_BASES = {
    "juta", "jt", "jta", "jeti", "ribu", "rebu", "rb", "ratus", "puluh", "miliar", "milyar",
    "sejuta", "seribu", "seratus", "sepuluh", "semiliar", "semilyar",
}
# Kata pengisi yang aman diabaikan (mis. "sekitar 2 juta per bulan").
_FILLER_WORDS = {
    "sekitar", "sebesar", "kurang", "lebih", "per", "bulan", "sebulan",
    "perbulan", "dan", "rupiah",
}

_NUM_RE = r"\d+(?:[.,]\d+)*"
_SCALE_CORE = (
    r"(?:juta|jta|jt|jeti|ribu|rebu|rb|miliar|milyar|ratus|puluh)(?:-?an)?"
    r"|belas"
)
_SCALE_RE = rf"(?:{_SCALE_CORE})"
_WORD_RE = (
    r"(?:nol|satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sebelas|setengah|"
    r"seceng|goceng|ceban|gocap|belas|"
    r"(?:sepuluh|seratus|seribu|sejuta|semiliar|semilyar|"
    r"juta|jta|jt|jeti|ribu|rebu|rb|miliar|milyar|ratus|puluh)(?:-?an)?)"
)
# Satu "segmen": angka + satuan ("1,5jt", "2 setengah juta", "5k") atau rangkaian kata bilangan.
_SEGMENT_RE = (
    rf"(?:{_NUM_RE}\s*(?:setengah\s*)?{_SCALE_RE}(?![a-z])"
    rf"|{_NUM_RE}k(?![a-z])"
    rf"|(?<![a-z]){_WORD_RE}(?![a-z])(?:\s+{_WORD_RE}(?![a-z]))*)"
)
_SCALED_PHRASE_PATTERN = re.compile(rf"(?:(?<![a-z])rp\.?\s*)?{_SEGMENT_RE}(?:\s*{_SEGMENT_RE})*")
# Angka polos (tanpa satuan): 1000000, 1.500.000, 1,500,000
_BARE_NUMBER_PATTERN = re.compile(r"(?:(?<![a-z])rp\.?\s*)?\d[\d.,]*\d|\d")
_INCOME_KEYWORD_PATTERN = re.compile(r"penghasilan|pendapatan")


def _number_token(token: str) -> Decimal:
    """Angka dalam teks slang: '1.500' (pemisah ribuan) atau '1,5' / '2.5' (desimal)."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        return Decimal(token.replace(".", ""))
    if re.fullmatch(r"\d+(?:[.,]\d+)?", token):
        return Decimal(token.replace(",", "."))
    raise ValueError("Nominal tidak dapat dibaca.")


def _parse_amount_tokens(tokens: list[str]) -> Decimal:
    """Hitung nilai dari token angka/kata bilangan Indonesia. Raise ValueError bila tak valid."""
    total = Decimal(0)      # hasil dari kelompok yang sudah ditutup satuan (ribu/juta/miliar)
    current = Decimal(0)    # kelompok < 1000 yang sedang dirakit (ratus/puluh/belas)
    pending = Decimal(0)    # angka yang menunggu pengali (satuan/puluh/ratus/skala)
    last_scale: Optional[Decimal] = None

    for token in tokens:
        if token[0].isdigit():
            if pending:
                raise ValueError("Dua angka berurutan tidak valid.")
            pending = _number_token(token)
        elif token in _UNIT_WORDS:
            if pending:
                raise ValueError("Dua angka berurutan tidak valid.")
            pending = Decimal(_UNIT_WORDS[token])
        elif token == "setengah":
            if not pending and not current and last_scale is not None:
                total += last_scale / 2          # "sejuta setengah" = 1,5 juta
            else:
                pending += Decimal("0.5")        # "setengah juta", "dua setengah juta"
        elif token in ("belas", "puluh", "ratus"):
            if not pending:
                raise ValueError("Pengali tanpa angka.")
            if token == "belas":
                current += pending + 10
            elif token == "puluh":
                current += pending * 10
            else:
                current += pending * 100
            pending = Decimal(0)
        elif token in _COIN_WORDS:
            if pending:
                current += pending * _COIN_WORDS[token]      # "dua ceban" = 20.000
            elif current:
                current *= _COIN_WORDS[token]                # "seratus ceban" = 1.000.000
            else:
                current = _COIN_WORDS[token]                 # "goceng" = 5.000
            pending = Decimal(0)
        elif token in _SCALE_WORDS:
            group = current + pending
            if not group:
                raise ValueError("Satuan tanpa angka.")
            last_scale = _SCALE_WORDS[token]
            total += group * last_scale
            current = pending = Decimal(0)
        else:
            raise ValueError("Kata tidak dikenali.")

    group = current + pending
    if group:
        if last_scale is not None and last_scale >= Decimal(1000000) and group < 1000:
            # Lisan: "satu juta lima ratus" = 1,5 juta ("ribu" dilesapkan).
            if group < 100:
                raise ValueError("Sisa angka ambigu.")
            total += group * (last_scale / 1000)
        else:
            total += group
    return total


def _normalize_amount(value: Decimal) -> Decimal:
    """Buang desimal nol yang tidak perlu: Decimal('1500000.0') -> Decimal('1500000')."""
    if value == value.to_integral_value():
        return value.quantize(Decimal("1"))
    return value


def _parse_money(raw: str) -> Decimal:
    """
    Parse nominal Indonesia (baku maupun slang) menjadi Decimal.
    Raise ValueError bila format tidak dikenali (tidak pernah melempar error jenis lain).
    """
    try:
        text = str(raw).lower().strip()
        text = re.sub(r"(?<![a-z])(?:rp|idr)\.?\s*", "", text)
        text = text.replace("/", " ")
        text = re.sub(r"(?<=[a-z])\s*-\s*an\b", "an", text)   # "juta-an" -> "jutaan"
        text = re.sub(r"(?<=\d)(?=[a-z])", " ", text)           # "1,5jt" -> "1,5 jt"

        tokens = [
            t for t in re.findall(r"\d+(?:[.,]\d+)*|[a-z]+", text)
            if t not in _FILLER_WORDS
        ]
        if not tokens:
            raise ValueError("Nominal tidak dapat dibaca.")

        # Hanya angka (1.000.000 / 1000000 / 1,000,000): perilaku lama dipertahankan.
        if not any(t.isalpha() for t in tokens):
            if len(tokens) == 1:
                # Buang sen desimal: "1.500.000,00" / "1.500.000,-" / "1,500,000.00"
                tok = tokens[0]
                m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+),\d{1,2}", tok) or \
                    re.fullmatch(r"(\d{1,3}(?:,\d{3})+)\.\d{1,2}", tok) or \
                    re.fullmatch(r"(\d{4,}),\d{1,2}", tok)
                if m:
                    text = m.group(1)
            digits = re.sub(r"[^0-9]", "", text)
            if not digits:
                raise ValueError("Nominal tidak dapat dibaca.")
            return Decimal(digits)

        expanded: list[str] = []
        for token in tokens:
            if token.endswith("an") and token[:-2] in _AN_BASES:
                token = token[:-2]                                  # jutaan -> juta
            expanded.extend(_ALIASES.get(token, (token,)))
        return _normalize_amount(_parse_amount_tokens(expanded))
    except (InvalidOperation, ArithmeticError, AttributeError, TypeError) as exc:
        raise ValueError("Nominal tidak dapat dibaca.") from exc


def _parse_money_lenient(raw: str) -> Optional[Decimal]:
    """Seperti _parse_money, tapi bila gagal coba buang kata di ujung; None jika tetap gagal."""
    parts = raw.split()
    while parts:
        try:
            return _parse_money(" ".join(parts))
        except ValueError:
            parts.pop()
    return None


def extract_base_income(question: str) -> Optional[Decimal]:
    """
    Mencoba menemukan nominal dasar penghasilan dari pertanyaan user.
    Mendukung angka baku dan slang ('1,5jt', '2.5 jt', 'sejuta', 'dua juta lima ratus ribu').
    Mengembalikan None bila tidak ada nominal yang valid (>= MIN_INCOME).
    """
    try:
        text = str(question).lower()
    except Exception:
        return None

    # Kumpulkan semua kandidat nominal: (posisi, teks mentah), berurutan sesuai kemunculan.
    scaled = [(m.start(), m.end(), m.group(0)) for m in _SCALED_PHRASE_PATTERN.finditer(text)]
    bare = [
        (m.start(), m.end(), m.group(0))
        for m in _BARE_NUMBER_PATTERN.finditer(text)
        if not any(m.start() < e and s < m.end() for s, e, _ in scaled)   # hindari tumpang tindih
    ]
    candidates = sorted(scaled + bare)

    def valid_income(raw: str) -> Optional[Decimal]:
        value = _parse_money_lenient(raw)
        if value is not None and value >= MIN_INCOME:
            return value
        return None

    # 1) Prioritaskan nominal yang muncul tepat setelah kata penghasilan/pendapatan
    #    (maks. 40 karakter, tanpa angka lain di antaranya).
    for keyword in _INCOME_KEYWORD_PATTERN.finditer(text):
        for start, _end, raw in candidates:
            if start < keyword.end() or start - keyword.end() > 40:
                continue
            if re.search(r"\d", text[keyword.end():start]):
                continue
            value = valid_income(raw)
            if value is not None:
                return value

    # 2) Fallback: nominal berskala/kata dulu (1,5jt, sejuta), baru angka polos (1500000).
    for _start, _end, raw in sorted(scaled) + sorted(bare):
        value = valid_income(raw)
        if value is not None:
            return value

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
    # Nominal slang tanpa kata "rp"/"penghasilan": "hitung iuran 1,5jt", "berapa iuran sejuta"
    has_slang_amount = bool(
        re.search(r"\d\s*(?:juta|jt|ribu|rb)(?![a-z])|(?<![a-z])(?:sejuta|seribu|setengah juta)(?![a-z])", text)
        or (_SCALED_PHRASE_PATTERN.search(text) and extract_base_income(text) is not None)
    )
    return has_calculation_word and (has_program_or_income or has_slang_amount)


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