Chatbot Informasi BPJS Ketenagakerjaan (RAG) — Tahap 1

Chatbot berbasis RAG (Retrieval-Augmented Generation) untuk membantu rekan magang
lapangan menjawab pertanyaan calon peserta seputar program, syarat klaim, dan
pendaftaran BPJS Ketenagakerjaan.

1. Persiapan Awal

Pastikan Python 3.10+ sudah terpasang: python --version

Buat virtual environment (supaya library proyek ini tidak bentrok dengan proyek lain):

python -m venv venv

Aktifkan virtual environment:

Windows: venv\Scripts\activate

Mac/Linux: source venv/bin/activate

Install seluruh library yang dibutuhkan:

pip install -r requirements.txt

2. Dapatkan API Key Groq (Gratis)

Daftar/login di https://console.groq.com/keys

Buat API key baru, lalu salin.

Salin file .env.example menjadi .env.

Buka file .env, ganti isi_dengan_api_key_groq_kamu_disini dengan API key kamu.

3. Siapkan Dokumen BPJS

Folder data/ sudah berisi bpjs_info.txt sebagai contoh basis pengetahuan.
Untuk penggunaan nyata, ganti/tambahkan file di folder ini dengan dokumen RESMI
(FAQ resmi, buku panduan peserta, dsb.) dari BPJS Ketenagakerjaan. Cukup simpan
sebagai file .txt (dukungan PDF bisa ditambahkan di Tahap 2, lihat roadmap).

4. Bangun Index Pencarian (Vector Store)

Jalankan sekali setiap kali dokumen di folder data/ berubah:

python ingest.py

Perintah ini akan membuat folder vector_store/ berisi index hasil pemrosesan dokumen.

5. Jalankan Chatbot

streamlit run app.py

Browser akan otomatis terbuka menampilkan halaman chat. Coba tanyakan misalnya:
"Apa saja syarat klaim JHT?" atau "Bagaimana cara daftar BPJS Ketenagakerjaan untuk
pekerja mandiri?"

Troubleshooting Singkat

Error "GROQ_API_KEY belum diatur" → cek apakah file .env sudah dibuat dan diisi.

Error saat memuat vector store → jalankan python ingest.py terlebih dahulu.

Jawaban terasa kurang relevan → tambah lebih banyak dokumen di data/, atau
sesuaikan CHUNK_SIZE/TOP_K di ingest.py/chatbot.py.

6. Evaluasi Kualitas Chatbot

Project ini menyediakan benchmark awal di evaluation_dataset.json dan runner di evaluate.py.

Evaluasi tanpa LLM

python evaluate.py

Perintah tersebut menguji:

retrieval hit@k terhadap sumber/section yang diharapkan,

privacy guard,

deterministic calculator,

fallback untuk pertanyaan di luar domain.

Evaluasi dengan LLM

python evaluate.py --with-llm

Mode ini menambahkan smoke test generation berdasarkan expected keywords. Ini bukan pengganti review manusia.

Prasyarat retrieval evaluation

Pastikan vector store sudah dibuat setelah dokumen berubah:

python ingest.py

Hasil

Laporan lengkap disimpan ke evaluation_results.json.

Tahap 8 — Retrieval Quality

Tahap 8 meningkatkan kualitas pencarian dengan: metadata section yang dibawa ke setiap chunk, chunk default 800 karakter dengan overlap 120, pengulangan judul section pada setiap chunk, retrieval kandidat k=8, lexical reranking ringan di atas semantic score, diversifikasi maksimal 2 chunk per section, serta query expansion berbasis history hanya untuk pertanyaan follow-up.

Setelah perubahan ingestion, jalankan ulang python ingest.py agar vector store dibangun dari chunk baru. Setelah itu jalankan python evaluate.py untuk mengukur Hit@1, Hit@3, dan MRR menggunakan pipeline retrieval yang sama dengan chatbot.