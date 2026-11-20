"""Test untuk memastikan system prompt L-11 memuat aturan kepanjangan dan ketelitian."""


def test_system_prompt_contains_l11_rules():
    """L-11: Memastikan system prompt memuat aturan kepanjangan BPU, PU, JMO dan ketelitian."""
    from sapa.chatbot import SYSTEM_PROMPT
    
    # Verifikasi 3 string kunci dari L-11 ada di system prompt
    assert "Bukan Penerima Upah" in SYSTEM_PROMPT, "SYSTEM_PROMPT harus menyebut 'Bukan Penerima Upah'"
    assert "Jamsostek Mobile" in SYSTEM_PROMPT, "SYSTEM_PROMPT harus menyebut 'Jamsostek Mobile'"
    assert "tidak diikuti peserta BPU" in SYSTEM_PROMPT, "SYSTEM_PROMPT harus menyebut 'tidak diikuti peserta BPU'"


if __name__ == "__main__":
    test_system_prompt_contains_l11_rules()
    print("PASS: test_system_prompt_contains_l11_rules")
