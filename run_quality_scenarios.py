#!/usr/bin/env python3
import sys, time, re, json
from pathlib import Path
from datetime import date, datetime, timezone
from unittest.mock import patch

def sanitize_phone(text):
    return re.sub(r'\+62\s*8\d{2}[-.\s]?\d{3,4}[-.\s]?\d{3,5}', '+62 8xx-xxxx-xxxx', text)

# 15 skenario
SCENARIOS = [
    ("S01", "Ojol + Promo Transportasi", [], ["Halo, saya ojek online", "Berapa iuran 3 program?", "Penghasilan Rp5 juta"]),
    ("S02", "Pedagang + Promo", [], ["Saya pedagang toko", "Iuran JKK & JKM penghasilan 2,5 juta?", "Ada diskon?"]),
    ("S03", "Follow-up 3 Program", [], ["Iuran pedagang 1 juta?", "Kalau 3 program?"]),
    ("S04", "Nominal Majemuk: 1 Juta 500 Ribu", [], ["Penghasilan 1 juta 500 ribu", "Iuran JKK berapa?"]),
    ("S05", "Nominal Ambigu: 1 Juta 500", [], ["Penghasilan 1 juta 500", "Hitung iuran"]),
    ("S06", "Ganti Calon Peserta", [{"role":"user","content":"Ojol 3 juta"}, {"role":"assistant","content":"Baik"}], ["Simulasi pedagang 2 juta", "2 program JKK & JKM?"]),
    ("S07", "Di Bawah Min Lalu Valid", [], ["Pedagang 500 ribu iuran?", "Sekarang 1.250.000, hitung ulang"]),
    ("S08", "Parsing Rp1.250.000", [], ["Penghasilan Rp1.250.000", "Iuran 2 program?"]),
    ("S09", "Follow-up Tanpa Nominal", [{"role":"user","content":"Ojol"}, {"role":"assistant","content":"Baik"}], ["Berapa iurannya?"]),
    ("S10", "Follow-up Syaratnya", [{"role":"user","content":"Apa itu BPU?"}, {"role":"assistant","content":"BPU adalah..."}], ["Syaratnya apa?"]),
    ("S11", "Off-Domain: Presiden", [], ["Siapa presiden Indonesia?"]),
    ("S12", "Off-Domain: BPJS Kesehatan", [], ["Beda BPJS Kesehatan dan Ketenagakerjaan?"]),
    ("S13", "PII: NIK", [], ["NIK 1234567890123456 iuran?"]),
    ("S14", "Promo Basi (2027-01-05)", [], ["Ada promo diskon non-transport?"], date(2027, 1, 5)),
    ("S15", "Target Magang Basi", [], ["Target akuisisi mahasiswa magang?"])
]

def run_scenario(id, title, history, questions, mock_today=None):
    from chatbot import ask_stream, load_retriever, load_llm
    ret = load_retriever()
    llm = load_llm()
    h = list(history)
    results = []
    for q in questions:
        if mock_today:
            with patch("promo_config.today_jakarta", return_value=mock_today):
                ans = "".join(ask_stream(q, ret, llm, history=h))
        else:
            ans = "".join(ask_stream(q, ret, llm, history=h))
        ans = sanitize_phone(ans)
        results.append((q, ans))
        h.extend([{"role":"user","content":q}, {"role":"assistant","content":ans}])
        time.sleep(2)
    return (id, title, results)

def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "before"
    out = Path(f"docs/quality_review_{phase}.md")
    out.parent.mkdir(exist_ok=True)
    print(f"\n=== Quality Review {phase.upper()} ===\n")
    with out.open("w", encoding="utf-8") as f:
        f.write(f"# Quality Review — {phase.upper()}\n**Timestamp**: {datetime.now(timezone.utc).isoformat()}\n\n")
        for i, s in enumerate(SCENARIOS, 1):
            try:
                print(f"[{i}/15] {s[0]}: {s[1]}")
                mock = s[5] if len(s) > 5 else None
                id, title, res = run_scenario(s[0], s[1], s[2], s[3], mock)
                f.write(f"## {id}: {title}\n\n")
                for q, a in res:
                    f.write(f"**Q**: {q}\n\n**A**: {a[:300]}...\n\n---\n\n")
            except Exception as e:
                print(f"  ERROR: {e}")
                f.write(f"## {s[0]}: {s[1]} — ERROR\n{e}\n\n")
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
