"""
promo_config.py
---------------
SATU-SATUNYA sumber kebenaran periode promo diskon iuran BPU di kode.

Saat promo diperpanjang/berakhir, ubah PROMO_PERIODS di sini, perbarui teks di data/, lalu
jalankan `python ingest.py`. Cek konsistensinya dengan:

    python promo_config.py --check

Modul ini murni Python (tanpa LangChain) sehingga bisa diuji dan dipakai calculator.py
maupun chatbot.py tanpa impor melingkar.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, Optional

PROMO_LEGAL_BASIS = "PP Nomor 50 Tahun 2025"

# Diskon 50% hanya untuk JKK + JKM (JHT tidak didiskon). Periode berbeda per sektor.
PROMO_PERIODS: dict[str, tuple[date, date]] = {
    "transportasi": (date(2026, 1, 1), date(2027, 3, 31)),
    "non_transportasi": (date(2026, 4, 1), date(2026, 12, 31)),
}

# Peringatan dini: berapa hari sebelum promo berakhir pengelola perlu memperbarui kode + dokumen.
EXPIRY_WARNING_DAYS = 45

_WIB = timezone(timedelta(hours=7))   # Waktu Indonesia Barat: tanpa DST, offset tetap

_ID_MONTHS = (
    "januari", "februari", "maret", "april", "mei", "juni",
    "juli", "agustus", "september", "oktober", "november", "desember",
)


def today_jakarta() -> date:
    """Tanggal hari ini di Asia/Jakarta.

    ZoneInfo butuh database zona waktu; Python di Windows tidak membawanya kecuali paket
    `tzdata` terpasang. Bila tidak ada, pakai offset tetap UTC+7 (WIB tidak mengenal DST),
    sehingga fitur promo tidak error di mesin tanpa tzdata.
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Jakarta")).date()
    except Exception:
        return datetime.now(_WIB).date()


class PromoState(NamedTuple):
    sector: str
    state: str          # "upcoming" | "active" | "ended"
    start: date
    end: date
    days_left: int      # hari sampai berakhir (negatif bila sudah berakhir)


def promo_timeline(on_date: Optional[date] = None) -> list[PromoState]:
    """Status tiap periode promo pada tanggal tertentu (default: hari ini di Jakarta)."""
    today = on_date or today_jakarta()
    result = []
    for sector, (start, end) in PROMO_PERIODS.items():
        if today < start:
            state = "upcoming"
        elif today <= end:
            state = "active"
        else:
            state = "ended"
        result.append(PromoState(sector, state, start, end, (end - today).days))
    return result


def _month_year(value: date) -> str:
    return f"{_ID_MONTHS[value.month - 1].capitalize()} {value.year}"


def describe_period(sector: str) -> str:
    """Contoh: 'April 2026 – Desember 2026'."""
    start, end = PROMO_PERIODS[sector]
    return f"{_month_year(start)} – {_month_year(end)}"


def maintenance_warnings(on_date: Optional[date] = None) -> list[str]:
    """Peringatan untuk pengelola: promo sudah/hampir berakhir sehingga kode & dokumen perlu diperbarui."""
    warnings = []
    for item in promo_timeline(on_date):
        label = item.sector.replace("_", " ")
        if item.state == "ended":
            warnings.append(
                f"Promo sektor {label} SUDAH BERAKHIR pada {item.end.isoformat()}. Perbarui promo_config.py "
                "dan teks promo di data/, lalu jalankan ingest.py agar jawaban tidak menyebut promo berlaku."
            )
        elif item.state == "active" and item.days_left <= EXPIRY_WARNING_DAYS:
            warnings.append(
                f"Promo sektor {label} berakhir {item.end.isoformat()} ({item.days_left} hari lagi). "
                "Siapkan pembaruan promo_config.py dan data/."
            )
    return warnings


# --- Konsistensi dengan dokumen di data/ -------------------------------------------------------

_PERIOD_IN_TEXT = re.compile(
    r"(" + "|".join(_ID_MONTHS) + r")\s+(20\d{2})\s*[–—-]\s*(" + "|".join(_ID_MONTHS) + r")\s+(20\d{2})",
    re.IGNORECASE,
)
_TIME_RELATIVE_PROMO = re.compile(
    r"(?:saat ini|sedang berlaku|per (?:" + "|".join(_ID_MONTHS) + r") 20\d{2})", re.IGNORECASE
)


def _month_index(name: str) -> int:
    return _ID_MONTHS.index(name.lower()) + 1


def _config_month_pairs() -> set[tuple[tuple[int, int], tuple[int, int]]]:
    return {
        ((start.year, start.month), (end.year, end.month))
        for start, end in PROMO_PERIODS.values()
    }


def doc_period_mismatches(data_dir: str | Path = "data") -> list[str]:
    """Periode (bulan tahun – bulan tahun) di data/*.txt yang TIDAK cocok dengan PROMO_PERIODS,
    serta periode konfigurasi yang tidak ditemukan di dokumen mana pun."""
    expected = _config_month_pairs()
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    problems = []

    for path in sorted(Path(data_dir).glob("**/*.txt")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in _PERIOD_IN_TEXT.finditer(line):
                pair = (
                    (int(match.group(2)), _month_index(match.group(1))),
                    (int(match.group(4)), _month_index(match.group(3))),
                )
                if pair in expected:
                    seen.add(pair)
                else:
                    problems.append(
                        f"{path.name}:{number}: periode '{match.group(0)}' tidak ada di PROMO_PERIODS"
                    )

    for pair in sorted(expected - seen):
        (sy, sm), (ey, em) = pair
        problems.append(
            f"PROMO_PERIODS memuat {_ID_MONTHS[sm-1].capitalize()} {sy} – {_ID_MONTHS[em-1].capitalize()} {ey} "
            "tetapi periode itu tidak ditemukan di data/ (dokumen belum diperbarui?)"
        )
    return problems


def time_relative_promo_claims(data_dir: str | Path = "data") -> list[str]:
    """Kalimat di data/ yang menyebut promo/diskon sebagai 'saat ini/sedang berlaku/per <bulan>'.

    Kalimat seperti ini menjadi basi saat periode berakhir; chatbot menimpanya dengan tanggal
    sistem, tetapi sebaiknya dokumen ditulis dengan periode eksplisit."""
    claims = []
    for path in sorted(Path(data_dir).glob("**/*.txt")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"promo|diskon", line, re.IGNORECASE) and _TIME_RELATIVE_PROMO.search(line):
                claims.append(f"{path.name}:{number}: {line.strip()[:110]}")
    return claims


def main(argv: list[str]) -> int:
    if "--check" not in argv:
        print(__doc__)
        return 0
    today = today_jakarta()
    print(f"Tanggal sistem (Asia/Jakarta): {today.isoformat()}")
    for item in promo_timeline(today):
        print(f"- {item.sector}: {item.state} ({describe_period(item.sector)}, {item.days_left} hari ke akhir)")

    problems = maintenance_warnings(today) + doc_period_mismatches()
    for line in problems:
        print("PERINGATAN:", line)
    for line in time_relative_promo_claims():
        print("INFO (kalimat relatif-waktu):", line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))