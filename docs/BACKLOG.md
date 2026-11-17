# BACKLOG — Masalah yang Ditemukan Selama Audit

**Tanggal:** 2026-11-13  
**Auditor:** AI Assistant (Kiro)  
**Branch:** quality-round2-20261106  

---

## C3-7a: Peringatan Skor Relevansi di Luar Rentang 0-1

### Temuan
Saat menjalankan tes retrieval (`test_retrieval_gate.py`) dan scenarios (`run_quality_scenarios.py`), muncul warning:

```
Skor relevansi di luar rentang 0-1. Periksa normalisasi embedding / metrik jarak indeks dan kalibrasi ulang MIN_RELEVANCE_SCORE.
```

### Lokasi
- **File:** `chatbot.py`, baris ~707 (fungsi `_retrieve_with_confidence`)
- **Konteks:** Warning dipicu di `_retrieve_with_confidence` ketika ada skor di luar rentang [0, 1]

### Penyebab
FAISS dengan metric L2 mengembalikan relevance score = 1 - (distance / sqrt(2)). Namun:
1. Skor bisa < 0 jika jarak > sqrt(2)
2. Skor bisa > 1 jika ada bug normalisasi
3. Nilai skor aktual yang diamati: dari -0.08 hingga > 1 (berdasarkan output test sebelumnya yang menampilkan skor hingga -0.086624384)

### Dampak
- Ambang `MIN_RELEVANCE_SCORE` (default 0.3) tidak bermakna karena skor bisa negatif
- Confidence gate semantik menjadi tidak akurat
- Rescuing dokumen dengan skor rendah bisa salah

### Rekomendasi (TODO)
1. Cek normalisasi embedding di `ingest.py` — apakah ada layer normalisasi vektor sebelum disimpan ke FAISS?
2. Verifikasi metric jarak FAISS (L2 vs. cosine similarity)
3. Kalibrasi ulang `MIN_RELEVANCE_SCORE` berdasarkan distribusi skor aktual
4. Mungkin perlu transformasi skor ke rentang [0, 1] secara deterministik

---

## C3-7b: Skor Relevansi Negatif Spesifik

### Contoh Nilai
Dari output test quality scenarios:
- `np.float32(0.07972264)` — normal (dalam rentang 0-1)
- `np.float32(-0.066242695)` — negatif
- `np.float32(-0.07156575)` — negatif
- `np.float32(-0.086624384)` — negatif
- `np.float32(-0.088413596)` — negatif

### Pemicu
Skor negatif muncul saat:
1. Embedding query dan dokumen sangat berbeda
2. Metrik jarak L2 menghasilkan distance > sqrt(2)
3. Formula `1 - (distance / sqrt(2))` menghasilkan nilai negatif

### Aksi
**Tidak ada aksi segera** — per instruksi "JANGAN ubah". Catat saja sebagai backlog untuk diselesaikan di tahap berikutnya.

---

## C3-1e: Inconsistensi LLM vs. Kalkulator Deterministik

### Temuan
Dari `docs/quality_review_round2.md`:
- **S01**: "Penghasilan Rp5 juta" → LLM menjawab dengan rumus PU (5.7% untuk JHT) bukan BPU (2%)
- **S03**: "Iuran pedagang 1 juta?" → LLM minta klarifikasi program, tidak langsung hitung

### Penyebab
- `detect_calculation_request` mungkin masih longgar
- Atau LLM tidak mengikuti hasil kalkulator deterministik yang disediakan di prompt

### Status
**Sudah diperbaiki** di commit C3-1 — `detect_calculation_request` diperluas untuk menangani pola baru.

---

## C3-4: Retrieval "Cara daftar BPU?" Gagal

### Temuan
Dari `docs/quality_review_round2.md` S18:
- "Cara daftar BPU?" → LLM mengarang "jalur khusus mahasiswa magang via kampus"
- Informasi kanal pendaftaran (website, JMO, kantor, Agen Perisai) ada di `data/info_bpu.txt` tetapi tidak diambil

### Status
**Sudah diperbaiki** di commit C3-4:
1. Tambah aturan SYSTEM_PROMPT: "DILARANG mengarang jalur... Jangan membuat kategori pendaftaran baru..."
2. Pembersihan token disensor dari query retrieval

---

## C3-14: Mock Date Tidak Berfungsi

### Temuan
Dari `docs/LAPORAN_BUG_ROUND2.md`:
- S14: Mock date 2027-01-05 tidak berfungsi — sistem tetap pakai 09 Nov 2026
- `patch("promo_config.today_jakarta")` mungkin tidak terimplementasi dengan benar

### Penyebab
Patch di `run_quality_scenarios.py` mungkin tidak mempengaruhi semua import `today_jakarta()` karena:
1. Multiple import paths (`from promo_config import today_jakarta`)
2. Mungkin ada caching di modul Python

### Status
**Belum diperbaiki** — perlu verifikasi di C3-6

---

## Daftar Prioritas
1. [ ] Kalibrasi skor relevansi FAISS (C3-7a)
2. [ ] Verifikasi mock date untuk promo basi (C3-14)
3. [ ] Test coverage untuk C3-1 sampai C3-5
4. [ ] Automated quality scenarios dengan assertion
5. [ ] Monitoring distribusi skor relevansi di production

---

**Catatan:** Semua item di atas adalah catatan temuan. Perbaikan akan dilakukan di tahap/tiket terpisah sesuai keputusan tim pengembang.
