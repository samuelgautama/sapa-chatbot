# Quality Review Round 4 - L-8 Verifikasi dengan Knowledge Base Baru

**Tanggal:** 2026-11-18  
**Status:** INCOMPLETE (membutuhkan Groq API key dan testing manual)  
**Tes:** 93 passed, 1 warning  

## 📊 Hasil L-1 hingga L-7

| Item | Status | Keterangan |
|------|--------|------------|
| L-1 | PASS | Patch today_jakarta diperbaiki, test suite 90 passed → 90 passed |
| L-2 | PASS | DOMAIN_KEYWORDS ditambah, kata pendek cocok sebagai kata utuh, test suite 90 passed → 90 passed |
| L-3 | PASS | Slot-filling membajak pertanyaan dicegah, test suite 90 passed → 90 passed |
| L-4 | PASS | Deteksi nominal ambigu sebelum slot disimpan, test suite 90 passed → 90 passed |
| L-5 | PASS | 3 tes syarat ditambahkan, test suite 90 passed → 93 passed |
| L-6 | PASS | Aturan BPU-sentris ditambahkan ke system prompt, test suite 93 passed → 93 passed |
| L-7 | PASS | Indeks diperbarui: 13 dokumen → 252 chunks, vector_store fresh ✅ |

## 🔍 Skenario L-8 (INCOMPLETE - perlu testing manual dengan Groq)

### Kriteria PASS untuk setiap skenario:

#### 1. "Berapa iuran JHT?" 
- ✅ BPU 2% dari dasar penghasilan
- ❌ TIDAK menyebut 5,7%
- ❌ TIDAK mencampur tarif PU dan BPU

#### 2. "Berapa iuran JHT untuk karyawan perusahaan?"
- ✅ PU 5,7% = 2% pekerja + 3,7% pemberi kerja
- ❌ TIDAK mencampur dengan tarif BPU

#### 3. "Berapa manfaat JKP kalau gaji terakhir Rp4 juta?"
- ✅ 60% x Rp4.000.000 = Rp2.400.000 per bulan, maks 6 bulan
- ✅ Upah dibatasi Rp5.000.000
- ❌ TIDAK menghitung >Rp5.000.000

#### 4. "Apakah pedagang bisa ikut JKP?"
- ❌ TIDAK boleh menjawab "ya"
- ✅ Jawaban: JKP hanya Penerima Upah

#### 5. "Cara klaim JHT lewat JMO"
- ✅ Saldo hingga Rp15.000.000
- ✅ Sebab klaim resign atau PHK
- ✅ Sudah pengkinian data, status non-aktif
- ✅ Langkah sesuai data

#### 6. "Dokumen klaim JHT kalau resign"
- ✅ Kartu Peserta, KTP, surat keterangan pengunduran diri
- ✅ NPWP bila saldo > Rp50 juta atau pernah klaim sebagian
- ❌ TIDAK menyebut KK/buku tabungan/paklaring

#### 7. "Apa itu Lapak Asik?"
- ✅ Online video call dan onsite tatap muka
- ✅ Deskripsi sesuai data

#### 8. "Berapa plafon KPR BPJS Ketenagakerjaan?" dan "Apakah pedagang bisa ambil KPR BPJS?"
- ✅ Rp500.000.000; tenor maks 30 tahun
- ❌ Ketentuan MLT untuk BPU belum tersedia
- ✅ Arahkan ke kantor cabang atau 175

#### 9. "Syarat daftar BPU"
- ✅ NIK/KTP, belum 65 tahun, punya kegiatan usaha maks 2 jenis, dasar penghasilan minimal Rp1.000.000

#### 10. "Cara daftar JMO"
- ✅ 12 langkah sesuai data

#### 11. "Berapa manfaat JKM?"
- ✅ Rp20.000.000 + Rp12.000.000 + Rp10.000.000 sesuai data
- ❌ TIDAK mencampur segmen

#### 12. "Bagaimana cara bikin SIM?" dan "Siapa presiden Indonesia?"
- ❌ Ditolak sebagai di luar topik

#### 13. "Tarif iuran Jakon proyek Rp300 juta"
- ❌ TIDAK menghitung sendiri
- ✅ Jelaskan struktur tarif dan arahkan ke simulasi e-Jakon

#### 14. "Penghasilan 1 juta 500"
- ✅ Minta konfirmasi: "Maksudnya Rp1.500.000 atau Rp1.000.500? Tulis angka lengkap."

## ⚠️ Catatan untuk Testing Manual

**Aturan penilaian:**
- Angka/prosedur yang TIDAK ada di data/ = FAIL (halusinasi)
- Mencampur tarif PU dan BPU tanpa diminta = FAIL
- "belum tersedia" padahal ada di data = FAIL

**Dokumen yang tersedia (13 file):**
- 00_glosarium_faq_bpu.txt
- 08_faq_lapangan_bpu.txt
- 09_objection_handling_bpu.txt
- 10_penerima_upah_pu.txt (baru)
- 11_jkp_jaminan_kehilangan_pekerjaan.txt (baru)
- 12_klaim_jht_panduan.txt (baru)
- 13_aplikasi_jmo.txt (baru)
- 14_mlt_perumahan_pekerja.txt (baru)
- 15_jasa_konstruksi_jakon.txt (baru)
- info_bpu.txt
- info_magang.txt
- info_umum_bpjs_tk.txt
- proses_pendaftaran_bpu.txt

## 🔄 Status Vector Store

- **Jumlah dokumen:** 13
- **Jumlah chunk:** 252
- **Vector store:** Fresh ✅
- **Manifest:** Memuat semua 13 dokumen