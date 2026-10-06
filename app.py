import html
import itertools
import json
import math
import re
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from chatbot import load_retriever, load_llm, ask_stream
from theme import get_custom_css, get_layout_script


# Wordmark SAPA (ikon + teks, gradient cyan->hijau/olive) dipakai di halaman
# awal (judul besar) dan navbar (saat chat berjalan). Di-inline sebagai data
# URI base64 supaya tidak bergantung pada file aset terpisah saat deploy.
_SAPA_WORDMARK = (
    "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTI1IiBoZWlnaHQ9IjM4IiB2aWV3Qm94PSIwIDAgMTI1IDM4IiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgo8ZyBjbGlwLXBhdGg9InVybCgjY2xpcDBfMTdfOSkiPgo8ZyBjbGlwLXBhdGg9InVybCgjY2xpcDFfMTdfOSkiPgo8cGF0aCBkPSJNMjIgMkMyOC42Mjc0IDIgMzQgNy4zNzI1OCAzNCAxNFYyMkMzNCAyOC42Mjc0IDI4LjYyNzQgMzQgMjIgMzRIMlYxNEMyIDcuMzcyNTggNy4zNzI1OCAyIDE0IDJIMjJaTTE1IDVDOS40NzcxNSA1IDUgOS40NzcxNSA1IDE1VjMxSDIxQzI2LjUyMjggMzEgMzEgMjYuNTIyOCAzMSAyMVYxNUMzMSA5LjQ3NzE1IDI2LjUyMjggNSAyMSA1SDE1WiIgZmlsbD0idXJsKCNwYWludDBfbGluZWFyXzE3XzkpIi8+CjxwYXRoIGQ9Ik0yNiAxOEMyNiAxOS4wODk1IDI1Ljc3NzUgMjAuMTY3NiAyNS4zNDYgMjEuMTY4MUMyNC45MTQ2IDIyLjE2ODYgMjQuMjgzMyAyMy4wNzA0IDIzLjQ5MDkgMjMuODE4MkMyMi4wMDc3IDI1LjIyMiAyMC4wNDIyIDI2LjAwMyAxOCAyNkMxNS44NzQ5IDI2IDEzLjk0MTggMjUuMTcwOSAxMi41MDkxIDIzLjgxODJDMTEuNzE2NyAyMy4wNzA0IDExLjA4NTQgMjIuMTY4NiAxMC42NTQgMjEuMTY4MUMxMC4yMjI1IDIwLjE2NzYgOS45OTk5OCAxOS4wODk1IDEwIDE4SDI2WiIgZmlsbD0idXJsKCNwYWludDFfbGluZWFyXzE3XzkpIi8+CjwvZz4KPHBhdGggZD0iTTQ5LjgxNiAzMS4zODRDNDguMzIyNyAzMS4zODQgNDYuOTM2IDMxLjEwNjcgNDUuNjU2IDMwLjU1MkM0NC4zNzYgMjkuOTc2IDQzLjI4OCAyOS4xOTczIDQyLjM5MiAyOC4yMTZDNDEuNDk2IDI3LjIzNDcgNDAuODM0NyAyNi4xMDQgNDAuNDA4IDI0LjgyNEw0My42MDggMjMuNDhDNDQuMTg0IDI0Ljk1MiA0NS4wMjY3IDI2LjA4MjcgNDYuMTM2IDI2Ljg3MkM0Ny4yNDUzIDI3LjY2MTMgNDguNTI1MyAyOC4wNTYgNDkuOTc2IDI4LjA1NkM1MC44MjkzIDI4LjA1NiA1MS41NzYgMjcuOTI4IDUyLjIxNiAyNy42NzJDNTIuODU2IDI3LjM5NDcgNTMuMzQ2NyAyNy4wMTA3IDUzLjY4OCAyNi41MkM1NC4wNTA3IDI2LjAyOTMgNTQuMjMyIDI1LjQ2NCA1NC4yMzIgMjQuODI0QzU0LjIzMiAyMy45NDkzIDUzLjk4NjcgMjMuMjU2IDUzLjQ5NiAyMi43NDRDNTMuMDA1MyAyMi4yMzIgNTIuMjggMjEuODI2NyA1MS4zMiAyMS41MjhMNDYuODQgMjAuMTJDNDUuMDQ4IDE5LjU2NTMgNDMuNjgyNyAxOC43MjI3IDQyLjc0NCAxNy41OTJDNDEuODA1MyAxNi40NCA0MS4zMzYgMTUuMDk2IDQxLjMzNiAxMy41NkM0MS4zMzYgMTIuMjE2IDQxLjY2NjcgMTEuMDQyNyA0Mi4zMjggMTAuMDRDNDIuOTg5MyA5LjAxNiA0My44OTYgOC4yMTYgNDUuMDQ4IDcuNjRDNDYuMjIxMyA3LjA2NCA0Ny41NTQ3IDYuNzc2IDQ5LjA0OCA2Ljc3NkM1MC40NzczIDYuNzc2IDUxLjc3ODcgNy4wMzIgNTIuOTUyIDcuNTQ0QzU0LjEyNTMgOC4wMzQ2NyA1NS4xMjggOC43MTczMyA1NS45NiA5LjU5MkM1Ni44MTMzIDEwLjQ2NjcgNTcuNDMyIDExLjQ4IDU3LjgxNiAxMi42MzJMNTQuNjggMTQuMDA4QzU0LjIxMDcgMTIuNzQ5MyA1My40NzQ3IDExLjc3ODcgNTIuNDcyIDExLjA5NkM1MS40OTA3IDEwLjQxMzMgNTAuMzQ5MyAxMC4wNzIgNDkuMDQ4IDEwLjA3MkM0OC4yNTg3IDEwLjA3MiA0Ny41NjUzIDEwLjIxMDcgNDYuOTY4IDEwLjQ4OEM0Ni4zNzA3IDEwLjc0NCA0NS45MDEzIDExLjEyOCA0NS41NiAxMS42NEM0NS4yNCAxMi4xMzA3IDQ1LjA4IDEyLjcwNjcgNDUuMDggMTMuMzY4QzQ1LjA4IDE0LjEzNiA0NS4zMjUzIDE0LjgxODcgNDUuODE2IDE1LjQxNkM0Ni4zMDY3IDE2LjAxMzMgNDcuMDUzMyAxNi40NjEzIDQ4LjA1NiAxNi43Nkw1Mi4yMTYgMTguMDcyQzU0LjExNDcgMTguNjQ4IDU1LjU0NCAxOS40OCA1Ni41MDQgMjAuNTY4QzU3LjQ2NCAyMS42MzQ3IDU3Ljk0NCAyMi45NjggNTcuOTQ0IDI0LjU2OEM1Ny45NDQgMjUuODkwNyA1Ny41OTIgMjcuMDY0IDU2Ljg4OCAyOC4wODhDNTYuMjA1MyAyOS4xMTIgNTUuMjU2IDI5LjkyMjcgNTQuMDQgMzAuNTJDNTIuODI0IDMxLjA5NiA1MS40MTYgMzEuMzg0IDQ5LjgxNiAzMS4zODRaTTU5LjkxNDUgMzFMNjguMjk4NSA3LjE2SDcyLjk3MDVMODEuMzU0NSAzMUg3Ny4zMjI1TDc1LjQ5ODUgMjUuNjU2SDY1LjgwMjVMNjMuOTQ2NSAzMUg1OS45MTQ1Wk02Ni44OTA1IDIyLjI5Nkg3NC4zNDY1TDcwLjEyMjUgOS44MTZINzEuMTc4NUw2Ni44OTA1IDIyLjI5NlpNODQuMTgyOCAzMVY3LjE2SDkyLjg1NDhDOTQuNDU0OCA3LjE2IDk1Ljg2MjggNy40NTg2NyA5Ny4wNzg4IDguMDU2Qzk4LjMxNjEgOC42MzIgOTkuMjc2MSA5LjQ4NTMzIDk5Ljk1ODggMTAuNjE2QzEwMC42NDEgMTEuNzI1MyAxMDAuOTgzIDEzLjA1ODcgMTAwLjk4MyAxNC42MTZDMTAwLjk4MyAxNi4xNTIgMTAwLjYzMSAxNy40NzQ3IDk5LjkyNjggMTguNTg0Qzk5LjI0NDEgMTkuNjkzMyA5OC4yOTQ4IDIwLjU0NjcgOTcuMDc4OCAyMS4xNDRDOTUuODYyOCAyMS43NDEzIDk0LjQ1NDggMjIuMDQgOTIuODU0OCAyMi4wNEg4Ny45NTg4VjMxSDg0LjE4MjhaTTg3Ljk1ODggMTguNjhIOTIuOTUwOEM5My44MDQxIDE4LjY4IDk0LjU1MDggMTguNTA5MyA5NS4xOTA4IDE4LjE2OEM5NS44MzA4IDE3LjgyNjcgOTYuMzMyMSAxNy4zNTczIDk2LjY5NDggMTYuNzZDOTcuMDU3NCAxNi4xNDEzIDk3LjIzODggMTUuNDE2IDk3LjIzODggMTQuNTg0Qzk3LjIzODggMTMuNzUyIDk3LjA1NzQgMTMuMDM3MyA5Ni42OTQ4IDEyLjQ0Qzk2LjMzMjEgMTEuODIxMyA5NS44MzA4IDExLjM1MiA5NS4xOTA4IDExLjAzMkM5NC41NTA4IDEwLjY5MDcgOTMuODA0MSAxMC41MiA5Mi45NTA4IDEwLjUySDg3Ljk1ODhWMTguNjhaTTEwMC44NTIgMzFMMTA5LjIzNiA3LjE2SDExMy45MDhMMTIyLjI5MiAzMUgxMTguMjZMMTE2LjQzNiAyNS42NTZIMTA2Ljc0TDEwNC44ODQgMzFIMTAwLjg1MlpNMTA3LjgyOCAyMi4yOTZIMTE1LjI4NEwxMTEuMDYgOS44MTZIMTEyLjExNkwxMDcuODI4IDIyLjI5NloiIGZpbGw9InVybCgjcGFpbnQyX2xpbmVhcl8xN185KSIvPgo8L2c+CjxkZWZzPgo8bGluZWFyR3JhZGllbnQgaWQ9InBhaW50MF9saW5lYXJfMTdfOSIgeDE9IjE4LjQ3MDYiIHkxPSIxOC40NzA2IiB4Mj0iMTguNDcwNiIgeTI9IjI2LjIzNTMiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KPHN0b3Agc3RvcC1jb2xvcj0iIzAwOUZERiIvPgo8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiMzOUE4NDkiLz4KPC9saW5lYXJHcmFkaWVudD4KPGxpbmVhckdyYWRpZW50IGlkPSJwYWludDFfbGluZWFyXzE3XzkiIHgxPSIxOC45OTA5IiB5MT0iMTcuMjAxOSIgeDI9IjE4Ljk5MDkiIHkyPSIyNS4yMDE5IiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CjxzdG9wIHN0b3AtY29sb3I9IiMwMDlGREYiLz4KPHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjMzlBODQ5Ii8+CjwvbGluZWFyR3JhZGllbnQ+CjxsaW5lYXJHcmFkaWVudCBpZD0icGFpbnQyX2xpbmVhcl8xN185IiB4MT0iODEuNSIgeTE9Ii0yIiB4Mj0iODEuNSIgeTI9IjMwIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CjxzdG9wIHN0b3AtY29sb3I9IiMwMDlGREYiLz4KPHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjQzRENjAwIi8+CjwvbGluZWFyR3JhZGllbnQ+CjxjbGlwUGF0aCBpZD0iY2xpcDBfMTdfOSI+CjxyZWN0IHdpZHRoPSIxMjUiIGhlaWdodD0iMzgiIGZpbGw9IndoaXRlIi8+CjwvY2xpcFBhdGg+CjxjbGlwUGF0aCBpZD0iY2xpcDFfMTdfOSI+CjxyZWN0IHdpZHRoPSIzMiIgaGVpZ2h0PSIzMiIgZmlsbD0id2hpdGUiIHRyYW5zZm9ybT0idHJhbnNsYXRlKDIgMikiLz4KPC9jbGlwUGF0aD4KPC9kZWZzPgo8L3N2Zz4K"
)


# ---------------------------------------------------------------------------
# Konfigurasi halaman
# ---------------------------------------------------------------------------
# Ikon tab browser (favicon). Taruh gambar ikon chatbot di folder "assets"
# sebelah app.py dengan nama "icon" (icon.png / icon.ico / icon.svg / ...).
# Kalau filenya belum ada, dipakai emoji cadangan supaya app tetap jalan.
_BASE_DIR = Path(__file__).resolve().parent


def load_page_icon(fallback: str = "💬"):
    for folder in (_BASE_DIR / "assets", _BASE_DIR):
        for ext in ("png", "ico", "svg", "webp", "jpg", "jpeg"):
            candidate = folder / f"icon.{ext}"
            if candidate.is_file():
                return str(candidate)
    return fallback


st.set_page_config(
    page_title="SAPA — Teman Magang",
    page_icon=load_page_icon(),
    layout="wide",
    initial_sidebar_state="collapsed",   # sidebar tidak dipakai
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "sources_map" not in st.session_state:
    st.session_state.sources_map = {}
if "used_actions" not in st.session_state:
    st.session_state.used_actions = set()
if "qa_open" not in st.session_state:
    st.session_state.qa_open = False   # popup bantuan cepat (hanya dipakai saat chat berjalan)
if "last_message_ts" not in st.session_state:
    st.session_state.last_message_ts = None     # waktu (monotonic) pesan terakhir yang DITERIMA; untuk rate limit
if "theme" not in st.session_state:
    st.session_state.theme = "system"           # "system" (ikut tema perangkat) | "light" | "dark"

# Rate limit per sesi: maksimal 1 pesan setiap RATE_LIMIT_SECONDS detik.
# Sengaja TIDAK di-reset oleh "+ Baru", supaya tombol itu tidak bisa dipakai menghindari batas.
RATE_LIMIT_SECONDS = 9


quick_action_defs = [
    {
        "key": "identifikasi",
        "label": "Identifikasi",
        "icon": "search",
        "desc": "Cek calon peserta BPU",
        "prompt": "Saya sedang menemui calon peserta. Bagaimana cara mengecek apakah orang ini termasuk BPU dan apa yang perlu saya tanyakan?",
    },
    {
        "key": "program",
        "label": "Program",
        "icon": "menu_book",
        "desc": "Ringkas JKK, JKM, dan JHT",
        "prompt": "Bagaimana cara menjelaskan JKK, JKM, dan JHT kepada calon peserta dengan bahasa sederhana?",
    },
    {
        "key": "iuran",
        "label": "Iuran",
        "icon": "payments",
        "desc": "Hitung iuran BPU",
        "prompt": "Bantu saya menghitung iuran BPU untuk calon peserta berdasarkan penghasilan yang saya sebutkan nanti.",
    },
    {
        "key": "keberatan",
        "label": "Keberatan",
        "icon": "forum",
        "desc": "Bantu jawab keraguan peserta",
        "prompt": "Calon peserta keberatan dengan iuran. Bantu saya menanggapi keberatan tersebut dengan sopan dan faktual.",
    },
    {
        "key": "pendaftaran",
        "label": "Pendaftaran",
        "icon": "how_to_reg",
        "desc": "Panduan alur pendaftaran",
        "prompt": "Bagaimana alur pendaftaran BPU melalui mahasiswa magang?",
    },
    {
        "key": "followup",
        "label": "Follow-up",
        "icon": "task_alt",
        "desc": "Tentukan langkah berikutnya",
        "prompt": "Apa yang perlu saya lakukan setelah pendaftaran calon peserta diproses?",
    },
]


# ---------------------------------------------------------------------------
# Helper UI
# ---------------------------------------------------------------------------
def start_new_conversation():
    st.session_state.messages = []
    st.session_state.pending_prompt = None
    st.session_state.sources_map = {}
    st.session_state.used_actions = set()
    st.session_state.qa_open = False


def set_theme(mode: str) -> None:
    """Simpan pilihan tema. Tombol tema selalu memilih nilai eksplisit ("light"/"dark"), jadi
    tidak perlu tahu tema perangkat di sisi server — CSS yang menentukan tombol mana yang tampil."""
    st.session_state.theme = mode if mode in ("light", "dark") else "system"


def render_theme_toggle() -> None:
    """
    Tombol ikon matahari/bulan. Dua tombol dirender (-> terang, -> gelap); theme.py hanya
    menampilkan yang sesuai dengan tema EFEKTIF (juga saat tema = "system"). Dalam keadaan
    Dark yang terlihat matahari (klik = terang), dalam Light yang terlihat bulan (klik = gelap).
    """
    st.button(
        "Ganti ke mode terang",
        key="theme_to_light",
        icon=":material/light_mode:",
        help="Ganti ke mode terang",
        on_click=set_theme,
        args=("light",),
    )
    st.button(
        "Ganti ke mode gelap",
        key="theme_to_dark",
        icon=":material/dark_mode:",
        help="Ganti ke mode gelap",
        on_click=set_theme,
        args=("dark",),
    )


# Popup Bantuan cepat dan dialog "+ Baru" dibuka/ditutup di sisi KLIEN (theme.py, JS), bukan
# lewat session_state: setiap buka/tutup via Streamlit = 1x rerun penuh (terasa berat).
# Dari Python hanya tersisa aksi yang memang perlu server: memilih bantuan cepat & reset chat.
def confirm_new_chat_action():
    start_new_conversation()


def render_quick_action_buttons():
    """Daftar bantuan cepat (dipakai di chat kosong maupun di dalam popup)."""
    with st.container(key="quick_actions"):
        for action in quick_action_defs:
            is_used = action["key"] in st.session_state.used_actions
            if st.button(
                action["desc"],
                icon=f":material/{action['icon']}:",
                key=f"qa_{action['key']}",
                use_container_width=True,
                type="secondary",
                disabled=is_used,
            ):
                st.session_state.used_actions.add(action["key"])
                st.session_state.pending_prompt = action["prompt"]
                st.session_state.qa_open = False   # popup menutup setelah memilih
                st.rerun()


def md_safe(text) -> str:
    """
    Jawaban AI dirender sebagai markdown. Tanda '$' dianggap pembuka rumus LaTeX
    oleh Streamlit, jadi dua '$' dalam satu jawaban bisa merusak tampilan teks.
    """
    return str(text).replace("$", r"\$")


# Kecepatan efek mesin tik (detik per kata). Dimulai agak pelan lalu mempercepat
# seiring jawaban memanjang, supaya jawaban panjang tidak terasa lama.
_TYPE_DELAY_START = 0.016
_TYPE_DELAY_MIN = 0.004
_TYPE_RAMP_WORDS = 250


def typewriter(deltas):
    """
    Generator untuk st.write_stream: memecah potongan teks dari LLM menjadi
    kata-per-kata dan memberi jeda singkat -> efek mesin tik yang halus walau
    LLM mengirim token sangat cepat. Baris tabel markdown (diawali '|') dikirim
    utuh agar tabel tidak tampil setengah jadi.
    """
    shown = 0
    for delta in deltas:
        for line in delta.splitlines(keepends=True):
            if line.lstrip().startswith("|"):
                pieces = [line]
            else:
                pieces = re.findall(r"\S+\s*|\s+", line)
            for piece in pieces:
                yield md_safe(piece)
                shown += 1
                ramp = max(0.0, 1.0 - shown / _TYPE_RAMP_WORDS)
                time.sleep(_TYPE_DELAY_MIN + (_TYPE_DELAY_START - _TYPE_DELAY_MIN) * ramp)


def cooldown_remaining() -> float:
    """Sisa detik sebelum pesan berikutnya boleh dikirim (0 bila sudah boleh)."""
    last = st.session_state.last_message_ts
    if last is None:
        return 0.0
    return max(0.0, RATE_LIMIT_SECONDS - (time.monotonic() - last))


def render_cooldown_sync() -> None:
    """
    Penanda tak terlihat untuk JS (theme.py): sisa cooldown RESMI dari server. JS memakainya
    untuk menonaktifkan tombol kirim + bantuan cepat dengan hitung mundur, jadi pengguna
    tidak perlu mengirim dulu lalu ditolak (dan teks yang diketik tidak hilang).
    """
    remaining = cooldown_remaining()
    if remaining <= 0:
        return
    st.markdown(
        f'<div class="sapa-cooldown-sync" data-key="{st.session_state.last_message_ts:.3f}" '
        f'data-remaining="{int(remaining * 1000)}" data-total="{RATE_LIMIT_SECONDS * 1000}"></div>',
        unsafe_allow_html=True,
    )


def render_rate_limit_warning(wait_seconds: float) -> None:
    """
    Peringatan ramah + hitung mundur. Hilang sendiri begitu jeda selesai, jadi tidak
    ada peringatan basi yang tertinggal di layar. Kalau pengguna berinteraksi lagi
    saat hitung mundur berjalan, Streamlit mererun skrip dan loop ini berhenti sendiri.
    """
    with st.container(key="rate_limit"):
        box = st.empty()
        deadline = time.monotonic() + wait_seconds
        shown = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            seconds = max(1, math.ceil(remaining))
            if seconds != shown:   # render ulang hanya saat angkanya berganti
                box.warning(
                    f"Pelan-pelan ya, pesanmu belum terkirim. "
                    f"Coba lagi dalam **{seconds} detik**.",
                    icon="⏳",
                )
                shown = seconds
            time.sleep(min(0.2, remaining))
        box.empty()


def render_user_message(text) -> None:
    """
    Teks pengguna ditampilkan APA ADANYA: baris baru (Shift+Enter) terjaga,
    dan karakter seperti * _ # $ < > tidak diparsing sebagai markdown/HTML.
    """
    safe = html.escape(str(text)).replace("\n", "<br>")
    st.markdown(f'<div class="sapa-user-text">{safe}</div>', unsafe_allow_html=True)


_COPY_BUTTON_HTML = """<!doctype html>
<html data-theme="__THEME__">
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="__SCHEME__">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600&display=swap">
<style>
  /* Palet tombol salin. Dark = default; Light dipilih lewat data-theme="light", atau
     data-theme="system" + perangkat terang. Iframe tidak bisa membaca tema aplikasi, jadi
     app.py meneruskannya lewat atribut ini. */
  :root {
    color-scheme: dark;
    --fg: #A9B0BD; --fg-hover: #ECEEF2; --hover-bg: rgba(255,255,255,.07);
    --done: #86EFAC; --done-bg: rgba(134,239,172,.10);
    --err: #FCA5A5; --err-bg: rgba(252,165,165,.10);
    --focus: rgba(165,180,252,.65);
  }
  :root[data-theme="light"] {
    color-scheme: light;
    --fg: #596171; --fg-hover: #0A0C11; --hover-bg: rgba(15,23,42,.07);
    --done: #15803D; --done-bg: rgba(21,128,61,.10);
    --err: #B91C1C; --err-bg: rgba(185,28,28,.08);
    --focus: rgba(79,70,229,.60);
  }
  :root[data-theme="system"] { color-scheme: light dark; }
  @media (prefers-color-scheme: light) {
    :root[data-theme="system"] {
      --fg: #596171; --fg-hover: #0A0C11; --hover-bg: rgba(15,23,42,.07);
      --done: #15803D; --done-bg: rgba(21,128,61,.10);
      --err: #B91C1C; --err-bg: rgba(185,28,28,.08);
      --focus: rgba(79,70,229,.60);
    }
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
  body {
    height: 38px; display: flex; align-items: center;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  button {
    all: unset; box-sizing: border-box;
    display: inline-flex; align-items: center; gap: 7px;
    height: 32px; padding: 0 13px 0 11px; border-radius: 9px;
    color: var(--fg); font-size: 13px; font-weight: 600; line-height: 1;
    cursor: pointer; user-select: none; -webkit-user-select: none;
    -webkit-tap-highlight-color: transparent;
    transition: background-color .18s ease, color .18s ease, transform .12s ease;
  }
  button:hover { background: var(--hover-bg); color: var(--fg-hover); }
  button:active { transform: scale(.96); }
  button:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
  button[data-state="done"]  { color: var(--done); background: var(--done-bg); }
  button[data-state="error"] { color: var(--err); background: var(--err-bg); }

  .ico { position: relative; width: 16px; height: 16px; flex: none; }
  .ico svg {
    position: absolute; inset: 0; width: 16px; height: 16px;
    fill: none; stroke: currentColor; stroke-width: 2;
    stroke-linecap: round; stroke-linejoin: round;
    transition: opacity .18s ease, transform .18s ease;
  }
  .ico .ok { opacity: 0; transform: scale(.5); }
  button[data-state="done"] .ico .cp { opacity: 0; transform: scale(.5); }
  button[data-state="done"] .ico .ok { opacity: 1; transform: scale(1); }

  @media (prefers-reduced-motion: reduce) {
    * { transition-duration: .01ms !important; }
  }
</style>
</head>
<body data-key="__KEY__">
  <button id="copy" type="button" title="Salin jawaban (format siap WhatsApp)" aria-label="Salin jawaban" data-state="idle">
    <span class="ico" aria-hidden="true">
      <svg class="cp" viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6.5A2.5 2.5 0 0 1 7.5 4H15"/></svg>
      <svg class="ok" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>
    </span>
    <span class="lbl" aria-live="polite">Salin</span>
  </button>
<script>
  const btn = document.getElementById("copy");
  const lbl = btn.querySelector(".lbl");
  const text = __TEXT__;
  let timer = null;

  function flash(state, label, ms) {
    clearTimeout(timer);
    btn.dataset.state = state;
    lbl.textContent = label;
    timer = setTimeout(() => { btn.dataset.state = "idle"; lbl.textContent = "Salin"; }, ms);
  }

  function legacyCopy() {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;top:0;left:0;opacity:0;";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) {}
    area.remove();
    return ok;
  }

  async function copyText() {
    let ok = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        ok = true;
      }
    } catch (e) {}
    if (!ok) ok = legacyCopy();
    if (ok) flash("done", "Tersalin", 1800);
    else flash("error", "Gagal menyalin", 2200);
  }

  btn.addEventListener("click", copyText);
</script>
</body>
</html>"""


def to_whatsapp(text) -> str:
    """
    Ubah markdown jawaban AI menjadi teks yang tampil rapi di WhatsApp.

    WhatsApp memakai *tebal*, _miring_, ~coret~ (bukan **tebal** / *miring*),
    tidak punya heading (#), dan tidak merender [teks](link).
    """
    t = str(text).replace("\r\n", "\n")

    # Garis pemisah (---, ***, ___) dibuang; harus sebelum konversi bullet
    t = re.sub(r"^[ \t]*([-*_])([ \t]*\1){2,}[ \t]*$", "", t, flags=re.M)
    # Heading (# Judul) -> *Judul*
    t = re.sub(
        r"^[ \t]{0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$",
        lambda m: "**" + re.sub(r"\*\*|__", "", m.group(1)).strip() + "**",
        t, flags=re.M,
    )
    # Bullet (*, +, •, -) -> "- " dengan indentasi tetap
    t = re.sub(r"^([ \t]*)[*+\u2022\-][ \t]+", r"\1- ", t, flags=re.M)
    # [teks](https://...) -> teks (https://...)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", t)
    # **tebal** / __tebal__ -> penanda sementara (supaya tidak ikut diubah jadi miring)
    t = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", "\x00\\2\x00", t)
    # ~~coret~~ -> ~coret~
    t = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"~\1~", t)
    # *miring* -> _miring_
    t = re.sub(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])", r"_\1_", t)
    # penanda tebal -> *tebal*
    t = t.replace("\x00", "*")

    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def render_copy_button(text: str, key_suffix: str):
    theme = st.session_state.get("theme", "system")
    # "<" di-escape supaya jawaban yang berisi "</script>" tidak merusak skrip
    payload = json.dumps(to_whatsapp(text), ensure_ascii=False).replace("<", "\\u003c")
    page = (
        _COPY_BUTTON_HTML
        .replace("__KEY__", html.escape(str(key_suffix)))
        .replace("__THEME__", theme)
        .replace("__SCHEME__", "light dark" if theme == "system" else theme)
        .replace("__TEXT__", payload)
    )
    # Lebar iframe dikunci sedikit di atas lebar tombol (label terpanjang: "Gagal menyalin"),
    # supaya area di belakang tombol tidak melebar sampai ujung kanan.
    components.html(page, width=150, height=38, scrolling=False)


def render_sources(sources):
    if not sources:
        return
    with st.expander(f"📚 Lihat sumber ({len(sources)})"):
        blocks = []
        for index, doc in enumerate(sources, start=1):
            metadata = getattr(doc, "metadata", {}) or {}
            source_name = (
                metadata.get("source_name")
                or metadata.get("source_file")
                or f"Sumber {index}"
            )
            section = metadata.get("section") or "Bagian umum"
            body = (getattr(doc, "page_content", "") or "").strip()

            # Satu baris HTML per kartu (tanpa baris kosong) agar tidak dipecah parser markdown
            blocks.append(
                '<div class="sapa-src">'
                '<div class="sapa-src-head">'
                f'<span class="sapa-src-num">{index}</span>'
                '<div class="sapa-src-meta">'
                f'<div class="sapa-src-name">{html.escape(str(source_name))}</div>'
                f'<div class="sapa-src-section">Bagian: {html.escape(str(section))}</div>'
                '</div></div>'
                f'<div class="sapa-src-body">{html.escape(body).replace(chr(10), "<br>")}</div>'
                '</div>'
            )
        st.markdown("".join(blocks), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Setup RAG
# ---------------------------------------------------------------------------
@st.cache_resource
def setup():
    retriever = load_retriever()
    llm = load_llm()
    return retriever, llm

try:
    retriever, llm = setup()
except Exception as e:
    st.error(f"Sistem tidak dapat dimuat: {e}")
    st.stop()


# ---------------------------------------------------------------------------
# 1. Input user
#    st.chat_input tetap di level root supaya Streamlit menempelkannya di bawah;
#    posisi tengah (desktop, chat masih kosong) diatur lewat CSS di theme.py.
#    Placeholder sengaja pendek: ::placeholder tidak bisa dipotong dengan CSS,
#    jadi teks panjang akan membungkus jadi 2 baris di layar sempit.
# ---------------------------------------------------------------------------
pending_prompt = st.session_state.pop("pending_prompt", None)
user_question = st.chat_input("Tanya apa saja soal magang...")
if user_question:
    user_question = user_question.strip()
if pending_prompt and not user_question:
    user_question = pending_prompt

# Rate limit: pesan hanya diterima bila sudah >= RATE_LIMIT_SECONDS sejak pesan
# terakhir yang diterima. Percobaan yang ditolak TIDAK memperpanjang hitungan.
# Pesan yang ditolak tidak masuk riwayat dan tidak menyentuh pipeline RAG sama sekali.
rate_limit_wait = 0.0
if user_question:
    now = time.monotonic()
    last_ts = st.session_state.last_message_ts
    elapsed = (now - last_ts) if last_ts is not None else RATE_LIMIT_SECONDS
    if elapsed < RATE_LIMIT_SECONDS:
        rate_limit_wait = RATE_LIMIT_SECONDS - elapsed
        if pending_prompt and pending_prompt == user_question:
            # Bantuan cepat yang ditolak: aktifkan lagi tombolnya (tadi sudah ditandai terpakai)
            for action in quick_action_defs:
                if action["prompt"] == pending_prompt:
                    st.session_state.used_actions.discard(action["key"])
        user_question = None
    else:
        st.session_state.last_message_ts = now
        st.session_state.messages.append({"role": "user", "content": user_question})
        # Popup bantuan cepat yang masih terbuka ditutup begitu pesan diterima, supaya
        # tidak ada tombol yang bisa diklik (dan memutus jawaban) selama jawaban dibuat.
        st.session_state.qa_open = False


# ---------------------------------------------------------------------------
# 2. State marker + CSS + script layout
# ---------------------------------------------------------------------------
is_empty = len(st.session_state.messages) == 0

# Penanda tema (.sapa-theme-light / -dark / -system) ikut di elemen yang sama dengan penanda
# status agar tidak menambah elemen baru; theme.py membacanya lewat :has().
_theme_cls = f"sapa-theme-{st.session_state.theme}"
st.markdown(
    ('<div class="sapa-empty"></div>' if is_empty else '<div class="sapa-chat-active"></div>')
    + f'<div class="{_theme_cls}"></div>',
    unsafe_allow_html=True,
)
st.markdown(get_custom_css(), unsafe_allow_html=True)
render_cooldown_sync()

# Menyesuaikan posisi input bar dengan keyboard virtual (tidak ada tampilan)
components.html(get_layout_script(), height=0)


# ---------------------------------------------------------------------------
# 3. Hero (chat kosong) / top bar (chat berjalan)
# ---------------------------------------------------------------------------
if is_empty:
    st.markdown(
        f'''
        <section class="sapa-hero">
            <h1 class="sapa-title"><img class="sapa-wordmark" src="{_SAPA_WORDMARK}" alt="SAPA — Teman Magang"></h1>
            <div class="sapa-tagline">Teman Magang, Siap Membantu.</div>
            <p class="sapa-desc">
                Sistem Asisten Pendamping Aktivitas untuk membantu edukasi,
                akuisisi, pendaftaran, dan follow-up peserta BPU.
            </p>
        </section>
        ''',
        unsafe_allow_html=True,
    )
    # Belum ada topbar di layar awal: tombol tema melayang di pojok kanan atas (CSS: .st-key-theme_corner)
    with st.container(key="theme_corner"):
        render_theme_toggle()
else:
    with st.container(key="topbar"):
        st.markdown(
            f'''
            <div class="sapa-chat-header">
                <img class="sapa-chat-brand" src="{_SAPA_WORDMARK}" alt="SAPA">
                <span class="sapa-chat-separator">•</span>
                <span class="sapa-chat-tagline">Teman Magang, Siap Membantu.</span>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        render_theme_toggle()
        st.button(
            "+ Baru",
            key="new_chat",
            help="Mulai percakapan baru",
        )   # dibuka oleh JS (tanpa rerun): lihat dialog di bawah


# ---------------------------------------------------------------------------
# 3b. Dialog konfirmasi "+ Baru" — mencegah misclick menghapus riwayat chat.
#     Backdrop (klik di luar = batal) + panel mengambang di tengah layar,
#     dengan animasi masuk yang halus (lihat theme.py: sapa-modal-in).
# ---------------------------------------------------------------------------
# Dialog SELALU dirender saat chat berjalan, tetapi tersembunyi lewat CSS; JS yang menampilkannya
# (html.sapa-confirm-open) -> muncul seketika. "Batal" & backdrop ditutup oleh JS tanpa rerun.
if not is_empty:
    with st.container(key="confirm_backdrop"):
        st.button("Tutup", key="confirm_dismiss")

    with st.container(key="confirm_dialog"):
        st.markdown(
            '''
            <div class="sapa-confirm-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8"/>
                    <path d="M21 3v5h-5"/>
                    <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16"/>
                    <path d="M3 21v-5h5"/>
                </svg>
            </div>
            <div class="sapa-confirm-title">Mulai obrolan baru?</div>
            <p class="sapa-confirm-desc">
                Riwayat percakapan ini akan dihapus dan tidak bisa dikembalikan.
            </p>
            ''',
            unsafe_allow_html=True,
        )
        col_cancel, col_ok = st.columns(2, gap="small")
        with col_cancel:
            st.button(
                "Batal",
                key="confirm_cancel",
                use_container_width=True,
            )
        with col_ok:
            st.button(
                "Ya, mulai baru",
                key="confirm_ok",
                type="primary",
                use_container_width=True,
                on_click=confirm_new_chat_action,
            )


# ---------------------------------------------------------------------------
# 4. Bantuan cepat (disable kalau sudah pernah diklik)
#    Chat kosong    : daftar terbuka, rata kiri (desktop: di bawah input,
#                     mobile: tepat di atas input)
#    Chat berjalan  : hanya tombol "Bantuan cepat" di atas input; daftarnya
#                     muncul sebagai popup saat tombol diklik. Popup menutup
#                     kalau: tombol diklik lagi, klik di luar popup, Esc, atau
#                     salah satu bantuan dipilih.
#    Popup SELALU dirender (tersembunyi lewat CSS) dan dibuka/ditutup oleh JS di
#    sisi klien (theme.py) -> instan, tanpa rerun Streamlit.
# ---------------------------------------------------------------------------
with st.container(key="qa_zone"):
    if is_empty:
        render_quick_action_buttons()
    else:
        st.button(
            "Bantuan cepat",
            icon=":material/bolt:",
            key="qa_toggle",
        )
        st.button("Tutup", key="qa_backdrop")   # area tap-untuk-menutup, ditangani JS
        render_quick_action_buttons()


# ---------------------------------------------------------------------------
# 5. Riwayat chat
# ---------------------------------------------------------------------------
for index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            render_user_message(message["content"])
        else:
            st.markdown(md_safe(message["content"]))
            render_copy_button(str(message["content"]), f"history-{index}")
            src = st.session_state.sources_map.get(index)
            if src:
                render_sources(src)


# Peringatan rate limit tampil tepat di bawah pesan terakhir (posisi tempat jawaban akan muncul).
if rate_limit_wait > 0:
    render_rate_limit_warning(rate_limit_wait)


# ---------------------------------------------------------------------------
# 6. Jawaban baru — loading state: waveform + label bergeser warna cyan->hijau
#    di area konten, sama persis di desktop maupun mobile (avatar diam, tidak
#    ikut dianimasikan).
# ---------------------------------------------------------------------------
if user_question:
    conversation_history = st.session_state.messages[:-1]

    # Penanda tak terlihat "sedang membuat jawaban" untuk theme.py: selama ada, tombol
    # Bantuan cepat dikunci (CSS + JS). Alasannya: setiap klik widget Streamlit memicu
    # rerun, dan rerun MEMUTUS skrip yang sedang men-stream jawaban (jawaban batal).
    # Dihapus lagi di finally supaya tombol aktif kembali tanpa rerun tambahan.
    generating_flag = st.empty()
    generating_flag.markdown('<div class="sapa-generating"></div>', unsafe_allow_html=True)

    try:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown(
                '<div class="sapa-thinking" role="status" aria-label="SAPA sedang menyusun jawaban">'
                '<span class="sapa-thinking-wave">'
                '<span></span><span></span><span></span><span></span><span></span>'
                '</span>'
                '<span class="sapa-thinking-label">Menyusun jawaban</span>'
                '</div>',
                unsafe_allow_html=True,
            )

            # Retrieval + prompt dijalankan di sini; waveform tetap tampil.
            stream = ask_stream(
                user_question,
                retriever,
                llm,
                history=conversation_history,
            )
            sources = stream.sources

            # Tunggu token pertama dulu (waveform tetap terlihat selama LLM "berpikir"),
            # baru ganti dengan teks yang mengalir ala mesin tik.
            deltas = iter(stream)
            first = next(deltas, None)
            if first is not None:
                with placeholder.container():
                    st.write_stream(typewriter(itertools.chain([first], deltas)))

            # Jawaban final (sanitasi penuh) yang disimpan ke riwayat. Layar hanya
            # dirender ulang bila berbeda dari yang sudah tampil (sangat jarang) atau kosong.
            answer = stream.text
            if first is None or stream.emitted != answer:
                placeholder.markdown(md_safe(answer))
            render_copy_button(str(answer), "latest")
            render_sources(sources)
    finally:
        generating_flag.empty()

    st.session_state.messages.append({"role": "assistant", "content": str(answer)})
    st.session_state.sources_map[len(st.session_state.messages) - 1] = sources