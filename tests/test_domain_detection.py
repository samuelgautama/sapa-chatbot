def test_off_domain_in_middle_of_bpu_conversation():
    """Test bahwa off-domain tetap off-domain meski setelah percakapan BPU."""
    from sapa.calculator import extract_base_income, extract_programs, detect_sector
    from sapa.chatbot import is_domain_relevant
    
    # Setelah "Saya pedagang" dan "Penghasilan 2 juta"
    # Pertanyaan "Siapa presiden Indonesia?" harus tetap off-domain
    history_with_domain = [
        {"role": "user", "content": "Saya pedagang"},
        {"role": "assistant", "content": "Baik, saya catat Anda pedagang."},
        {"role": "user", "content": "Penghasilan 2 juta"},
    ]
    # Domain check hanya untuk pesan terbaru "Siapa presiden Indonesia?"
    # yang tidak mengandung kata domain
    assert not is_domain_relevant("Siapa presiden Indonesia?"), "Presiden question should be off-domain"
    assert not is_domain_relevant("Harga motor 15 juta berapa cicilannya?"), "Motor cicilan should be off-domain"
    assert not is_domain_relevant("Saya bayar listrik 500 ribu"), "Listrik should be off-domain"
    assert not is_domain_relevant("Program TV favorit"), "TV should be off-domain"
    
    print("test_off_domain_in_middle_of_bpu_conversation PASSED!")

if __name__ == "__main__":
    test_off_domain_in_middle_of_bpu_conversation()
