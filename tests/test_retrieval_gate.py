"""Regression tests untuk confidence gate, rescue, dan kegagalan scoring (temuan audit #6-#7).

Memakai retriever tiruan sehingga tidak butuh FAISS/embedding. Bisa dijalankan dengan
`pytest test_retrieval_gate.py` atau `python test_retrieval_gate.py`.
"""

import logging

from test_critical_fixes import chatbot


class Doc:
    def __init__(self, content, section="Bagian umum", **meta):
        self.page_content = content
        self.metadata = {"section": section, **meta}


JHT = Doc("Bagian: Jaminan Hari Tua\n\nJHT adalah jaminan hari tua. Iuran JHT BPU 2% dari dasar penghasilan.",
          section="Jaminan Hari Tua", source_file="data/info_bpu.txt", section_id="section-4")


class FakeStore:
    def __init__(self, scored=None, error=None):
        self.scored, self.error = scored, error

    def similarity_search_with_relevance_scores(self, query, k=8):
        if self.error:
            raise self.error
        return list(self.scored)


class FakeRetriever:
    def __init__(self, scored=None, error=None, with_store=True):
        self.vectorstore = FakeStore(scored, error) if with_store else None
        self._docs = [d for d, _ in (scored or [(JHT, None)])]

    def invoke(self, query):
        return list(self._docs)


def retrieve(question, retriever, history=None):
    chatbot._logged_retrieval_issues.clear()
    return chatbot.retrieve_documents(question, retriever, history=history)


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def retrieve_logged(question, retriever):
    handler = _Capture()
    chatbot.logger.addHandler(handler)
    try:
        return retrieve(question, retriever), handler.records
    finally:
        chatbot.logger.removeHandler(handler)


# --- #6: rescue tidak boleh meloloskan query di luar domain ---------------------------------

def test_off_domain_query_is_not_rescued_by_generic_word():
    for q in ("berapa harga bitcoin hari ini", "cuaca hari ini di medan", "resep nasi goreng hari ini"):
        docs, _query, details = retrieve(q, FakeRetriever([(JHT, 0.08)]))
        assert docs == [] and details["gate_status"] == "rejected", q


def test_domain_query_with_low_score_is_rescued_and_marked():
    docs, _q, details = retrieve("apa itu JHT?", FakeRetriever([(JHT, 0.08)]))
    assert docs == [JHT] and details["gate_status"] == "rescued"


def test_domain_query_with_very_low_score_and_no_overlap_is_rejected():
    other = Doc("Bagian: Lain\n\nTopik sama sekali berbeda tentang kantor cabang.", section="Lain")
    docs, _q, details = retrieve("bagaimana iuran santunan?", FakeRetriever([(other, 0.02)]))
    assert docs == [] and details["gate_status"] == "rejected"


def test_normal_pass_is_marked_passed():
    docs, _q, details = retrieve("iuran JHT berapa?", FakeRetriever([(JHT, 0.62)]))
    assert docs == [JHT] and details["gate_status"] == "passed"
    assert details["best_semantic_score"] == 0.62


def test_follow_up_inherits_domain_from_previous_question():
    history = [{"role": "user", "content": "berapa iuran JHT?"}]
    docs, query, details = retrieve("kalau yang tadi bagaimana?", FakeRetriever([(JHT, 0.08)]), history)
    assert "JHT" in query and details["gate_status"] == "rescued"


# --- #7: kegagalan scoring tidak boleh diam-diam mematikan gate --------------------------------

def test_scoring_failure_is_logged_and_reported():
    (docs, _q, details), records = retrieve_logged(
        "apa itu JHT?", FakeRetriever([(JHT, None)], error=RuntimeError("api berubah"))
    )
    assert details["scoring_available"] is False
    assert "RuntimeError" in details["scoring_error"] and "api berubah" in details["scoring_error"]
    assert any("Scoring relevansi gagal" in r.getMessage() for r in records)
    assert docs == [JHT] and details["gate_status"] == "unscored"


def test_scoring_failure_no_longer_lets_off_domain_questions_through():
    docs, _q, details = retrieve(
        "berapa harga bitcoin hari ini", FakeRetriever([(JHT, None)], error=RuntimeError("x"))
    )
    assert docs == [] and details["gate_status"] == "rejected"


def test_missing_scoring_api_is_reported():
    (docs, _q, details), records = retrieve_logged(
        "apa itu JHT?", FakeRetriever([(JHT, None)], with_store=False)
    )
    assert details["scoring_available"] is False and "tidak menyediakan" in details["scoring_error"]
    assert records and docs == [JHT]


def test_scoring_issue_is_logged_once_per_kind():
    chatbot._logged_retrieval_issues.clear()
    handler = _Capture()
    chatbot.logger.addHandler(handler)
    try:
        for _ in range(3):
            chatbot.retrieve_documents("apa itu JHT?", FakeRetriever([(JHT, None)], error=RuntimeError("x")))
    finally:
        chatbot.logger.removeHandler(handler)
    assert len(handler.records) == 1


def test_score_scale_warning_flags_out_of_range_scores():
    docs, _q, details = retrieve("apa itu JHT?", FakeRetriever([(JHT, -0.3)]))
    assert details["score_scale_warning"] is True
    _docs, _q, ok = retrieve("apa itu JHT?", FakeRetriever([(JHT, 0.5)]))
    assert ok["score_scale_warning"] is False


# --- prompt jujur soal tingkat keyakinan --------------------------------------------------------

def test_prompt_notice_matches_gate_status():
    assert "lolos pemeriksaan relevansi minimum" in chatbot._retrieval_notice({"gate_status": "passed"})
    rescued = chatbot._retrieval_notice({"gate_status": "rescued"})
    assert "RENDAH" in rescued and "lolos pemeriksaan relevansi minimum" not in rescued
    assert "TIDAK TERUKUR" in chatbot._retrieval_notice({"gate_status": "unscored"})


def test_fallback_when_nothing_selected_for_off_domain():
    docs, query, details = retrieve("berapa harga bitcoin hari ini", FakeRetriever([(JHT, 0.08)]))
    assert docs == [] and not chatbot.is_domain_relevant(query)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"{len(tests)} tests passed")