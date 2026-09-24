"""FR-014 sliding-window per-IP rate limiting + trusted proxy header."""

from coa_profiler.config import Config
from coa_profiler.web.rate_limit import RateLimiter, client_ip


def test_limit_and_retry_after():
    limiter = RateLimiter(window_seconds=60)
    for _ in range(3):
        allowed, _ = limiter.check("upload", "1.2.3.4", 3)
        assert allowed
    allowed, retry = limiter.check("upload", "1.2.3.4", 3)
    assert not allowed
    assert 1 <= retry <= 60


def test_per_ip_isolation_and_buckets():
    limiter = RateLimiter()
    for _ in range(2):
        limiter.check("upload", "10.0.0.1", 2)
    assert limiter.check("upload", "10.0.0.2", 2)[0]  # different IP unaffected
    assert limiter.check("feedback", "10.0.0.1", 2)[0]  # different bucket unaffected
    assert not limiter.check("upload", "10.0.0.1", 2)[0]


def test_nonpositive_deployment_limit_fails_closed():
    limiter = RateLimiter(window_seconds=60)
    assert limiter.check("upload", "10.0.0.1", 0) == (False, 60)
    assert limiter._hits == {}


def test_window_resets(monkeypatch):
    limiter = RateLimiter(window_seconds=60)
    now = [1000.0]
    monkeypatch.setattr("coa_profiler.web.rate_limit.time.monotonic", lambda: now[0])
    assert limiter.check("upload", "1.1.1.1", 1)[0]
    assert not limiter.check("upload", "1.1.1.1", 1)[0]
    now[0] += 61
    assert limiter.check("upload", "1.1.1.1", 1)[0]


def test_global_sweep_evicts_inactive_identity_keys(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("coa_profiler.web.rate_limit.time.monotonic", lambda: now[0])
    limiter = RateLimiter(window_seconds=60, max_keys=20, sweep_interval_seconds=5)

    for index in range(20):
        assert limiter.check("upload", f"198.51.100.{index}", 1)[0]
    assert len(limiter._hits) == 20

    now[0] += 61
    assert limiter.check("upload", "203.0.113.1", 1)[0]
    assert list(limiter._hits) == [("upload", "203.0.113.1")]


def test_active_identity_table_has_a_hard_fail_closed_cap(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("coa_profiler.web.rate_limit.time.monotonic", lambda: now[0])
    limiter = RateLimiter(window_seconds=60, max_keys=3, sweep_interval_seconds=5)

    for index in range(3):
        assert limiter.check("upload", f"198.51.100.{index}", 2)[0]

    allowed, retry_after = limiter.check("upload", "203.0.113.99", 2)
    assert not allowed
    assert 1 <= retry_after <= 60
    assert len(limiter._hits) == 3
    # Existing identities retain their windows; capacity pressure never
    # evicts one and grants it a fresh allowance.
    assert limiter.check("upload", "198.51.100.0", 2)[0]
    assert not limiter.check("upload", "198.51.100.0", 2)[0]


class _FakeRequest:
    def __init__(self, headers=None, host="192.0.2.1"):
        self.headers = headers or {}
        self.client = type("C", (), {"host": host})()


def test_trusted_proxy_header():
    cfg = Config(trusted_proxy_header="X-Forwarded-For")
    req = _FakeRequest(headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert client_ip(req, cfg) == "203.0.113.9"


def test_socket_peer_default():
    cfg = Config(trusted_proxy_header="")
    req = _FakeRequest(headers={"X-Forwarded-For": "203.0.113.9"})
    assert client_ip(req, cfg) == "192.0.2.1"  # header ignored when not configured
