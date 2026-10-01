# 🏢 Chatbot Informasi BPJS Ketenagakerjaan (RAG)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Framework-FF4B4B?logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLM_API-f55036?logo=groq&logoColor=white)

Chatbot berbasis **RAG (Retrieval-Augmented Generation)** yang dirancang untuk membantu rekan magang lapangan menjawab pertanyaan calon peserta secara cepat dan akurat. Sistem ini mencakup informasi seputar program, syarat klaim, dan pendaftaran BPJS Ketenagakerjaan berdasarkan dokumen resmi.

---

## 📑 Daftar Isi
1. [Fitur & Optimasi](#-fitur--optimasi)
2. [Prasyarat](#-prasyarat)
3. [Panduan Instalasi](#-panduan-instalasi)
4. [Penggunaan](#-penggunaan)
5. [Evaluasi Kualitas Chatbot](#-evaluasi-kualitas-chatbot)
6. [Troubleshooting](#-troubleshooting)

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