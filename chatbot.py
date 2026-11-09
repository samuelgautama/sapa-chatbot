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

import logging
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
    extract_income_attempt,
    extract_programs,
    format_rupiah,
    promo_status,
    MIN_INCOME,
)
from promo_config import maintenance_warnings, promo_timeline, today_jakarta
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

MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.55"))
# Ambang minimum skor relevansi (0-1) dari FAISS L2 distance.
# LangChain FAISS mengkonversi L2 distance ke relevance score: 1 - (distance / sqrt(2)).
# Score 1.0 = dokumen identik, 0.0 = ambang, <0 = sangat berbeda.
# Nilai ini configurable lewat environment variable untuk kalibrasi dengan evaluation dataset.

RESCUE_MIN_LEXICAL = float(os.getenv("RESCUE_MIN_LEXICAL", "0.20"))
RESCUE_MIN_SEMANTIC = float(os.getenv("RESCUE_MIN_SEMANTIC", "0.10"))


# --- HELPER UNTUK OPTIMASI ---

# Pattern cepat untuk deteksi apakah teks berpotensi punya data sensitif
# (cek sebelum menjalankan sanitasi penuh untuk menghindari overhead)
_QUICK_SENSITIVE_CHECK = re.compile(r'\b(?:nik|ktp|kk|rekening|rek|hp|wa|whatsapp|telepon|@)\b', re.IGNORECASE)

def _needs_sanitization(text: str) -> bool:
    """Cek cepat apakah teks perlu disanitasi (untuk skip sanitasi berulang pada history)."""
    if not text or len(text) < 10:
        return False
    # Cek pattern sensitif dan pola digit panjang
    return bool(_QUICK_SENSITIVE_CHECK.search(text)) or bool(re.search(r'\d{8,}', text))
# Tahap penyelamatan (ketika semua kandidat di bawah MIN_RELEVANCE_SCORE) hanya berlaku untuk
# query yang memuat istilah domain, DAN salah satu: overlap leksikal >= RESCUE_MIN_LEXICAL atau
# skor semantik >= RESCUE_MIN_SEMANTIC. Tanpa syarat domain, kata umum seperti "hari" pada
# "harga bitcoin hari ini" cocok dengan chunk "Jaminan Hari Tua" dan lolos.

UNSCORED_MIN_LEXICAL = 0.5
# Ketika skor semantik tidak tersedia (API scoring gagal), query tanpa istilah domain hanya
# lolos bila overlap leksikalnya kuat (>= nilai ini).

DOMAIN_KEYWORDS = (
    "bpjs", "bpu", "jkk", "jkm", "jht", "jamsostek", "peserta",
    "iuran", "pendaftaran", "akuisisi", "magang", "jaminan", "kepesertaan",
    "kartu", "klaim", "ketenagakerjaan", "calon peserta", "follow up", "follow-up",
    # Kata spesifik untuk in-domain (HANYA jika ada konteks domain atau kata pengindah)
    "penghasilan", "pendapatan", "diskon", "promo", "potongan",
    "pedagang", "petani", "nelayan", "ojol", "ojek", "kurir", "sopir",
    "freelancer", "umkm",
)

logger = logging.getLogger(__name__)
_logged_retrieval_issues: set = set()


def is_domain_relevant(text) -> bool:
    """True bila teks memuat istilah domain BPJS/BPU/magang."""
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in DOMAIN_KEYWORDS)


def _log_retrieval_issue(key: str, message: str, *args, exc_info=False):
    """Log peringatan retrieval sekali per jenis masalah (hindari banjir log tiap request)."""
    if key in _logged_retrieval_issues:
        logger.debug(message, *args)
        return
    _logged_retrieval_issues.add(key)
    logger.warning(message, *args, exc_info=exc_info)

MAX_HISTORY_MESSAGES = 8
# jumlah maksimum pesan lama yang diteruskan ke LLM untuk menjaga konteks percakapan

MAX_HISTORY_MESSAGES_FOR_RETRIEVAL = 4
# jumlah maksimum pesan terakhir yang ikut membantu pencarian dokumen relevan
MAX_CHUNKS_PER_SECTION = 2
# batasi chunk dari section yang sama agar TOP_K tidak dipenuhi potongan yang hampir identik

# Periode promo: lihat promo_config.py (sumber tunggal). PROMO_SOURCES lama dihapus karena
# tidak dipakai dan menjadi salinan kedua yang bisa basi.

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
            "belum bayar", "sudah bayar", "bukti kepesertaan"
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
        "Halo! 👋 Saya **SAPA** — **Sistem Asisten Pendamping Aktivitas** (Teman Magang, Siap Membantu).\n\n"
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


def _short_question_clarification(text: str) -> Optional[str]:
    """
    Tanggapan klarsifikasi untuk pertanyaan pendek (<=3 kata) tanpa konteks domain.
    """
    if not text:
        return None
    words = text.lower().split()
    if len(words) > 3:
        return None

    clarifications = {
        ("berapa", "iuran"): (
            "Tarif iuran BPU: **JKK 1%**, **JKM Rp6.800**, **JHT 2%** dari dasar penghasilan.\\n\\n"
            "Sebutkan **dasar penghasilan per bulan** untuk saya hitung."
        ),
        ("syarat",): (
            "Berikut syarat-syarat umum BPU:\\n"
            "- Warga negara Indonesia\\n"
            "- Usia 17-65 tahun\\n"
            "- Masa tunggu 1 bulan setelah berhenti kerja (jika PU)\\n"
            "- Penghasilan minimal Rp1.000.000/bulan\\n\\n"
            "Mau tahu syarat **pendaftaran BPU**, **klaim JHT**, atau **magang**?"
        ),
        ("cara",): (
            "Berikut cara-cara umum:\\n"
            "- Daftar: JMO/website/kantor cabang/Agen Perisai\\n"
            "- Bayar: BNI, BCA mobile, Alfamart, Gojek, QRIS\\n"
            "- Klaim: Portal BPJS Ketenagakerjaan\\n\\n"
            "Mau tahu cara **pendaftaran BPU**, **pembayaran**, atau **klaim**?"
        ),
        ("berapa", "biaya"): (
            "Tarif iuran BPU: **JKK 1%**, **JKM Rp6.800**, **JHT 2%** dari dasar penghasilan.\\n\\n"
            "Sebutkan **dasar penghasilan per bulan** untuk saya hitung."
        ),
    }

    for keys, response in clarifications.items():
        if any(k in words for k in keys):
            return response

    return None


# --- PRE-COMPILED REGEX UNTUK OPTIMASI SANITASI ---
_INTERNAL_REF = re.compile(
    r"\bfaq\b|\.txt\b|\.md\b|\bsumber\s*\d+|konteks dokumen|knowledge base|basis pengetahuan"
    r"|\bchunk\b|retrieval|metadata"
)
_INTERNAL_REF_PATTERNS = [
    re.compile(r"[ \t]*\((?:lihat|rujuk|merujuk(?: ke)?|sesuai)\s+(?:FAQ\s*[-‑–—]?\s*\d+|`[^`]+\.txt`|[^)\n]*(?:\.txt|\.md))\)\.?", re.IGNORECASE),
    re.compile(r"[ \t]*\[(?:lihat|rujuk|merujuk(?: ke)?|sesuai)?\s*(?:FAQ\s*[-‑–—]?\s*\d+|[^\]]+\.txt)\]\.?", re.IGNORECASE),
    re.compile(r"[ \t]*(?:lihat|rujuk|merujuk(?: ke)?|sesuai)\s+(?:FAQ\s*[-‑–—]?\s*\d+|`[^`]+\.txt`|[^.\n]+\.txt)\.?", re.IGNORECASE),
]
_RETRIEVAL_LABEL_PATTERN = re.compile(r"\[(?:SUMBER|Sumber)\s*\d+\]\s*", re.IGNORECASE)
_CANDIDATE_COUNT_PATTERN = re.compile(r"\bJumlah kandidat(?: yang diperiksa)?\s*:\s*\d+\.?", re.IGNORECASE)
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")
_MID_LINE_SPACES_PATTERN = re.compile(r"(?<=\S)[ \t]{2,}")


def sanitize_assistant_output(text: str) -> str:
    """Hapus referensi internal knowledge base dari teks yang akan dilihat user.

    SAPA tetap menggunakan metadata/sumber untuk grounding dan UI internal,
    tetapi pengguna tidak perlu melihat ID FAQ, nama file, chunk, atau catatan
    evaluasi internal.
    """
    if text is None:
        return ""

    cleaned = str(text).replace("\r\n", "\n")

    # Hapus baris meta yang membicarakan sumber internal / FAQ sebagai bahan
    # evaluasi. Jangan menghapus isi jawaban substantif.
    lines = []
    for line in cleaned.split("\n"):
        low = line.strip().lower()
        if not low:
            lines.append("")
            continue
        internal_meta = (
            "catatan:" in low and _INTERNAL_REF.search(low)
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

    # Hapus referensi inline SETELAH filter baris meta di atas.
    for pattern in _INTERNAL_REF_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Hapus label retrieval yang kadang ikut dipantulkan model.
    cleaned = _RETRIEVAL_LABEL_PATTERN.sub("", cleaned)
    cleaned = _CANDIDATE_COUNT_PATTERN.sub("", cleaned)

    # Rapikan whitespace setelah pembersihan.
    cleaned = _MULTI_NEWLINE_PATTERN.sub("\n\n", cleaned)
    # Hanya ratakan spasi ganda DI TENGAH baris; indentasi awal baris (sub-bullet) dipertahankan.
    cleaned = _MID_LINE_SPACES_PATTERN.sub(" ", cleaned)
    return cleaned.strip()

# --- SYSTEM PROMPT ---
# Ini adalah "kepribadian" tetap chatbot: persona, gaya bahasa, format jawaban,
# dan aturan fallback-nya. Isinya SELALU SAMA di setiap pertanyaan (tidak berisi
# {context}/{question} karena keduanya nanti dikirim terpisah lewat HumanMessage
# di dalam fungsi ask()).
#
# Bagian FALLBACK (daftar kontak) dibangun dinamis dari contacts_config.py agar
# tidak ada duplikasi hardcode saat kontak berubah.

from contacts_config import build_fallback_section

_SYSTEM_PROMPT_CORE = """Kamu adalah **SAPA** — **Sistem Asisten Pendamping Aktivitas** (Teman Magang, Siap Membantu) yang mendampingi mahasiswa magang
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

"""

# Build SYSTEM_PROMPT lengkap dengan bagian fallback dinamis
SYSTEM_PROMPT = _SYSTEM_PROMPT_CORE + build_fallback_section()


# --- BAGIAN 3: FUNGSI-FUNGSI UTAMA ---

def _log_promo_maintenance():
    """Peringatan di log saat startup bila promo sudah/hampir berakhir (kode + dokumen perlu diperbarui)."""
    for message in maintenance_warnings():
        logger.warning(message)


def load_retriever():
    """Memuat kembali vector store dari disk dan membungkusnya sebagai retriever."""
    _log_promo_maintenance()
    
    # Cek fresh index dengan warning log (bukan exception)
    try:
        from check_index_fresh import check_index_fresh
        check_index_fresh(warn_only=True)
    except Exception as exc:
        # Jika check_index_fresh gagal, log warning tapi lanjutkan
        logging.getLogger(__name__).warning(f"[load_retriever] check_index_fresh error: {exc}")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True}  # harus sama dengan ingest.py untuk konsistensi skor similarity
    )
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
    """Mendeteksi jenis bantuan lapangan secara ringan tanpa memanggil LLM tambahan.

    Urutan prioritas: keberatan paling awal. Keberatan calon peserta ("iurannya mahal")
    juga memuat kata "iuran", sehingga jika simulasi dicek lebih dulu, mode menangani
    keberatan hampir tidak pernah aktif. Kata kunci dicocokkan sebagai AWAL kata
    ("rp" cocok "Rp1.000.000" tetapi tidak "terpercaya").
    """
    question_lower = question.lower().strip()

    priority_order = [
        "keberatan",
        "follow_up",
        "pendaftaran",
        "simulasi",
        "identifikasi",
        "edukasi",
        "umum",
    ]

    for intent_name in priority_order:
        intent = FIELD_INTENTS[intent_name]
        if any(re.search(r"(?<!\w)" + re.escape(keyword), question_lower) for keyword in intent["keywords"]):
            return intent_name

    return "umum"


def get_intent_instruction(intent_name):
    """Mengambil instruksi bentuk bantuan untuk intent yang terdeteksi."""
    return FIELD_INTENTS.get(intent_name, FIELD_INTENTS["umum"])["instruction"]


def _retrieve_with_confidence(retriever, query):
    """
    Mengambil kandidat dokumen sekaligus skor relevansinya.

    Mengembalikan (scored_documents, scoring_available, scoring_error).

    LangChain FAISS menyediakan similarity_search_with_relevance_scores() yang
    menghasilkan skor yang dimaksudkan 0-1 (semakin tinggi semakin relevan). Jika API
    itu gagal atau tidak ada, fungsi mundur ke retriever biasa. Kegagalan TIDAK lagi
    ditelan diam-diam: dicatat ke log dan dibawa lewat scoring_error, dan
    _select_relevant_documents memakai gate leksikal sebagai pengganti confidence gate.
    """
    vector_store = getattr(retriever, "vectorstore", None)
    scoring_error = None

    if vector_store is not None and hasattr(vector_store, "similarity_search_with_relevance_scores"):
        try:
            scored_documents = vector_store.similarity_search_with_relevance_scores(
                query,
                k=RETRIEVAL_K,
            )
            # LangChain FAISS dengan metric L2 mengembalikan relevance score = 1 - (distance / sqrt(2))
            # Score sudah dalam range [0, 1] (1 = identik, 0 = ambang, <0 = sangat berbeda)
            # Tidak perlu remap karena FAISS menggunakan IndexFlatL2.
            return scored_documents, True, None
        except Exception as exc:
            scoring_error = f"{type(exc).__name__}: {exc}"
            _log_retrieval_issue(
                "scoring-failed",
                "Scoring relevansi gagal (%s). Confidence gate semantik NONAKTIF; memakai gate leksikal.",
                scoring_error,
                exc_info=True,
            )
    else:
        scoring_error = "vector store tidak menyediakan similarity_search_with_relevance_scores"
        _log_retrieval_issue(
            "scoring-missing",
            "Scoring relevansi tidak tersedia (%s). Confidence gate semantik NONAKTIF; memakai gate leksikal.",
            scoring_error,
        )

    documents = retriever.invoke(query)
    return [(document, None) for document in documents], False, scoring_error


def _prepare_question_and_history(question: str, history: list[dict] | None) -> tuple[str, list[dict]]:
    """Sanitasi question dan history yang digunakan oleh retrieval dan ask.
    
    Menghindari double sanitization dengan cek _needs_sanitization.
    """
    sanitized_question = sanitize_user_input(question)
    clean_question = sanitized_question.text
    
    clean_history = _normalize_history(history)
    clean_history = [
        {
            "role": item["role"],
            "content": (
                sanitize_user_input(item["content"]).text
                if _needs_sanitization(item["content"])
                else item["content"]
            )
        }
        for item in clean_history
    ]
    return clean_question, clean_history


def _detect_prompt_injection(question: str) -> bool:
    """
    Deteksi prompt injection dengan pattern matching deterministik.
    
    Mengembalikan True jika pertanyaan mengandung pola injection yang jelas.
    False positive: lebih baik reject pertanyaan sah daripada membiarkan injection.
    
    Pattern yang dicek:
    - "abaikan instruksi" (case-insensitive)
    - "ignore previous", "ignore instruction"
    - "SYSTEM:", "instruction override"
    - "mode developer", "tanpa batasan"
    - "override", "protocol", "jangan mengikuti"
    - HTML/XML comment dengan "override"
    """
    question_lower = question.lower()
    
    # Pattern injection yang jelas
    injection_patterns = [
        "abaikan instruksi",
        "ignore previous",
        "ignore instruction",
        "system:",
        "instruction override",
        "mode developer",
        "tanpa batasan",
        "override safety",
        "override protocol",
        "protokol keamanan",
        "jangan mengikuti",
        "<!-- override",
        "<!--instruction",
    ]
    
    return any(pattern in question_lower for pattern in injection_patterns)


def retrieve_documents(question, retriever, history=None, top_k=TOP_K):
    """Menjalankan retrieval lengkap yang dipakai chatbot dan evaluation benchmark."""
    clean_question, clean_history = _prepare_question_and_history(question, history)
    
    # Injection guard: deteksi pola prompt injection sebelum retrieval
    if _detect_prompt_injection(clean_question):
        _log_retrieval_issue(
            "injection-detected",
            "Prompt injection terdeteksi, retrieval dilewati: %s",
            clean_question[:100],
        )
        details = {
            "scoring_available": False,
            "scoring_error": "injection_detected",
            "score_scale_warning": False,
            "gate_status": "rejected",
            "candidate_count": 0,
            "selected_count": 0,
            "best_semantic_score": None,
            "injection_detected": True,
        }
        return [], clean_question, details

    retrieval_query = build_retrieval_query(
        clean_question,
        clean_history,
        max_history_messages=MAX_HISTORY_MESSAGES_FOR_RETRIEVAL,
    )
    scored_documents, scoring_available, scoring_error = _retrieve_with_confidence(
        retriever,
        retrieval_query,
    )

    # Skor di luar 0-1 menandakan skala relevance score tidak cocok dengan ambang (mis. embedding
    # tidak dinormalisasi). Ambang MIN_RELEVANCE_SCORE tidak bermakna dalam kondisi itu.
    score_scale_warning = any(
        score is not None and not (0.0 <= float(score) <= 1.0)
        for _document, score in scored_documents
    )
    if score_scale_warning:
        _log_retrieval_issue(
            "score-scale",
            "Skor relevansi di luar rentang 0-1. Periksa normalisasi embedding / metrik jarak indeks "
            "dan kalibrasi ulang MIN_RELEVANCE_SCORE.",
        )

    # _select_relevant_documents memakai TOP_K global agar konfigurasi runtime chatbot tetap
    # konsisten. Parameter top_k di sini hanya digunakan evaluation bila ingin membaca subset lebih kecil.
    selected_docs, best_score, gate_status = _select_relevant_documents(
        scored_documents,
        scoring_available,
        retrieval_query,
    )
    selected_docs = selected_docs[:max(1, int(top_k))]

    details = {
        "scoring_available": scoring_available,
        "scoring_error": scoring_error,
        "score_scale_warning": score_scale_warning,
        "gate_status": gate_status,
        "candidate_count": len(scored_documents),
        "selected_count": len(selected_docs),
        "best_semantic_score": (float(best_score) if best_score is not None else None),
    }
    return selected_docs, retrieval_query, details


def _best_score(scored_documents):
    scores = [float(score) for _doc, score in scored_documents if score is not None]
    return max(scores) if scores else None


def _select_relevant_documents(scored_documents, scoring_available, query):
    """Menyaring kandidat, reranking + diversifikasi section.

    Mengembalikan (dokumen, skor_semantik_terbaik, gate_status) dengan gate_status:
    - "passed"   : lolos MIN_RELEVANCE_SCORE;
    - "rescued"  : di bawah ambang tetapi lolos penyelamatan (hanya query berdomain);
    - "unscored" : skor tidak tersedia, lolos gate leksikal;
    - "rejected" : tidak ada yang lolos (pemanggil harus memakai fallback);
    - "empty"    : tidak ada kandidat sama sekali.
    """
    if not scored_documents:
        return [], None, "empty"

    domain_ok = is_domain_relevant(query)

    # Off-domain check: query tanpa istilah domain langsung ditolak tanpa skor
    if not domain_ok:
        return [], _best_score(scored_documents), "rejected"

    if not scoring_available:
        # Tanpa skor semantik, confidence gate diganti gate leksikal: query harus memuat istilah
        # domain, atau overlap leksikalnya kuat. Dulu jalur ini selalu meloloskan semuanya.
        reranked = rerank_scored_documents(
            query,
            scored_documents,
            top_k=TOP_K,
            max_chunks_per_section=MAX_CHUNKS_PER_SECTION,
        )
        if not reranked:
            return [], None, "rejected"
        best_lexical = reranked[0][2]
        if not (domain_ok or best_lexical >= UNSCORED_MIN_LEXICAL):
            return [], None, "rejected"
        return [document for document, _c, _l, _s in reranked], None, "unscored"

    # Confidence gate: cek apakah ada kandidat yang skornya >= MIN_RELEVANCE_SCORE
    # Jika tidak ada, lanjut ke tahap penyelamatan.
    has_relevant = any(
        score is not None and float(score) >= MIN_RELEVANCE_SCORE
        for _, score in scored_documents
    )

    if has_relevant:
        # Ambil TOP_K dari SELURUH kandidat yang sudah di-rerank,
        # bukan hanya dari yang di atas threshold MIN_RELEVANCE_SCORE
        reranked = rerank_scored_documents(
            query,
            scored_documents,
            top_k=TOP_K,
            max_chunks_per_section=MAX_CHUNKS_PER_SECTION,
        )
        if reranked:
            selected = [document for document, _c, _l, _s in reranked]
            best_score = max(float(score) for _, score in scored_documents if score is not None)
            return selected, best_score, "passed"

    # Tahap penyelamatan: ambang bisa terlalu ketat bila skala skor berubah antar-versi/metrik.
    # Hanya untuk query berdomain; query tanpa istilah domain langsung ditolak.
    best_score = _best_score(scored_documents)
    if domain_ok:
        rescue = rerank_scored_documents(
            query,
            scored_documents,
            top_k=TOP_K,
            max_chunks_per_section=MAX_CHUNKS_PER_SECTION,
        )
        if rescue:
            _document, _combined, lexical_score, semantic_score = rescue[0]
            if lexical_score >= RESCUE_MIN_LEXICAL or (
                semantic_score is not None and float(semantic_score) >= RESCUE_MIN_SEMANTIC
            ):
                return [document for document, _c, _l, _s in rescue], best_score, "rescued"

    return [], best_score, "rejected"


def _fallback_response(intent_name, domain_relevant=True):
    """
    Respons fallback deterministik saat tidak ada sumber yang cukup relevan.

    Untuk pertanyaan domain BPJS/magang, arahkan ke narahubung yang relevan.
    Untuk input yang jelas di luar domain, jangan langsung memberikan nomor kontak internal.
    """
    if not domain_relevant:
        return _off_domain_response()

    # Import lokal untuk menghindari circular dependency
    from contacts_config import INTENT_TO_CONTACT, format_contacts
    
    category = INTENT_TO_CONTACT.get(intent_name, "operasional_magang")
    contact = format_contacts(category)

    return (
        "Maaf, saya belum menemukan sumber yang cukup relevan untuk menjawab pertanyaan ini "
        "dengan aman. Saya tidak ingin menebak atau memberikan informasi yang belum terverifikasi.\n\n"
        f"Untuk memastikan jawabannya, silakan hubungi **{contact}**."
    )

def _below_minimum_response(amount, *, inherited: bool) -> str:
    """Penolakan eksplisit untuk dasar penghasilan di bawah minimum (tanpa memakai angka lain)."""
    source = "pada pesan sebelumnya" if inherited else "pada pertanyaan ini"
    return (
        "## Simulasi Iuran BPU\n\n"
        f"Nominal yang disebut {source} (**{format_rupiah(amount)}**) berada di bawah batas minimum. "
        f"Dasar penghasilan yang didaftarkan minimal **{format_rupiah(MIN_INCOME)} per bulan**.\n\n"
        f"Sebutkan dasar penghasilan **{format_rupiah(MIN_INCOME)} atau lebih** untuk saya hitung."
    )


_SLOT_LABELS = {
    "base_income": "dasar penghasilan",
    "programs": "pilihan program",
    "sector": "sektor pekerjaan",
}


def _inherited_note(context: ConversationContext, discount_requested: bool) -> str:
    """Beritahu user slot mana yang dipakai dari pesan sebelumnya (bukan dari pertanyaan ini)."""
    slots = [
        slot for slot in context.inherited_slots
        if slot != "sector" or discount_requested   # sektor hanya relevan untuk promo
    ]
    if not slots:
        return ""
    labels = " dan ".join(_SLOT_LABELS[slot] for slot in slots)
    return (
        f"\n\n*Catatan: {labels} dipakai dari pesan sebelumnya. Sebutkan nilai baru jika berbeda, "
        "atau tulis \"calon peserta baru\" untuk memulai simulasi dari awal.*"
    )


def _try_deterministic_calculation(
    question: str,
    context: Optional[ConversationContext] = None,
):
    """Mengembalikan jawaban numerik tanpa LLM dengan mewarisi slot percakapan."""
    context = context or ConversationContext()

    if not detect_calculation_request(
        question, has_income_context=context.base_income is not None
    ):
        return None

    # Nominal di bawah minimum yang disebut pada pertanyaan INI harus ditolak secara eksplisit,
    # bukan diam-diam diganti penghasilan lama dari percakapan.
    attempt = extract_income_attempt(question)
    if attempt is not None and attempt < MIN_INCOME:
        return _below_minimum_response(attempt, inherited=False)

    # Pertanyaan terbaru selalu menang (sudah ditangani build_conversation_context).
    # Slot yang tidak disebut diwarisi dari pesan user sebelumnya dan WAJIB diberitahukan.
    base_income = context.base_income
    if base_income is not None and base_income < MIN_INCOME:
        return _below_minimum_response(
            base_income, inherited="base_income" in context.inherited_slots
        )
    if base_income is None:
        return (
            "## Simulasi Iuran BPU\n\n"
            "Saya bisa menghitungnya secara otomatis. Sebutkan **dasar penghasilan per bulan**, "
            "misalnya **Rp1.000.000**, lalu sebutkan apakah calon peserta mengambil **2 program (JKK + JKM)** "
            "atau **3 program (JKK + JKM + JHT)**."
        )

    programs = context.programs
    discount_requested = detect_discount_request(question)
    inherited_note = _inherited_note(context, discount_requested)
    discount = False
    discount_note = ""

    if discount_requested:
        # Sektor boleh diwarisi dari percakapan sebelumnya, tetapi permintaan promo sendiri
        # tidak disimpan agar simulasi berikutnya tidak otomatis ikut diskon.
        sector = context.sector
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
            f"Dasar penghasilan: **{format_rupiah(two_programs.base_income)}**\n\n"
            "**2 program — JKK + JKM**\n\n"
            + build_calculation_response(two_programs)
            + "\n\n**3 program — JKK + JKM + JHT**\n\n"
            + build_calculation_response(three_programs)
            + discount_note
            + inherited_note
        )
        return response

    result = calculate_bpu_contribution(
        base_income, programs, discount_jkk_jkm=discount
    )
    return build_calculation_response(result) + discount_note + inherited_note


_PROMO_WORDS = ("promo", "diskon", "potongan", "50%")
_PROMO_IN_TEXT = re.compile(r"promo|diskon|potongan", re.IGNORECASE)


def _temporal_context(question: str, documents=None, today=None) -> str:
    """Status waktu untuk informasi promo yang memiliki periode berlaku.

    Disuntikkan bila pertanyaan menyebut promo ATAU dokumen yang diambil menyebut promo/diskon.
    Kasus kedua penting: pertanyaan umum ("iuran JKK berapa?") bisa mengambil chunk yang menulis
    "sedang berlaku diskon 50%", dan tanpa tanggal sistem LLM akan mengulang klaim basi itu.
    """
    asks_about_promo = detect_discount_request(question) or any(
        word in question.lower() for word in _PROMO_WORDS
    )
    docs_mention_promo = any(
        _PROMO_IN_TEXT.search(str(getattr(document, "page_content", "")))
        for document in (documents or [])
    )
    if not (asks_about_promo or docs_mention_promo):
        return "Tanggal sistem Asia/Jakarta: tidak diperlukan untuk pertanyaan ini."

    current = today or today_jakarta()
    status_lines = [f"Tanggal sistem Asia/Jakarta: {current.isoformat()}."]

    for item in promo_timeline(current):
        sector = item.sector.replace("_", " ")
        if item.state == "active":
            status_lines.append(
                f"Promo 50% JKK+JKM untuk sektor {sector} sedang berada dalam periode "
                f"berlaku sampai {item.end.isoformat()}."
            )
        elif item.state == "upcoming":
            status_lines.append(
                f"Promo 50% JKK+JKM untuk sektor {sector} belum mulai; periode "
                f"{item.start.isoformat()} sampai {item.end.isoformat()}."
            )
        else:
            status_lines.append(
                f"Promo 50% JKK+JKM untuk sektor {sector} sudah berakhir pada {item.end.isoformat()}."
            )

    status_lines.append(
        "Jangan menyebut promo sebagai berlaku tanpa memperhatikan sektor dan periode di atas. "
        "JHT tidak termasuk diskon 50%."
    )
    status_lines.append(
        "Dokumen ditulis pada tanggal tertentu dan dapat menyebut promo sebagai \"sedang berlaku\" "
        "atau \"saat ini\". Jika berbeda dengan status di atas, IKUTI status di atas."
    )
    return "\n".join(status_lines)


def _retrieval_notice(details) -> str:
    """Catatan hasil retrieval untuk LLM yang jujur soal tingkat keyakinan sumber."""
    gate = details.get("gate_status", "passed")
    no_score = "Jangan menyebut skor similarity sebagai probabilitas atau tingkat kepastian kepada pengguna. "
    if gate == "passed":
        return (
            "HASIL RETRIEVAL: Sumber di bawah telah lolos pemeriksaan relevansi minimum. " + no_score
        )
    reason = (
        "relevansinya RENDAH (hanya lolos pemeriksaan cadangan)"
        if gate == "rescued"
        else "relevansinya TIDAK TERUKUR (skor semantik tidak tersedia)"
    )
    return (
        f"HASIL RETRIEVAL: Perhatian, {reason}. Gunakan sumber di bawah HANYA bila benar-benar "
        "menjawab pertanyaan. Jika tidak, katakan bahwa informasinya belum tersedia dan arahkan ke "
        "kontak pada aturan FALLBACK; jangan menebak. " + no_score
    )


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
    pii_warning: str = ""


def _prepare_ask(question, retriever, history=None) -> _AskPlan:
    """
    Logika RAG bersama untuk ask() dan ask_stream(): sanitasi input, small talk,
    deteksi intent, retrieval + confidence gate, fallback, kalkulator deterministik,
    dan penyusunan prompt. Urutan & isinya sama persis dengan ask() versi sebelumnya,
    supaya perilaku (dan hasil evaluation) tidak berubah.
    """
    raw_question = question
    question, history = _prepare_question_and_history(question, history)
    
    # Cek data pribadi (PII) pada pertanyaan mentah sebelum sanitasi penuh
    pii_check = sanitize_user_input(raw_question)
    pii_warning = ""
    if pii_check.redacted or pii_check.flagged:
        pii_warning = (
            "⚠️ *Catatan SAPA: Mohon jangan mengetik atau menempelkan NIK, nomor KTP, KK, rekening, "
            "atau data identitas pribadi ke dalam chat. Gunakan formulir atau kanal resmi.*\\n\\n"
        )

    # Percakapan ringan tidak perlu melalui RAG. Ini mencegah input seperti "halo"
    # gagal melewati confidence gate dan mendapatkan fallback yang kaku.
    small_talk = detect_small_talk(question)
    if small_talk is not None:
        ans = SMALL_TALK_RESPONSES[small_talk]
        return _AskPlan(sources=[], static_answer=ans, pii_warning=pii_warning)

    # Slot-filling: jika hanya isi satu slot (penghasilan/sektor/program) TANPA kata tanya, jawab singkat tanpa LLM
    conversation_context = build_conversation_context(question, history)
    has_inherited = conversation_context.inherited_slots
    new_slot_count = sum([
        1 if conversation_context.base_income is not None else 0,
        1 if conversation_context.sector is not None else 0,
        1 if conversation_context.programs else 0,
    ])
    
    question_words = ("apakah", "berapa", "ada", "bagaimana", "gimana", "kapan", "siapa", "mengapa", "kenapa", "?")
    is_question = any(w in question.lower() for w in question_words)

    # Jika hanya satu slot baru (tidak ada yang diwarisi) DAN bukan kalimat tanya
    if new_slot_count == 1 and not has_inherited and not is_question:
        slot_label = "dasar penghasilan" if conversation_context.base_income is not None else (
            "sektor" if conversation_context.sector else "program"
        )
        slot_value = format_rupiah(conversation_context.base_income) if conversation_context.base_income is not None else (
            conversation_context.sector.replace("_", " ") if conversation_context.sector else ", ".join(conversation_context.programs)
        )
        return _AskPlan(
            sources=[],
            static_answer=f"Siap, {slot_label} **{slot_value}** tercatat. Mau dihitung untuk 2 program (JKK+JKM) atau 3 program (JKK+JKM+JHT)?",
        )

    # Pertanyaan pendek <=3 kata tanpa konteks domain → klarifikasi
    words = question.lower().split()
    if len(words) <= 3:
        clarification = _short_question_clarification(question)
        if clarification:
            return _AskPlan(sources=[], static_answer=clarification)

    intent_name = detect_intent(question)
    intent_instruction = get_intent_instruction(intent_name)

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
        ans = sanitize_assistant_output(deterministic_calculation)
        if pii_warning:
            ans = pii_warning + ans
        return _AskPlan(
            sources=relevant_docs,
            static_answer=ans,
        )

    # Jika tidak ada dokumen yang lolos retrieval/confidence gate, jangan panggil LLM.
    # Ini mencegah pertanyaan di luar domain mendapatkan jawaban yang terdengar meyakinkan.
    if not relevant_docs:
        # Pakai query retrieval (sudah memuat pertanyaan sebelumnya untuk follow-up) agar
        # lanjutan seperti "kalau 3 program?" tetap dikenali sebagai pertanyaan domain.
        is_domain = is_domain_relevant(retrieval_query)
        ans = sanitize_assistant_output(
            _fallback_response(intent_name, domain_relevant=is_domain)
        )
        if pii_warning:
            ans = pii_warning + ans
        return _AskPlan(
            sources=[],
            static_answer=ans,
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
        f"VALIDITAS INFORMASI BERTANGGAL:\n{_temporal_context(question, relevant_docs)}\n\n"
        f"{_retrieval_notice(retrieval_details)}"
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
    return _AskPlan(sources=relevant_docs, messages=messages, pii_warning=pii_warning)


def _llm_error_message(exc: Exception) -> str:
    """Pesan ramah (tanpa detail teknis) untuk kegagalan pemanggilan LLM."""
    name = type(exc).__name__.lower()
    detail = str(exc).lower()
    if "ratelimit" in name or "429" in detail or "rate limit" in detail or "rate_limit" in detail:
        reason = "Batas penggunaan layanan jawaban sedang tercapai. Tunggu sekitar satu menit lalu coba kirim ulang pertanyaan."
    elif "timeout" in name or "timed out" in detail or "connection" in name:
        reason = "Koneksi ke layanan jawaban terputus atau terlalu lama. Periksa sinyal internet lalu coba kirim ulang."
    elif "auth" in name or "401" in detail or "invalid api key" in detail:
        reason = "Layanan jawaban belum dikonfigurasi dengan benar (kunci API). Hubungi pengelola aplikasi."
    else:
        reason = "Layanan jawaban sedang bermasalah. Coba kirim ulang pertanyaan beberapa saat lagi."
    return "Maaf, saya belum bisa menjawab saat ini. " + reason


def ask(question, retriever, llm, history=None):
    """
    Fungsi RAG non-streaming (tetap dipertahankan untuk evaluation/benchmark & kode lama).
    Mengembalikan (jawaban, dokumen_sumber).
    Untuk UI dengan efek mesin tik, pakai ask_stream().
    """
    plan = _prepare_ask(question, retriever, history)
    if plan.static_answer is not None:
        return plan.static_answer, plan.sources

    try:
        response = llm.invoke(plan.messages)
        # GENERATION: LLM menerima aturan sistem + riwayat + konteks sumber + pertanyaan terbaru
    except Exception as exc:
        logger.exception("Pemanggilan LLM gagal")
        return _llm_error_message(exc), plan.sources

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
    """

    def __init__(self, sources, static_answer=None, llm=None, messages=None, pii_warning=""):
        self.sources = sources
        self._static_answer = static_answer
        self._llm = llm
        self._messages = messages
        self._pii_warning = pii_warning
        self.emitted = ""
        self.text = static_answer if static_answer is not None else ""
        if pii_warning and self._static_answer is not None and not self.text.startswith(pii_warning):
            self.text = pii_warning + self.text
            self.emitted = self.text

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
            self.emitted = self.text
            yield self.text
            return

        # Kirim peringatan PII sebagai potongan pertama jika ada
        if self._pii_warning:
            self.emitted = self._pii_warning
            yield self._pii_warning

        raw = ""
        committed = 0   # panjang raw yang sudah berupa baris-baris lengkap
        try:
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
        except Exception as exc:
            # Stream gagal (rate limit, koneksi putus, dsb): akhiri dengan pesan ramah, bukan
            # exception yang mematikan UI. Jawaban parsial (jika ada) dipertahankan + diberi catatan.
            logger.exception("Streaming LLM gagal")
            notice = _llm_error_message(exc)
            partial = sanitize_assistant_output(raw)
            self.text = f"{partial}\n\n{notice}" if partial else notice
            if self.text.startswith(self.emitted):
                tail = self.text[len(self.emitted):]
                self.emitted = self.text
                if tail:
                    yield tail
            return

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
        pii_warning=plan.pii_warning,
    )