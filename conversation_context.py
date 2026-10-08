"""
conversation_context.py
-----------------------
Memory terstruktur ringan untuk mempertahankan konteks percakapan tanpa
memanggil LLM tambahan.

Prinsip:
- hanya membaca pesan USER untuk mengisi slot, sehingga jawaban LLM tidak dapat
  "menulis ulang" memory secara tidak sengaja;
- pesan terbaru memiliki prioritas;
- slot yang belum disebut di pesan terbaru dapat diwarisi dari percakapan
  sebelumnya;
- slot ini dipakai sebagai konteks, bukan sebagai sumber fakta eksternal.

Slot yang saat ini dijaga:
- base_income : dasar penghasilan calon peserta;
- programs    : program yang terakhir disebut user;
- sector      : sektor pekerjaan, terutama untuk validasi promo.

Discount/promo request TIDAK disimpan sebagai slot persisten. Permintaan diskon
harus disebut pada pertanyaan saat ini agar promo lama tidak terbawa ke simulasi
berikutnya secara tidak sengaja.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

from calculator import detect_sector, extract_base_income, extract_programs


# Slot hanya diwarisi dari N pesan user terakhir. Tanpa batas, penghasilan calon peserta
# pertama masih terpakai puluhan pesan kemudian untuk calon peserta lain.
MAX_CONTEXT_USER_MESSAGES = 6

# Frasa yang menandai user berpindah ke calon peserta lain / memulai simulasi baru.
# Slot dari pesan SEBELUM pesan penanda tidak diwarisi lagi.
_RESET_PATTERN = re.compile(
    r"\b(?:"
    r"(?:calon\s+peserta|peserta|calon|orang|pelanggan|warga|bapak|ibu|pak|bu)\s+(?:lain|lainnya|baru|berikutnya|selanjutnya)"
    r"|(?:bapak|pak)\s*/\s*(?:ibu|bu)\s+lain"
    r"|ganti\s+calon"
    r"|mulai\s+(?:dari\s+awal|ulang|baru)"
    r"|simulasi\s+baru"
    r"|reset"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConversationContext:
    """Snapshot slot percakapan yang aman dipakai oleh logic deterministik.

    inherited_slots berisi nama slot ("base_income", "programs", "sector") yang nilainya
    BUKAN berasal dari pertanyaan saat ini melainkan diwarisi dari pesan sebelumnya.
    Pemanggil wajib menampilkannya ke user agar pewarisan tidak terjadi diam-diam.
    """

    base_income: Optional[Decimal] = None
    programs: tuple[str, ...] = ()
    sector: Optional[str] = None
    inherited_slots: tuple[str, ...] = ()

    @property
    def has_any(self) -> bool:
        return bool(self.base_income is not None or self.programs or self.sector)

    def to_prompt(self) -> str:
        """Format singkat untuk membantu LLM memahami state percakapan."""
        if not self.has_any:
            return "Tidak ada konteks terstruktur yang tersimpan."

        lines: list[str] = []
        if self.base_income is not None:
            lines.append(f"- Dasar penghasilan yang disebut user: {self.base_income}")
        if self.programs:
            lines.append(f"- Program terakhir yang disebut user: {', '.join(self.programs)}")
        if self.sector:
            sector_label = self.sector.replace("_", " ")
            lines.append(f"- Sektor terakhir yang disebut user: {sector_label}")
        return "\n".join(lines)


def _user_messages(history: Iterable[dict[str, Any]] | None) -> list[str]:
    """Ambil hanya pesan user yang punya isi."""
    if not history:
        return []

    messages: list[str] = []
    for item in history:
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content = str(item.get("content", "")).strip()
        if content:
            messages.append(content)
    return messages


def _latest_slot(
    messages: list[str],
    extractor,
):
    """Ambil nilai terbaru yang berhasil diekstrak dari kumpulan pesan user."""
    for message in reversed(messages):
        value = extractor(message)
        if value:
            return value
    return None


def _active_user_messages(
    previous_users: list[str],
    current: str,
    max_messages: int = MAX_CONTEXT_USER_MESSAGES,
) -> list[str]:
    """Pesan user yang masih boleh menyumbang slot: setelah penanda reset terakhir, dalam jendela N pesan."""
    messages = previous_users + ([current] if current else [])

    last_reset = None
    for index, message in enumerate(messages):
        if _RESET_PATTERN.search(message):
            last_reset = index
    if last_reset is not None:
        messages = messages[last_reset:]

    return messages[-max_messages:]


def _income_slot(message: str):
    # Tanpa cek minimum: nominal penghasilan di bawah minimum tetap menjadi "penghasilan terbaru"
    # agar tidak diam-diam digantikan angka lama; penolakannya dilakukan oleh pemanggil.
    return extract_base_income(message, enforce_minimum=False)


def build_conversation_context(
    current_question: str,
    history: Iterable[dict[str, Any]] | None,
    max_messages: int = MAX_CONTEXT_USER_MESSAGES,
) -> ConversationContext:
    """
    Bangun context dengan prioritas:

        pertanyaan terbaru > pesan user sebelumnya (dalam jendela, setelah reset terakhir).

    Slot yang tidak disebut pada pertanyaan terbaru tetapi terisi dari riwayat dicatat di
    `inherited_slots`.
    """
    current = str(current_question or "").strip()
    previous_users = _user_messages(history)
    messages = _active_user_messages(previous_users, current, max_messages)

    base_income = _latest_slot(messages, _income_slot)
    programs = _latest_slot(messages, extract_programs) or ()
    sector = _latest_slot(messages, detect_sector)

    inherited: list[str] = []
    if current:
        if base_income is not None and _income_slot(current) is None:
            inherited.append("base_income")
        if programs and not extract_programs(current):
            inherited.append("programs")
        if sector is not None and detect_sector(current) is None:
            inherited.append("sector")

    return ConversationContext(
        base_income=base_income,
        programs=programs,
        sector=sector,
        inherited_slots=tuple(inherited),
    )