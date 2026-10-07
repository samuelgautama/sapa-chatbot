"""
chatbot.py
----------
Modul ini berisi "logika inti" chatbot RAG (Retrieval-Augmented Generation):
1. RETRIEVAL   -> mengambil potongan dokumen BPJS yang paling relevan dengan pertanyaan
2. AUGMENTATION -> menggabungkan potongan dokumen itu ke dalam prompt
3. GENERATION  -> meminta LLM (lewat Groq) menjawab HANYA berdasarkan potongan dokumen tadi

Modul ini tidak dijalankan langsung, melainkan dipanggil oleh app.py (antarmuka Streamlit).
"""

# --- BAGIAN 1: IMPORT LIBRARY ---

import os
import re
from dataclasses import dataclass
from typing import Optional
# modul bawaan Python untuk membaca environment variable (misalnya API key)

from dotenv import load_dotenv
# untuk membaca file .env dan memuat isinya sebagai environment variable

from langchain_huggingface import HuggingFaceEmbeddings
# model embedding -> HARUS SAMA PERSIS dengan yang dipakai di ingest.py,
# supaya "bahasa angka" antara pertanyaan dan dokumen bisa saling dibandingkan

from langchain_community.vectorstores import FAISS
# untuk memuat kembali vector store yang sudah dibuat oleh ingest.py

from langchain_groq import ChatGroq
# wrapper LangChain untuk memanggil LLM (Large Language Model) lewat Groq API

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from privacy_guard import sanitize_user_input
from retrieval_utils import (
    build_retrieval_query,
    rerank_scored_documents,
)
from conversation_context import ConversationContext, build_conversation_context

from calculator import (
    build_calculation_response,
    calculate_bpu_contribution,
    detect_calculation_request,
    detect_discount_request,
    detect_sector,
    extract_base_income,
    extract_programs,
    promo_status,
    PROMO_PERIODS,
)
# SystemMessage -> untuk mengirim "aturan main" / persona tetap ke LLM (system prompt)
# HumanMessage  -> untuk mengirim isi pesan dari user (konteks + pertanyaan) secara terpisah
# Memisahkan keduanya adalah cara yang lebih benar dibanding menggabung semuanya
# jadi satu string, karena kebanyakan chat model (termasuk yang dipakai Groq)
# memang dilatih untuk membedakan instruksi "sistem" vs isi "percakapan user"


load_dotenv()
# baca file .env di folder proyek ini, lalu masukkan isinya (mis. GROQ_API_KEY)
# ke dalam environment variable supaya bisa diakses lewat os.getenv(...)


# --- BAGIAN 2: KONFIGURASI ---

VECTOR_STORE_PATH = "vector_store"
# lokasi vector store hasil ingest.py

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# WAJIB identik dengan EMBEDDING_MODEL_NAME di ingest.py

LLM_MODEL_NAME = "openai/gpt-oss-20b"
# Nama model LLM yang tersedia di Groq untuk akun Developer/gratis.
# CATATAN: model "llama-3.1-8b-instant" & "llama-3.3-70b-versatile" per saat ini
# sudah dipindah Groq ke tier Enterprise (contact sales), jadi TIDAK BISA dipakai
# akun developer biasa lagi -> kalau dipaksa, akan muncul error 404 model_not_found.
# Kalau ingin kualitas jawaban lebih baik (dengan sedikit trade-off kecepatan),
# ganti ke "openai/gpt-oss-120b".
# Katalog model Groq bisa berubah lagi kapan saja -> cek daftar model TERBARU yang
# benar-benar bisa diakses akunmu lewat: https://console.groq.com/docs/models
# atau langsung lewat API: GET https://api.groq.com/openai/v1/models
# (pakai header Authorization: Bearer <GROQ_API_KEY> milikmu)

TOP_K = 3
# jumlah potongan dokumen yang akhirnya diberikan ke LLM

RETRIEVAL_K = 8
# jumlah kandidat yang dicari lebih dulu sebelum dilakukan pemeriksaan relevansi

MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.15"))
# ambang minimum skor relevansi LangChain (0-1) agar hasil retrieval dianggap cukup
# relevan. Nilai ini sengaja dibuat configurable untuk dikalibrasi menggunakan
# evaluation dataset pada tahap berikutnya.

MAX_HISTORY_MESSAGES = 8
# jumlah maksimum pesan lama yang diteruskan ke LLM untuk menjaga konteks percakapan

MAX_HISTORY_MESSAGES_FOR_RETRIEVAL = 4
# jumlah maksimum pesan terakhir yang ikut membantu pencarian dokumen relevan
MAX_CHUNKS_PER_SECTION = 2
# batasi chunk dari section yang sama agar TOP_K tidak dipenuhi potongan yang hampir identik

PROMO_SOURCES = {
    "non_transportasi": "April 2026 – Desember 2026",
    "transportasi": "Januari 2026 – Maret 2027",
}

# Tahap 2: chatbot difokuskan sebagai "Asisten Akuisisi BPU".
# Intent dipakai untuk mengubah cara chatbot membantu mahasiswa magang,
# bukan untuk menggantikan RAG sebagai sumber fakta.
FIELD_INTENTS = {
    "identifikasi": {
        "label": "🔎 Identifikasi Calon Peserta",
        "keywords": [
            "calon peserta", "siapa yang bisa", "cocok jadi peserta",
            "pedagang", "petani", "nelayan", "freelancer", "ojol",
            "pekerja mandiri", "bpu", "pekerjaan"
        ],
        "instruction": (
            "Bantu mahasiswa menilai apakah situasi calon peserta sesuai dengan "
            "kategori BPU berdasarkan dokumen. Jangan membuat syarat baru. "
            "Jika informasi calon peserta belum cukup, ajukan pertanyaan klarifikasi yang singkat. "
            "Fokus pada jenis pekerjaan, status kepesertaan, dan kebutuhan informasi yang memang "
            "didukung dokumen."
        ),
    },
    "edukasi": {
        "label": "📚 Edukasi Program",
        "keywords": [
            "jelaskan", "apa itu", "manfaat", "jkk", "jkm", "jht",
            "perlindungan", "jaminan", "program"
        ],
        "instruction": (
            "Bantu mahasiswa menjelaskan program kepada calon peserta dengan bahasa lapangan "
            "yang sederhana. Utamakan manfaat, syarat, dan angka yang benar-benar ada di dokumen. "
            "Jika berguna, berikan contoh kalimat yang dapat disampaikan kepada calon peserta."
        ),
    },
    "simulasi": {
        "label": "💰 Simulasi Iuran",
        "keywords": [
            "iuran", "berapa bayar", "berapa per bulan", "hitung", "simulasi",
            "rp", "penghasilan"
        ],
        "instruction": (
            "Bantu menghitung atau menjelaskan simulasi iuran berdasarkan angka dan rumus yang "
            "tersedia di konteks dokumen. Tunjukkan komponen JKK, JKM, dan JHT secara terpisah. "
            "Jangan menebak tarif atau promo yang tidak ada di konteks. Jika nominal dasar penghasilan "
            "belum diberikan, minta nominal tersebut terlebih dahulu."
        ),
    },
    "keberatan": {
        "label": "💬 Menangani Keberatan",
        "keywords": [
            "mahal", "tidak mau", "nggak mau", "enggan", "ragu", "keberatan",
            "belum yakin", "buat apa", "tidak perlu", "nanti saja", "takut"
        ],
        "instruction": (
            "Bantu mahasiswa merespons keberatan calon peserta secara persuasif tetapi tetap faktual "
            "dan tidak menyesatkan. Jangan menjanjikan hasil, jangan menekan calon peserta, dan jangan "
            "menambahkan manfaat yang tidak ada di konteks. Berikan contoh respons singkat yang sopan, "
            "kemudian poin fakta yang dapat dipakai untuk menjelaskan."
        ),
    },
    "pendaftaran": {
        "label": "📝 Pendaftaran BPU",
        "keywords": [
            "daftar", "pendaftaran", "formulir", "registrasi", "mendaftar",
            "1x24", "kartu", "bayar iuran", "nomor pembayaran"
        ],
        "instruction": (
            "Bantu mahasiswa mengikuti alur pendaftaran BPU yang relevan dengan program magang. "
            "Bedakan dengan jelas kanal pendaftaran umum dan alur khusus melalui mahasiswa magang "
            "bila konteks mendukungnya. Tulis langkah secara berurutan."
        ),
    },
    "follow_up": {
        "label": "🔄 Follow-up Peserta",
        "keywords": [
            "follow up", "follow-up", "tindak lanjut", "konfirmasi pembayaran",
            "belum bayar", "sudah bayar", "bukti kepesertaan", "kartu"
        ],
        "instruction": (
            "Bantu mahasiswa melakukan tindak lanjut setelah pendaftaran. Gunakan alur yang tersedia "
            "di dokumen, termasuk konfirmasi pembayaran dan penyerahan bukti kepesertaan jika relevan. "
            "Jangan membuat prosedur tambahan."
        ),
    },
    "umum": {
        "label": "🤝 Bantuan Umum Lapangan",
        "keywords": [],
        "instruction": (
            "Bantu mahasiswa memahami informasi BPJS Ketenagakerjaan dan pelaksanaan akuisisi BPU. "
            "Saat memungkinkan, hubungkan jawaban dengan langkah kerja lapangan yang didukung dokumen, "
            "tanpa membuat prosedur baru."
        ),
    },
}


SMALL_TALK_RESPONSES = {
    "greeting": (
        "Halo! 👋 Saya **Asisten Akuisisi BPU**.\n\n"
        "Saya bisa membantu kamu saat kegiatan magang, misalnya **menjelaskan program BPU**, "
        "**menghitung iuran**, **menangani keberatan calon peserta**, serta **memandu pendaftaran dan follow-up**.\n\n"
        "Coba tanyakan, misalnya: *\"Berapa iuran JKK + JKM untuk penghasilan Rp1 juta?\"*"
    ),
    "thanks": "Sama-sama! 😊 Semoga kegiatan akuisisinya lancar.",
    "bye": "Sampai jumpa! Semoga kegiatan magangnya lancar. 👋",
    "help": (
        "Tentu. Saya bisa membantu kamu dalam **6 hal utama**:\n\n"
        "- 🔎 **Identifikasi calon peserta BPU**\n"
        "- 📚 **Menjelaskan JKK, JKM, dan JHT**\n"
        "- 💰 **Simulasi iuran**\n"
        "- 💬 **Menangani keberatan calon peserta**\n"
        "- 📝 **Panduan pendaftaran**\n"
        "- 🔄 **Follow-up setelah pendaftaran**\n\n"
        "Kamu bisa langsung menceritakan situasi yang sedang kamu hadapi di lapangan."
    ),
}


def detect_small_talk(question):
    """Mendeteksi percakapan ringan yang tidak memerlukan RAG."""
    text = question.lower().strip()
    normalized = text.replace("!", "").replace("?", "").strip()

    greeting_phrases = {
        "halo", "hai", "hi", "hello", "hei", "hey",
        "pagi", "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
        "assalamualaikum", "assalamu alaikum",
    }
    thanks_phrases = {
        "terima kasih", "makasih", "thanks", "thank you", "thx",
    }
    bye_phrases = {
        "bye", "dadah", "sampai jumpa", "sampai nanti", "selamat tinggal",
    }
    help_phrases = {
        "bisa bantu apa", "kamu bisa apa", "bisa membantu apa",
        "apa yang bisa kamu bantu", "cara menggunakan chatbot", "help", "bantuan",
    }

    if normalized in greeting_phrases:
        return "greeting"
    if normalized in thanks_phrases:
        return "thanks"
    if normalized in bye_phrases:
        return "bye"
    if normalized in help_phrases:
        return "help"
    return None


def _off_domain_response():
    return (
        "Saya fokus membantu **kegiatan magang BPJS Ketenagakerjaan**, khususnya akuisisi peserta BPU.\n\n"
        "Saya bisa membantu menjelaskan **program, iuran, manfaat, pendaftaran, keberatan calon peserta, "
        "dan follow-up**. Coba ceritakan pertanyaan atau situasi yang kamu hadapi di lapangan."
    )


def sanitize_assistant_output(text: str) -> str:
    """Hapus referensi internal knowledge base dari teks yang akan dilihat user.

    SAPA tetap menggunakan metadata/sumber untuk grounding dan UI internal,
    tetapi pengguna tidak perlu melihat ID FAQ, nama file, chunk, atau catatan
    evaluasi internal.
    """
    if text is None:
        return ""

    cleaned = str(text).replace("\r\n", "\n")

    # Hapus parenthetical / inline references seperti:
    # (lihat FAQ-04), (FAQ‑36), [FAQ-04], lihat `proses_pendaftaran_bpu.txt`.
    internal_ref_patterns = [
        r"\s*\((?:lihat|rujuk|merujuk(?: ke)?|sesuai)\s+(?:FAQ\s*[-‑–—]?\s*\d+|`[^`]+\.txt`|[^)\n]*(?:\.txt|\.md))\)\.?",
        r"\s*\[(?:lihat|rujuk|merujuk(?: ke)?|sesuai)?\s*(?:FAQ\s*[-‑–—]?\s*\d+|[^\]]+\.txt)\]\.?",
        r"\s*(?:lihat|rujuk|merujuk(?: ke)?|sesuai)\s+(?:FAQ\s*[-‑–—]?\s*\d+|`[^`]+\.txt`|[^.\n]+\.txt)\.?",
    ]
    for pattern in internal_ref_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Hapus baris meta yang membicarakan sumber internal / FAQ sebagai bahan
    # evaluasi. Jangan menghapus isi jawaban substantif.
    lines = []
    for line in cleaned.split("\n"):
        low = line.strip().lower()
        if not low:
            lines.append("")
            continue
        internal_meta = (
            "catatan:" in low and ("faq" in low or "sumber" in low or "dokumen" in low)
        ) or (
            any(token in low for token in ("didukung oleh", "didukung oleh definisi", "didukung oleh sumber"))
            and ("faq" in low or ".txt" in low or "sumber" in low)
        ) or (
            "semua pertanyaan" in low and ("faq" in low or "sumber" in low)
        )
        if internal_meta:
            continue
        lines.append(line)

    cleaned = "\n".join(lines)

    # Hapus label retrieval yang kadang ikut dipantulkan model.
    cleaned = re.sub(r"\[SUMBER\s*\d+\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[Sumber\s*\d+\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bJumlah kandidat(?: yang diperiksa)?\s*:\s*\d+\.?", "", cleaned, flags=re.IGNORECASE)

    # Rapikan whitespace setelah pembersihan.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()

# --- SYSTEM PROMPT ---
# Ini adalah "kepribadian" tetap chatbot: persona, gaya bahasa, format jawaban,
# dan aturan fallback-nya. Isinya SELALU SAMA di setiap pertanyaan (tidak berisi
# {context}/{question} karena keduanya nanti dikirim terpisah lewat HumanMessage
# di dalam fungsi ask()).
SYSTEM_PROMPT = """Kamu adalah **Asisten Akuisisi BPU** yang mendampingi mahasiswa magang
BPJS Ketenagakerjaan saat bekerja di lapangan. Tujuanmu bukan sekadar menjawab FAQ, tetapi
membantu mahasiswa menjalankan proses akuisisi secara runtut: **identifikasi → pendekatan →
edukasi → akuisisi → follow-up → pelaporan**, sesuai informasi yang tersedia di dokumen.

=== PERAN UTAMA ===
- Bantu mahasiswa memahami informasi yang dapat mereka sampaikan kepada calon peserta.
- Bila pertanyaan berkaitan dengan pekerjaan lapangan, berikan jawaban yang **siap dipakai**:
  penjelasan singkat, langkah berikutnya, atau contoh kalimat komunikasi.
- Tetap netral dan tidak memaksa calon peserta. Jangan membuat janji atau manfaat yang tidak ada.
- Untuk proses yang spesifik pada program magang, prioritaskan prosedur dan istilah yang memang
  digunakan dalam materi program magang.

=== GAYA BAHASA ===
- Ramah, sopan, hangat, dan praktis.
- Gunakan Bahasa Indonesia sederhana yang cocok dibaca cepat di lapangan.
- Gunakan **bold** untuk angka, program, syarat, dan langkah penting.
- Gunakan bullet/penomoran untuk prosedur, syarat, dan checklist.
- Hindari paragraf panjang.
- Tulis semua angka dan rumus sebagai TEKS BIASA. LaTeX/MathJax dilarang keras (lihat aturan di bawah).

=== LARANGAN KERAS: FORMAT MATEMATIKA (LaTeX) ===
- DILARANG KERAS menggunakan LaTeX, MathJax, KaTeX, atau notasi matematika berformat apa pun.
  Antarmuka ini TIDAK bisa merendernya, sehingga pengguna hanya melihat kode mentah yang berantakan.
- JANGAN PERNAH menulis perintah berawalan backslash seperti \\times, \\cdot, \\div, \\mathbf, \\text,
  \\frac, \\approx, \\rightarrow, \\left, \\right, \\sum, atau perintah LaTeX lainnya.
- JANGAN membungkus angka atau rumus dengan tanda kurung siku/kurung matematika seperti \\[ ... \\] atau
  \\( ... \\), maupun dengan tanda dolar seperti $...$ atau $$...$$.
- Tulis semua angka dan rumus sebagai TEKS BIASA:
  - perkalian: huruf x atau tanda * (contoh: 1.000.000 x 0,24% = Rp2.400), bukan \\times
  - pembagian: tanda / atau kata "dibagi"; pengurangan dan penjumlahan: tanda - dan +
  - persen: tulis 0,24% (bukan \\%); mata uang: tulis Rp16.800 (bukan \\text{Rp})
  - hasil atau angka penting: gunakan **bold** markdown biasa (bukan \\mathbf)
- Untuk perhitungan bertahap, tulis satu langkah per baris dalam teks biasa atau bullet,
  misalnya: "- JKK: Rp1.000.000 x 0,24% = **Rp2.400**".
- Aturan ini berlaku untuk SEMUA jawaban, termasuk saat menjelaskan rumus atau contoh hitungan.

=== MODE BANTUAN LAPANGAN ===
Sistem akan memberikan INTENT BANTUAN pada pertanyaan terbaru. Gunakan intent tersebut untuk
memilih bentuk jawaban yang paling membantu, tetapi **jangan pernah menggunakannya sebagai sumber fakta**.
Semua fakta, angka, syarat, manfaat, periode, dan prosedur harus berasal dari KONTEKS DOKUMEN.

=== ATURAN TAMPILAN SUMBER ===
- Jangan pernah menyebut ID FAQ seperti **FAQ-04** atau **FAQ-36** kepada pengguna.
- Jangan menyebut nama file, path, chunk, metadata, skor retrieval, atau struktur knowledge base.
- Jangan menulis "lihat FAQ...", "lihat file...", "rujuk ke...", atau catatan tentang dokumen internal.
- Sampaikan isi informasinya langsung dengan bahasa pengguna. Transparansi sumber ditangani oleh UI, bukan oleh isi jawaban.

=== ATURAN SUMBER FAKTA ===
Jawablah hanya berdasarkan **KONTEKS DOKUMEN** yang diberikan pada pesan terbaru.
DILARANG mengarang, menebak, atau menambahkan informasi yang tidak ada di konteks.
Jika informasi belum tersedia di konteks, katakan bahwa informasi tersebut belum tersedia.

Riwayat percakapan hanya dipakai untuk memahami maksud pertanyaan lanjutan seperti "yang tadi",
"kalau 3 program", atau "setelah itu". Riwayat bukan sumber fakta. Jika ada perbedaan,
selalu ikuti KONTEKS DOKUMEN terbaru.

=== FORMAT BERDASARKAN KEBUTUHAN ===
- Jika user sedang menghadapi calon peserta: berikan **jawaban yang bisa disampaikan** dan, bila relevan,
  **poin fakta pendukung**.
- Jika user meminta langkah kerja: berikan **checklist berurutan**.
- Jika user meminta simulasi: gunakan **HASIL PERHITUNGAN DETERMINISTIK** bila disediakan sistem.
  **Jangan menghitung ulang, membulatkan ulang, atau mengubah angka hasil kalkulator.**
- Jika user menghadapi keberatan: berikan **contoh respons sopan** lalu fakta pendukung.
- Jika user meminta pendaftaran/follow-up: bedakan langkah **pendaftaran**, **pembayaran**, dan
  **konfirmasi/bukti kepesertaan** sesuai konteks.

=== DATA PRIBADI ===
- Jangan meminta pengguna mengetik atau menempelkan NIK, nomor KTP, nomor KK, nomor rekening, nomor telepon,
  email, atau data identitas pribadi lainnya ke dalam chat.
- Jika pengguna sudah menuliskan data pribadi, jangan mengulang, menyalin, atau meringkas nilainya.
- Arahkan pengguna untuk memasukkan data tersebut hanya melalui formulir atau kanal resmi yang disebutkan
  dalam dokumen bila memang diperlukan.

=== FALLBACK ===
Jika jawaban tidak ditemukan pada KONTEKS DOKUMEN:
1. Katakan dengan ramah bahwa informasi tersebut belum tersedia di sistem saat ini.
2. Jangan mengarang jawaban atau angka.
3. Arahkan ke kontak yang paling relevan di bawah ini.

- 🗂️ **Operasional Magang** (kegiatan umum & administrasi magang):
  Samuel (+62 856-6820-6081), Nabilariza (+62 823-6370-3956)
- 📄 **Pengambilan Brosur BPJS TK**:
  Grace (+62 822-7143-8378)
- 📝 **Pendaftaran BPU hingga Pencetakan Kartu**:
  Zahra (+62 852-7812-4901)
- 🗓️ **Absensi & Logbook Aktivitas**:
  Elvan (+62 813-9617-3602), Jeremy (+62 813-1505-4991)

Kejujuran lebih penting daripada terlihat serba tahu, terutama karena informasi ini menyangkut hak
dan kewajiban peserta jaminan sosial."""


# --- BAGIAN 3: FUNGSI-FUNGSI UTAMA ---

def load_retriever():
    """Memuat kembali vector store dari disk dan membungkusnya sebagai retriever."""
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    # siapkan "penerjemah" teks -> vector angka, harus sama dengan saat indexing

    vector_store = FAISS.load_local(
        VECTOR_STORE_PATH,                     # folder tempat index FAISS disimpan oleh ingest.py
        embeddings,                             # model embedding untuk membaca ulang isi index
        allow_dangerous_deserialization=True,   # diizinkan karena file ini kita buat & percaya sendiri (bukan dari sumber luar)
    )

    return vector_store.as_retriever(search_kwargs={"k": RETRIEVAL_K})
    # jadikan vector store sebagai "retriever" yang otomatis mengambil TOP_K
    # potongan dokumen paling mirip setiap kali diberi sebuah pertanyaan


def load_llm():
    """Menyiapkan koneksi ke LLM Groq menggunakan API key dari file .env."""
    api_key = os.getenv("GROQ_API_KEY")   # ambil API key dari environment variable

    if not api_key:
        # beri pesan error yang jelas kalau developer (kamu) lupa mengisi API key
        raise ValueError(
            "GROQ_API_KEY belum diatur. Salin file .env.example menjadi .env, "
            "lalu isi dengan API key gratis dari https://console.groq.com/keys"
        )

    return ChatGroq(
        api_key=api_key,          # kunci autentikasi ke akun Groq kamu
        model=LLM_MODEL_NAME,     # nama model LLM yang dipakai untuk menjawab
        temperature=0.2,          # nilai rendah (0-1) supaya jawaban konsisten & tidak "mengarang", penting untuk info resmi
    )


def _source_metadata(document, fallback_index):
    """Mengambil metadata sumber dalam format yang aman untuk UI maupun prompt."""
    metadata = getattr(document, "metadata", {}) or {}
    source_name = metadata.get("source_name") or metadata.get("source_file") or f"Sumber {fallback_index}"
    section = metadata.get("section") or "Bagian umum"
    source_file = metadata.get("source_file") or metadata.get("source") or "-"
    return {
        "source_name": str(source_name),
        "section": str(section),
        "source_file": str(source_file),
    }


def format_context(documents):
    """Menggabungkan konteks dengan label sumber/section agar provenance tetap terlihat oleh LLM."""
    blocks = []
    for index, doc in enumerate(documents, start=1):
        source = _source_metadata(doc, index)
        blocks.append(
            f"[SUMBER {index}] {source['source_name']}\n"
            f"Bagian: {source['section']}\n"
            f"Isi: {doc.page_content}"
        )
    return "\n\n---\n\n".join(blocks)


def _normalize_history(history):
    """Mengubah riwayat chat menjadi format sederhana yang aman dipakai oleh RAG."""
    if not history:
        return []

    normalized = []
    for message in history:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not content:
            continue

        normalized.append({"role": role, "content": str(content)})

    return normalized


def detect_intent(question):
    """Mendeteksi jenis bantuan lapangan secara ringan tanpa memanggil LLM tambahan."""
    question_lower = question.lower().strip()

    # Cek intent yang lebih spesifik terlebih dahulu.
    priority_order = [
        "follow_up",
        "pendaftaran",
        "simulasi",
        "keberatan",
        "identifikasi",
        "edukasi",
        "umum",
    ]

    for intent_name in priority_order:
        intent = FIELD_INTENTS[intent_name]
        if any(keyword in question_lower for keyword in intent["keywords"]):
            return intent_name

    return "umum"


def get_intent_instruction(intent_name):
    """Mengambil instruksi bentuk bantuan untuk intent yang terdeteksi."""
    return FIELD_INTENTS.get(intent_name, FIELD_INTENTS["umum"])["instruction"]


def _retrieve_with_confidence(retriever, query):
    """
    Mengambil kandidat dokumen sekaligus skor relevansinya.

    LangChain FAISS menyediakan similarity_search_with_relevance_scores() yang
    menghasilkan skor dalam rentang yang dimaksudkan 0-1 (semakin tinggi semakin
    relevan). Jika API tersebut tidak tersedia pada versi LangChain yang dipakai,
    fungsi mundur ke retriever biasa tanpa mengklaim adanya confidence score.
    """
    vector_store = getattr(retriever, "vectorstore", None)

    if vector_store is not None and hasattr(vector_store, "similarity_search_with_relevance_scores"):
        try:
            scored_documents = vector_store.similarity_search_with_relevance_scores(
                query,
                k=RETRIEVAL_K,
            )
            return scored_documents, True
        except Exception:
            # Jangan membuat aplikasi mati hanya karena API scoring berbeda antar versi.
            pass

    documents = retriever.invoke(query)
    return [(document, None) for document in documents], False


def retrieve_documents(question, retriever, history=None, top_k=TOP_K):
    """Menjalankan retrieval lengkap yang dipakai chatbot dan evaluation benchmark."""
    sanitized_question = sanitize_user_input(question)
    clean_question = sanitized_question.text
    clean_history = _normalize_history(history)
    clean_history = [
        {"role": item["role"], "content": sanitize_user_input(item["content"]).text}
        for item in clean_history
    ]

    retrieval_query = build_retrieval_query(
        clean_question,
        clean_history,
        max_history_messages=MAX_HISTORY_MESSAGES_FOR_RETRIEVAL,
    )
    scored_documents, scoring_available = _retrieve_with_confidence(
        retriever,
        retrieval_query,
    )

    # _select_relevant_documents memakai TOP_K global agar konfigurasi runtime chatbot tetap
    # konsisten. Parameter top_k di sini hanya digunakan evaluation bila ingin membaca subset lebih kecil.
    selected_docs, best_score = _select_relevant_documents(
        scored_documents,
        scoring_available,
        retrieval_query,
    )
    selected_docs = selected_docs[:max(1, int(top_k))]

    details = {
        "scoring_available": scoring_available,
        "candidate_count": len(scored_documents),
        "selected_count": len(selected_docs),
        "best_semantic_score": (float(best_score) if best_score is not None else None),
    }
    return selected_docs, retrieval_query, details


def _select_relevant_documents(scored_documents, scoring_available, query):
    """Menyaring kandidat dan melakukan reranking + diversifikasi section."""
    if not scored_documents:
        return [], None

    if not scoring_available:
        reranked = rerank_scored_documents(
            query,
            scored_documents,
            top_k=TOP_K,
            max_chunks_per_section=MAX_CHUNKS_PER_SECTION,
        )
        documents = [document for document, _combined, _lexical, _semantic in reranked]
        return documents, None

    # Confidence gate tetap menggunakan semantic score mentah. Reranking lexical hanya
    # menentukan urutan kandidat yang sudah lolos gate, bukan mengubah definisi confidence.
    relevant = [
        (document, score)
        for document, score in scored_documents
        if score is not None and float(score) >= MIN_RELEVANCE_SCORE
    ]

    if not relevant:
        # Threshold terlalu ketat dapat membuat seluruh hasil hilang, terutama ketika
        # skala relevance score berubah antar-versi LangChain/vector metric. Sebelum
        # memicu fallback, lakukan satu tahap penyelamatan berbasis reranking lexical.
        rescue = rerank_scored_documents(
            query,
            scored_documents,
            top_k=TOP_K,
            max_chunks_per_section=MAX_CHUNKS_PER_SECTION,
        )
        if rescue:
            best = rescue[0]
            _document, _combined, lexical_score, semantic_score = best
            if lexical_score >= 0.20 or (semantic_score is not None and float(semantic_score) >= 0.05):
                selected = [document for document, _combined, _lexical, _semantic in rescue]
                best_score = max(
                    float(score) for _doc, score in scored_documents if score is not None
                ) if any(score is not None for _doc, score in scored_documents) else None
                return selected, best_score

        best_score = scored_documents[0][1] if scored_documents else None
        return [], best_score

    reranked = rerank_scored_documents(
        query,
        relevant,
        top_k=TOP_K,
        max_chunks_per_section=MAX_CHUNKS_PER_SECTION,
    )
    selected = [document for document, _combined, _lexical, _semantic in reranked]
    best_score = max(float(score) for _doc, score in relevant)
    return selected, best_score

def _fallback_response(intent_name, domain_relevant=True):
    """
    Respons fallback deterministik saat tidak ada sumber yang cukup relevan.

    Untuk pertanyaan domain BPJS/magang, arahkan ke narahubung yang relevan.
    Untuk input yang jelas di luar domain, jangan langsung memberikan nomor kontak internal.
    """
    if not domain_relevant:
        return _off_domain_response()

    contact = {
        "pendaftaran": "Zahra (+62 852-7812-4901)",
        "follow_up": "Zahra (+62 852-7812-4901)",
        "umum": "Samuel (+62 856-6820-6081) atau Nabilariza (+62 823-6370-3956)",
        "identifikasi": "Samuel (+62 856-6820-6081) atau Nabilariza (+62 823-6370-3956)",
        "edukasi": "Samuel (+62 856-6820-6081) atau Nabilariza (+62 823-6370-3956)",
        "simulasi": "Zahra (+62 852-7812-4901)",
        "keberatan": "Samuel (+62 856-6820-6081) atau Nabilariza (+62 823-6370-3956)",
    }.get(intent_name, "Samuel (+62 856-6820-6081) atau Nabilariza (+62 823-6370-3956)")

    return (
        "Maaf, saya belum menemukan sumber yang cukup relevan untuk menjawab pertanyaan ini "
        "dengan aman. Saya tidak ingin menebak atau memberikan informasi yang belum terverifikasi.\n\n"
        f"Untuk memastikan jawabannya, silakan hubungi **{contact}**."
    )

def _try_deterministic_calculation(
    question: str,
    context: Optional[ConversationContext] = None,
):
    """Mengembalikan jawaban numerik tanpa LLM dengan mewarisi slot percakapan."""
    if not detect_calculation_request(question):
        return None

    context = context or ConversationContext()

    # Pertanyaan terbaru selalu menang. Jika slot tidak disebut, warisi nilai terakhir
    # yang tersimpan dari percakapan user sebelumnya.
    base_income = extract_base_income(question) or context.base_income
    if base_income is None:
        return (
            "## Simulasi Iuran BPU\n\n"
            "Saya bisa menghitungnya secara otomatis. Sebutkan **dasar penghasilan per bulan**, "
            "misalnya **Rp1.000.000**, lalu sebutkan apakah calon peserta mengambil **2 program (JKK + JKM)** "
            "atau **3 program (JKK + JKM + JHT)**."
        )

    programs = extract_programs(question) or context.programs
    discount_requested = detect_discount_request(question)
    discount = False
    discount_note = ""

    if discount_requested:
        # Sektor boleh diwarisi dari percakapan sebelumnya, tetapi permintaan promo sendiri
        # tidak disimpan agar simulasi berikutnya tidak otomatis ikut diskon.
        sector = detect_sector(question) or context.sector
        status, eligible = promo_status(sector=sector)
        discount_note = f"\n\n*Status promo: {status}*"
        if eligible:
            discount = True
        else:
            # Jangan menghitung dengan diskon jika syarat sektor/periode belum terpenuhi.
            if sector is None:
                return (
                    "## Simulasi Iuran BPU\n\n"
                    "Untuk menghitung **promo/diskon 50%**, saya perlu mengetahui sektor pekerjaan calon peserta "
                    "karena periode promo dibedakan antara **transportasi** dan **non-transportasi**. "
                    "Sebutkan sektornya terlebih dahulu." + discount_note
                )

    if not programs:
        two_programs = calculate_bpu_contribution(
            base_income, ("JKK", "JKM"), discount_jkk_jkm=discount
        )
        three_programs = calculate_bpu_contribution(
            base_income, ("JKK", "JKM", "JHT"), discount_jkk_jkm=discount
        )
        response = (
            "## Simulasi Iuran BPU\n\n"
            f"Dasar penghasilan: **{two_programs.base_income}**\n\n"
            "**2 program — JKK + JKM**\n\n"
            + build_calculation_response(two_programs)
            + "\n\n**3 program — JKK + JKM + JHT**\n\n"
            + build_calculation_response(three_programs)
            + discount_note
        )
        return response

    result = calculate_bpu_contribution(
        base_income, programs, discount_jkk_jkm=discount
    )
    return build_calculation_response(result) + discount_note


def _temporal_context(question: str) -> str:
    """Berikan status waktu untuk informasi promo yang memiliki periode berlaku."""
    if not detect_discount_request(question) and not any(
        word in question.lower() for word in ("promo", "diskon", "potongan", "50%")
    ):
        return "Tanggal sistem Asia/Jakarta: tidak diperlukan untuk pertanyaan ini."

    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    status_lines = [f"Tanggal sistem Asia/Jakarta: {today.isoformat()}."]

    for sector, (start, end) in PROMO_PERIODS.items():
        if start <= today <= end:
            status_lines.append(
                f"Promo 50% JKK+JKM untuk sektor {sector.replace('_', ' ')} sedang berada dalam periode "
                f"berlaku sampai {end.isoformat()}."
            )
        elif today < start:
            status_lines.append(
                f"Promo 50% JKK+JKM untuk sektor {sector.replace('_', ' ')} belum mulai; periode {start.isoformat()} sampai {end.isoformat()}."
            )
        else:
            status_lines.append(
                f"Promo 50% JKK+JKM untuk sektor {sector.replace('_', ' ')} sudah berakhir pada {end.isoformat()}."
            )

    status_lines.append(
        "Jangan menyebut promo sebagai berlaku tanpa memperhatikan sektor dan periode di atas. "
        "JHT tidak termasuk diskon 50%."
    )
    return "\n".join(status_lines)


@dataclass
class _AskPlan:
    """
    Hasil tahap RETRIEVAL + AUGMENTATION (semua yang terjadi SEBELUM LLM dipanggil).

    - static_answer terisi  -> jawaban sudah final tanpa LLM (small talk, fallback,
                               hasil kalkulator deterministik). messages = None.
    - static_answer = None  -> messages siap dikirim ke LLM (invoke ataupun stream).
    """
    sources: list
    static_answer: Optional[str] = None
    messages: Optional[list] = None


def _prepare_ask(question, retriever, history=None) -> _AskPlan:
    """
    Logika RAG bersama untuk ask() dan ask_stream(): sanitasi input, small talk,
    deteksi intent, retrieval + confidence gate, fallback, kalkulator deterministik,
    dan penyusunan prompt. Urutan & isinya sama persis dengan ask() versi sebelumnya,
    supaya perilaku (dan hasil evaluation) tidak berubah.
    """
    sanitized_question = sanitize_user_input(question)
    question = sanitized_question.text
    history = _normalize_history(history)
    history = [
        {"role": item["role"], "content": sanitize_user_input(item["content"]).text}
        for item in history
    ]
    # Percakapan ringan tidak perlu melalui RAG. Ini mencegah input seperti "halo"
    # gagal melewati confidence gate dan mendapatkan fallback yang kaku.
    small_talk = detect_small_talk(question)
    if small_talk is not None:
        return _AskPlan(sources=[], static_answer=SMALL_TALK_RESPONSES[small_talk])

    intent_name = detect_intent(question)
    intent_instruction = get_intent_instruction(intent_name)
    conversation_context = build_conversation_context(question, history)

    relevant_docs, retrieval_query, retrieval_details = retrieve_documents(
        question,
        retriever,
        history=history,
        top_k=TOP_K,
    )

    # Tahap perhitungan deterministik dijalankan SEBELUM confidence fallback.
    # Dengan begitu follow-up seperti "hitung iuran untuk 3 program" tetap bisa
    # memakai penghasilan dari bubble sebelumnya meski retrieval sedang kurang yakin.
    deterministic_calculation = _try_deterministic_calculation(
        question,
        context=conversation_context,
    )
    if deterministic_calculation is not None:
        return _AskPlan(
            sources=relevant_docs,
            static_answer=sanitize_assistant_output(deterministic_calculation),
        )

    # Jika tidak ada dokumen yang lolos retrieval/confidence gate, jangan panggil LLM.
    # Ini mencegah pertanyaan di luar domain mendapatkan jawaban yang terdengar meyakinkan.
    if not relevant_docs:
        domain_keywords = (
            "bpjs", "bpu", "jkk", "jkm", "jht", "jamsostek", "peserta",
            "iuran", "pendaftaran", "akuisisi", "magang", "jaminan", "kepesertaan",
            "kartu", "klaim", "ketenagakerjaan", "calon peserta", "follow up", "follow-up"
        )
        is_domain_relevant = any(keyword in question.lower() for keyword in domain_keywords)
        return _AskPlan(
            sources=[],
            static_answer=sanitize_assistant_output(
                _fallback_response(intent_name, domain_relevant=is_domain_relevant)
            ),
        )

    context = format_context(relevant_docs)
    # AUGMENTATION: gabungkan potongan dokumen hasil retrieval

    human_content = (
        "CATATAN: Riwayat percakapan hanya digunakan untuk memahami konteks, "
        "misalnya kata \"tersebut\", \"yang tadi\", atau pertanyaan lanjutan. "
        "Riwayat BUKAN sumber fakta. Semua fakta dan angka untuk jawaban wajib berasal "
        "dari KONTEKS DOKUMEN.\n\n"
        f"INTENT BANTUAN LAPANGAN: {intent_name}\n"
        f"BENTUK BANTUAN YANG DIUTAMAKAN: {intent_instruction}\n"
        f"VALIDITAS INFORMASI BERTANGGAL:\n{_temporal_context(question)}\n\n"
        "HASIL RETRIEVAL: Sumber di bawah telah lolos pemeriksaan relevansi minimum. "
        "Jangan menyebut skor similarity sebagai probabilitas atau tingkat kepastian kepada pengguna. "
        f"Jumlah kandidat yang diperiksa: {retrieval_details['candidate_count']}.\n\n"
        "KONTEKS TERSTRUKTUR DARI PERCAKAPAN USER (bukan sumber fakta dokumen):\n"
        f"{conversation_context.to_prompt()}\n\n"
        f"KONTEKS DOKUMEN:\n{context}\n\n"
        f"PERTANYAAN TERBARU:\n{question}"
    )
    # History diberikan sebagai message sebelumnya agar model memahami referensi percakapan,
    # sementara blok ini secara eksplisit menetapkan dokumen retrieval sebagai sumber fakta.

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
    ]

    # Tambahkan riwayat dalam bentuk message role yang sebenarnya, bukan sekadar teks.
    for message in history[-MAX_HISTORY_MESSAGES:]:
        if message["role"] == "user":
            messages.append(HumanMessage(content=message["content"]))
        else:
            messages.append(AIMessage(content=message["content"]))

    messages.append(HumanMessage(content=human_content))
    return _AskPlan(sources=relevant_docs, messages=messages)


def ask(question, retriever, llm, history=None):
    """
    Fungsi RAG non-streaming (tetap dipertahankan untuk evaluation/benchmark & kode lama).
    Mengembalikan (jawaban, dokumen_sumber).
    Untuk UI dengan efek mesin tik, pakai ask_stream().
    """
    plan = _prepare_ask(question, retriever, history)
    if plan.static_answer is not None:
        return plan.static_answer, plan.sources

    response = llm.invoke(plan.messages)
    # GENERATION: LLM menerima aturan sistem + riwayat + konteks sumber + pertanyaan terbaru

    return sanitize_assistant_output(response.content), plan.sources
    # kembalikan teks jawaban LLM beserta dokumen sumber untuk ditampilkan transparan


def _chunk_text(chunk) -> str:
    """Ambil teks dari satu chunk hasil llm.stream() (content bisa str atau list blok)."""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


class AnswerStream:
    """
    Jawaban yang bisa di-iterasi (generator) untuk st.write_stream.

    - .sources : dokumen sumber, sudah tersedia SEBELUM iterasi dimulai.
    - iterasi  : menghasilkan potongan teks (delta) yang SUDAH disanitasi.
    - .emitted : gabungan semua delta yang sudah dikirim ke UI.
    - .text    : jawaban final (sanitasi penuh); valid setelah iterasi selesai.

    Sanitasi tetap aman saat streaming: teks mentah dari LLM hanya "dilepas" ke UI
    per BARIS LENGKAP, lalu disanitasi dengan sanitize_assistant_output() yang sama.
    Semua aturan sanitasi bekerja di dalam satu baris, jadi referensi internal
    (FAQ-xx, nama file .txt, [SUMBER n], catatan meta) tidak sempat tampil sebagian.
    Di akhir stream, sanitasi penuh dijalankan sekali lagi sebagai versi otoritatif.

    Objek ini sekali pakai (satu kali iterasi).
    """

    def __init__(self, sources, static_answer=None, llm=None, messages=None):
        self.sources = sources
        self._static_answer = static_answer
        self._llm = llm
        self._messages = messages
        self.emitted = ""
        self.text = static_answer if static_answer is not None else ""

    def _delta(self, candidate_raw: str) -> str:
        """Sanitasi kandidat lalu kembalikan hanya bagian barunya (kalau konsisten)."""
        cleaned = sanitize_assistant_output(candidate_raw)
        if cleaned.startswith(self.emitted):
            delta = cleaned[len(self.emitted):]
            self.emitted = cleaned
            return delta
        # Sanitasi mengubah teks yang sudah terlanjur tampil (sangat jarang):
        # tahan dulu, koreksi dilakukan di akhir lewat .text.
        return ""

    def __iter__(self):
        # Jawaban tanpa LLM (small talk, fallback, kalkulator deterministik)
        if self._static_answer is not None:
            self.emitted = self._static_answer
            self.text = self._static_answer
            yield self._static_answer
            return

        raw = ""
        committed = 0   # panjang raw yang sudah berupa baris-baris lengkap
        for chunk in self._llm.stream(self._messages):
            # GENERATION (streaming): token datang bertahap dari LLM
            piece = _chunk_text(chunk)
            if not piece:
                continue
            raw += piece
            cut = raw.rfind("\n") + 1
            if cut > committed:
                committed = cut
                delta = self._delta(raw[:cut])
                if delta:
                    yield delta

        # Akhir stream: sanitasi penuh = versi final yang disimpan ke riwayat
        self.text = sanitize_assistant_output(raw)
        tail = self._delta(raw)
        if tail:
            yield tail


def ask_stream(question, retriever, llm, history=None) -> AnswerStream:
    """
    Versi streaming dari ask(): retrieval, confidence gate, kalkulator deterministik,
    dan prompt sama persis (lewat _prepare_ask). Bedanya, jawaban LLM diambil lewat
    llm.stream() dan dikembalikan sebagai AnswerStream.

    Retrieval berjalan di dalam pemanggilan ini (sebelum iterasi), jadi indikator
    loading di UI tetap tampil selama retrieval dan menunggu token pertama.
    """
    plan = _prepare_ask(question, retriever, history)
    return AnswerStream(
        sources=plan.sources,
        static_answer=plan.static_answer,
        llm=llm,
        messages=plan.messages,
    )