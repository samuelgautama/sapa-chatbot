"""
theme.py — SAPA
Layout ala Gemini / ChatGPT / DeepSeek (tanpa sidebar):

  • Area chat terpusat dengan lebar maksimal (--content-w).
  • Kolom input fixed di bawah-tengah layar dan naik mengikuti keyboard virtual
    di mobile (lewat visualViewport API, lihat get_layout_script()).
  • Desktop, percakapan masih kosong : sapaan di atas, input di tengah layar,
                                       bantuan cepat di bawah input.
  • Desktop, percakapan berjalan     : input turun ke bawah (animasi halus),
                                       bantuan cepat diringkas jadi tombol "Bantuan cepat"
                                       di atas input yang membuka popup.
  • Mobile & desktop                 : avatar AI dihapus di SEMUA ukuran layar, jawaban
                                       rata kiri selebar konten (pembeda peran cukup dari
                                       bubble pengguna di kanan).

Variabel CSS yang diisi JS (semua punya fallback, jadi CSS tetap jalan tanpa JS):
  --kb        tinggi keyboard virtual (px)
  --bottom-h  tinggi kolom input (px)
  --main-l    jarak kiri area utama dari tepi layar (px)
  --main-r    jarak kanan area utama dari tepi layar (px, sudah menghitung scrollbar)

Loading state ("SAPA sedang menyusun jawaban") tidak lagi memakai 3 titik statis,
melainkan waveform 5-garis tipis (class .sapa-thinking, lihat app.py) + label putih
polos (tanpa shimmer/animasi warna) supaya lebih clean. Tampilannya SAMA di semua
ukuran layar. Tinggi & jeda tiap garis waveform sengaja dibuat berbeda-beda supaya
gerakannya terkesan acak ("merangkai data").
"""

from __future__ import annotations

import json


def _row(key: str) -> str:
    """
    Selector "baris" untuk st.container(key=...).
    Streamlit versi baru membungkus container ber-key dalam stLayoutWrapper,
    versi lama tidak — selector ini menangkap keduanya.
    """
    return (
        f':is(.st-key-{key}:not(:has(> [data-testid="stVerticalBlock"])), '
        f'.st-key-{key} > [data-testid="stVerticalBlock"])'
    )


_QA_ROW = _row('quick_actions')
_TB_ROW = _row('topbar')
_CONFIRM_ROW = _row('confirm_dialog')

_CSS = r'''<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

/* ================================================================
   TOKENS
   ================================================================ */
:root {
    color-scheme: dark;
    --font: "Plus Jakarta Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;

    --bg: #07080C;
    --bg-rgb: 7,8,12;
    --text: #F1F3F7;
    --text-2: #A9B0BD;
    --text-3: #838B99;
    --line: rgba(255,255,255,.08);
    --line-2: rgba(255,255,255,.14);
    --surface-hover: rgba(255,255,255,.09);
    --accent: #A5B4FC;
    --inset: inset 0 1px 0 rgba(255,255,255,.06);

    /* Brand mark (logo_sapa.svg, di-inline sebagai data-URI supaya tanpa request
       jaringan tambahan) + palet resminya, dipakai ulang di avatar & loading state. */
    --brand-cyan: #009FDF;
    --brand-green: #39A849;
    --sapa-logo: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGcgY2xpcC1wYXRoPSJ1cmwoI2NsaXAwXzE2XzkpIj4KPHBhdGggZD0iTTIwIDBDMjYuNjI3NCAwIDMyIDUuMzcyNTggMzIgMTJWMjBDMzIgMjYuNjI3NCAyNi42Mjc0IDMyIDIwIDMySDBWMTJDMCA1LjM3MjU4IDUuMzcyNTggMCAxMiAwSDIwWk0xMyAzQzcuNDc3MTUgMyAzIDcuNDc3MTUgMyAxM1YyOUgxOUMyNC41MjI4IDI5IDI5IDI0LjUyMjggMjkgMTlWMTNDMjkgNy40NzcxNSAyNC41MjI4IDMgMTkgM0gxM1oiIGZpbGw9InVybCgjcGFpbnQwX2xpbmVhcl8xNl85KSIvPgo8cGF0aCBkPSJNMjQgMTZDMjQgMTcuMDg5NSAyMy43Nzc1IDE4LjE2NzYgMjMuMzQ2IDE5LjE2ODFDMjIuOTE0NiAyMC4xNjg2IDIyLjI4MzMgMjEuMDcwNCAyMS40OTA5IDIxLjgxODJDMjAuMDA3NyAyMy4yMjIgMTguMDQyMiAyNC4wMDMgMTYgMjRDMTMuODc0OSAyNCAxMS45NDE4IDIzLjE3MDkgMTAuNTA5MSAyMS44MTgyQzkuNzE2NzEgMjEuMDcwNCA5LjA4NTQ0IDIwLjE2ODYgOC42NTM5OCAxOS4xNjgxQzguMjIyNTMgMTguMTY3NiA3Ljk5OTk4IDE3LjA4OTUgOCAxNkgyNFoiIGZpbGw9InVybCgjcGFpbnQxX2xpbmVhcl8xNl85KSIvPgo8L2c+CjxkZWZzPgo8bGluZWFyR3JhZGllbnQgaWQ9InBhaW50MF9saW5lYXJfMTZfOSIgeDE9IjE2LjQ3MDYiIHkxPSIxNi40NzA2IiB4Mj0iMTYuNDcwNiIgeTI9IjI0LjIzNTMiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KPHN0b3Agc3RvcC1jb2xvcj0iIzAwOUZERiIvPgo8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiMzOUE4NDkiLz4KPC9saW5lYXJHcmFkaWVudD4KPGxpbmVhckdyYWRpZW50IGlkPSJwYWludDFfbGluZWFyXzE2XzkiIHgxPSIxNi45OTA5IiB5MT0iMTUuMjAxOSIgeDI9IjE2Ljk5MDkiIHkyPSIyMy4yMDE5IiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CjxzdG9wIHN0b3AtY29sb3I9IiMwMDlGREYiLz4KPHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjMzlBODQ5Ii8+CjwvbGluZWFyR3JhZGllbnQ+CjxjbGlwUGF0aCBpZD0iY2xpcDBfMTZfOSI+CjxyZWN0IHdpZHRoPSIzMiIgaGVpZ2h0PSIzMiIgZmlsbD0id2hpdGUiLz4KPC9jbGlwUGF0aD4KPC9kZWZzPgo8L3N2Zz4K");

    /* Layout */
    --content-w: 768px;          /* lebar maksimal area chat & input */
    --gutter: 24px;
    --topbar-h: 52px;

    /* Pesan */
    --avatar: 30px;
    --msg-gap: 24px;
    --msg-inner-gap: 12px;

    /* Kolom input */
    --ta-h: 52px;
    --ta-lh: 24px;
    --btn: 38px;
    --bar-pt: 8px;
    --bar-pb: 20px;

    /* Strip quick action (mode chat aktif) */
    --pills-h: 36px;
    --pills-gap: 8px;

    --ease: cubic-bezier(.22,.68,0,1);
    --safe-top: env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --safe-left: env(safe-area-inset-left, 0px);
    --safe-right: env(safe-area-inset-right, 0px);
}

.stApp {
    /* Tinggi kolom input: diukur JS, fallback perkiraan */
    --bar-h: var(--bottom-h, calc(var(--bar-pt) + var(--ta-h) + 2px + var(--bar-pb) + var(--safe-bottom)));
    --pills-zone: 0px;
    --top-zone: 0px;
}
.stApp:has(.sapa-chat-active) {
    --pills-zone: calc(var(--pills-h) + var(--pills-gap));
    --top-zone: calc(var(--safe-top) + var(--topbar-h));
}

/* ================================================================
   GLOBAL
   ================================================================ */
html, body {
    background: var(--bg) !important;
    overscroll-behavior: none;
    -webkit-text-size-adjust: 100%;
}

.stApp {
    height: 100vh; height: 100dvh;
    position: relative;
    color: var(--text) !important;
    font-family: var(--font) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background:
        radial-gradient(1200px 1000px at 50% 100%, rgba(30,20,55,.55), transparent 62%),
        linear-gradient(180deg, #0C0E16 0%, #08090D 55%, #050508 100%) !important;
    background-attachment: fixed !important;
    animation: sapa-app-in .5s var(--ease) both;
    isolation: isolate;
}
/* Lapisan "aurora": beberapa gumpalan warna besar & buram yang bergerak pelan,
   di belakang seluruh konten (z-index -1), untuk kesan latar yang lebih hidup
   dan modern dibanding gradient statis. Dihormati oleh prefers-reduced-motion
   lewat aturan animation-duration global di bagian bawah file ini. */
.stApp::before {
    content: ""; position: fixed; inset: -12%; z-index: -2; pointer-events: none;
    background:
        radial-gradient(32% 26% at 14% 10%, rgba(99,102,241,.40), transparent 72%),
        radial-gradient(30% 24% at 88% 6%, rgba(56,189,248,.28), transparent 72%),
        radial-gradient(40% 32% at 22% 92%, rgba(168,85,247,.26), transparent 72%),
        radial-gradient(34% 28% at 82% 96%, rgba(236,72,153,.14), transparent 74%);
    filter: blur(90px) saturate(150%);
    animation: sapa-aurora-drift 34s var(--ease) infinite alternate;
    will-change: transform;
}
/* Vinyet halus + grain tipis di atas aurora supaya tepi layar sedikit meredup
   dan latar tidak terasa "flat" — masih di belakang seluruh konten (z-index -1). */
.stApp::after {
    content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
    background:
        radial-gradient(120% 90% at 50% 38%, transparent 55%, rgba(0,0,0,.42) 100%),
        repeating-linear-gradient(0deg, rgba(255,255,255,.015) 0px, transparent 1px, transparent 3px);
    mix-blend-mode: soft-light;
}
@keyframes sapa-aurora-drift {
    0%   { transform: translate3d(0, 0, 0) scale(1); }
    50%  { transform: translate3d(-2.5%, 2%, 0) scale(1.06); }
    100% { transform: translate3d(2.5%, -1.5%, 0) scale(1); }
}
@keyframes sapa-app-in { from { opacity: 0 } to { opacity: 1 } }
@keyframes sapa-fade-up {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes sapa-fade-in { from { opacity: 0 } to { opacity: 1 } }

[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stAppScrollToBottomContainer"] { background: transparent !important; }

/* Sembunyikan chrome Streamlit — sidebar dihapus total */
#MainMenu, footer, header,
[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] { display: none !important; }

/* Badge "Manage app" Streamlit Community Cloud (ikon merah pojok kanan bawah,
   dengan link status "running"/jumlah viewer) — ini elemen yang disuntikkan
   Streamlit SENDIRI ke halaman utama, bukan bagian dari script app.py kita,
   jadi tidak bisa dihapus lewat Python — hanya bisa disembunyikan via CSS
   seperti ini. Class CSS-nya pakai hash acak yang berubah tiap rilis Streamlit
   (mis. "viewerBadge_container__xxxxx"), jadi dicocokkan via "berawalan" supaya
   tidak putus saat Streamlit update versi, plus cadangan lewat href-nya yang
   selalu mengarah ke streamlit.io. Badge ini hanya muncul di app yang di-host
   di Community Cloud (streamlit.app) — tidak akan kelihatan efeknya saat
   dijalankan lokal, baru terlihat setelah di-deploy ulang. */
[class*="viewerBadge_container"],
[class*="viewerBadge_link"],
a[href*="streamlit.io/cloud"],
a[href^="https://share.streamlit.io"] { display: none !important; }

.stApp [data-stale="true"] { opacity: 1 !important; transition: none !important; }

* { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,.12) transparent; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,.12); border-radius: 999px; }
::-webkit-scrollbar-track { background: transparent; }

.stApp p, .stApp li, .stApp label, .stApp button, .stApp textarea, .stApp input,
.stApp summary, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp td, .stApp th,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stText"] {
    font-family: var(--font) !important;
}
.stApp button { -webkit-tap-highlight-color: transparent; touch-action: manipulation; }

/* ================================================================
   AREA UTAMA — chat terpusat, lebar maksimal
   ================================================================ */
[data-testid="stMainBlockContainer"] {
    width: 100% !important;
    max-width: var(--content-w) !important;
    margin: 0 auto !important;
    box-sizing: border-box !important;
    padding-top: calc(var(--top-zone) + 12px) !important;
    padding-left: max(var(--gutter), var(--safe-left)) !important;
    padding-right: max(var(--gutter), var(--safe-right)) !important;
    /* ruang untuk kolom input (+ strip quick action) yang fixed di bawah.
       + --kb: saat keyboard terbuka container scroll tetap setinggi layar penuh,
       jadi tanpa ini pesan terakhir terhalang keyboard */
    padding-bottom: calc(var(--bar-h) + var(--pills-zone) + 28px + var(--kb, 0px)) !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stElementContainer"]:has(.sapa-empty),
[data-testid="stElementContainer"]:has(.sapa-chat-active) { display: none !important; }

/* Kondisi kosong (default & mobile): sapaan + bantuan cepat di tengah vertikal,
   input tetap di bawah. Desktop punya tata letak sendiri (lihat media query DESKTOP). */
.stApp:has(.sapa-empty) [data-testid="stMainBlockContainer"] {
    min-height: 100vh; min-height: 100dvh;
    display: flex !important; flex-direction: column; justify-content: center;
    padding-top: calc(var(--safe-top) + 28px) !important;
    padding-bottom: calc(var(--bar-h) + 24px + var(--kb, 0px)) !important;
}
.stApp:has(.sapa-empty) [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
    flex: 0 0 auto; width: 100%;
}

/* Sebelum status (kosong / aktif) diketahui, input disembunyikan agar tidak "melompat" */
.stApp:not(:has(.sapa-empty)):not(:has(.sapa-chat-active)) [data-testid="stBottom"] { opacity: 0; }

/* ================================================================
   TOP BAR (mode chat aktif) — merek di kiri, tombol "Baru" di kanan
   ================================================================ */
.st-key-topbar {
    position: fixed !important; top: 0 !important;
    left: var(--main-l, 0px) !important; right: var(--main-r, 0px) !important;
    z-index: 60 !important;
    margin: 0 !important; padding: 0 !important;
}
.st-key-topbar::before {
    content: ""; position: absolute; z-index: -1; pointer-events: none;
    left: 0; right: 0; top: 0;
    height: calc(var(--safe-top) + var(--topbar-h) + 18px);
    background: linear-gradient(180deg,
        rgba(var(--bg-rgb), .96) 0%,
        rgba(var(--bg-rgb), .90) 62%,
        rgba(var(--bg-rgb), 0) 100%);
}
__TB_ROW__ {
    display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
    align-items: center !important; justify-content: space-between !important;
    gap: 12px !important;
    width: 100% !important; max-width: var(--content-w) !important;
    height: var(--topbar-h) !important; box-sizing: border-box !important;
    margin: var(--safe-top) auto 0 !important;
    padding: 0 max(var(--gutter), var(--safe-right)) 0 max(var(--gutter), var(--safe-left)) !important;
}
.st-key-topbar [data-testid="stElementContainer"] {
    margin: 0 !important; padding: 0 !important; width: auto !important; min-width: 0 !important;
    align-self: center !important;
}
.st-key-topbar [data-testid="stElementContainer"]:has(.sapa-chat-header) { flex: 1 1 auto; }
.st-key-topbar [data-testid="stElementContainer"]:has([data-testid="stButton"]) { flex: 0 0 auto; }
.st-key-topbar [data-testid="stButton"] { align-self: center !important; }

.sapa-chat-header {
    display: flex; align-items: center; gap: 8px; min-width: 0;
    height: 34px; box-sizing: border-box;
    color: var(--text-3); font-size: 12.5px; white-space: nowrap;
}
.sapa-chat-brand {
    display: block; flex: none; height: 18px; width: auto;
    aspect-ratio: 125 / 38;
}
/* Sama persis dengan mekanisme perataan tombol "+ Baru" di sebelahnya
   (flex + height:100% + line-height:1) supaya keduanya pasti sejajar — line-height
   browser default ("normal", biasanya ~1.2-1.4x font-size) bisa membuat kotak teks
   tagline sedikit lebih tinggi dari kotak teks tombol walau tinggi kontainernya
   sama, sehingga pusat optiknya bergeser 1-2px. Dengan line-height:1 di kedua sisi,
   tidak ada lagi selisih yang bisa disebabkan oleh itu. */
.sapa-chat-separator,
.sapa-chat-tagline {
    display: inline-flex; align-items: center; height: 100%;
    line-height: 1;
}
.sapa-chat-separator { color: var(--text-3); flex: none; }
.sapa-chat-tagline { color: var(--text-3); overflow: hidden; text-overflow: ellipsis; }

.st-key-new_chat, .st-key-new_chat [data-testid="stButton"] { width: auto !important; margin: 0 !important; }
.st-key-new_chat button {
    height: 34px !important; min-height: 34px !important; box-sizing: border-box !important;
    padding: 0 14px !important; border-radius: 999px !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    border: 1px solid var(--line) !important;
    background: rgba(255,255,255,.05) !important;
    color: var(--text-2) !important;
    box-shadow: var(--inset) !important;
    transition: background .2s var(--ease), border-color .2s var(--ease),
                color .2s var(--ease), transform .2s var(--ease);
}
.st-key-new_chat button:hover {
    background: var(--surface-hover) !important;
    border-color: var(--line-2) !important; color: #fff !important;
}
.st-key-new_chat button:active { transform: scale(.97); }
.st-key-new_chat button [data-testid="stMarkdownContainer"] {
    display: flex !important; align-items: center !important; height: 100%;
}
.st-key-new_chat button p {
    margin: 0 !important; font-size: 13px !important; font-weight: 600 !important;
    color: inherit !important; white-space: nowrap !important; line-height: 1 !important;
}

/* ================================================================
   HERO
   ================================================================ */
.sapa-hero {
    width: 100%; max-width: 680px; margin: 0 auto;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center; padding: 0 8px;
}
.sapa-title {
    margin: 0; line-height: 1.05;
    animation: sapa-fade-up .55s var(--ease) both;
}
/* Wordmark (ikon + teks "SAPA" dengan gradient bawaan di SVG-nya sendiri).
   Lebar mengikuti tinggi lewat aspect-ratio supaya tidak pernah gepeng/molor,
   dan tingginya responsif lewat clamp() — sama persis rentangnya dengan
   font-size judul teks yang digantikannya, supaya skalanya terasa senada
   di semua lebar layar. */
.sapa-wordmark {
    display: block; height: clamp(2.3rem, 9vw, 4rem); width: auto;
    aspect-ratio: 125 / 38;
}
.sapa-tagline {
    margin-top: 18px; font-size: clamp(.95rem, 2.4vw, 1.05rem);
    font-weight: 500; color: var(--text-2);
    animation: sapa-fade-up .5s var(--ease) .08s both;
}
.sapa-desc {
    width: 100%; max-width: 480px; margin: 10px auto 0;
    font-size: clamp(.8rem, 2vw, .9rem); line-height: 1.6; color: var(--text-3);
    animation: sapa-fade-up .5s var(--ease) .14s both;
}
/* Jarak aman minimum ke apa pun di bawahnya (daftar bantuan cepat atau langsung
   kolom input) — supaya hero TIDAK PERNAH terasa mepet, apapun tinggi jendelanya
   (termasuk jendela desktop pendek yang tidak kena breakpoint khusus di bawah). */
.sapa-hero { margin-bottom: clamp(28px, 6vh, 56px); }

/* ================================================================
   QUICK ACTIONS
   Satu gaya daftar (ikon + teks, RATA KIRI) dipakai di dua tempat:
     - chat kosong    : daftar terbuka di bawah input (desktop) / di atas input (mobile)
     - chat berjalan  : popup yang dibuka lewat tombol "Bantuan cepat" di atas input
   ================================================================ */
.st-key-qa_zone { width: 100%; margin: 0 !important; padding: 0 !important; }
.st-key-quick_actions { width: 100%; margin: 0 !important; padding: 0 !important; }
.st-key-quick_actions:has(> [data-testid="stVerticalBlock"]) { display: block !important; }
__QA_ROW__ {
    display: flex !important; flex-direction: column !important;
    gap: 4px !important;
    width: 100% !important; max-width: none !important;
    margin: 0 !important; padding: 0 !important;
}
.st-key-quick_actions [data-testid="stElementContainer"],
.st-key-quick_actions [data-testid="stButton"] {
    width: 100% !important; min-width: 0 !important;
    margin: 0 !important; padding: 0 !important;
}

/* Tombol = satu baris daftar. Streamlit membungkus isi tombol dalam beberapa lapis
   elemen yang secara bawaan MEMUSATKAN isinya, jadi rata kiri harus dipaksa di
   tombol dan di setiap pembungkus di dalamnya. */
.st-key-quick_actions button {
    position: relative !important;
    width: 100% !important; height: 48px !important; min-height: 48px !important;
    padding: 0 12px !important; border-radius: 10px !important;
    display: flex !important; align-items: center !important; justify-content: flex-start !important;
    gap: 14px !important; white-space: nowrap !important; text-align: left !important;
    border: 0 !important; background: transparent !important;
    color: var(--text) !important; box-shadow: none !important;
    transition: background .2s var(--ease), transform .2s var(--ease);
}
.st-key-quick_actions button > div,
.st-key-quick_actions button > span,
.st-key-quick_actions button [data-has-shortcut] {
    display: flex !important; align-items: center !important; justify-content: flex-start !important;
    gap: 14px !important; width: 100% !important; min-width: 0 !important;
    margin: 0 !important; padding: 0 !important; text-align: left !important;
}
.st-key-quick_actions button::after { display: none !important; content: none !important; }
/* line-height longgar + padding vertikal pada <p>: overflow meng-clip di batas padding,
   jadi bagian bawah huruf (g, p, y, j) tidak terpotong. */
.st-key-quick_actions button [data-testid="stMarkdownContainer"] {
    flex: 0 1 auto !important; min-width: 0 !important; max-width: 100% !important;
    margin: 0 !important; text-align: left !important;
    line-height: 1.5 !important; overflow: visible !important;
}
.st-key-quick_actions button p {
    margin: 0 !important; padding: 3px 0 !important;
    font-size: 15px !important; font-weight: 450 !important; line-height: 1.5 !important;
    color: var(--text-2) !important; text-align: left !important;
    white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
}
/* Ikon material bawaan Streamlit dibuat monokrom, sedikit lebih terang saat hover */
.st-key-quick_actions button [data-testid="stIconMaterial"] {
    color: var(--text-3) !important; font-size: 19px !important; flex: none;
    transition: color .2s var(--ease);
}
.st-key-quick_actions button:hover:not(:disabled) { background: rgba(255,255,255,.05) !important; }
.st-key-quick_actions button:hover:not(:disabled) p,
.st-key-quick_actions button:hover:not(:disabled) [data-testid="stIconMaterial"] {
    color: var(--text) !important;
}
.st-key-quick_actions button:active:not(:disabled) { transform: scale(.99); }
.st-key-quick_actions button:disabled,
.st-key-quick_actions button[disabled] {
    opacity: 1 !important; cursor: default !important;
    background: transparent !important; transform: none !important;
}
.st-key-quick_actions button:disabled p,
.st-key-quick_actions button[disabled] p { color: rgba(226,229,235,.38) !important; }
.st-key-quick_actions button:disabled [data-testid="stIconMaterial"],
.st-key-quick_actions button[disabled] [data-testid="stIconMaterial"] { opacity: .5 !important; }

/* ---------- Chat kosong: daftar selebar kolom input, rata dengan tepi kirinya ---------- */
.stApp:has(.sapa-empty) .st-key-quick_actions {
    max-width: calc(var(--content-w) - 2 * var(--gutter)) !important;
    margin: 0 auto !important;
}
.stApp:has(.sapa-empty) .st-key-quick_actions button { padding: 0 18px !important; }

/* ---------- Chat berjalan: tombol "Bantuan cepat" + popup ----------
   Tombol, popup, dan lapisan klik-di-luar masing-masing position: fixed dengan posisi
   dihitung dari variabel CSS (bukan bergantung pada pembungkus Streamlit, yang
   berbeda antar versi). --col-l = tepi kiri kolom chat/input.
     tombol popup   -> tepat di atas kolom input
     popup          -> melayang di atas tombol, kaca buram + bayangan dalam
     backdrop       -> meredupkan & mengaburkan layar di belakangnya (DI BAWAH
                       kolom input, z 89 < 90) supaya popup terasa seperti lapisan
                       sungguhan di atas konten, bukan sekadar daftar yang nongol;
                       transparan untuk klik: tap di mana pun di luar popup menutupnya
   Catatan teknis: Streamlit merender ulang saat popup ditutup (elemen langsung lenyap
   dari DOM), jadi tidak ada cara murni CSS untuk MENGANIMASIKAN penutupannya — animasi
   di bawah ini fokus membuat saat popup MUNCUL terasa mulus & premium (kaca buram
   mengembang lembut + setiap baris bantuan muncul bertahap/cascade), sama persis di
   desktop maupun mobile karena tidak ada media query di sini. */
@keyframes sapa-backdrop-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes sapa-pop-in {
    from { opacity: 0; transform: translateY(16px) scale(.93); filter: blur(4px); }
    55%  { filter: blur(0); }
    to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}
@keyframes sapa-row-in {
    from { opacity: 0; transform: translateY(7px); }
    to   { opacity: 1; transform: translateY(0); }
}
.stApp:has(.sapa-chat-active) {
    --col-l: calc(var(--main-l, 0px)
                  + max(var(--gutter), var(--safe-left))
                  + max(0px, (100vw - var(--main-l, 0px) - var(--main-r, 0px) - var(--content-w)) / 2));
    --above-bar: calc(var(--kb, 0px) + var(--bar-h));
}
/* Wadah hanya penampung: tidak punya kotak sendiri, semua anaknya fixed */
.stApp:has(.sapa-chat-active) .st-key-qa_zone {
    position: static !important; height: 0 !important; min-height: 0 !important;
    margin: 0 !important; padding: 0 !important; gap: 0 !important;
    overflow: visible !important;
}

.st-key-qa_toggle {
    position: fixed !important; z-index: 95 !important;
    left: var(--col-l) !important; right: auto !important;
    bottom: var(--above-bar) !important; top: auto !important;
    width: auto !important; height: var(--pills-h) !important;
    margin: 0 !important; padding: 0 !important;
    animation: sapa-fade-in .4s var(--ease) both;
}
.st-key-qa_toggle [data-testid="stButton"] { width: auto !important; margin: 0 !important; }
.st-key-qa_toggle button {
    height: var(--pills-h) !important; min-height: var(--pills-h) !important;
    padding: 0 14px 0 12px !important; border-radius: 999px !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    gap: 6px !important; white-space: nowrap !important;
    border: 1px solid var(--line) !important;
    background: rgba(30,32,40,.72) !important;
    color: var(--text) !important; box-shadow: var(--inset) !important;
    transition: background .2s var(--ease), border-color .2s var(--ease),
                border-radius .22s var(--ease), transform .2s var(--ease), box-shadow .2s var(--ease);
}
.st-key-qa_toggle button:hover {
    background: var(--surface-hover) !important; border-color: var(--line-2) !important;
    box-shadow: var(--inset), 0 4px 14px rgba(0,0,0,.20) !important;
}
.st-key-qa_toggle button:active { transform: scale(.97); }
.st-key-qa_toggle button p {
    margin: 0 !important; padding: 3px 0 !important;
    font-size: 12.5px !important; font-weight: 600 !important; line-height: 1.5 !important;
    color: var(--text) !important; white-space: nowrap !important;
}
.st-key-qa_toggle button [data-testid="stIconMaterial"] {
    color: var(--accent) !important; font-size: 17px !important;
    display: inline-block !important;
    transition: transform .3s var(--ease), color .2s var(--ease);
}
/* Popup terbuka: tombol diberi aksen + sudut kiri-bawah "menyatu" dengan sudut
   kiri-bawah panel di atasnya (radius sama-sama diperkecil), dan ikon petir berputar
   halus — detail kecil yang membuat tombol & panel terasa satu potongan, bukan dua
   elemen lepas yang kebetulan bertumpuk. */
.stApp:has(.st-key-qa_backdrop) .st-key-qa_toggle button {
    background: rgba(165,180,252,.16) !important;
    border-color: rgba(165,180,252,.5) !important;
    border-bottom-left-radius: 7px !important;
}
.stApp:has(.st-key-qa_backdrop) .st-key-qa_toggle button [data-testid="stIconMaterial"] {
    transform: rotate(18deg); color: #fff !important;
}

/* Backdrop: meredupkan + mengaburkan latar di belakang popup supaya panel terasa
   melayang sebagai lapisan sendiri (efek "sheet" ala aplikasi native), sekaligus
   jadi area tap-untuk-menutup. Ada di BAWAH kolom input (z89 < 90) supaya input
   tetap terang & tetap bisa dipakai langsung meski popup sedang terbuka. */
.st-key-qa_backdrop {
    position: fixed !important; inset: 0 !important; z-index: 89 !important;
    width: 100vw !important; height: 100vh !important; height: 100dvh !important;
    margin: 0 !important; padding: 0 !important;
    background: rgba(4,5,9,.50) !important;
    backdrop-filter: blur(3px) saturate(115%) !important;
    -webkit-backdrop-filter: blur(3px) saturate(115%) !important;
    animation: sapa-backdrop-in .3s var(--ease) both;
}
.st-key-qa_backdrop [data-testid="stButton"],
.st-key-qa_backdrop button {
    width: 100% !important; height: 100% !important; min-height: 0 !important;
    margin: 0 !important; padding: 0 !important;
    border: 0 !important; border-radius: 0 !important; box-shadow: none !important;
    background: transparent !important;
    color: transparent !important; font-size: 0 !important; cursor: default !important;
}
.st-key-qa_backdrop button p { display: none !important; }
/* Sama seperti dialog konfirmasi "+ Baru": paksa rantai height 100% sampai ke
   tombol, supaya seluruh area gelap benar-benar bisa diklik untuk menutup,
   bukan cuma tombol berukuran alami yang menyusut. */
.st-key-qa_backdrop,
.st-key-qa_backdrop > [data-testid="stVerticalBlock"],
.st-key-qa_backdrop [data-testid="stElementContainer"] {
    display: block !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important;
}
.st-key-qa_backdrop > [data-testid="stVerticalBlock"],
.st-key-qa_backdrop [data-testid="stElementContainer"] {
    width: 100% !important; height: 100% !important;
}

.stApp:has(.sapa-chat-active) .st-key-quick_actions {
    position: fixed !important; z-index: 96 !important;
    left: var(--col-l) !important; right: auto !important; top: auto !important;
    bottom: calc(var(--above-bar) + var(--pills-h) + 8px) !important;
    width: min(360px, calc(100vw - var(--col-l) - var(--main-r, 0px) - max(var(--gutter), var(--safe-right)))) !important;
    max-height: min(420px, calc(100vh - var(--top-zone) - var(--above-bar) - var(--pills-h) - 32px)) !important;
    overflow-y: auto !important; overflow-x: hidden !important; scrollbar-width: none;
    box-sizing: border-box !important; padding: 6px !important; margin: 0 !important;
    /* Kaca buram: latar tidak 100% opak + backdrop-filter, supaya sedikit warna di
       belakangnya tetap terasa (frosted glass), konsisten dengan nuansa aurora aplikasi */
    background: rgba(22,24,32,.86) !important;
    backdrop-filter: blur(22px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(160%) !important;
    border: 1px solid var(--line-2) !important;
    border-radius: 18px 18px 18px 7px !important;   /* sudut kiri-bawah menyatu dgn tombol toggle */
    box-shadow:
        0 24px 60px rgba(0,0,0,.5),
        0 2px 10px rgba(0,0,0,.3),
        0 -1px 0 rgba(165,180,252,.10) inset,
        var(--inset) !important;
    transform-origin: 0 100%;
    animation: sapa-pop-in .32s var(--ease) both;
}
.stApp:has(.sapa-chat-active) .st-key-quick_actions::-webkit-scrollbar { display: none; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions button { height: 44px !important; min-height: 44px !important; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions button p { font-size: 14px !important; }
/* Tiap baris bantuan muncul bertahap (cascade), bukan serentak — kesan lebih halus
   & "hidup" dibanding satu blok yang langsung nongol utuh. Jeda antar baris singkat
   (28ms) supaya total tetap terasa cepat walau daftarnya sampai 6-8 item. */
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"] {
    animation: sapa-row-in .3s var(--ease) both;
}
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(1) { animation-delay: .04s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(2) { animation-delay: .07s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(3) { animation-delay: .10s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(4) { animation-delay: .13s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(5) { animation-delay: .16s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(6) { animation-delay: .19s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(7) { animation-delay: .22s; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions [data-testid="stElementContainer"]:nth-child(8) { animation-delay: .25s; }
/* prefers-reduced-motion mematikan durasi animasi secara global di akhir file ini,
   jadi orang yang sensitif terhadap gerak tetap mendapat popup yang langsung utuh. */

/* Keyboard terbuka -> tombol & popup disembunyikan supaya area chat lega */
html.sapa-kb-open .stApp:has(.sapa-chat-active) .st-key-qa_zone { display: none !important; }
html.sapa-kb-open .stApp { --pills-zone: 0px; }

/* ================================================================
   DIALOG KONFIRMASI "+ Baru"
   Modal sungguhan di tengah layar (bukan anchored seperti popup bantuan
   cepat) — dipakai untuk mencegah misclick menghapus riwayat chat.
   z-index sengaja jauh lebih tinggi (200+) dari elemen lain di file ini
   (tertinggi sebelumnya 96) supaya selalu di paling atas, di skenario apa pun.
   ================================================================ */
@keyframes sapa-modal-in {
    from { opacity: 0; transform: translate(-50%, -50%) scale(.92) translateY(10px); filter: blur(6px); }
    60%  { filter: blur(0); }
    to   { opacity: 1; transform: translate(-50%, -50%) scale(1) translateY(0); filter: blur(0); }
}
@keyframes sapa-modal-icon-in {
    from { opacity: 0; transform: scale(.6) rotate(-25deg); }
    to   { opacity: 1; transform: scale(1) rotate(0deg); }
}

/* Backdrop: dim + blur latar, dan jadi area tap-untuk-batal. Transparan agar
   tetap terlihat aurora di belakangnya (senada dengan popup bantuan cepat). */
.st-key-confirm_backdrop {
    position: fixed !important; inset: 0 !important; z-index: 200 !important;
    width: 100vw !important; height: 100vh !important; height: 100dvh !important;
    margin: 0 !important; padding: 0 !important;
    background: rgba(4,5,9,.62) !important;
    backdrop-filter: blur(6px) saturate(115%) !important;
    -webkit-backdrop-filter: blur(6px) saturate(115%) !important;
    animation: sapa-backdrop-in .25s var(--ease) both;
}
.st-key-confirm_backdrop [data-testid="stButton"],
.st-key-confirm_backdrop button {
    width: 100% !important; height: 100% !important; min-height: 0 !important;
    margin: 0 !important; padding: 0 !important;
    border: 0 !important; border-radius: 0 !important; box-shadow: none !important;
    background: transparent !important;
    color: transparent !important; font-size: 0 !important; cursor: default !important;
}
.st-key-confirm_backdrop button p { display: none !important; }
/* Rantai tinggi 100%: kalau induk langsung tombol (stElementContainer, atau
   stVerticalBlock di versi Streamlit yang membungkusnya) tidak ikut diberi
   height:100%, maka height:100% pada tombol tidak resolve ke 100vh sungguhan
   — dia menyusut jadi tombol berukuran alami, dan klik di area gelap sekitarnya
   tidak kena apa-apa (cuma bagian kecil yang benar-benar bisa diklik). display:
   block dipaksa di sini supaya height% resolve dengan aturan block biasa,
   bukan bergantung pada flex-grow yang tidak kita set. */
.st-key-confirm_backdrop,
.st-key-confirm_backdrop > [data-testid="stVerticalBlock"],
.st-key-confirm_backdrop [data-testid="stElementContainer"] {
    display: block !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important;
}
.st-key-confirm_backdrop > [data-testid="stVerticalBlock"],
.st-key-confirm_backdrop [data-testid="stElementContainer"] {
    width: 100% !important; height: 100% !important;
}

/* Panel: melayang persis di tengah layar (bukan flex-centering supaya tidak
   perlu wrapper tambahan) — kaca buram senada dengan popup bantuan cepat,
   tapi simetris & sudut membulat penuh karena ini modal berdiri sendiri. */
.st-key-confirm_dialog {
    position: fixed !important; z-index: 201 !important;
    left: 50% !important; top: 50% !important; right: auto !important; bottom: auto !important;
    width: min(360px, calc(100vw - 32px)) !important;
    box-sizing: border-box !important; margin: 0 !important; padding: 22px 22px 18px !important;
    background: rgba(22,24,32,.92) !important;
    backdrop-filter: blur(26px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(26px) saturate(160%) !important;
    border: 1px solid var(--line-2) !important;
    border-radius: 20px !important;
    box-shadow:
        0 30px 70px rgba(0,0,0,.55),
        0 4px 16px rgba(0,0,0,.35),
        0 -1px 0 rgba(165,180,252,.10) inset,
        var(--inset) !important;
    transform-origin: center center;
    animation: sapa-modal-in .34s var(--ease) both;
}
__CONFIRM_ROW__ { gap: 0 !important; }
.sapa-confirm-icon {
    width: 44px; height: 44px; margin: 0 auto 14px; border-radius: 999px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(165,180,252,.14); color: var(--accent);
    animation: sapa-modal-icon-in .4s var(--ease) .05s both;
}
.sapa-confirm-title {
    text-align: center; color: var(--text); font-size: 16px; font-weight: 700;
    letter-spacing: -.01em; margin-bottom: 6px;
}
.sapa-confirm-desc {
    text-align: left; color: var(--text-2); font-size: 13.5px; line-height: 1.55;
    margin: 0 0 18px;
}
/* Dua tombol berdampingan: batal (ghost) & konfirmasi (terisi, aksen indigo) */
.st-key-confirm_dialog [data-testid="stHorizontalBlock"] { gap: 10px !important; }
.st-key-confirm_dialog [data-testid="stColumn"] { padding: 0 !important; min-width: 0 !important; }
.st-key-confirm_dialog [data-testid="stButton"] { width: 100% !important; margin: 0 !important; }
.st-key-confirm_dialog button {
    width: 100% !important; height: 42px !important; min-height: 42px !important;
    border-radius: 11px !important; padding: 0 12px !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    font-size: 13.5px !important; font-weight: 650 !important;
    transition: background .2s var(--ease), border-color .2s var(--ease),
                color .2s var(--ease), transform .2s var(--ease), filter .2s var(--ease);
}
.st-key-confirm_dialog button [data-testid="stMarkdownContainer"] {
    display: flex !important; align-items: center !important; justify-content: center !important;
    height: 100%; width: 100%;
}
.st-key-confirm_dialog button p { margin: 0 !important; line-height: 1 !important; }
.st-key-confirm_dialog button:active { transform: scale(.97); }
.st-key-confirm_dialog [data-testid="stBaseButton-secondary"] {
    border: 1px solid var(--line) !important;
    background: rgba(255,255,255,.04) !important;
    color: var(--text-2) !important; box-shadow: none !important;
}
.st-key-confirm_dialog [data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface-hover) !important; border-color: var(--line-2) !important; color: #fff !important;
}
.st-key-confirm_dialog [data-testid="stBaseButton-primary"] {
    border: 1px solid rgba(165,180,252,.55) !important;
    background: linear-gradient(180deg, #B7C2FD 0%, #97A6F7 100%) !important;
    color: #12131A !important; box-shadow: 0 6px 18px rgba(99,102,241,.28) !important;
}
.st-key-confirm_dialog [data-testid="stBaseButton-primary"]:hover { filter: brightness(1.06); }

@media (max-width: 480px) {
    .st-key-confirm_dialog { width: calc(100vw - 32px) !important; padding: 20px 18px 16px !important; }
}

/* ================================================================
   PESAN
   ================================================================ */
[data-testid="stChatMessage"] {

    display: flex !important; width: 100% !important;
    background: transparent !important; border: 0 !important;
    gap: var(--msg-inner-gap) !important; padding: 0 !important;
    margin: 0 0 var(--msg-gap) !important;
    align-items: flex-start !important;
    box-sizing: border-box;
    animation: sapa-fade-up .35s var(--ease) both;
}
[data-testid="stChatMessageAvatarUser"] { display: none !important; }

/* Avatar AI dihapus di SEMUA ukuran layar (desktop & mobile) — jawaban rata kiri
   selebar konten, pembeda peran cukup dari bubble pengguna di kanan. Loading state
   tetap punya identitas visual sendiri lewat waveform (.sapa-thinking-wave), jadi
   avatar tidak dibutuhkan di sana juga. */
[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    margin-top: 2px !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) > [data-testid="stChatMessageContent"] {
    width: 100% !important; padding-top: 0 !important;
}

[data-testid="stChatMessageContent"] {
    overflow-wrap: anywhere; min-width: 0;
}
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"],
[data-testid="stChatMessageContent"] [data-testid="stMarkdown"] {
    margin: 0 !important; padding: 0 !important;
    background: transparent !important; border: 0 !important;
}
[data-testid="stChatMessageContent"] p {
    margin: 0 0 .72em !important; color: var(--text) !important;
    font-size: .94rem !important; line-height: 1.7 !important;
}
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0 !important; }
[data-testid="stChatMessageContent"] strong { color: #fff !important; font-weight: 700 !important; }
[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol {
    margin: .2em 0 .8em !important; padding-left: 1.3em !important;
}
[data-testid="stChatMessageContent"] li {
    margin: .3em 0 !important; font-size: .94rem !important; line-height: 1.65 !important;
}
[data-testid="stChatMessageContent"] h1,
[data-testid="stChatMessageContent"] h2,
[data-testid="stChatMessageContent"] h3,
[data-testid="stChatMessageContent"] h4 {
    margin: .25em 0 .6em !important; color: #fff !important;
    font-size: 1.04rem !important; line-height: 1.3 !important; font-weight: 700 !important;
}
/* Tabel & kode lebar tidak boleh mendorong halaman melebar */
[data-testid="stChatMessageContent"] pre,
[data-testid="stChatMessageContent"] table {
    display: block; max-width: 100%; overflow-x: auto;
}

/* Bubble user — rata kanan */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    justify-content: flex-end !important;
    margin-top: 4px !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] {
    flex: 0 1 auto !important;
    width: fit-content !important; min-width: 0 !important;
    max-width: min(85%, 620px) !important;
    margin: 0 !important;
    padding: 11px 16px !important;
    border-radius: 20px !important;
    background: rgba(255,255,255,.11) !important;
    border: 1px solid rgba(255,255,255,.08) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.15) !important;
    box-sizing: border-box !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] > *,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] > * > * {
    margin: 0 !important; padding: 0 !important;
    min-width: 0 !important; max-width: 100% !important;
    background: transparent !important; border: 0 !important; box-shadow: none !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] p {
    margin: 0 !important; line-height: 1.55 !important; text-align: left !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] * {
    color: #F5F7FB !important;
}

/* Teks pengguna ditampilkan apa adanya (baris baru terjaga, tanpa parsing markdown) */
.sapa-user-text {
    margin: 0; white-space: pre-wrap; overflow-wrap: anywhere;
    font-size: .94rem; line-height: 1.55; text-align: left;
}
/* Jarak antar elemen dalam pesan dirapatkan (jawaban → tombol salin → sumber) */
[data-testid="stChatMessageContent"] [data-testid="stVerticalBlock"] { gap: 4px !important; }

/* Asisten — tanpa avatar, teks memenuhi seluruh lebar konten */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    justify-content: flex-start !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) > [data-testid="stChatMessageContent"] {
    flex: 1 1 0 !important; max-width: 100% !important;
    background: transparent !important; border: 0 !important; box-shadow: none !important;
}

/* ================================================================
   LOADING STATE — "SAPA sedang menyusun jawaban" (ganti 3 titik statis)
   ------------------------------------------------------------------
   .sapa-thinking : baris waveform + label yang menggantikan 3 titik statis,
     tampil seragam di semua ukuran layar (avatar TIDAK ikut dianimasikan —
     dulu ada cincin berputar di avatar untuk desktop, sengaja dilepas supaya
     loading state konsisten dengan mobile: cukup waveform + label saja).
   Warna memakai --brand-cyan / --brand-green (#009FDF -> #39A849) sesuai brand.
   ================================================================ */

/* --- Waveform + label (semua ukuran layar, termasuk desktop) --- */
.sapa-thinking {
    display: flex !important; align-items: center !important;
    gap: 11px !important; height: 26px !important; min-height: 26px !important;
    line-height: 1 !important; margin: 0 !important; padding: 0 !important;
    box-sizing: border-box !important;
}
.sapa-thinking-wave {
    display: flex !important; align-items: center !important;
    gap: 3px !important; height: 100%;
}
.sapa-thinking-wave span {
    display: block !important;
    width: 2.5px !important; border-radius: 2px !important;
    background: linear-gradient(180deg, var(--brand-cyan), var(--brand-green)) !important;
    box-shadow: 0 0 6px rgba(0,159,223,.35);
    /* setiap garis diberi tinggi dasar, durasi & jeda berbeda supaya gerakan
       terkesan acak (audio-reactive), bukan animasi 5 garis yang serempak */
    animation: sapa-wave-bounce ease-in-out infinite both !important;
    will-change: transform, opacity;
}
/* animation-duration/-delay ditandai !important juga: shorthand "animation" di atas
   sudah !important, dan shorthand itu diam-diam meng-override duration/delay ke nilai
   awal (0s) kalau longhand di bawah ini tidak ikut !important -> animasi "selesai"
   dalam 0 detik dan macet di frame terakhir (kelihatan diam, bukan acak). */
.sapa-thinking-wave span:nth-child(1) { --h: 7px;  animation-duration: .96s !important;  animation-delay: -.62s !important; }
.sapa-thinking-wave span:nth-child(2) { --h: 15px; animation-duration: 1.18s !important; animation-delay: -.11s !important; }
.sapa-thinking-wave span:nth-child(3) { --h: 19px; animation-duration: .84s !important;  animation-delay: -.83s !important; }
.sapa-thinking-wave span:nth-child(4) { --h: 12px; animation-duration: 1.32s !important; animation-delay: -.34s !important; }
.sapa-thinking-wave span:nth-child(5) { --h: 16px; animation-duration: 1.02s !important; animation-delay: -.55s !important; }
@keyframes sapa-wave-bounce {
    0%, 100% { height: 4px; opacity: .45; }
    50%      { height: var(--h); opacity: 1; }
}

.sapa-thinking-label {
    font-size: 13px !important; font-weight: 600 !important; white-space: nowrap;
    color: #fff !important;   /* putih polos, tanpa efek shimmer */
}

/* ================================================================
   EXPANDER (sumber)
   Streamlit menggambar border + radius sendiri di <details>. Kalau <stExpander>
   juga diberi border, hasilnya dua border bertumpuk dengan radius berbeda
   (sudut jadi kotor). Di sini HANYA <stExpander> yang punya border & radius;
   semua elemen di dalamnya dibuat polos dan di-clip oleh overflow: hidden.
   ================================================================ */
[data-testid="stExpander"] {
    border: 1px solid var(--line) !important;
    border-radius: 14px !important;
    background: rgba(255,255,255,.03) !important;
    box-shadow: var(--inset);
    overflow: hidden; isolation: isolate;          /* isolation: clip radius rapi di Safari */
    margin-top: 10px !important; padding: 0 !important;
    width: fit-content !important; max-width: 100% !important;
    display: inline-block !important;
    transition: border-color .2s var(--ease), background-color .2s var(--ease);
}
[data-testid="stExpander"]:hover { border-color: var(--line-2) !important; }
[data-testid="stExpander"]:has(details[open]),
[data-testid="stExpander"][open] { width: 100% !important; display: block !important; }

[data-testid="stExpander"] details,
[data-testid="stExpander"] > details {
    border: 0 !important; border-radius: 0 !important;
    background: transparent !important; box-shadow: none !important;
    margin: 0 !important; padding: 0 !important;
}
[data-testid="stExpander"] summary {
    padding: 9px 14px !important; list-style: none !important;
    cursor: pointer !important;
    display: flex !important; align-items: center !important; gap: 8px !important;
    border-radius: 0 !important; outline: none !important;
    background: transparent !important;
    transition: background-color .2s var(--ease);
}
[data-testid="stExpander"] summary::-webkit-details-marker { display: none !important; }
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary:focus-visible { background: rgba(255,255,255,.04) !important; }
[data-testid="stExpander"] summary p {
    margin: 0 !important; color: var(--text-2) !important;
    font-size: 12.5px !important; font-weight: 500 !important; white-space: nowrap !important;
    transition: color .2s var(--ease);
}
[data-testid="stExpander"] summary:hover p { color: var(--text) !important; }
[data-testid="stExpander"] summary svg,
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    color: var(--text-3) !important; flex: none;
    width: 14px !important; height: 14px !important; font-size: 16px !important;
    transition: transform .25s var(--ease);
}
[data-testid="stExpander"]:has(details[open]) summary svg,
[data-testid="stExpander"][open] summary svg { transform: rotate(90deg); }

[data-testid="stExpander"] > details > div,
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 12px 14px 14px !important;
    border-top: 1px solid var(--line) !important;
    margin-top: 0 !important;
    min-width: 0;
}
[data-testid="stExpander"] pre,
[data-testid="stExpander"] code,
[data-testid="stExpander"] [data-testid="stCodeBlock"] {
    background: transparent !important; font-size: 12px !important;
}

/* Kartu sumber (dirender dari render_sources di app.py) */
.sapa-src { padding: 12px 0; border-top: 1px solid var(--line); }
.sapa-src:first-child { padding-top: 0; border-top: 0; }
.sapa-src:last-child { padding-bottom: 0; }
.sapa-src-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
.sapa-src-num {
    flex: none; width: 20px; height: 20px; margin-top: 1px;
    display: grid; place-items: center; border-radius: 6px;
    background: rgba(165,180,252,.14); color: var(--accent);
    font-size: 11px; font-weight: 700;
}
.sapa-src-meta { min-width: 0; }
.sapa-src-name { color: var(--text); font-size: 13px; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.sapa-src-section { color: var(--text-3); font-size: 11.5px; margin-top: 2px; }
.sapa-src-body {
    padding: 10px 12px; border-radius: 10px;
    background: rgba(255,255,255,.03); border: 1px solid var(--line);
    color: var(--text-2); font-size: 12.5px; line-height: 1.6;
    overflow-wrap: anywhere;
}

iframe {
    border: 0 !important; background: transparent !important; max-width: 100% !important;
    /* color-scheme iframe harus sama dengan dokumen di dalamnya (dark); kalau beda,
       browser mengecatnya dengan kanvas OPAK → muncul kotak hitam selebar kolom */
    color-scheme: dark !important;
}
/* Iframe tombol salin: hanya selebar tombolnya, tidak melebar sampai ujung */
[data-testid="stChatMessageContent"] iframe {
    width: 150px !important; max-width: 100% !important; display: block;
}

/* ================================================================
   KOLOM INPUT — fixed di bawah-tengah layar
   ================================================================ */
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
    border: 0 !important; box-shadow: none !important; outline: none !important;
}
[data-testid="stBottom"] > div { margin: 0 !important; padding: 0 !important; }

[data-testid="stBottom"] {
    position: fixed !important;
    top: auto !important;
    /* naik mengikuti keyboard virtual (--kb diisi JS; 0 di desktop) */
    bottom: var(--kb, 0px) !important;
    left: var(--main-l, 0px) !important;
    right: var(--main-r, 0px) !important;
    width: auto !important;
    transform: translateY(0) !important;
    transition: transform .55s var(--ease), opacity .3s var(--ease);
    z-index: 90 !important;
    padding: 0 !important;
}
/* Fade di belakang input (dan strip pill) supaya teks chat tidak menabrak */
[data-testid="stBottom"]::before {
    content: ""; position: absolute; z-index: -1; pointer-events: none;
    left: 0; right: 0; bottom: 0;
    top: calc(-1 * (var(--pills-zone) + 28px));
    background: linear-gradient(
        180deg,
        rgba(var(--bg-rgb), 0) 0%,
        rgba(var(--bg-rgb), .88) 32%,
        rgba(var(--bg-rgb), .97) 55%,
        rgba(var(--bg-rgb), 1) 100%
    );
}
[data-testid="stBottom"] [data-testid="stBottomBlockContainer"] {
    width: 100% !important; max-width: var(--content-w) !important;
    margin: 0 auto !important; box-sizing: border-box !important;
    padding: var(--bar-pt)
             max(var(--gutter), var(--safe-right))
             calc(var(--bar-pb) + var(--safe-bottom))
             max(var(--gutter), var(--safe-left)) !important;
}
/* Keyboard terbuka: home-indicator tidak lagi di bawah bar, rapatkan */
html.sapa-kb-open [data-testid="stBottomBlockContainer"] {
    padding-bottom: calc(var(--bar-pt) + 4px) !important;
}

/* Buat background input solid agar tidak tembus pandang */
[data-testid="stChatInput"] {
    width: 100% !important;
    background: #1C1E24 !important; /* Diubah dari rgba semi-transparan ke solid */
    border: 1px solid rgba(255,255,255,.11) !important;
    border-radius: 26px !important;
    box-shadow: 0 3px 12px rgba(0,0,0,.22), var(--inset) !important;
    outline: none !important;
    transition: border-color .25s var(--ease), background-color .25s var(--ease), box-shadow .25s var(--ease);
    overflow: hidden !important; isolation: isolate !important;
    display: flex !important; flex-direction: row !important;
    align-items: flex-end !important; justify-content: stretch !important;
    min-height: 0 !important; max-height: none !important; height: auto !important;
    padding: 0 !important;
}
[data-testid="stChatInput"]:hover {
    border-color: rgba(255,255,255,.15) !important;
    box-shadow: 0 5px 18px rgba(0,0,0,.26), var(--inset) !important;
}
[data-testid="stChatInput"]:focus-within {
    background: rgba(32,34,42,.98) !important;
    border-color: rgba(165,180,252,.55) !important;
    box-shadow: 0 0 0 3px rgba(165,180,252,.13), 0 4px 20px rgba(0,0,0,.30), var(--inset) !important;
}

/* Setiap pembungkus antara [data-testid="stChatInput"] dan <textarea> dipaksa
   melebar penuh & berbaris (flex row), APAPUN kedalaman nesting-nya.
   ":has(textarea)" mencocokkan turunan di semua level (bukan cuma anak langsung),
   jadi ini tahan terhadap perbedaan struktur DOM antar versi Streamlit.

   flex-basis DIPAKSA 0% (BUKAN "auto" + width:100%): kombinasi "auto"+width bisa
   dihitung tidak konsisten di sejumlah WebView mobile ketika ada beberapa lapis
   pembungkus bersarang (tiap lapis membulatkan angkanya sendiri, errornya menumpuk),
   hasilnya textarea terlihat lebih sempit dari kotaknya — ada celah kosong sebelum
   tombol kirim, teks jadi patah lebih awal dari seharusnya (persis bug yang pernah
   dilaporkan dari tangkapan layar hosting Streamlit Cloud). flex-basis:0% + grow:1
   TIDAK bergantung pada lebar konten/pembungkus sama sekali, jadi bebas dari masalah
   itu di kedalaman nesting berapa pun — JANGAN diubah balik ke width:100%+flex:auto. */
[data-testid="stChatInput"] div:has(textarea) {
    display: flex !important; flex-direction: row !important;
    align-items: flex-end !important; justify-content: stretch !important;
    background: transparent !important; background-color: transparent !important;
    border: 0 !important; box-shadow: none !important; outline: none !important;
    min-height: 0 !important; max-height: none !important;
    padding: 0 !important; margin: 0 !important;
    flex: 1 1 0% !important; min-width: 0 !important;
}
/* CATATAN PENTING — dulu ada DUA bug berbeda di sini, jangan sampai salah satu
   perbaikannya mengundang yang lain balik lagi:
   Bug A (selector fallback terlalu luas): sempat ada aturan "cadangan" untuk
   browser tanpa dukungan :has() memakai selector "[data-testid="stChatInput"] > div".
   Selector itu TIDAK CUMA kena pembungkus textarea, tapi JUGA kena pembungkus
   TOMBOL KIRIM (keduanya sama-sama <div> anak langsung stChatInput) -> keduanya
   dipaksa flex:1 1 0% dan berebut lebar 50/50, kotak ketik jadi sempit dengan
   celah kosong lebar di sebelah kanan. Solusinya: fallback itu DIHAPUS total
   (bukan diperbaiki) — seluruh halaman ini sudah bergantung total pada :has() di
   mana-mana (sapa-empty/sapa-chat-active dkk), jadi browser yang tidak
   mendukungnya sudah pasti rusak total di bagian lain juga; fallback parsial di
   sini tidak ada gunanya, cuma bikin rusak di browser modern.
   Bug B (flex-basis:auto+width:100%): setelah Bug A diperbaiki, flex-basis di
   atas sempat ikut diganti ke "width:100%+flex:1 1 auto" — ini JUSTRU membawa
   balik gejala yang MIRIP (textarea sempit, celah kosong sebelum tombol) lewat
   jalur berbeda: pembulatan yang tidak konsisten di WebView mobile saat ada
   nesting. Sudah dikembalikan ke flex-basis:0% (blok CSS di atas) karena itu
   SATU-SATUNYA pola yang imun dari KEDUA bug sekaligus. */

/* Textarea: satu baris = --ta-h, membesar otomatis sampai batas maksimal.
   flex-basis:0% juga dipakai di sini dengan alasan yang sama seperti di atas —
   textarea tidak lagi diberi width eksplisit, murni mengisi sisa ruang lewat flex-grow. */
[data-testid="stChatInputTextArea"] {
    background: transparent !important;
    color: var(--text) !important;
    border: 0 !important; box-shadow: none !important; outline: none !important;
    font-size: 16px !important;
    line-height: var(--ta-lh) !important;
    padding: calc((var(--ta-h) - var(--ta-lh)) / 2) 8px calc((var(--ta-h) - var(--ta-lh)) / 2) 18px !important;
    border-radius: 26px !important;
    resize: none !important;
    min-height: var(--ta-h) !important;
    max-height: min(200px, 32vh) !important;
    max-height: min(200px, 32dvh) !important;
    box-sizing: border-box !important;
    display: block !important; overflow-y: auto !important;
    flex: 1 1 0% !important; min-width: 0 !important;
}
[data-testid="stChatInputTextArea"]:focus { outline: none !important; box-shadow: none !important; }
[data-testid="stChatInputTextArea"]::placeholder {
    /* white-space / overflow / text-overflow TIDAK berlaku di ::placeholder,
       jadi placeholder panjang akan membungkus jadi 2 baris & terpotong.
       Solusinya: teks placeholder dipendekkan di app.py + ukuran dikecilkan. */
    color: var(--text-3) !important; opacity: 1 !important;
    font-size: 15px !important;
}
/* Scrollbar textarea disembunyikan (tidak muncul di 1 baris), tetap bisa di-scroll */
[data-testid="stChatInputTextArea"] { scrollbar-width: none !important; caret-color: var(--accent); }
[data-testid="stChatInputTextArea"]::-webkit-scrollbar { display: none !important; }

/* Tombol kirim: menempel di bawah supaya tetap rapi saat textarea multi-baris */
[data-testid="stChatInputSubmitButton"] {
    flex: 0 0 auto !important; align-self: flex-end !important;
    width: var(--btn) !important; height: var(--btn) !important;
    min-width: var(--btn) !important; min-height: var(--btn) !important;
    margin: 0 calc((var(--ta-h) - var(--btn)) / 2) calc((var(--ta-h) - var(--btn)) / 2) 0 !important;
    padding: 0 !important;
    border-radius: 50% !important; border: 0 !important;
    background: linear-gradient(180deg, #FFFFFF 0%, #E2E4E8 100%) !important;
    color: #0A0C11 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.9) !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    transition: transform .25s var(--ease), box-shadow .25s var(--ease);
}
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) { transform: scale(1.07); }
[data-testid="stChatInputSubmitButton"]:active:not(:disabled) { transform: scale(.96); }
[data-testid="stChatInputSubmitButton"]:disabled {
    background: rgba(255,255,255,.08) !important;
    color: rgba(255,255,255,.30) !important;
    box-shadow: none !important; transform: none !important;
}
[data-testid="stChatInputSubmitButton"] svg {
    width: 18px !important; height: 18px !important; margin: 0 !important; display: block !important;
}

/* ================================================================
   MOBILE / TABLET KECIL  (< 768px)
   ================================================================ */
@media (max-width: 767px) {
    :root {
        --gutter: 16px;
        --msg-gap: 22px;
        --ta-h: 48px;
        --btn: 36px;
        --bar-pt: 6px;
        --bar-pb: 12px;
        --pills-h: 34px;
        --topbar-h: 48px;
        /* Perkiraan tinggi list bantuan cepat (6 baris x 48px + 5 jarak 4px + 10px
           jarak ke input). Kalau jumlah bantuan cepat berubah, nilai ini perlu
           disesuaikan supaya sapaan tidak tertutup/terlalu naik. */
        --qa-h: 318px;
    }
    .sapa-tagline { margin-top: 10px; }
    .sapa-desc { max-width: 340px; line-height: 1.5; margin-top: 8px; }

    /* Top bar ringkas: hanya merek + tombol Baru */
    .sapa-chat-separator, .sapa-chat-tagline { display: none; }
    .sapa-chat-brand { height: 16px; }

    /* Bantuan cepat dilepas dari alur (tidak lagi ikut center bersama sapaan),
       lalu ditempel fixed tepat di atas kolom input — seperti referensi. */
    .stApp:has(.sapa-empty) [data-testid="stMainBlockContainer"] {
        padding-bottom: calc(var(--bar-h) + var(--qa-h) + 24px + var(--kb, 0px)) !important;
    }
    .stApp:has(.sapa-empty) .st-key-qa_zone {
        position: fixed !important;
        left: var(--main-l, 0px) !important; right: var(--main-r, 0px) !important;
        bottom: calc(var(--bar-h) + var(--kb, 0px) + 10px) !important;
        top: auto !important;
        padding: 0 max(var(--gutter), var(--safe-left)) !important;
        box-sizing: border-box !important;
        z-index: 80 !important;
    }
    /* Keyboard terbuka: sembunyikan supaya area ketik lega (konsisten dengan strip mode chat aktif) */
    html.sapa-kb-open .stApp:has(.sapa-empty) .st-key-qa_zone { display: none !important; }

    /* Avatar AI sudah dihapus secara global (lihat bagian PESAN di atas);
       di mobile hanya lebar maksimum bubble pengguna yang perlu disesuaikan. */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] {
        max-width: 88% !important;
    }
}

/* Layar sempit: list penuh lebar (dulu grid 2 kolom) */
@media (max-width: 519px) {
    .stApp:has(.sapa-empty) __QA_ROW__ { max-width: 100%; }
}

@media (max-width: 380px) {
    :root { --gutter: 14px; }
    .sapa-desc { font-size: .76rem; }
    .stApp:has(.sapa-empty) .st-key-quick_actions button p { font-size: 13px !important; }
}

/* ================================================================
   DESKTOP (>= 768px, tinggi >= 600px) — kondisi kosong ala Gemini/ChatGPT
     sapaan  → di atas garis tengah
     input   → di garis tengah  (sama-sama elemen fixed di bawah, hanya "diangkat"
               dengan transform, jadi bisa turun dengan animasi saat chat dimulai)
     bantuan → di bawah input
   ================================================================ */
@media (min-width: 768px) and (min-height: 600px) {
    .stApp:has(.sapa-empty) {
        --cy: calc(50vh - 20px);
        --lift: calc(100vh - var(--cy) - var(--bar-pb) - var(--ta-h) / 2 - 1px);
    }

    /* Input diangkat ke tengah dengan z-index di atas hero */
    .stApp:has(.sapa-empty) [data-testid="stBottom"] {
        transform: translateY(calc(-1 * var(--lift))) !important;
        z-index: 100 !important;
    }
    .stApp:has(.sapa-empty) [data-testid="stBottom"]::before { display: none; }

    /* Posisikan Hero lebih tinggi di atas input bar */
    .stApp:has(.sapa-empty) [data-testid="stElementContainer"]:has(.sapa-hero) {
        position: fixed !important;
        left: var(--main-l, 0px); right: var(--main-r, 0px);
        bottom: calc(100vh - var(--cy) + 70px);
        display: flex; justify-content: center;
        padding: 0 var(--gutter); box-sizing: border-box;
        margin: 0 !important;
        z-index: 10 !important;
    }

    /* Bantuan cepat: tepat di bawah input.
       max-height + overflow: list kini lebih tinggi dari grid lama, jadi di layar
       pendek (mis. tinggi 600-650px) ia scroll sendiri alih-alih meluber ke luar
       layar (elemen fixed tidak ikut men-scroll halaman). */
    .stApp:has(.sapa-empty) .st-key-qa_zone {
        position: fixed !important;
        left: var(--main-l, 0px); right: var(--main-r, 0px);
        top: calc(var(--cy) + 27px + 8px);
        max-height: calc(100vh - var(--cy) - 35px - var(--safe-bottom) - 16px);
        overflow-y: auto !important; overflow-x: hidden !important;
        scrollbar-width: none;
        padding: 0 var(--gutter) !important; box-sizing: border-box;
        z-index: 1;
    }
    .stApp:has(.sapa-empty) .st-key-qa_zone::-webkit-scrollbar { display: none; }
}

/* HP landscape / jendela pendek */
@media (max-height: 520px) {
    .sapa-desc { display: none; }
    .stApp:has(.sapa-empty) [data-testid="stMainBlockContainer"] {
        padding-top: calc(var(--safe-top) + 24px) !important;
    }
    .stApp:has(.sapa-chat-active) .st-key-qa_zone { display: none !important; }
    .stApp { --pills-zone: 0px; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: .01ms !important;
        animation-delay: 0ms !important;
        transition-duration: .01ms !important;
        scroll-behavior: auto !important;
    }
}
</style>'''


# ---------------------------------------------------------------------------
# JS — dijalankan di dokumen induk Streamlit (bukan di dalam iframe)
# ---------------------------------------------------------------------------
_LAYOUT_JS = r'''
(function () {
  if (window.__sapaLayoutV2) return;
  window.__sapaLayoutV2 = true;

  var root = document.documentElement;
  var vv = window.visualViewport;
  var prevKb = 0, scheduled = false, observed = [];
  var ro = window.ResizeObserver ? new ResizeObserver(schedule) : null;
  
  // Variabel untuk melacak auto-scroll
  var prevMsgCount = 0;
  var prevScrollHeight = 0;

  function q(sel) { return document.querySelector(sel); }

  var meta = q('meta[name="viewport"]');
  if (meta) {
    var c = meta.getAttribute('content') || '';
    if (c.indexOf('viewport-fit') < 0) c += ', viewport-fit=cover';
    if (c.indexOf('interactive-widget') < 0) c += ', interactive-widget=resizes-content';
    meta.setAttribute('content', c);
  }

  function scrollBox() {
    var a = q('[data-testid="stAppScrollToBottomContainer"]');
    if (a && a.scrollHeight > a.clientHeight) return a;
    return q('[data-testid="stMain"]');
  }

  function observe() {
    if (!ro) return;
    ['[data-testid="stBottom"]', '[data-testid="stMain"]'].forEach(function (sel) {
      var el = q(sel);
      if (el && observed.indexOf(el) < 0) { observed.push(el); ro.observe(el); }
    });
  }

  function update() {
    scheduled = false;
    observe();

    // 1) Tinggi keyboard virtual
    var kb = 0;
    if (vv && vv.scale <= 1.01) {
      kb = Math.round(window.innerHeight - vv.height - vv.offsetTop);
      if (kb < 80) kb = 0;
    }
    root.style.setProperty('--kb', kb + 'px');
    root.classList.toggle('sapa-kb-open', kb > 0);

    // 2) Tinggi kolom input
    var bar = q('[data-testid="stBottom"]');
    if (bar && bar.offsetHeight) root.style.setProperty('--bottom-h', bar.offsetHeight + 'px');

    // 3) Posisi area utama
    var main = q('[data-testid="stMain"]');
    if (main) {
      var r = main.getBoundingClientRect();
      root.style.setProperty('--main-l', Math.max(0, Math.round(r.left)) + 'px');
      root.style.setProperty('--main-r',
        Math.max(0, Math.round(window.innerWidth - (r.left + main.clientWidth))) + 'px');
    }

    // 4) Logika Cerdas Auto-Scroll
    var box = scrollBox();
    if (box) {
      var msgs = document.querySelectorAll('[data-testid="stChatMessage"]');
      var currentMsgCount = msgs.length;
      var currentScrollHeight = box.scrollHeight;

      // a. Saat keyboard terbuka pertama kali
      if (kb > 0 && prevKb === 0) {
        box.scrollTop = currentScrollHeight;
      }
      
      // b. Saat bubble pesan baru/animasi loading muncul
      if (currentMsgCount > prevMsgCount) {
        setTimeout(function() {
          var freshBox = scrollBox();
          if (freshBox) freshBox.scrollTop = freshBox.scrollHeight;
        }, 50);
      }
      
      // c. Saat teks final memanjang menggantikan waveform loading state.
      // Cek apakah posisi baca user berada di jarak < 120px dari bawah layar.
      // Mencegah layar memaksa ke bawah jika user sedang men-scroll manual ke atas baca histori lama.
      else if (currentScrollHeight > prevScrollHeight) {
        var distanceToBottom = prevScrollHeight - box.scrollTop - box.clientHeight;
        if (distanceToBottom < 120) {
          box.scrollTop = currentScrollHeight;
        }
      }

      prevMsgCount = currentMsgCount;
      prevScrollHeight = currentScrollHeight;
    }
    prevKb = kb;
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(update);
  }

  window.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', schedule);
  if (vv) {
    vv.addEventListener('resize', schedule);
    vv.addEventListener('scroll', schedule);
  }
  document.addEventListener('focusin', function () {
    setTimeout(schedule, 60); setTimeout(schedule, 350);
  });
  
  // Gunakan MutationObserver agar auto-scroll berjalan secepat kilat setiap DOM berubah
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  schedule();
})();
'''


def get_custom_css() -> str:
    return (
        _CSS
        .replace('__QA_ROW__', _QA_ROW)
        .replace('__TB_ROW__', _TB_ROW)
        .replace('__CONFIRM_ROW__', _CONFIRM_ROW)
    )


def get_layout_script() -> str:
    """
    HTML untuk components.html(..., height=0).

    Script disuntikkan ke <head> dokumen induk sebagai elemen <script> sungguhan,
    sehingga berjalan di realm halaman utama (bukan iframe) dan tetap hidup walau
    iframe-nya dibuat ulang saat rerun Streamlit.
    """
    payload = json.dumps(_LAYOUT_JS).replace('<', '\\u003c')
    return f'''<script>
(function () {{
  try {{
    var doc = window.parent.document;
    if (doc.getElementById("sapa-layout-js-v2")) return;
    var s = doc.createElement("script");
    s.id = "sapa-layout-js-v2";
    s.textContent = {payload};
    doc.head.appendChild(s);
  }} catch (e) {{
    console.warn("SAPA: script layout tidak dapat dimuat", e);
  }}
}})();
</script>'''


__all__ = ['get_custom_css', 'get_layout_script']