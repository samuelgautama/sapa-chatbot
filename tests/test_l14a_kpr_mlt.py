"""
Tests untuk L-14a: Kalkulator iuran tidak membajak pertanyaan KPR/MLT

Masalah: "Plafon KPR Rp500 juta tenor 30 tahun, cicilannya berapa?" dijawab sebagai
simulasi iuran BPU karena detect_calculation_request mendeteksi nominal besar.
"""

import pytest
from sapa.calculator import detect_calculation_request


def test_kpr_questions_not_calculation():
    """L-14a(a): Pertanyaan KPR/MLT tidak dianggap permintaan kalkulasi iuran."""
    # Tanpa history
    assert not detect_calculation_request("Plafon KPR Rp500 juta tenor 30 tahun, cicilannya berapa?")
    assert not detect_calculation_request("Cicilan PUMP Rp150 juta 20 tahun?")
    assert not detect_calculation_request("Angsuran rumah Rp300 juta berapa per bulan?")
    assert not detect_calculation_request("Pinjaman perumahan Rp200 juta tenor 15 tahun?")
    assert not detect_calculation_request("Kredit MLT Rp100 juta angsurannya berapa?")
    
    # Dengan history yang memuat JHT/BPU (simulasi sebelumnya)
    history = [
        {"role": "user", "content": "Berapa iuran JHT untuk penghasilan 3 juta?"},
        {"role": "assistant", "content": "Iuran JHT 3 program..."},
    ]
    assert not detect_calculation_request(
        "Plafon KPR Rp500 juta tenor 30 tahun, cicilannya berapa?",
        history=history
    )
    assert not detect_calculation_request(
        "Cicilan PUMP Rp150 juta 20 tahun?",
        history=history
    )


def test_bpu_iuran_questions_still_work():
    """L-14a(b): Pertanyaan iuran BPU tetap terdeteksi dengan benar."""
    # Tes lama yang harus tetap True
    assert detect_calculation_request("Berapa iuran 3 program untuk penghasilan 5 juta?")
    assert detect_calculation_request("Iuran JKK + JKM untuk 2 juta?")
    assert detect_calculation_request("Simulasi iuran pedagang 1 juta")
    
    # Dengan history
    history = [
        {"role": "user", "content": "Berapa iuran 3 program?"},
        {"role": "assistant", "content": "Berapa dasar penghasilan per bulan?"},
    ]
    assert detect_calculation_request("Penghasilan 5 juta", history=history)
    assert detect_calculation_request("5 juta", has_income_context=False, history=history)


def test_iuran_with_kpr_context_allowed():
    """L-14a(c): Jika jelas menyebut 'iuran' atau 'simulasi', tetap dianggap kalkulasi."""
    # Edge case: seseorang bertanya iuran BPU dalam konteks KPR (jarang, tapi valid)
    assert detect_calculation_request("Simulasi iuran BPU untuk pekerja perumahan 3 juta")
    assert detect_calculation_request("Iuran JKK untuk kurir rumah tangga 2 juta")
