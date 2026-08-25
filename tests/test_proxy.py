import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.proxy import parse_proxy, parse_proxy_file, ProxyManager
import asyncio


def test_parse_http():
    p = parse_proxy("1.2.3.4:8080")
    assert p is not None
    assert p["scheme"] == "http"
    assert p["host"] == "1.2.3.4"
    assert p["port"] == 8080
    assert not p["has_auth"]


def test_parse_http_with_auth():
    p = parse_proxy("1.2.3.4:8080:user:pass")
    assert p is not None
    assert p["has_auth"]
    assert p["scheme"] == "http"


def test_parse_socks5():
    p = parse_proxy("socks5://1.2.3.4:1080")
    assert p is not None
    assert p["scheme"] == "socks5"


def test_parse_socks5_auth():
    p = parse_proxy("socks5://user:pass@1.2.3.4:1080")
    assert p is not None
    assert p["has_auth"]


def test_parse_invalid():
    assert parse_proxy("") is None
    assert parse_proxy("#") is None
    assert parse_proxy("notaproxy") is None
    assert parse_proxy("1.2.3.4:99999") is None


def test_parse_file():
    text = """1.2.3.4:8080
# comment
socks5://5.6.7.8:1080
1.2.3.4:8080:user:pass
invalid
"""
    results = parse_proxy_file(text)
    assert len(results) == 3


def test_proxy_manager():
    pm = ProxyManager()
    pm.load_from_strings(["1.2.3.4:8080", "5.6.7.8:8080"])
    assert len(pm) == 2
    pm.clear()
    assert len(pm) == 0


def test_proxy_manager_mark_dead():
    pm = ProxyManager()
    pm.load_from_strings(["http://1.2.3.4:8080"])
    pm.proxies[0]["alive"] = True
    pm.mark_dead("http://1.2.3.4:8080")
    assert not pm.proxies[0]["alive"]
    assert pm.alive_count == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
