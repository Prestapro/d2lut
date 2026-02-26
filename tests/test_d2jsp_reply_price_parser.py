from d2lut.normalize.d2jsp_market import extract_reply_price_only_signals


def test_reply_price_only_rejects_bare_five_digit_outlier() -> None:
    assert extract_reply_price_only_signals("44444") == []
    assert extract_reply_price_only_signals("c/o 44444") == []


def test_reply_price_only_keeps_normal_values() -> None:
    assert extract_reply_price_only_signals("4444") == [("co", 4444.0)]
    assert extract_reply_price_only_signals("@ 750") == [("co", 750.0)]


def test_reply_price_only_keeps_explicit_fg_via_primary_parser() -> None:
    # This path is parsed by extract_fg_signals() first, not the fallback cap.
    assert extract_reply_price_only_signals("44444 fg") == [("co", 44444.0)]

