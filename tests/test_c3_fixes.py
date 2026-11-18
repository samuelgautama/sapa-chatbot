"""
Test untuk perbaikan C3-1 sampai C3-5 (audit round 3).

C3-1: Jawaban hitung iuran/diskon harus deterministik dari calculator.py
C3-2: Nominal ambigu "1 juta 500" harus minta konfirmasi
C3-3: Pertanyaan lanjutan "Syarat?" dengan konteks domain harus masuk RAG
C3-4: Retrieval pasca-sensor dan "Cara daftar BPU?"
C3-5: Fallback kontak relevan dengan intent
"""

import re
from decimal import Decimal
from sapa.calculator import detect_ambiguous_nominal, detect_calculation_request, format_rupiah
from sapa.retrieval_utils import build_retrieval_query, needs_history_for_retrieval


# --- C3-1: Kalkulator deterministik ---

def test_c3_1a_riwayat_berapa_iuran_3_program_lalu_penghasilan():
    """C3-1a: riwayat ['Berapa iuran 3 program?', ...] lalu 'Penghasilan Rp5 juta' → hitung."""
    history = [
        {"role": "user", "content": "Berapa iuran 3 program?"},
        {"role": "assistant", "content": "Silakan sebutkan penghasilan..."},
    ]
    question = "Penghasilan Rp5 juta"
    
    # detect_calculation_request harus mengenali ini dengan history
    result = detect_calculation_request(question, has_income_context=False, history=history)
    assert result is True, "Harus deteksi kalkulasi dengan history 'Berapa iuran 3 program?'"


def test_c3_1b_riwayat_penghasilan_lalu_hitung_iuran():
    """C3-1b: riwayat berisi penghasilan lalu 'Hitung iuran' → simulasi."""
    history = [
        {"role": "user", "content": "Penghasilan 2 juta"},
        {"role": "assistant", "content": "Tercatat"},
    ]
    question = "Hitung iuran"
    
    result = detect_calculation_request(question, has_income_context=True, history=history)
    assert result is True, "Harus deteksi 'Hitung iuran' dengan konteks penghasilan"


def test_c3_1c_riwayat_sektor_penghasilan_lalu_ada_diskon():
    """C3-1c: riwayat sektor+penghasilan+simulasi lalu 'Ada diskon?' → jawab deterministik."""
    history = [
        {"role": "user", "content": "Saya pedagang"},
        {"role": "assistant", "content": "Baik"},
        {"role": "user", "content": "Penghasilan 1 juta"},
        {"role": "assistant", "content": "Tercatat"},
        {"role": "user", "content": "Hitung iuran"},
        {"role": "assistant", "content": "Hasil simulasi..."},
    ]
    question = "Ada diskon?"
    
    result = detect_calculation_request(question, has_income_context=True, history=history)
    assert result is True, "Harus deteksi 'Ada diskon?' dengan riwayat kalkulasi"


def test_c3_1d_iuran_pedagang_1_juta():
    """C3-1d: 'Iuran pedagang 1 juta?' → langsung hitung (nominal terbaca)."""
    question = "Iuran pedagang 1 juta?"
    
    result = detect_calculation_request(question, has_income_context=False, history=None)
    assert result is True, "Harus deteksi 'Iuran pedagang 1 juta?' tanpa konteks"


# --- C3-2: Nominal ambigu ---

def test_c3_2_nominal_ambigu_1_juta_500():
    """C3-2: '1 juta 500' (tanpa satuan akhir) → minta konfirmasi."""
    question = "Penghasilan 1 juta 500"
    
    result = detect_ambiguous_nominal(question)
    assert result is not None, "Harus deteksi nominal ambigu '1 juta 500'"
    assert "Rp1.000.500" in result or "1 juta 500" in result, "Harus menyebut opsi pertama"
    assert "Rp1.500.000" in result or "1 juta 500 ribu" in result, "Harus menyebut opsi kedua"


def test_c3_2_nominal_jelas_1_juta_500_ribu():
    """C3-2: '1 juta 500 ribu' (dengan satuan akhir) → BUKAN ambigu."""
    question = "Penghasilan 1 juta 500 ribu"
    
    result = detect_ambiguous_nominal(question)
    assert result is None, "Harus TIDAK menganggap '1 juta 500 ribu' sebagai ambigu"


# --- C3-5: Fallback kontak relevan ---

def test_c3_5_fallback_kontak_relevan_dengan_intent():
    """C3-5: Fallback harus menampilkan kontak relevan dengan intent, bukan semua."""
    # Ini akan diuji di level integrasi dengan _fallback_response
    pass


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
    exit(0 if failed == 0 else 1)
