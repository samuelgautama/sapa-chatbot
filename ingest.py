"""
ingest.py
---------
Script ini bertugas membangun "otak pencarian" (vector store) dari dokumen-dokumen
BPJS Ketenagakerjaan yang ada di folder data/.

KAPAN DIJALANKAN?
Jalankan script ini SETIAP KALI kamu menambah, menghapus, atau mengubah isi
dokumen di folder data/. Cukup jalankan sekali saja setelah itu (tidak perlu
dijalankan ulang setiap kali chatbot dipakai).

CARA MENJALANKAN (dari terminal, di folder proyek ini):
    python ingest.py

ALUR KERJA SCRIPT INI:
1. Baca semua dokumen teks di folder data/
2. Potong dokumen jadi bagian-bagian kecil (chunk)
3. Ubah setiap chunk menjadi representasi angka (embedding)
4. Simpan seluruh embedding ke dalam vector store FAISS di folder vector_store/
"""

# --- BAGIAN 1: IMPORT LIBRARY ---

import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
# DirectoryLoader  -> untuk membaca BANYAK file sekaligus dari satu folder
# TextLoader       -> loader spesifik untuk membaca isi file .txt biasa

from langchain_text_splitters import RecursiveCharacterTextSplitter
# RecursiveCharacterTextSplitter -> alat untuk memotong dokumen panjang menjadi
# potongan-potongan kecil (chunk) yang lebih mudah dicari dan pas dengan
# batas konteks yang bisa diproses oleh LLM

from langchain_huggingface import HuggingFaceEmbeddings
# HuggingFaceEmbeddings -> mengubah teks menjadi vector angka (embedding)
# menggunakan model open-source dari HuggingFace, berjalan 100% lokal (gratis)

from langchain_community.vectorstores import FAISS
# FAISS -> "database vector" ringan buatan Meta yang berjalan sepenuhnya di
# komputer lokal (tidak perlu server tambahan), cocok untuk skala proyek kuliah


# --- BAGIAN 2: KONFIGURASI ---
# Kumpulkan semua nilai yang mungkin ingin kamu ubah di satu tempat supaya mudah di-maintain

DATA_PATH = "data"
# Lokasi folder berisi dokumen sumber (peraturan/FAQ BPJS Ketenagakerjaan)

VECTOR_STORE_PATH = "vector_store"
# Lokasi untuk menyimpan hasil index (vector store) di disk

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Model embedding multibahasa yang cukup ringan namun mendukung Bahasa Indonesia
# dengan baik. Model akan otomatis didownload dari HuggingFace saat pertama kali dipakai.

CHUNK_SIZE = 800        # chunk lebih besar agar tabel/syarat/manfaat tidak mudah terpecah
CHUNK_OVERLAP = 120     # overlap cukup untuk menjaga konteks antarchunk


# --- BAGIAN 3: FUNGSI-FUNGSI UTAMA ---

def load_documents():
    """Membaca semua file .txt di dalam folder data/ menjadi list dokumen LangChain."""
    loader = DirectoryLoader(
        DATA_PATH,                              # folder yang mau dibaca
        glob="**/*.txt",                        # pola nama file: ambil semua file .txt, termasuk di dalam subfolder
        loader_cls=TextLoader,                  # gunakan TextLoader untuk tiap file yang ditemukan
        loader_kwargs={"encoding": "utf-8"},    # paksa encoding UTF-8 agar huruf/karakter Indonesia terbaca dengan benar
    )
    documents = loader.load()                    # jalankan proses pembacaan, hasilnya berupa list object Document
    print(f"[INFO] Berhasil memuat {len(documents)} dokumen dari folder '{DATA_PATH}'")
    return documents                              # kembalikan daftar dokumen mentah


def _friendly_source_name(source_path):
    """Mengubah nama file teknis menjadi nama sumber yang lebih ramah untuk UI."""
    filename = source_path.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]
    names = {
        "info_bpu": "Informasi Program BPU",
        "info_magang": "Program Magang Mahasiswa USU di BPJS Ketenagakerjaan",
        "info_umum_bpjs_tk": "Gambaran Umum BPJS Ketenagakerjaan",
        "proses_pendaftaran_bpu": "Proses Pendaftaran BPU melalui Mahasiswa Magang",
    }
    return names.get(filename, filename.replace("_", " ").title())


def _extract_sections(document):
    """Memisahkan dokumen berdasarkan heading Markdown agar metadata section konsisten."""
    text = document.page_content
    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))

    if not matches:
        clone = document.model_copy(deep=True)
        clone.metadata = dict(document.metadata)
        clone.metadata["section"] = "Bagian umum"
        clone.metadata["heading_level"] = 0
        clone.metadata["section_id"] = "section-0"
        return [clone]

    sections = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if not content:
            continue

        section_title = match.group(2).strip()
        clone = document.model_copy(deep=True)
        clone.page_content = content
        clone.metadata = dict(document.metadata)
        clone.metadata["section"] = section_title
        clone.metadata["heading_level"] = len(match.group(1))
        clone.metadata["section_id"] = f"section-{index + 1}"
        sections.append(clone)

    # Pertahankan isi sebelum heading pertama jika ada.
    prefix = text[:matches[0].start()].strip()
    if prefix:
        clone = document.model_copy(deep=True)
        clone.page_content = prefix
        clone.metadata = dict(document.metadata)
        clone.metadata["section"] = "Pendahuluan"
        clone.metadata["heading_level"] = 0
        clone.metadata["section_id"] = "section-0"
        sections.insert(0, clone)

    return sections


def split_documents(documents):
    """Memecah dokumen menjadi chunk sambil membawa metadata sumber dan section."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    for document in documents:
        source_path = document.metadata.get("source", "unknown")
        source_name = _friendly_source_name(source_path)
        sections = _extract_sections(document)

        for section_document in sections:
            section_title = section_document.metadata.get("section", "Bagian umum")
            section_chunks = splitter.split_documents([section_document])
            chunk_count = len(section_chunks)

            for chunk_index, chunk in enumerate(section_chunks, start=1):
                chunk.metadata = dict(chunk.metadata)
                chunk.metadata["source_name"] = source_name
                chunk.metadata["source_file"] = source_path
                chunk.metadata["chunk_index"] = chunk_index
                chunk.metadata["chunk_count"] = chunk_count
                chunk.metadata["citation_label"] = (
                    f"{source_name} — {section_title}"
                )

                # Ulangi judul section pada setiap chunk. Ini membantu embedding mengenali
                # konteks topik walaupun chunk bukan potongan pertama dari section tersebut.
                chunk.page_content = (
                    f"Bagian: {section_title}\n\n"
                    f"{chunk.page_content.strip()}"
                )
                chunks.append(chunk)

    print(f"[INFO] Dokumen berhasil dipecah menjadi {len(chunks)} chunk dengan metadata sumber/section")
    return chunks


def build_vector_store(chunks):
    """Mengubah setiap chunk menjadi embedding, lalu menyimpannya sebagai vector store di disk."""
    print("[INFO] Memuat model embedding (mungkin butuh waktu saat pertama kali dijalankan)...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)  # siapkan "penerjemah" teks -> vector angka

    print("[INFO] Membuat index vector dari seluruh chunk, mohon tunggu...")
    vector_store = FAISS.from_documents(chunks, embeddings)  # hitung embedding tiap chunk & susun jadi index FAISS

    vector_store.save_local(VECTOR_STORE_PATH)   # simpan index ke disk supaya bisa dipakai ulang tanpa membangun dari nol
    print(f"[INFO] Vector store berhasil disimpan di folder '{VECTOR_STORE_PATH}/'")


def main():
    """Fungsi utama yang menjalankan seluruh proses ingestion secara berurutan."""
    documents = load_documents()                 # langkah 1: baca dokumen mentah dari folder data/

    if not documents:                             # jika folder data/ kosong atau tidak ada file .txt ditemukan
        print(
            "[ERROR] Tidak ada dokumen ditemukan di folder 'data/'. "
            "Tambahkan minimal satu file .txt sebelum menjalankan script ini."
        )
        return                                      # hentikan proses lebih awal, tidak lanjut ke langkah berikutnya

    chunks = split_documents(documents)           # langkah 2: pecah dokumen jadi chunk-chunk kecil
    build_vector_store(chunks)                    # langkah 3: ubah chunk jadi embedding & simpan sebagai vector store


if __name__ == "__main__":
    # Blok ini hanya dijalankan kalau file ini dieksekusi langsung (python ingest.py),
    # bukan ketika file ini di-import sebagai modul oleh file lain.
    main()
