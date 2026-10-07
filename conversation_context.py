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

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

from calculator import detect_sector, extract_base_income, extract_programs


@dataclass(frozen=True)
class ConversationContext:
    """Snapshot slot percakapan yang aman dipakai oleh logic deterministik."""

    base_income: Optional[Decimal] = None
    programs: tuple[str, ...] = ()
    sector: Optional[str] = None

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


def build_conversation_context(
    current_question: str,
    history: Iterable[dict[str, Any]] | None,
) -> ConversationContext:
    """
    Bangun context dengan prioritas:

        pertanyaan terbaru > pesan user sebelumnya.

    Nilai dari pertanyaan saat ini dimasukkan terlebih dahulu sehingga extractor
    tidak perlu diubah dan perilaku parser yang sudah ada tetap terpakai.
    """
    current = str(current_question or "").strip()
    previous_users = _user_messages(history)
    all_user_messages = previous_users + ([current] if current else [])

    return ConversationContext(
        base_income=_latest_slot(all_user_messages, extract_base_income),
        programs=_latest_slot(all_user_messages, extract_programs) or (),
        sector=_latest_slot(all_user_messages, detect_sector),
    )
