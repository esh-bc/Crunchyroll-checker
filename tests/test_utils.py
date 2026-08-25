import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.formatting import fancy, fmt_num, pct, progress_bar, checking_progress_msg, hit_message
from utils.validators import is_valid_email, validate_combo_line, sanitize_input


def test_fancy():
    assert fancy("hello") == "ʜᴇʟʟᴏ"
    assert fancy("Hello") == "Hᴇʟʟᴏ"
    assert fancy("ABC") == "ABC"


def test_fmt_num():
    assert fmt_num(1000) == "1,000"
    assert fmt_num(0) == "0"


def test_pct():
    assert pct(50, 100) == "50.0%"
    assert pct(0, 100) == "0.0%"
    assert pct(1, 0) == "0.0%"


def test_progress_bar():
    bar = progress_bar(5, 10, width=10)
    assert "■" in bar
    assert "□" in bar
    bar_empty = progress_bar(0, 0)
    assert " " in bar_empty


def test_checking_progress_msg():
    msg = checking_progress_msg(100, 200, 5, 10, 80, 3, 2, 12.5, "2m 30s")
    assert "Cʜᴇᴄᴋɪɴɢ" in msg
    assert "12.5/s" in msg
    assert "5" in msg  # hits
    assert "DEV:" in msg


def test_hit_message():
    info = {
        "user": "testuser",
        "plan": "MEGA FAN",
        "expires": "2027-01-01",
        "renew": "Yes",
        "streams": "4",
        "country": "United States",
        "payment": "Credit Card",
        "verified": "Yes",
    }
    msg = hit_message("test@example.com", "pass123", info, "TestUser", 123456, "free")
    assert "test@example.com" in msg
    assert "MEGA FAN" in msg
    assert "free" in msg
    assert "DEV:" in msg


def test_is_valid_email():
    assert is_valid_email("test@example.com")
    assert not is_valid_email("notanemail")
    assert not is_valid_email("")


def test_validate_combo_line():
    valid, email, password = validate_combo_line("test@example.com:password123")
    assert valid
    assert email == "test@example.com"
    assert password == "password123"

    valid, _, _ = validate_combo_line("invalid")
    assert not valid

    valid, _, _ = validate_combo_line("")
    assert not valid

    valid, _, _ = validate_combo_line("# comment")
    assert not valid


def test_sanitize_input():
    assert sanitize_input("  hello  ") == "hello"
    assert len(sanitize_input("x" * 10000, max_len=100)) == 100


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
