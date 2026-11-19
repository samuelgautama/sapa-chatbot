import re
import json
from pathlib import Path
from unittest.mock import Mock

from scripts.ingest import _is_chunk_useful


def test_is_chunk_useful_skips_empty_heading():
    """Test bahwa chunk yang hanya berisi 'Bagian:' dan heading dilewati."""
    content = "Bagian: Cara Daftar BPU\n\n## B. Program dan Iuran"
    assert not _is_chunk_useful(content), "Chunk hanya heading harus dilewati"


def test_is_chunk_useful_passes_short_but_substantive():
    """Test bahwa chunk pendek namun substantif tetap lolos (>=25 karakter)."""
    # Ini 39 karakter tanpa spasi, 47 dengan spasi
    content = "Bagian: FAQ\n\n**Jawaban:** BPU adalah peserta bukan penerima upah."
    assert _is_chunk_useful(content), "Chunk substantif >=25 karakter harus lolos"


def test_is_chunk_useful_passes_multi_line_content():
    """Test bahwa chunk dengan beberapa baris konten lolos."""
    content = """Bagian: Prosedur

Langkah 1: Isi formulir.
Langkah 2: Bayar iuran.
Langkah 3: Ambil kartu."""
    assert _is_chunk_useful(content), "Chunk dengan konten multi-baris harus lolos"


def test_is_chunk_useful_skips_metadata_only():
    """Test bahwa chunk metadata seperti '# Catatan:' dilewati."""
    content = "Bagian: Metadata\n\n# Catatan:\n# Sumber:"
    assert not _is_chunk_useful(content), "Chunk hanya metadata harus dilewati"


if __name__ == "__main__":
    test_is_chunk_useful_skips_empty_heading()
    test_is_chunk_useful_passes_short_but_substantive()
    test_is_chunk_useful_passes_multi_line_content()
    test_is_chunk_useful_skips_metadata_only()
    print("PASS: Semua tes _is_chunk_useful berjalan")
