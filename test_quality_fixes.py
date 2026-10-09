"""Regression tests untuk temuan audit #10-#15 dan #20 (intent, sanitasi output, retrieval query, error LLM)."""

from retrieval_utils import (
    build_retrieval_query, lexical_overlap_score, needs_history_for_retrieval,
    normalize_tokens, rerank_scored_documents,
)
from test_critical_fixes import chatbot
from test_retrieval_gate import JHT, Doc, FakeRetriever


# --- #13: intent -----------------------------------------------------------------------------

def test_objection_beats_simulation_keywords():
    for q in (
        "Iurannya mahal, saya nggak mau",
        "Saya belum yakin, buat apa punya kartu BPJS?",
        "Gimana kalau dia bilang takut rugi? iuran 16 ribu",
        "calon peserta bilang nanti saja, iurannya terlalu mahal",
    ):
        assert chatbot.detect_intent(q) == "keberatan", q


def test_other_intents_unchanged_or_improved():
    cases = {
        "bagaimana cara cetak kartu peserta": "pendaftaran",
        "sudah bayar tapi belum dapat bukti kepesertaan": "follow_up",
        "hitung iuran Rp1.000.000": "simulasi",
        "berapa iuran untuk pedagang": "simulasi",
        "apa itu JKK?": "edukasi",
        "gimana cara mendaftar BPU": "pendaftaran",
        "halo selamat pagi": "umum",
    }
    for q, expected in cases.items():
        assert chatbot.detect_intent(q) == expected, (q, chatbot.detect_intent(q))


def test_intent_keywords_match_word_starts_only():
    # "rp" tidak boleh cocok di tengah kata ("terpercaya"), tetapi cocok "Rp1.000.000".
    assert chatbot.detect_intent("apakah aplikasi ini terpercaya?") == "umum"
    assert chatbot.detect_intent("penghasilan saya Rp1.500.000") == "simulasi"


# --- #11/#12: sanitasi output ------------------------------------------------------------------

def test_legitimate_catatan_with_word_dokumen_is_kept():
    text = "**Catatan:** Calon peserta perlu menyiapkan dokumen identitas (KTP)."
    assert chatbot.sanitize_assistant_output(text) == text


def test_internal_references_are_still_removed():
    assert chatbot.sanitize_assistant_output("Total Rp36.800 (lihat FAQ-18).") == "Total Rp36.800"
    out = chatbot.sanitize_assistant_output("Isi jawaban.\nCatatan: lihat FAQ-04 untuk detail.\nLanjut.")
    assert "FAQ" not in out and "Isi jawaban." in out and "Lanjut." in out
    assert "[SUMBER 2]" not in chatbot.sanitize_assistant_output("Teks [SUMBER 2] lanjut")
    assert "info_bpu.txt" not in chatbot.sanitize_assistant_output("Catatan: didukung oleh info_bpu.txt")


def test_nested_list_indentation_is_preserved():
    text = "Langkah:\n- Utama\n  - sub poin\n    - sub-sub"
    assert chatbot.sanitize_assistant_output(text) == text


def test_inline_double_spaces_still_collapse():
    assert chatbot.sanitize_assistant_output("kata   banyak    spasi") == "kata banyak spasi"


def test_reference_removal_does_not_merge_lines():
    out = chatbot.sanitize_assistant_output("Langkah 1.\n(lihat FAQ-04)\nLangkah 2.")
    lines = [l for l in out.split("\n") if l.strip()]
    assert lines == ["Langkah 1.", "Langkah 2."]


# --- #10: kunci diversifikasi -----------------------------------------------------------------

def test_same_section_id_in_different_files_is_not_one_section():
    docs = [
        (Doc("a1", section_id="section-3", source_file="data/info_bpu.txt"), 0.9),
        (Doc("a2", section_id="section-3", source_file="data/info_bpu.txt"), 0.85),
        (Doc("a3", section_id="section-3", source_file="data/info_bpu.txt"), 0.84),
        (Doc("b1", section_id="section-3", source_file="data/info_magang.txt"), 0.8),
        (Doc("c1", section_id="section-3", source_file="data/proses.txt"), 0.7),
    ]
    picked = [d.page_content for d, *_ in rerank_scored_documents("x", docs, top_k=3, max_chunks_per_section=2)]
    assert picked == ["a1", "a2", "b1"]   # a3 ditahan (kuota 2 per section di file yang sama), b1 lolos


# --- #14/#15: query follow-up -----------------------------------------------------------------

def test_standalone_questions_are_not_stitched():
    for q in ("Kalau saya tidak punya KTP bagaimana mendaftar BPU?",
              "apa saja syarat daftar BPU?",
              "lalu apa saja manfaat JKK untuk pedagang kecil"):
        assert needs_history_for_retrieval(q) is False, q


def test_real_follow_ups_are_still_stitched():
    for q in ("Syaratnya apa saja?", "kalau 3 program?", "kalau JHT juga?", "dan JKM?",
              "Bagaimana dengan JHT?", "kalau yang tadi bagaimana?"):
        assert needs_history_for_retrieval(q) is True, q


def test_greeting_or_ack_is_not_used_as_previous_question():
    history = [
        {"role": "user", "content": "Bagaimana cara daftar BPU?"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "terima kasih"},
        {"role": "user", "content": "ok"},
    ]
    query = build_retrieval_query("Syaratnya apa saja?", history)
    assert "Bagaimana cara daftar BPU?" in query and "terima kasih" not in query


def test_short_domain_question_is_valid_previous_question():
    history = [{"role": "user", "content": "Berapa iuran JHT?"}]
    assert "Berapa iuran JHT?" in build_retrieval_query("kalau 3 program?", history)


def test_stitch_header_does_not_dilute_lexical_score():
    stitched = build_retrieval_query(
        "Syaratnya apa saja?", [{"role": "user", "content": "cara daftar BPU"}]
    )
    assert not ({"konteks", "pertanyaan", "sebelumnya", "lanjutan"} & normalize_tokens(stitched))
    doc = Doc("Syarat daftar BPU: usia 17 tahun. Cara daftar lewat formulir.", section="Syarat")
    assert lexical_overlap_score(stitched, doc) >= 0.75


# --- #20: error LLM ----------------------------------------------------------------------------

class RateLimitError(Exception):
    pass


class BrokenLLM:
    def __init__(self, error, before=()):
        self.error, self.before = error, before

    def invoke(self, messages):
        raise self.error

    def stream(self, messages):
        for piece in self.before:
            yield type("Chunk", (), {"content": piece})()
        raise self.error


RETRIEVER = FakeRetriever([(JHT, 0.6)])
QUESTION = "apa itu JHT?"


def _collect(stream):
    return list(stream)


def test_ask_returns_friendly_message_on_rate_limit():
    answer, sources = chatbot.ask(QUESTION, RETRIEVER, BrokenLLM(RateLimitError("Error code: 429 rate limit")))
    assert "Batas penggunaan" in answer and "429" not in answer and sources == [JHT]


def test_stream_error_before_first_token_yields_notice():
    stream = chatbot.ask_stream(QUESTION, RETRIEVER, BrokenLLM(TimeoutError("timed out")))
    deltas = _collect(stream)
    assert "".join(deltas) == stream.text == stream.emitted
    assert "Koneksi" in stream.text and stream.sources == [JHT]


def test_stream_error_midway_keeps_partial_answer_and_adds_notice():
    stream = chatbot.ask_stream(QUESTION, RETRIEVER,
                                BrokenLLM(RateLimitError("429"), before=("JHT adalah jaminan.\n", "Iuran 2% dari")))
    deltas = _collect(stream)
    assert "".join(deltas) == stream.emitted == stream.text
    assert stream.text.startswith("JHT adalah jaminan.") and "Batas penggunaan" in stream.text


def test_generic_error_message_has_no_technical_detail():
    msg = chatbot._llm_error_message(RuntimeError("Traceback secret internals gsk_abc"))
    assert "gsk_" not in msg and "Traceback" not in msg and msg.startswith("Maaf")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"{len(tests)} tests passed")