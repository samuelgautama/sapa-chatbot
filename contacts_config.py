"""
contacts_config.py
------------------
Sumber terpusat untuk data narahubung program magang BPJS Ketenagakerjaan.

Digunakan oleh chatbot.py untuk SYSTEM_PROMPT dan fallback response.
Saat kontak berubah, edit file ini saja (tidak perlu ubah chatbot.py).
"""

# Kontak per kategori bantuan
CONTACTS = {
    "operasional_magang": [
        {"name": "Samuel", "phone": "+62 856-6820-6081"},
        {"name": "Nabilariza", "phone": "+62 823-6370-3956"},
    ],
    "brosur": [
        {"name": "Grace", "phone": "+62 822-7143-8378"},
    ],
    "pendaftaran": [
        {"name": "Zahra", "phone": "+62 852-7812-4901"},
    ],
    "absensi_logbook": [
        {"name": "Elvan", "phone": "+62 813-9617-3602"},
        {"name": "Jeremy", "phone": "+62 813-1505-4991"},
    ],
}

# Mapping intent chatbot → kategori kontak untuk fallback
INTENT_TO_CONTACT = {
    "pendaftaran": "pendaftaran",
    "follow_up": "pendaftaran",
    "simulasi": "pendaftaran",
    "umum": "operasional_magang",
    "identifikasi": "operasional_magang",
    "edukasi": "operasional_magang",
    "keberatan": "operasional_magang",
}


def format_contacts(category: str) -> str:
    """Return kontak terformat: 'Nama (+62...)' atau 'Nama1 (+62...) atau Nama2 (+62...)'
    
    Contoh output:
    - "Grace (+62 822-7143-8378)"
    - "Samuel (+62 856-6820-6081) atau Nabilariza (+62 823-6370-3956)"
    """
    if category not in CONTACTS:
        # Default fallback ke operasional magang
        category = "operasional_magang"
    
    contacts = CONTACTS[category]
    return " atau ".join(f"{c['name']} ({c['phone']})" for c in contacts)


def build_fallback_section() -> str:
    """Generate bagian FALLBACK untuk SYSTEM_PROMPT dengan kontak terkini."""
    return f"""=== FALLBACK ===
Jika jawaban tidak ditemukan pada KONTEKS DOKUMEN:
1. Katakan dengan ramah bahwa informasi tersebut belum tersedia di sistem saat ini.
2. Jangan mengarang jawaban atau angka.
3. Arahkan ke kontak yang paling relevan di bawah ini.

- 🗂️ **Operasional Magang** (kegiatan umum & administrasi magang):
  {format_contacts("operasional_magang")}
- 📄 **Pengambilan Brosur BPJS TK**:
  {format_contacts("brosur")}
- 📝 **Pendaftaran BPU hingga Pencetakan Kartu**:
  {format_contacts("pendaftaran")}
- 🗓️ **Absensi & Logbook Aktivitas**:
  {format_contacts("absensi_logbook")}

Kejujuran lebih penting daripada terlihat serba tahu, terutama karena informasi ini menyangkut hak
dan kewajiban peserta jaminan sosial."""
