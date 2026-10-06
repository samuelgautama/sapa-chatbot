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
_TC_ROW = _row('theme_corner')

# ---------------------------------------------------------------------------
# Palet warna. HANYA warna / bayangan / latar — tidak ada ukuran, jarak, posisi,
# flexbox, atau animasi. Dark = default (nilai lama, tidak diubah); Light = baru.
# Nama variabelnya sama persis, jadi seluruh CSS cukup memakai var(--...).
# ---------------------------------------------------------------------------
_DARK_VARS = '''    --scheme: dark;

    /* Permukaan & teks */
    --bg: #07080C;
    --bg-rgb: 7,8,12;
    --text: #F1F3F7;
    --text-2: #C3C9D4;
    --text-3: #A3ABB9;
    --text-strong: #FFFFFF;
    --text-disabled: rgba(226,229,235,.58);
    --line: rgba(255,255,255,.08);
    --line-2: rgba(255,255,255,.14);
    --surface-hover: rgba(255,255,255,.09);
    --fill-xs: rgba(255,255,255,.03);
    --fill-s: rgba(255,255,255,.04);
    --fill-m: rgba(255,255,255,.05);
    --scroll: rgba(255,255,255,.12);
    --accent: #A5B4FC;
    --accent-rgb: 165,180,252;
    --code-fg: #E8EBF2;
    --code-bg: rgba(255,255,255,.09);

    /* Latar halaman: gradient statis + vinyet (tanpa aurora) */
    --app-bg:
        radial-gradient(900px 600px at 12% 0%, rgba(99,102,241,.16), transparent 70%),
        radial-gradient(800px 560px at 92% 0%, rgba(56,189,248,.09), transparent 70%),
        radial-gradient(1200px 1000px at 50% 100%, rgba(30,20,55,.55), transparent 62%),
        linear-gradient(180deg, #0C0E16 0%, #08090D 55%, #050508 100%);
    --vignette:
        radial-gradient(120% 90% at 50% 38%, transparent 55%, rgba(0,0,0,.42) 100%),
        repeating-linear-gradient(0deg, rgba(255,255,255,.015) 0px, transparent 1px, transparent 3px);
    --vignette-blend: soft-light;
    --wm-dark: block;
    --wm-light: none;

    /* Bayangan */
    --inset: inset 0 1px 0 rgba(255,255,255,.06);
    --sh-toggle-hover: var(--inset), 0 4px 14px rgba(0,0,0,.20);
    --sh-pop: 0 24px 60px rgba(0,0,0,.5), 0 2px 10px rgba(0,0,0,.3), 0 -1px 0 rgba(165,180,252,.10) inset, var(--inset);
    --sh-modal: 0 30px 70px rgba(0,0,0,.55), 0 4px 16px rgba(0,0,0,.35), 0 -1px 0 rgba(165,180,252,.10) inset, var(--inset);
    --sh-input: 0 3px 12px rgba(0,0,0,.22), var(--inset);
    --sh-input-hover: 0 5px 18px rgba(0,0,0,.26), var(--inset);
    --sh-input-focus: 0 0 0 3px rgba(165,180,252,.13), 0 4px 20px rgba(0,0,0,.30), var(--inset);
    --sh-send: 0 2px 8px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.9);
    --sh-bubble: 0 2px 10px rgba(0,0,0,.15);
    --sh-alert: 0 10px 30px rgba(0,0,0,.40), var(--inset);
    --sh-primary: 0 6px 18px rgba(99,102,241,.28);

    /* Popup bantuan cepat, dialog, backdrop */
    --toggle-bg: rgba(30,32,40,.72);
    --toggle-open-bg: rgba(165,180,252,.16);
    --toggle-open-border: rgba(165,180,252,.5);
    --toggle-open-icon: #FFFFFF;
    --pop-bg: rgba(24,26,34,.97);
    --modal-bg: rgba(24,26,34,.98);
    --scrim-pop: rgba(4,5,9,.58);
    --scrim-modal: rgba(4,5,9,.68);
    --primary-bg: linear-gradient(180deg, #B7C2FD 0%, #97A6F7 100%);
    --primary-fg: #12131A;
    --primary-border: rgba(165,180,252,.55);

    /* Kolom input & tombol kirim */
    --input-bg: #1C1E24;
    --input-bg-focus: rgba(32,34,42,.98);
    --input-border: rgba(255,255,255,.11);
    --input-border-hover: rgba(255,255,255,.15);
    --input-border-focus: rgba(165,180,252,.55);
    --send-bg: linear-gradient(180deg, #FFFFFF 0%, #E2E4E8 100%);
    --send-fg: #0A0C11;
    --send-off-bg: rgba(255,255,255,.08);
    --send-off-fg: rgba(255,255,255,.30);
    --ring-track: rgba(255,255,255,.14);

    /* Pesan, peringatan, loading waveform */
    --bubble-bg: rgba(255,255,255,.11);
    --bubble-border: rgba(255,255,255,.08);
    --bubble-text: #F5F7FB;
    --alert-bg: rgba(32,24,10,.82);
    --alert-border: rgba(251,191,36,.30);
    --alert-strong: #FCD34D;
    --wave-a: #009FDF;
    --wave-b: #39A849;
    --wave-glow: 0 0 6px rgba(0,159,223,.35);
    --wave-min-o: .45;'''

_LIGHT_VARS = '''    --scheme: light;

    /* Permukaan & teks: putih / abu sangat terang, teks abu kehitaman */
    --bg: #F5F6FA;
    --bg-rgb: 245,246,250;
    --text: #13151B;
    --text-2: #3B4250;
    --text-3: #596171;
    --text-strong: #0A0C11;
    --text-disabled: rgba(19,21,27,.40);
    --line: rgba(15,23,42,.10);
    --line-2: rgba(15,23,42,.18);
    --surface-hover: rgba(15,23,42,.06);
    --fill-xs: rgba(15,23,42,.025);
    --fill-s: rgba(15,23,42,.035);
    --fill-m: rgba(15,23,42,.045);
    --scroll: rgba(15,23,42,.22);
    --accent: #4F46E5;
    --accent-rgb: 79,70,229;
    --code-fg: #1F2430;
    --code-bg: rgba(15,23,42,.07);

    /* Latar halaman: gradient statis pastel */
    --app-bg:
        radial-gradient(900px 600px at 12% 0%, rgba(99,102,241,.10), transparent 70%),
        radial-gradient(800px 560px at 92% 0%, rgba(56,189,248,.10), transparent 70%),
        radial-gradient(1200px 1000px at 50% 100%, rgba(165,180,252,.24), transparent 62%),
        linear-gradient(180deg, #FBFBFE 0%, #F5F6FA 55%, #EDEFF5 100%);
    /* Tanpa vinyet di Light: tepi abu-abu + garis grain tipis terlihat kotor/bergaris di atas putih */
    --vignette: none;
    --vignette-blend: normal;
    /* Logo: varian terang (app.py) dengan ujung gradient teks hijau tua, bukan kuning-hijau
       #C4D600 yang pucat di atas putih. Dua <img> dirender; hanya satu yang tampil. */
    --wm-dark: none;
    --wm-light: block;

    /* Bayangan: putih transparan -> hitam/slate transparan */
    --inset: inset 0 1px 0 rgba(15,23,42,.04);
    --sh-toggle-hover: var(--inset), 0 4px 14px rgba(15,23,42,.12);
    --sh-pop: 0 20px 48px rgba(15,23,42,.18), 0 2px 8px rgba(15,23,42,.10), var(--inset);
    --sh-modal: 0 28px 64px rgba(15,23,42,.22), 0 4px 14px rgba(15,23,42,.12), var(--inset);
    --sh-input: 0 2px 10px rgba(15,23,42,.07), var(--inset);
    --sh-input-hover: 0 4px 16px rgba(15,23,42,.10), var(--inset);
    --sh-input-focus: 0 0 0 3px rgba(79,70,229,.14), 0 4px 18px rgba(15,23,42,.10), var(--inset);
    --sh-send: 0 2px 8px rgba(15,23,42,.25), inset 0 1px 0 rgba(255,255,255,.18);
    --sh-bubble: 0 1px 4px rgba(15,23,42,.06);
    --sh-alert: 0 8px 24px rgba(15,23,42,.12), var(--inset);
    --sh-primary: 0 6px 18px rgba(79,70,229,.30);

    /* Popup bantuan cepat, dialog, backdrop */
    --toggle-bg: rgba(255,255,255,.88);
    --toggle-open-bg: rgba(79,70,229,.10);
    --toggle-open-border: rgba(79,70,229,.45);
    --toggle-open-icon: #4F46E5;
    --pop-bg: rgba(255,255,255,.99);
    --modal-bg: #FFFFFF;
    /* kabut putih (bukan abu): menyatu mulus dengan fade bg di belakang kolom input */
    --scrim-pop: rgba(245,246,250,.78);
    --scrim-modal: rgba(15,23,42,.42);
    --primary-bg: linear-gradient(180deg, #6366F1 0%, #4F46E5 100%);
    --primary-fg: #FFFFFF;
    --primary-border: rgba(79,70,229,.60);

    /* Kolom input & tombol kirim (tombol kirim jadi gelap di atas input putih) */
    --input-bg: #FFFFFF;
    --input-bg-focus: #FFFFFF;
    --input-border: rgba(15,23,42,.14);
    --input-border-hover: rgba(15,23,42,.24);
    --input-border-focus: rgba(79,70,229,.60);
    --send-bg: linear-gradient(180deg, #2A2F3C 0%, #0F1219 100%);
    --send-fg: #FFFFFF;
    --send-off-bg: rgba(15,23,42,.08);
    --send-off-fg: rgba(15,23,42,.35);
    --ring-track: rgba(15,23,42,.14);

    /* Pesan, peringatan, loading waveform (cyan/hijau digelapkan agar kontras di putih) */
    --bubble-bg: rgba(15,23,42,.065);
    --bubble-border: rgba(15,23,42,.08);
    --bubble-text: #13151B;
    --alert-bg: rgba(255,248,230,.96);
    --alert-border: rgba(217,119,6,.35);
    --alert-strong: #B45309;
    --wave-a: #0083BD;
    --wave-b: #2F8F3E;
    --wave-glow: 0 0 5px rgba(0,131,189,.20);
    --wave-min-o: .75;'''

# Selektor tema terang: pilihan eksplisit, atau "system" (tanpa penanda gelap/terang) + perangkat terang.
_LIGHT_BLOCKS = (
    ':root:has(.sapa-theme-light), .stApp:has(.sapa-theme-light) {\n' + _LIGHT_VARS + '\n}\n'
    '@media (prefers-color-scheme: light) {\n'
    '    :root:not(:has(.sapa-theme-dark)):not(:has(.sapa-theme-light)),\n'
    '    .stApp:not(:has(.sapa-theme-dark)):not(:has(.sapa-theme-light)) {\n' + _LIGHT_VARS + '\n    }\n'
    '}'
)

# Tombol tema yang tampil = kebalikan dari tema efektif (Dark -> tombol "ke terang" dst.).
# Hanya display on/off; ukuran/posisi diatur di CSS utama.
_LIGHT_SEL = ':root:has(.sapa-theme-light)'
_SYSTEM_LIGHT_SEL = ':root:not(:has(.sapa-theme-dark)):not(:has(.sapa-theme-light))'
_THEME_VIS = (
    '.st-key-theme_to_dark { display: none !important; }\n'
    + _LIGHT_SEL + ' .st-key-theme_to_light { display: none !important; }\n'
    + _LIGHT_SEL + ' .st-key-theme_to_dark { display: flex !important; }\n'
    '@media (prefers-color-scheme: light) {\n'
    '    ' + _SYSTEM_LIGHT_SEL + ' .st-key-theme_to_light { display: none !important; }\n'
    '    ' + _SYSTEM_LIGHT_SEL + ' .st-key-theme_to_dark { display: flex !important; }\n'
    '}'
)


_CSS = r'''<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

/* ================================================================
   TOKENS
   ================================================================ */
:root {
    /* color-scheme mengikuti tema aktif (--scheme ada di grup warna di bawah) */
    color-scheme: var(--scheme, dark);
    --font: "Plus Jakarta Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;

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

    /* Jarak aman dari badge "Hosted with Streamlit" (Streamlit Community
       Cloud menyuntikkan badge ini sendiri di pojok kanan bawah viewport,
       di LUAR kendali CSS/HTML kita — mencoba menyembunyikannya lewat CSS
       classname tidak reliable karena nama class-nya di-hash & bisa berubah
       tiap rilis). Daripada mengejar cara menyembunyikannya, kolom input
       cukup diangkat sedikit dari tepi bawah layar supaya tombol kirim
       tidak ketiban badge.
       Default di sini 0px (desktop tidak butuh — badge ada di pojok kanan
       BAWAH yang jauh dari kolom input yang sudah dibatasi --content-w &
       ada jarak dari tepi layar). Nilai sungguhan di-set di breakpoint
       mobile saja (lihat @media max-width:767px), karena di layar sempit
       kolom input melebar penuh sampai dekat pojok kanan bawah tempat
       badge nongkrong. */
    --badge-clearance: 0px;

    /* Strip quick action (mode chat aktif) */
    --pills-h: 36px;
    --pills-gap: 8px;

    --ease: cubic-bezier(.22,.68,0,1);
    --safe-top: env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --safe-left: env(safe-area-inset-left, 0px);
    --safe-right: env(safe-area-inset-right, 0px);
}

/* ================================================================
   THEME COLORS — satu-satunya tempat warna tema didefinisikan
   ----------------------------------------------------------------
   Grup ini HANYA berisi warna, bayangan, dan latar (tidak ada ukuran, jarak,
   posisi, flexbox, atau animasi). Default = Dark. Light Mode menimpa nilai yang
   sama di bawahnya:
     - .stApp:has(.sapa-theme-light)  -> pengguna memilih Light (app.py)
     - @media (prefers-color-scheme: light) dan TIDAK ada penanda .sapa-theme-dark
       -> tema "system" mengikuti pengaturan perangkat (juga dipakai sebelum
          penanda sempat dirender, supaya tidak ada kilatan gelap)
   Aturan di bagian lain file ini cukup memakai var(--...) dari grup ini.
   ================================================================ */
:root {
__DARK_VARS__
}
__LIGHT_BLOCKS__

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
    background: var(--app-bg) !important;
    background-attachment: fixed !important;
    animation: sapa-app-in .5s var(--ease) both;
    isolation: isolate;
}
/* Lapisan "aurora" (blur 90px + animasi tanpa henti) DIHAPUS demi performa render;
   warna latar kini hanya gradient statis di --app-bg. */
/* Vinyet halus + grain tipis supaya tepi layar sedikit meredup dan latar tidak
   terasa "flat" — di belakang seluruh konten (z-index -1). */
.stApp::after {
    content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
    background: var(--vignette);
    mix-blend-mode: var(--vignette-blend);
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

.stApp [data-stale="true"] { opacity: 1 !important; transition: none !important; }

* { scrollbar-width: thin; scrollbar-color: var(--scroll) transparent; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: var(--scroll); border-radius: 999px; }
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
    padding-bottom: calc(var(--bar-h) + var(--badge-clearance) + var(--pills-zone) + 28px + var(--kb, 0px)) !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stElementContainer"]:has(.sapa-empty),
[data-testid="stElementContainer"]:has(.sapa-chat-active),
[data-testid="stElementContainer"]:has(.sapa-theme-light),
[data-testid="stElementContainer"]:has(.sapa-theme-dark),
[data-testid="stElementContainer"]:has(.sapa-theme-system) { display: none !important; }

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
    /* Centering "aman": margin auto membagi ruang sisa rata atas-bawah kalau muat,
       tapi kalau konten LEBIH TINGGI dari ruang yang ada, margin-nya jadi 0 dan
       konten mulai dari atas (meluber ke bawah). justify-content:center biasa
       justru meluber ke ATAS dan BAWAH sekaligus — di HP pendek itulah yang
       membuat logo SAPA terdorong sampai menempel/lewat tepi atas layar. */
    margin-block: auto !important;
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
/* Alignment: setiap item topbar (merek, tombol tema, "+ Baru") dipaksa selebar-isi, setinggi
   34px, dan isinya dipusatkan secara vertikal. Pembungkus markdown Streamlit (stMarkdown /
   stMarkdownContainer) dan pembungkus tombol sering membawa margin/padding/min-height
   sendiri yang menggeser logo beberapa px dari tombol; semuanya dinolkan di sini. */
:where(.st-key-topbar) [data-testid="stElementContainer"] {   /* :where = spesifisitas rendah, agar aturan sembunyi tombol tema tetap menang */
    display: flex !important; align-items: center !important;
}
.st-key-topbar [data-testid="stElementContainer"] {
    height: 34px !important; min-height: 0 !important;
    margin: 0 !important; padding: 0 !important;
}
.st-key-topbar [data-testid="stMarkdown"],
.st-key-topbar [data-testid="stMarkdownContainer"],
.st-key-topbar [data-testid="stButton"] {
    display: flex !important; align-items: center !important;
    height: 34px !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important;
}
.st-key-topbar [data-testid="stMarkdownContainer"] { height: auto !important; }
.sapa-chat-brand { align-self: center; }
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
    background: var(--fill-m) !important;
    color: var(--text-2) !important;
    box-shadow: var(--inset) !important;
    transition: background .2s var(--ease), border-color .2s var(--ease),
                color .2s var(--ease), transform .2s var(--ease);
}
.st-key-new_chat button:hover {
    background: var(--surface-hover) !important;
    border-color: var(--line-2) !important; color: var(--text-strong) !important;
}
.st-key-new_chat button:active { transform: scale(.97); }
.st-key-new_chat button [data-testid="stMarkdownContainer"] {
    display: flex !important; align-items: center !important; height: 100%;
}
.st-key-new_chat button p {
    margin: 0 !important; font-size: 13px !important; font-weight: 600 !important;
    color: inherit !important; white-space: nowrap !important; line-height: 1 !important;
}

/* ---------- Tombol tema (matahari/bulan) ----------
   Dua tombol dirender app.py (-> terang / -> gelap); CSS menampilkan yang relevan dengan
   tema EFEKTIF, termasuk saat tema = "system", yang tidak bisa diketahui server.
   Gaya mengikuti ikon "Bantuan cepat": ikon Material, aksen, 17px. */
__THEME_VIS__
.st-key-theme_to_light, .st-key-theme_to_dark,
.st-key-theme_to_light [data-testid="stButton"], .st-key-theme_to_dark [data-testid="stButton"] {
    width: auto !important; margin: 0 !important;
}
.st-key-theme_to_light button, .st-key-theme_to_dark button {
    width: 34px !important; height: 34px !important; min-height: 34px !important; min-width: 34px !important;
    box-sizing: border-box !important; padding: 0 !important; border-radius: 999px !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    border: 1px solid var(--line) !important;
    background: var(--fill-m) !important;
    color: var(--accent) !important;
    box-shadow: var(--inset) !important;
    transition: background .2s var(--ease), border-color .2s var(--ease), transform .2s var(--ease);
}
.st-key-theme_to_light button:hover, .st-key-theme_to_dark button:hover {
    background: var(--surface-hover) !important; border-color: var(--line-2) !important;
}
.st-key-theme_to_light button:active, .st-key-theme_to_dark button:active { transform: scale(.94); }
/* Ikon digambar sendiri (SVG via CSS mask), bukan font Material: glyph font punya
   bearing/ascent sendiri sehingga bulan/matahari selalu bergeser dari tengah. SVG ini
   ber-viewBox simetris (bbox tepat di 12,12), dipusatkan oleh flex pada <button>. Warna
   mengikuti currentColor (= aksen). */
.st-key-theme_to_light button::before, .st-key-theme_to_dark button::before {
    content: ""; display: block; flex: none;
    width: 18px; height: 18px; background-color: currentColor;
    -webkit-mask: var(--theme-ico) center / 18px 18px no-repeat;
            mask: var(--theme-ico) center / 18px 18px no-repeat;
}
.st-key-theme_to_light button {
    --theme-ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41'/%3E%3C/svg%3E");
}
.st-key-theme_to_dark button {
    /* bulan sabit: massa visualnya condong ke kiri-bawah, jadi digeser 0.5px ke kanan-atas (koreksi optik) */
    --theme-ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='-0.5 0.5 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E");
}
/* Label tetap ada untuk pembaca layar, tapi tidak terlihat (tombol hanya ikon) */
.st-key-theme_to_light button p, .st-key-theme_to_dark button p {
    position: absolute !important; width: 1px !important; height: 1px !important;
    margin: -1px !important; padding: 0 !important; overflow: hidden !important;
    clip: rect(0 0 0 0) !important; white-space: nowrap !important;
}
/* Selama jawaban dibuat: klik memicu rerun yang memutus stream -> dikunci
   (selaras dengan Bantuan cepat; lihat bagian ".sapa-generating") */
.stApp:has(.sapa-generating) .st-key-theme_to_light button,
.stApp:has(.sapa-generating) .st-key-theme_to_dark button {
    opacity: .5 !important; cursor: not-allowed !important; pointer-events: none !important;
}
/* Layar awal (belum ada topbar): tombol tema melayang di pojok kanan atas kolom konten */
.st-key-theme_corner {
    position: fixed !important; z-index: 60 !important;
    top: calc(var(--safe-top) + (var(--topbar-h) - 34px) / 2) !important;
    right: calc(var(--main-r, 0px) + max(var(--gutter), var(--safe-right))
                + max(0px, (100vw - var(--main-l, 0px) - var(--main-r, 0px) - var(--content-w)) / 2)) !important;
    left: auto !important; width: auto !important; margin: 0 !important; padding: 0 !important;
}
__TC_ROW__ {
    display: flex !important; flex-direction: row !important; gap: 0 !important;
    width: auto !important; margin: 0 !important; padding: 0 !important;
}
.st-key-theme_corner [data-testid="stElementContainer"] { margin: 0 !important; padding: 0 !important; width: auto !important; }
/* Di topbar: rapatkan jarak ke tombol "+ Baru" (gap 12px -> 8px) */
.st-key-topbar .st-key-theme_to_light, .st-key-topbar .st-key-theme_to_dark { margin-right: -4px !important; }

/* ================================================================
   HERO
   ================================================================ */
.sapa-hero {
    width: 100%; max-width: 680px; margin: 0 auto;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center; padding: 0 8px;
}
.sapa-wordmark.sapa-wm-dark, .sapa-chat-brand.sapa-wm-dark { display: var(--wm-dark); }
.sapa-wordmark.sapa-wm-light, .sapa-chat-brand.sapa-wm-light { display: var(--wm-light); }
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

/* Spasi hero DIKUNCI eksplisit. Markdown Streamlit memberi <h1> padding & <p>
   margin bawaan (mis. h1 padding 1.25rem 0 1rem, p margin-bottom 1rem) yang
   spesifisitasnya setara/lebih tinggi dari class biasa, jadi tinggi hero
   diam-diam membengkak puluhan px dan jaraknya berbeda antar versi Streamlit.
   Akibatnya di HP pendek hero kehabisan ruang: logo terdorong ke atas dan
   tagline/deskripsi menempel ke daftar bantuan cepat. Dengan nilai eksplisit
   di bawah, tinggi hero bisa dihitung & dijaga. */
.sapa-hero .sapa-title,
.sapa-hero .sapa-title * { margin: 0 !important; padding: 0 !important; }
.sapa-hero .sapa-title { line-height: 0 !important; min-height: 0 !important; }
.sapa-hero .sapa-tagline {
    margin: clamp(12px, 2.2dvh, 20px) 0 0 !important; padding: 0 !important; line-height: 1.4 !important;
}
.sapa-hero .sapa-desc {
    margin: clamp(6px, 1.2dvh, 10px) auto 0 !important; padding: 0 !important;
}

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
    transition: background .2s var(--ease), transform .2s var(--ease), opacity .35s var(--ease);
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
.st-key-quick_actions button:hover:not(:disabled) { background: var(--fill-m) !important; }
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
.st-key-quick_actions button[disabled] p { color: var(--text-disabled) !important; }
.st-key-quick_actions button:disabled [data-testid="stIconMaterial"],
.st-key-quick_actions button[disabled] [data-testid="stIconMaterial"] { opacity: .65 !important; }

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
/* Hanya opacity + transform (jalan di compositor GPU). Dulu ada animasi filter: blur() yang
   memaksa repaint tiap frame. */
@keyframes sapa-pop-in {
    from { opacity: 0; transform: translateY(10px) scale(.96); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
.stApp:has(.sapa-chat-active) {
    --col-l: calc(var(--main-l, 0px)
                  + max(var(--gutter), var(--safe-left))
                  + max(0px, (100vw - var(--main-l, 0px) - var(--main-r, 0px) - var(--content-w)) / 2));
    /* + --badge-clearance (0px di desktop, 40px di mobile): stBottom diangkat sebesar itu,
       jadi tombol & popup bantuan cepat harus ikut naik agar tidak menimpa input */
    --above-bar: calc(var(--kb, 0px) + var(--bar-h) + var(--badge-clearance));
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
    background: var(--toggle-bg) !important;
    color: var(--text) !important; box-shadow: var(--inset) !important;
    transition: background .2s var(--ease), border-color .2s var(--ease),
                border-radius .22s var(--ease), transform .2s var(--ease), box-shadow .2s var(--ease);
}
.st-key-qa_toggle button:hover {
    background: var(--surface-hover) !important; border-color: var(--line-2) !important;
    box-shadow: var(--sh-toggle-hover) !important;
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
html.sapa-qa-open .st-key-qa_toggle button {
    background: var(--toggle-open-bg) !important;
    border-color: var(--toggle-open-border) !important;
    border-bottom-left-radius: 7px !important;
}
html.sapa-qa-open .st-key-qa_toggle button [data-testid="stIconMaterial"] {
    transform: rotate(18deg); color: var(--toggle-open-icon) !important;
}

/* Backdrop: meredupkan + mengaburkan latar di belakang popup supaya panel terasa
   melayang sebagai lapisan sendiri (efek "sheet" ala aplikasi native), sekaligus
   jadi area tap-untuk-menutup. Ada di BAWAH kolom input (z89 < 90) supaya input
   tetap terang & tetap bisa dipakai langsung meski popup sedang terbuka. */
.st-key-qa_backdrop {
    position: fixed !important; inset: 0 !important; z-index: 89 !important;
    width: 100vw !important; height: 100vh !important; height: 100dvh !important;
    margin: 0 !important; padding: 0 !important;
    background: var(--scrim-pop) !important;
    animation: sapa-backdrop-in .18s ease-out both;
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
    /* Hampir opak, TANPA backdrop-filter: blur 22px di atas latar harus
       disampel ulang GPU tiap frame, dan itulah yang membuat popup terasa berat di HP. */
    background: var(--pop-bg) !important;
    border: 1px solid var(--line-2) !important;
    border-radius: 18px 18px 18px 7px !important;   /* sudut kiri-bawah menyatu dgn tombol toggle */
    box-shadow: var(--sh-pop) !important;
    transform-origin: 0 100%;
    animation: sapa-pop-in .2s var(--ease) both;
}
.stApp:has(.sapa-chat-active) .st-key-quick_actions::-webkit-scrollbar { display: none; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions button { height: 44px !important; min-height: 44px !important; }
.stApp:has(.sapa-chat-active) .st-key-quick_actions button p { font-size: 14px !important; }
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
    from { opacity: 0; transform: translate(-50%, -50%) scale(.95) translateY(8px); }
    to   { opacity: 1; transform: translate(-50%, -50%) scale(1) translateY(0); }
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
    background: var(--scrim-modal) !important;
    animation: sapa-backdrop-in .18s ease-out both;
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
    background: var(--modal-bg) !important;
    border: 1px solid var(--line-2) !important;
    border-radius: 20px !important;
    box-shadow: var(--sh-modal) !important;
    transform-origin: center center;
    animation: sapa-modal-in .22s var(--ease) both;
}
__CONFIRM_ROW__ { gap: 0 !important; }
.sapa-confirm-icon {
    width: 44px; height: 44px; margin: 0 auto 14px; border-radius: 999px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(var(--accent-rgb), .14); color: var(--accent);
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
    background: var(--fill-s) !important;
    color: var(--text-2) !important; box-shadow: none !important;
}
.st-key-confirm_dialog [data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface-hover) !important; border-color: var(--line-2) !important; color: var(--text-strong) !important;
}
.st-key-confirm_dialog [data-testid="stBaseButton-primary"] {
    border: 1px solid var(--primary-border) !important;
    background: var(--primary-bg) !important;
    color: var(--primary-fg) !important; box-shadow: var(--sh-primary) !important;
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
[data-testid="stChatMessageContent"] strong { color: var(--text-strong) !important; font-weight: 700 !important; }
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
    margin: .25em 0 .6em !important; color: var(--text-strong) !important;
    font-size: 1.04rem !important; line-height: 1.3 !important; font-weight: 700 !important;
}
/* ---------- Keterbacaan: warna teks dipaksa terang ----------
   Elemen markdown yang tidak kita style satu per satu (li, em, tabel, blockquote,
   tautan, kode inline, alert, caption, dll.) memakai warna dari tema Streamlit.
   Kalau perangkat memakai mode terang, warna itu GELAP dan nyaris menyatu dengan
   background gelap kita. :where() membuat spesifisitas = 0, jadi aturan ini hanya
   mengisi "celah"; semua aturan khusus di file ini tetap menang. */
:where([data-testid="stMarkdownContainer"], [data-testid="stChatMessageContent"], [data-testid="stExpanderDetails"])
  :where(p, li, ul, ol, span, em, i, b, td, th, h1, h2, h3, h4, h5, h6, small, label, dd, dt):not([class*="sapa-"]) {
    color: var(--text) !important;
}
:where([data-testid="stMarkdownContainer"], [data-testid="stChatMessageContent"]) :where(strong, h1, h2, h3, h4, h5, h6) { color: var(--text-strong) !important; }
:where([data-testid="stMarkdownContainer"], [data-testid="stChatMessageContent"]) :where(a) {
    color: var(--accent) !important; text-decoration-color: rgba(var(--accent-rgb), .5);
}
:where([data-testid="stMarkdownContainer"], [data-testid="stChatMessageContent"]) :where(blockquote, blockquote *) { color: var(--text-2) !important; }
:where([data-testid="stMarkdownContainer"], [data-testid="stChatMessageContent"]) :where(code) {
    color: var(--code-fg) !important; background: var(--code-bg) !important;
}
:where([data-testid="stMarkdownContainer"], [data-testid="stChatMessageContent"]) :where(pre, pre *) { color: var(--code-fg) !important; }
:where([data-testid="stChatMessageContent"]) :where(th, td) { border-color: var(--line-2) !important; }
:where([data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *) { color: var(--text-2) !important; }
:where([data-testid="stAlert"], [data-testid="stAlert"] *) { color: var(--text) !important; }

/* ---------- Peringatan rate limit (responsif) ----------
   Mode chat berjalan : kartu mengambang tepat di atas strip "Bantuan cepat" / kolom input,
                        selebar kolom chat (maks. isi kolom desktop, tepi-ke-tepi dalam gutter di mobile),
                        ikut naik bersama keyboard virtual (--above-bar sudah memuat --kb & --badge-clearance).
   Mode chat kosong   : mengalir biasa di bawah sapaan, rata tengah. */
.st-key-rate_limit { animation: sapa-rl-in .28s ease-out both; }
.stApp:has(.sapa-chat-active) .st-key-rate_limit {
    position: fixed !important; z-index: 97 !important;
    left: var(--col-l) !important; right: auto !important; top: auto !important;
    bottom: calc(var(--above-bar) + var(--pills-zone) + 6px) !important;
    width: min(calc(var(--content-w) - 2 * var(--gutter)),
               calc(100vw - var(--col-l) - var(--main-r, 0px) - max(var(--gutter), var(--safe-right)))) !important;
    box-sizing: border-box !important; margin: 0 !important; padding: 0 !important;
}
.stApp:has(.sapa-empty) .st-key-rate_limit {
    width: 100% !important; max-width: min(520px, 100%) !important; margin: 10px auto 0 !important;
}
.st-key-rate_limit [data-testid="stAlert"] { width: 100% !important; }
.st-key-rate_limit [data-testid="stAlert"] > div,
.st-key-rate_limit [data-testid="stAlert"] [data-baseweb="notification"] {
    background: var(--alert-bg) !important;
    backdrop-filter: blur(16px) saturate(150%) !important;
    -webkit-backdrop-filter: blur(16px) saturate(150%) !important;
    border: 1px solid var(--alert-border) !important;
    border-radius: 14px !important;
    box-shadow: var(--sh-alert) !important;
    padding: 11px 14px !important;
    font-family: var(--font) !important;
    align-items: center !important; gap: 10px !important;
}
.st-key-rate_limit [data-testid="stAlert"] [data-testid="stAlertContainer"] { width: 100% !important; min-width: 0 !important; }
.st-key-rate_limit [data-testid="stAlert"] p {
    color: var(--text) !important; font-size: 14px !important; line-height: 1.5 !important;
    margin: 0 !important; overflow-wrap: anywhere !important;
}
.st-key-rate_limit [data-testid="stAlert"] strong { color: var(--alert-strong) !important; white-space: nowrap; }
@media (max-width: 767px) {
    .st-key-rate_limit [data-testid="stAlert"] > div,
    .st-key-rate_limit [data-testid="stAlert"] [data-baseweb="notification"] {
        padding: 10px 12px !important; border-radius: 13px !important; gap: 8px !important;
    }
    .st-key-rate_limit [data-testid="stAlert"] p { font-size: 13px !important; line-height: 1.45 !important; }
}
@keyframes sapa-rl-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .st-key-rate_limit { animation: none; } }

/* ---------- Cooldown kirim (kelas html.sapa-cooldown dipasang JS, sinkron dengan server) ----------
   Tombol kirim nonaktif + cincin progres + angka hitung mundur. Ukuran mengikuti --btn,
   jadi otomatis pas di desktop (38px) maupun mobile (36px). Bantuan cepat ikut meredup. */
[data-testid="stElementContainer"]:has(.sapa-cooldown-sync) { display: none !important; }
html.sapa-cooldown [data-testid="stChatInputSubmitButton"] {
    position: relative !important; cursor: not-allowed !important;
    background: var(--send-off-bg) !important; color: transparent !important;
    box-shadow: none !important; transform: none !important;
    animation: sapa-cd-settle .42s var(--ease) both;
}
html.sapa-cooldown [data-testid="stChatInputSubmitButton"] svg { opacity: 0 !important; }
html.sapa-cooldown [data-testid="stChatInputSubmitButton"]::before {
    content: ""; position: absolute; inset: 0; border-radius: 50%; pointer-events: none;
    animation: sapa-cd-ring-in .5s var(--ease) both;
    background: conic-gradient(var(--accent) calc(var(--cd-p, 0) * 360deg), var(--ring-track) 0);
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px));
            mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px));
}
html.sapa-cooldown [data-testid="stChatInputSubmitButton"]::after {
    content: var(--cd-n, ""); position: absolute; inset: 0; pointer-events: none;
    display: flex; align-items: center; justify-content: center;
    font: 700 13px/1 var(--font); color: var(--text); font-variant-numeric: tabular-nums;
    animation: var(--cd-anim, sapa-cd-tick-a) .34s var(--ease) both;   /* nama animasi digilir JS tiap detik -> angka "ganti" halus */
}
html.sapa-cooldown .st-key-quick_actions button { opacity: .5 !important; cursor: not-allowed !important; }
@keyframes sapa-cd-settle { from { transform: scale(.88); } to { transform: scale(1); } }
@keyframes sapa-cd-ring-in { from { opacity: 0; transform: rotate(-90deg) scale(.9); } to { opacity: 1; transform: none; } }
@keyframes sapa-cd-tick-a { from { opacity: .15; } to { opacity: 1; } }
@keyframes sapa-cd-tick-b { from { opacity: .15; } to { opacity: 1; } }
/* Cooldown selesai: cincin tipis memancar sekali dari tombol kirim (kelas dipasang JS ~0,7 dtk) */
html.sapa-cd-ready [data-testid="stChatInputSubmitButton"] { position: relative !important; }
html.sapa-cd-ready [data-testid="stChatInputSubmitButton"]::after {
    content: ""; position: absolute; inset: 0; border-radius: 50%; pointer-events: none;
    border: 2px solid var(--accent);
    animation: sapa-cd-ready .7s cubic-bezier(.2,.7,.2,1) both;
}
@keyframes sapa-cd-ready { from { opacity: .9; transform: scale(1); } to { opacity: 0; transform: scale(1.38); } }

/* ---------- Sedang membuat jawaban (penanda .sapa-generating dari app.py) ----------
   Klik widget Streamlit apa pun memicu rerun yang MEMUTUS jawaban yang sedang di-stream.
   Jadi selama jawaban dibuat, tombol Bantuan cepat (toggle + isi popup) dikunci. Dikunci
   lewat CSS (bukan atribut disabled dari Python) supaya otomatis aktif lagi begitu penanda
   dihapus di akhir jawaban, tanpa rerun tambahan. Aktivasi keyboard ditahan oleh JS. */
[data-testid="stElementContainer"]:has(.sapa-generating) { display: none !important; }
.stApp:has(.sapa-generating) .st-key-qa_toggle button,
.stApp:has(.sapa-generating) .st-key-quick_actions button {
    opacity: .5 !important; cursor: not-allowed !important; pointer-events: none !important;
}
@keyframes sapa-shake {
    0%, 100% { transform: translateX(0); } 20% { transform: translateX(-4px); }
    40% { transform: translateX(4px); } 60% { transform: translateX(-3px); } 80% { transform: translateX(2px); }
}
.sapa-shake { animation: sapa-shake .42s ease-in-out !important; }

/* ---------- Popup Bantuan cepat & dialog "+ Baru": buka/tutup 100% di sisi klien ----------
   Dulu membuka/menutup = 1x rerun Streamlit (tunggu server, kirim ulang seluruh halaman,
   render ulang riwayat chat) -> terasa berat. Sekarang elemen popup SELALU ada di DOM tetapi
   disembunyikan; JS cukup memasang/melepas html.sapa-qa-open / html.sapa-confirm-open, jadi
   muncul seketika tanpa menyentuh server. Ini juga menutup popup langsung saat bantuan
   dipilih (tidak lagi tertinggal sampai jawaban selesai). Spesifisitas sengaja tinggi agar
   mengalahkan aturan display lain di file ini. */
html:not(.sapa-qa-open) .stApp:has(.sapa-chat-active) .st-key-quick_actions,
html:not(.sapa-qa-open) .st-key-qa_backdrop,
html:not(.sapa-confirm-open) .st-key-confirm_backdrop,
html:not(.sapa-confirm-open) .st-key-confirm_dialog { display: none !important; }

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
    background: var(--bubble-bg) !important;
    border: 1px solid var(--bubble-border) !important;
    box-shadow: var(--sh-bubble) !important;
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
    color: var(--bubble-text) !important;
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
    background: linear-gradient(180deg, var(--wave-a), var(--wave-b)) !important;
    box-shadow: var(--wave-glow);
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
    0%, 100% { height: 4px; opacity: var(--wave-min-o); }
    50%      { height: var(--h); opacity: 1; }
}

.sapa-thinking-label {
    font-size: 13px !important; font-weight: 600 !important; white-space: nowrap;
    color: var(--text-strong) !important;   /* polos, tanpa efek shimmer */
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
    background: var(--fill-xs) !important;
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
[data-testid="stExpander"] summary:focus-visible { background: var(--fill-s) !important; }
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
    background: rgba(var(--accent-rgb), .14); color: var(--accent);
    font-size: 11px; font-weight: 700;
}
.sapa-src-meta { min-width: 0; }
.sapa-src-name { color: var(--text); font-size: 13px; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.sapa-src-section { color: var(--text-3); font-size: 11.5px; margin-top: 2px; }
.sapa-src-body {
    padding: 10px 12px; border-radius: 10px;
    background: var(--fill-xs); border: 1px solid var(--line);
    color: var(--text-2); font-size: 12.5px; line-height: 1.6;
    overflow-wrap: anywhere;
}

iframe {
    border: 0 !important; background: transparent !important; max-width: 100% !important;
    /* color-scheme iframe harus sama dengan dokumen di dalamnya (mengikuti tema aktif);
       kalau beda, browser mengecatnya dengan kanvas OPAK → muncul kotak selebar kolom */
    color-scheme: var(--scheme, dark) !important;
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
    /* naik mengikuti keyboard virtual (--kb diisi JS; 0 di desktop/tanpa
       keyboard) + jarak aman tetap dari badge Streamlit Cloud */
    bottom: calc(var(--kb, 0px) + var(--badge-clearance)) !important;
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
    background: var(--input-bg) !important; /* solid agar tidak tembus pandang */
    border: 1px solid var(--input-border) !important;
    border-radius: 26px !important;
    box-shadow: var(--sh-input) !important;
    outline: none !important;
    transition: border-color .25s var(--ease), background-color .25s var(--ease), box-shadow .25s var(--ease);
    overflow: hidden !important; isolation: isolate !important;
    display: flex !important; flex-direction: row !important;
    align-items: flex-end !important; justify-content: stretch !important;
    min-height: 0 !important; max-height: none !important; height: auto !important;
    padding: 0 !important;
}
[data-testid="stChatInput"]:hover {
    border-color: var(--input-border-hover) !important;
    box-shadow: var(--sh-input-hover) !important;
}
[data-testid="stChatInput"]:focus-within {
    background: var(--input-bg-focus) !important;
    border-color: var(--input-border-focus) !important;
    box-shadow: var(--sh-input-focus) !important;
}

/* ====== RIWAYAT BUG "kotak input menyempit" (3 percobaan sebelumnya) ======
   Percobaan 1: fallback selector "[data-testid=stChatInput] > div" ternyata
   JUGA mengenai pembungkus TOMBOL KIRIM (sama-sama <div> anak langsung),
   membuat keduanya berebut lebar 50/50 -> fallback dihapus total.
   Percobaan 2: flex-basis sempat diganti ke "width:100%+flex:1 1 auto",
   yang justru tidak konsisten dibulatkan di sejumlah WebView mobile saat ada
   nesting -> dikembalikan ke flex-basis:0%.
   Percobaan 3 (flex-basis:0% + selector "div:has(textarea)"): masih tetap
   bisa gagal total kalau Streamlit ternyata TIDAK membungkus textarea-nya
   pakai tag <div> (melainkan <label>, <span>, atau tag lain) — selector itu
   HANYA mencocokkan tag <div> secara eksplisit, jadi kalau tag pembungkusnya
   beda, aturan ini tidak pernah kena sama sekali, dan textarea jatuh balik ke
   lebar bawaan browser (~20 karakter) -> persis gejala "satu huruf per baris".

   SOLUSI SEKARANG — display:contents, bukan lagi flex per level:
   Setiap pembungkus di antara [data-testid="stChatInput"] dan isi sesungguhnya
   (textarea, tombol kirim) dibuat "transparan" total dari sisi layout lewat
   display:contents — pembungkusnya tetap ada di DOM tapi SAMA SEKALI tidak lagi
   ikut menentukan ukuran/posisi, seolah tidak pernah ada. Efeknya, textarea &
   tombol kirim otomatis jadi "anak flex LANGSUNG" dari stChatInput itu sendiri
   — TIDAK PEDULI berapa lapis pembungkusnya atau tag apa yang dipakai (div,
   label, span, dll), karena selector di bawah pakai "*" (elemen apa saja),
   bukan "div" secara spesifik. Ini jauh lebih tahan banting daripada percobaan
   manapun sebelumnya karena tidak lagi bergantung sama sekali pada dugaan
   struktur/tag DOM Streamlit.

   display:contents SENGAJA TIDAK dipasang pada textarea/tombolnya SENDIRI,
   cuma pada pembungkus di SEKITARNYA — display:contents pada elemen form
   interaktif (<button>, <textarea>) punya riwayat bug aksesibilitas/fungsional
   di sejumlah browser, jadi elemen fungsionalnya wajib tetap apa adanya. */
[data-testid="stChatInput"] *:has(textarea) { display: contents !important; }
[data-testid="stChatInput"] *:has([data-testid="stChatInputSubmitButton"]) { display: contents !important; }

/* Textarea: satu baris = --ta-h, membesar otomatis sampai batas maksimal.
   flex-basis:0% (bukan width:100%) — lihat riwayat bug Percobaan 2 di atas. */
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
    background: var(--send-bg) !important;
    color: var(--send-fg) !important;
    box-shadow: var(--sh-send) !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    transition: transform .25s var(--ease), box-shadow .25s var(--ease);
}
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) { transform: scale(1.07); }
[data-testid="stChatInputSubmitButton"]:active:not(:disabled) { transform: scale(.96); }
[data-testid="stChatInputSubmitButton"]:disabled {
    background: var(--send-off-bg) !important;
    color: var(--send-off-fg) !important;
    box-shadow: none !important; transform: none !important;
}
[data-testid="stChatInputSubmitButton"] svg {
    width: 18px !important; height: 18px !important; margin: 0 !important; display: block !important;
    transition: opacity .3s var(--ease);
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
        /* Lihat penjelasan --badge-clearance di :root — baru relevan di
           mobile, sengaja 0px di desktop. */
        --badge-clearance: 40px;
        /* Daftar bantuan cepat (chat kosong) mengecil mengikuti tinggi layar —
           baris 40px di HP pendek, mentok 48px di HP tinggi — supaya sapaan tetap
           punya ruang. --qa-count = jumlah bantuan cepat di app.py (ubah di sini
           kalau jumlahnya berubah); 4px = jarak antar baris. */
        --qa-count: 6;
        --qa-row: clamp(40px, 6.2dvh, 48px);
        --qa-h: calc(var(--qa-row) * var(--qa-count) + (var(--qa-count) - 1) * 4px);
        /* Jarak minimum antara sapaan dan daftar bantuan cepat */
        --hero-gap: clamp(24px, 4dvh, 40px);
        --hero-top: clamp(24px, 5dvh, 48px);
    }
    .sapa-desc { max-width: 340px; line-height: 1.5; }
    .sapa-hero { margin-bottom: 0; }   /* jaraknya sudah dijaga --hero-gap di padding container */

    /* Top bar ringkas: hanya merek + tombol Baru */
    .sapa-chat-separator, .sapa-chat-tagline { display: none; }
    .sapa-chat-brand { height: 16px; }

    /* Bantuan cepat dilepas dari alur (tidak lagi ikut center bersama sapaan),
       lalu ditempel fixed tepat di atas kolom input — seperti referensi. */
    .stApp:has(.sapa-empty) [data-testid="stMainBlockContainer"] {
        padding-top: calc(var(--safe-top) + var(--hero-top)) !important;
        /* = tinggi input + clearance + daftar (fixed) + 10px (jarak daftar ke input) + --hero-gap */
        padding-bottom: calc(var(--bar-h) + var(--badge-clearance) + var(--qa-h) + 10px + var(--hero-gap) + var(--kb, 0px)) !important;
    }
    .stApp:has(.sapa-empty) .st-key-quick_actions button {
        height: var(--qa-row) !important; min-height: var(--qa-row) !important;
    }
    .stApp:has(.sapa-empty) .st-key-qa_zone {
        position: fixed !important;
        left: var(--main-l, 0px) !important; right: var(--main-r, 0px) !important;
        /* + --badge-clearance: kolom input (stBottom) sendiri sudah diangkat sebesar itu,
           jadi daftar harus ikut naik agar tidak tertutup input */
        bottom: calc(var(--bar-h) + var(--badge-clearance) + var(--kb, 0px) + 10px) !important;
        top: auto !important;
        padding: 0 max(var(--gutter), var(--safe-left)) !important;
        box-sizing: border-box !important;
        z-index: 80 !important;
    }
    /* Efek blur/fade hitam disebarkan sampai tepi bawah layar (menutup celah
       --badge-clearance di bawah kolom input), termasuk area aman home-indicator. */
    [data-testid="stBottom"]::before {
        bottom: calc(-1 * (var(--badge-clearance) + var(--safe-bottom))) !important;
    }

    /* Keyboard terbuka: sembunyikan supaya area ketik lega (konsisten dengan strip mode chat aktif) */
    html.sapa-kb-open .stApp:has(.sapa-empty) .st-key-qa_zone { display: none !important; }

    /* Avatar AI sudah dihapus secara global (lihat bagian PESAN di atas);
       di mobile hanya lebar maksimum bubble pengguna yang perlu disesuaikan. */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > [data-testid="stChatMessageContent"] {
        max-width: 88% !important;
    }
}

/* HP pendek (mis. 360x640, 320x568): paragraf deskripsi paling tidak esensial,
   disembunyikan lebih awal dari aturan max-height:520px di bawah supaya logo,
   tagline, dan daftar bantuan cepat tetap lega. */
@media (max-width: 767px) and (max-height: 620px) {
    .sapa-desc { display: none; }
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
        /* -var(--badge-clearance) di sini menetralkan tambahan "bottom" di
           atas, supaya posisi tengah saat chat kosong tidak ikut bergeser
           naik oleh jarak aman badge (itu cuma relevan saat bar menempel
           di tepi bawah layar, yaitu mode chat berjalan). */
        --lift: calc(100vh - var(--cy) - var(--bar-pb) - var(--ta-h) / 2 - 1px - var(--badge-clearance));
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
  if (window.__sapaLayoutV6) return;
  window.__sapaLayoutV6 = true;

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

  // ---- Mobile: keyboard otomatis tertutup setelah kirim (Enter / tombol kirim) ----
  // Hanya perangkat layar sentuh / layar sempit. Shift+Enter tetap baris baru.
  // blur() ditunda supaya handler Streamlit (yang mengirim pesan) jalan lebih dulu.
  var lastTouch = 0, noRefocusUntil = 0;
  function isMobileUI() {
    return window.matchMedia('(max-width: 767px)').matches ||
           window.matchMedia('(pointer: coarse)').matches;
  }
  function chatTa() { return q('[data-testid="stChatInputTextArea"]'); }
  function dismissKeyboard(ta) {
    noRefocusUntil = Date.now() + 1500;
    setTimeout(function () {
      var t = ta || chatTa();
      if (t && document.activeElement === t) t.blur();
    }, 60);
  }
  document.addEventListener('pointerdown', function () { lastTouch = Date.now(); }, true);
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (!t || !t.getAttribute || t.getAttribute('data-testid') !== 'stChatInputTextArea') return;
    if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
    if (!isMobileUI()) return;
    if (!t.value || !t.value.trim()) return;      // tidak ada yang dikirim
    dismissKeyboard(t);
  }, false);
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest && e.target.closest('[data-testid="stChatInputSubmitButton"]');
    if (!b || !isMobileUI()) return;
    dismissKeyboard();
  }, true);
  // Streamlit bisa memfokuskan ulang input setelah rerun -> tahan sebentar,
  // kecuali pengguna memang baru saja mengetuk input.
  document.addEventListener('focusin', function (e) {
    var t = e.target;
    if (!t || !t.getAttribute || t.getAttribute('data-testid') !== 'stChatInputTextArea') return;
    if (Date.now() < noRefocusUntil && Date.now() - lastTouch > 450 && isMobileUI()) {
      setTimeout(function () { if (document.activeElement === t) t.blur(); }, 0);
    }
  }, true);

  // ---- Cooldown kirim (rate limit) + bantuan cepat ----
  // Server (app.py) menaruh penanda .sapa-cooldown-sync berisi sisa waktu resmi; JS hanya
  // menampilkan & menegakkannya: tombol kirim nonaktif, Enter diblok, bantuan cepat terkunci.
  // Teks yang sedang diketik TIDAK hilang karena pesan memang tidak pernah dikirim.
  var CD_DEFAULT = 9000;
  var cd = { end: 0, total: CD_DEFAULT, raf: 0, n: -1, key: '' };
  function cdLeft() { return Math.max(0, cd.end - performance.now()); }
  function submitBtn() { return q('[data-testid="stChatInputSubmitButton"]'); }
  function releaseSubmit() {
    var b = submitBtn(), ta = chatTa();
    if (b) b.disabled = !(ta && ta.value && ta.value.trim().length);   // sama dengan aturan bawaan Streamlit
  }
  // Dirender per frame (requestAnimationFrame, ~60fps) supaya cincin progres mengalir mulus,
  // bukan lompat tiap 100 ms. Angka (--cd-n) hanya diperbarui saat detiknya berganti.
  function cdFrame() {
    cd.raf = 0;
    var left = cdLeft();
    if (left <= 0) {
      cd.n = -1;
      root.classList.remove('sapa-cooldown');
      root.style.removeProperty('--cd-n');
      root.style.removeProperty('--cd-p');
      root.style.removeProperty('--cd-anim');
      releaseSubmit();
      var b0 = submitBtn();
      if (b0 && !b0.disabled) {                 // tombol langsung bisa dipakai -> pancaran "siap"
        root.classList.add('sapa-cd-ready');
        setTimeout(function () { root.classList.remove('sapa-cd-ready'); }, 750);
      }
      return;
    }
    var n = Math.ceil(left / 1000);
    if (n !== cd.n) {
      cd.n = n;
      root.style.setProperty('--cd-n', '"' + n + '"');
      root.style.setProperty('--cd-anim', (n % 2) ? 'sapa-cd-tick-a' : 'sapa-cd-tick-b');
    }
    root.style.setProperty('--cd-p', Math.min(1, Math.max(0, 1 - left / cd.total)).toFixed(4));
    var b = submitBtn();
    if (b && !b.disabled) b.disabled = true;
    cd.raf = requestAnimationFrame(cdFrame);
  }
  function startCooldown(ms, total) {
    cd.end = performance.now() + ms;
    cd.total = total > 0 ? total : CD_DEFAULT;
    root.classList.remove('sapa-cd-ready');
    root.classList.add('sapa-cooldown');
    if (!cd.raf) cd.raf = requestAnimationFrame(cdFrame);
  }
  function syncCooldown() {
    var all = document.querySelectorAll('.sapa-cooldown-sync');
    var el = all.length ? all[all.length - 1] : null;
    if (el) {
      var key = el.getAttribute('data-key') + '|' + el.getAttribute('data-remaining');
      if (key !== cd.key) {
        cd.key = key;
        var rem = parseFloat(el.getAttribute('data-remaining'));
        if (rem > 0) startCooldown(rem, parseFloat(el.getAttribute('data-total')));
      }
    }
    // Kembali ke layar kosong (mis. setelah "+ Baru") -> pastikan popup tidak tertinggal "terbuka"
    if (!q('.sapa-chat-active')) root.classList.remove('sapa-qa-open', 'sapa-confirm-open');
  }
  var syncQueued = false;
  function queueSync() {
    if (syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(function () { syncQueued = false; syncCooldown(); });
  }
  // React menyalakan lagi tombol kirim saat pengguna mengetik -> paksa mati selama cooldown
  new MutationObserver(function (muts) {
    if (!cdLeft()) return;
    for (var i = 0; i < muts.length; i++) {
      var t = muts[i].target;
      if (t && t.getAttribute && t.getAttribute('data-testid') === 'stChatInputSubmitButton' && !t.disabled) t.disabled = true;
    }
  }).observe(document.body, { attributes: true, attributeFilter: ['disabled'], subtree: true });
  new MutationObserver(queueSync).observe(document.body, { childList: true, subtree: true });

  function nudge(el) {
    if (!el) return;
    el.classList.remove('sapa-shake');
    void el.offsetWidth;
    el.classList.add('sapa-shake');
    setTimeout(function () { el.classList.remove('sapa-shake'); }, 480);
  }
  // Enter saat cooldown: blok SEBELUM handler Streamlit (fase capture), teks tetap utuh
  document.addEventListener('keydown', function (e) {
    if (!cdLeft()) return;
    var t = e.target;
    if (!t || !t.getAttribute || t.getAttribute('data-testid') !== 'stChatInputTextArea') return;
    if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    nudge(submitBtn());
  }, true);
  // ---- Popup Bantuan cepat & dialog "+ Baru": buka/tutup di sisi klien (tanpa rerun) ----
  // Klik tombol pembuka/penutup DITELAN di fase capture sehingga tidak pernah sampai ke
  // Streamlit (tidak ada rerun = instan). Hanya aksi yang memang butuh server yang diteruskan:
  // memilih bantuan cepat dan "Ya, mulai baru".
  function closePopups() { root.classList.remove('sapa-qa-open', 'sapa-confirm-open'); }
  function swallow(e) { e.preventDefault(); e.stopImmediatePropagation(); }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closePopups(); return; }
    // Pesan akan terkirim (Enter, bukan saat cooldown): tutup popup seketika
    var t = e.target;
    if (cdLeft() || e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
    if (t && t.getAttribute && t.getAttribute('data-testid') === 'stChatInputTextArea' && t.value && t.value.trim()) {
      root.classList.remove('sapa-qa-open');
    }
  }, true);
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;

    if (t.closest('[data-testid="stChatInputSubmitButton"]')) {   // kirim -> tutup popup seketika
      if (!cdLeft()) root.classList.remove('sapa-qa-open');
      return;
    }

    // Tombol tema: dikunci selama jawaban dibuat (rerun akan memutus stream); selain itu
    // diteruskan ke Streamlit (server menyimpan pilihan tema) dan popup ditutup.
    var themeBtn = t.closest('.st-key-theme_to_light button, .st-key-theme_to_dark button');
    if (themeBtn) {
      if (q('.sapa-generating')) { swallow(e); nudge(themeBtn); return; }
      closePopups();
      return;
    }

    // "+ Baru" dan dialog konfirmasinya
    if (t.closest('.st-key-new_chat button')) { swallow(e); root.classList.add('sapa-confirm-open'); return; }
    if (t.closest('.st-key-confirm_backdrop button, .st-key-confirm_cancel button')) {
      swallow(e); root.classList.remove('sapa-confirm-open'); return;
    }
    if (t.closest('.st-key-confirm_ok button')) { closePopups(); return; }   // diteruskan: server mereset chat

    // Bantuan cepat
    if (t.closest('.st-key-qa_backdrop button')) { swallow(e); root.classList.remove('sapa-qa-open'); return; }
    var toggle = t.closest('.st-key-qa_toggle button');
    if (toggle) {
      swallow(e);
      if (q('.sapa-generating')) return;   // dikunci selama jawaban dibuat (selaras dengan CSS)
      var open = root.classList.toggle('sapa-qa-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      return;
    }
    var item = t.closest('.st-key-quick_actions button');
    if (item) {
      // Jawaban sedang dibuat / cooldown: tidak boleh memicu rerun
      if (q('.sapa-generating')) { swallow(e); return; }
      if (cdLeft()) { swallow(e); nudge(item); return; }
      root.classList.remove('sapa-qa-open');   // diteruskan ke Streamlit; popup menutup seketika
    }
  }, true);

  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  schedule();
  queueSync();
})();
'''


def get_custom_css() -> str:
    return (
        _CSS
        .replace('__QA_ROW__', _QA_ROW)
        .replace('__TB_ROW__', _TB_ROW)
        .replace('__CONFIRM_ROW__', _CONFIRM_ROW)
        .replace('__TC_ROW__', _TC_ROW)
        .replace('__THEME_VIS__', _THEME_VIS)
        .replace('__DARK_VARS__', _DARK_VARS)
        .replace('__LIGHT_BLOCKS__', _LIGHT_BLOCKS)
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
    if (doc.getElementById("sapa-layout-js-v6")) return;
    var s = doc.createElement("script");
    s.id = "sapa-layout-js-v6";
    s.textContent = {payload};
    doc.head.appendChild(s);
  }} catch (e) {{
    console.warn("SAPA: script layout tidak dapat dimuat", e);
  }}
}})();
</script>'''


__all__ = ['get_custom_css', 'get_layout_script']