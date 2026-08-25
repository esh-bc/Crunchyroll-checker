import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.worker import parse_combos, JobContext


def test_parse_combos():
    text = """test@example.com:pass1
# comment
test2@example.com:pass2:extra
test3@example.com:
:password
"""
    combos = parse_combos(text)
    assert len(combos) == 2
    assert combos[0] == ("test@example.com", "pass1")
    assert combos[1] == ("test2@example.com", "pass2:extra")


def test_parse_dupes():
    text = """test@example.com:pass1
TEST@example.com:pass2
test3@example.com:pass3
"""
    combos = parse_combos(text)
    assert len(combos) == 2  # deduped by lowercase email


def test_job_context():
    ctx = JobContext(job_id="abc123", user_id=123, total=100)
    assert ctx.status == "running"
    assert ctx.checked == 0
    assert ctx.total == 100
    assert ctx.cps() == 0.0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
