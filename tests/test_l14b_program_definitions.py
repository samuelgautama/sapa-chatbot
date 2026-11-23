"""
Tests untuk L-14b: Definisi singkatan program di system prompt
"""

import pytest


def test_system_prompt_contains_program_definitions():
    """L-14b: System prompt memuat definisi singkatan program."""
    from sapa.chatbot import SYSTEM_PROMPT
    
    # Harus ada baris yang mendefinisikan program
    assert "JKK = Jaminan Kecelakaan Kerja" in SYSTEM_PROMPT
    assert "JKM = Jaminan Kematian" in SYSTEM_PROMPT
    assert "JHT = Jaminan Hari Tua" in SYSTEM_PROMPT
    assert "JKP = Jaminan Kehilangan Pekerjaan" in SYSTEM_PROMPT
    assert "JP = Jaminan Pensiun" in SYSTEM_PROMPT
