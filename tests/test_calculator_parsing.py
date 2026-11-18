def test_parse_money_compound():
    """Test parsing nominal majemuk seperti '1 juta 500 ribu'."""
    from sapa.calculator import _parse_money
    from decimal import Decimal
    
    # Majemuk: 1 juta 500 ribu = 1.500.000
    assert _parse_money("1 juta 500 ribu") == Decimal("1500000")
    assert _parse_money("1jt 500rb") == Decimal("1500000")
    assert _parse_money("1 juta 500 rb") == Decimal("1500000")
    
    # Single: tetap bekerja
    assert _parse_money("1 juta") == Decimal("1000000")
    assert _parse_money("500 ribu") == Decimal("500000")
    assert _parse_money("1.250.000") == Decimal("1250000")
    assert _parse_money("Rp1.250.000") == Decimal("1250000")
    assert _parse_money("800 ribu") == Decimal("800000")
    
    # Dengan desimal
    assert _parse_money("1,5 juta") == Decimal("1500000")
    assert _parse_money("2,5 juta") == Decimal("2500000")
    
    print("All _parse_money tests passed!")

if __name__ == "__main__":
    test_parse_money_compound()
