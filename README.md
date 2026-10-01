# 🏢 Chatbot Informasi BPJS Ketenagakerjaan (RAG)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Framework-FF4B4B?logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLM_API-f55036?logo=groq&logoColor=white)

Chatbot berbasis **RAG (Retrieval-Augmented Generation)** yang dirancang untuk membantu rekan magang lapangan menjawab pertanyaan calon peserta secara cepat dan akurat. Sistem ini mencakup informasi seputar program, syarat klaim, dan pendaftaran BPJS Ketenagakerjaan berdasarkan dokumen resmi.

---

## 📑 Daftar Isi
1. Fitur & Optimasi
2. Prasyarat
3. Panduan Instalasi
4. Penggunaan
5. Evaluasi Kualitas Chatbot
6. Troubleshooting

---

## ✨ Fitur & Optimasi

Sistem ini telah melewati optimasi **Tahap 8 (Retrieval Quality)** dengan peningkatan kualitas pencarian berikut:
* **Metadata & Chunking**: Membawa metadata *section* ke setiap *chunk*. Konfigurasi *default* menggunakan 800 karakter dengan *overlap* 120, serta pengulangan judul *section* pada setiap *chunk*.
* **Advanced Retrieval**: Pengambilan kandidat dokumen (*retrieval candidates*) hingga `k=8`, dikombinasikan dengan *lexical reranking* ringan di atas nilai semantik.
* **Diversifikasi & Ekspansi**: Maksimal 2 *chunk* per *section* untuk diversifikasi hasil, serta ekspansi *query* berbasis riwayat (khusus untuk pertanyaan lanjutan/ *follow-up*).

---

## ⚙️ Prasyarat

Sebelum memulai, pastikan sistem Anda telah memenuhi persyaratan berikut:
* **Python**: Versi 3.10 atau lebih baru. Cek dengan menjalankan `python --version`.
* **API Key Groq**: Diperlukan untuk inferensi LLM. Anda bisa mendapatkannya secara gratis di [Console Groq](https://console.groq.com/keys).

---

## 🚀 Panduan Instalasi

**1. Persiapan *Virtual Environment***  
Sangat disarankan menggunakan *virtual environment* agar dependensi proyek tidak bentrok.

```bash
# Membuat virtual environment
python -m venv venv

# Mengaktifkan virtual environment (Windows)
venv\Scripts\activate

# Mengaktifkan virtual environment (Mac/Linux)
source venv/bin/activate
```

**2. Instalasi Dependensi**
Install seluruh pustaka yang dibutuhkan melalui `requirements.txt`.

```bash
pip install -r requirements.txt
```

**3. Konfigurasi Environment Variables**
Salin *file* konfigurasi dan masukkan API Key Anda.

```bash
cp .env.example .env
```
Buka file `.env` dan ganti `isi_dengan_api_key_groq_kamu_disini` dengan API Key Groq Anda yang sebenarnya.

---

## 💡 Penggunaan

**1. Siapkan Dokumen Pengetahuan (Knowledge Base)**'
Sistem membutuhkan data referensi untuk RAG.
- Folder `data/` telah menyediakan *file* `bpjs_info.txt` sebagai contoh.
- Untuk implementasi nyata, tambahkan atau ganti dengan dokumen RESMI dari BPJS Ketenagakerjaan (seperti FAQ resmi atau buku panduan). Saat ini, sistem mendukung format `.txt`.

**2. Bangun Index Pencarian (Vector Store)**
Setiap kali ada perubahan atau penambahan dokumen di dalam folder `data/`, Anda wajib memperbarui indeks.

```bash
python ingest.py
```
(Perintah ini akan memproses dokumen dan membuat folder `vector_store/` yang berisi indeks pencarian).

**3. Jalankan Aplikasi Chatbot**
Mulai antarmuka pengguna berbasis Streamlit.

```bash
streamlit run app.py
```
Browser akan otomatis terbuka. Anda dapat langsung menguji chatbot dengan pertanyaan seperti:
- "Apa itu JHT?"
- "Bagaimana cara daftar BPJS Ketenagakerjaan untuk pekerja mandiri?"

---

## 📊 Evaluasi Kualitas Chatbot

Proyek ini dilengkapi dengan modul evaluasi (benchmark awal di `evaluation_dataset.json` dan runner di `evaluate.py`) untuk mengukur akurasi dari metrik Hit@1, Hit@3, dan MRR.

> ⚠️ Penting: Pastikan vector store sudah dibuat/diperbarui dengan menjalankan `python ingest.py` sebelum melakukan evaluasi.

**Evaluasi Tanpa LLM**
Menguji retrieval hit@k, privacy guard, kalkulator deterministik, dan respons fallback untuk pertanyaan di luar domain.

```bash
python evaluate.py
```

**Evaluasi Menggunakan LLM**
Menambahkan smoke test generation berdasarkan ekspektasi kata kunci (expected keywords). Mode ini berguna sebagai pengecekan otomatis, namun tidak menggantikan tinjauan manual/manusia.

```bash
python evaluate.py --with-llm
```
Laporan lengkap hasil evaluasi akan disimpan secara otomatis ke dalam `evaluation_results.json`.

---

## 🛠️ Troubleshooting Singkat

| Isu / Kendala | Solusi yang Disarankan |
| -------- | -------- |
| Error "GROQ_API_KEY belum diatur" | Cek kembali apakah file `.env` sudah dibuat dan API Key telah diisi dengan benar. |
| Error saat memuat vector store | Anda belum membuat indeks. Jalankan perintah `python ingest.py` terlebih dahulu. |
| Jawaban terasa kurang relevan | Tambahkan lebih banyak dokumen pendukung di folder `data/`, atau lakukan penyesuaian nilai `CHUNK_SIZE / TOP_K` pada file `ingest.py` dan `chatbot.py`. |