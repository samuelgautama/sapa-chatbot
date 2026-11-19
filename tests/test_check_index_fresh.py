"""Test untuk memastikan import check_index_fresh setelah refactor."""


def test_check_index_fresh_import_works():
    """L-9: Memastikan import check_index_fresh dari scripts/ berfungsi."""
    from scripts.check_index_fresh import check_index_fresh
    
    # Fungsi harus dapat dipanggil dengan warn_only=True
    result = check_index_fresh(warn_only=True)
    
    # Result harus boolean (True jika fresh, False jika stale)
    assert isinstance(result, bool), "check_index_fresh harus mengembalikan boolean"


if __name__ == "__main__":
    test_check_index_fresh_import_works()
    print("PASS: test_check_index_fresh_import_works")
