"""Integration: the section-3 journey over HTTP via TestClient.

Covers upload -> result -> PDF -> feedback -> teardown, typed errors, rate
limits, thread-pool saturation signal, session TTL, privacy/algorithm pages,
and the 404 probes for absent auth/payment surfaces.
"""

import io
import json
import re
import time
from pathlib import Path

import pypdf
from fastapi.testclient import TestClient
from PIL import Image

from coa_profiler.app import create_app
from coa_profiler.config import Config
from coa_profiler.web.session import SESSION_COOKIE
from tests.process_worker_helpers import delayed_real_upload, hang_upload

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _client(tmp_path, **overrides):
    defaults = {
        "session_cookie_secure": False,
        "heic_enabled": False,
        "session_tmp_root": str(tmp_path / "sessions"),
    }
    defaults.update(overrides)
    return TestClient(create_app(Config(**defaults)))


def _upload(client, name="fl_coa_sample.pdf"):
    return client.post("/upload", files={"file": (name, (FIXTURES / name).read_bytes())})


class TestPrimaryJourney:
    def test_full_journey(self, client):
        resp = _upload(client)
        assert resp.status_code == 200  # TestClient followed the 303
        html = resp.text
        for needle in [
            "spectrum-bar",
            "uncertainty",
            "rationale",
            "chemistry",
            "<details",
            "Data completeness",
            "18.2",
        ]:
            assert needle in html, needle
        assert re.search(r"Placement:\s*95\s*of\s*100", html)
        assert re.search(r"uncertainty band:\s*90.100", html.replace("&ndash;", "-"))

        cookie = client.cookies.get("session")
        assert cookie and re.fullmatch(r"[0-9a-f]{32}", cookie)

        pdf = client.get("/result/profile.pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF-1.4")
        assert len(pdf.content) < 500 * 1024
        embedded_html_json = re.search(
            r'<script type="application/json" id="result-data">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert embedded_html_json is not None
        reader = pypdf.PdfReader(io.BytesIO(pdf.content))
        assert reader.attachments["coa-profile-data.json"] == [embedded_html_json.group(1).encode("utf-8")]
        assert "coa-profile-sources.json" in reader.attachments

        fb = client.post(
            "/feedback",
            json={
                "helpful": True,
                "placement": 95,
                "completeness": "full",
                "lab_format": "confident_cannabis",
            },
        )
        assert fb.status_code == 204

        # "Analyze another COA" tears down the session.
        client.get("/new")
        assert client.get("/result").status_code == 410

    def test_second_upload_replaces_first(self, client):
        _upload(client, "fl_coa_sample.pdf")
        assert "spectrum-bar" in client.get("/result").text
        _upload(client, "cannabinoids_only.pdf")
        html = client.get("/result").text
        assert "degraded" in html and "weighted THC-total" in html

    def test_refusal_journey(self, client):
        _upload(client, "no_chemistry.pdf")
        html = client.get("/result").text
        assert "spectrum-bar" not in html
        assert "No placement" in html
        assert "Chemotype summary" in html

        pdf = client.get("/result/profile.pdf")
        reader = pypdf.PdfReader(io.BytesIO(pdf.content))
        result_data = json.loads(reader.attachments["coa-profile-data.json"][0])
        assert result_data["score"] is None
        assert result_data["band_low"] is None
        assert result_data["scoring_steps"]["raw_score"] is None

    def test_thca_derivation_visible(self, client):
        _upload(client, "thca_cbda_coa.pdf")
        html = client.get("/result").text
        assert "derived" in html and "0.877" in html

    def test_unit_normalization_visible(self, client):
        _upload(client, "unit_mgg_coa.pdf")
        html = client.get("/result").text
        assert "182 mg/g" in html and "18.2" in html

    def test_plausibility_flag_visible(self, client):
        _upload(client, "plausibility_high_coa.pdf")
        html = client.get("/result").text
        assert 'data-plausibility="true"' in html

    def test_band_wider_when_less_confident(self, client):
        _upload(client, "fl_coa_sample.pdf")
        full = client.get("/result").text
        _upload(client, "cannabinoids_only.pdf")
        degraded = client.get("/result").text
        band = lambda h: re.search(r"uncertainty band:\s*(\d+).(\d+)", h.replace("&ndash;", "-")).groups()
        flo, fhi = map(int, band(full))
        dlo, dhi = map(int, band(degraded))
        assert (dhi - dlo) > (fhi - flo)


class TestTypedErrors:
    def test_upload_is_origin_agnostic_for_share_links_and_proxies(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("fake.pdf", b"plain text bytes")},
            headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
        )
        assert resp.status_code == 422
        assert "INVALID_FILE_TYPE" in resp.text

    def test_null_origin_browser_upload_is_allowed(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("fake.pdf", b"plain text bytes")},
            headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"},
        )
        assert resp.status_code == 422
        assert "INVALID_FILE_TYPE" in resp.text

    def test_invalid_file_type(self, client):
        resp = client.post("/upload", files={"file": ("fake.pdf", b"plain text bytes")})
        assert resp.status_code == 422
        assert "INVALID_FILE_TYPE" in resp.text

    def test_oversize(self, tmp_path):
        with _client(tmp_path, max_upload_mb=1) as client:
            big = b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024)
            resp = client.post("/upload", files={"file": ("big.jpg", big)})
            assert resp.status_code == 422
            assert "FILE_TOO_LARGE" in resp.text
            assert resp.headers["Cache-Control"] == "private, no-store, max-age=0"

    def test_not_a_coa(self, client):
        resp = _upload(client, "not_a_coa.txt")
        assert resp.status_code == 422  # text bytes fail magic sniffing

    def test_heic_rejected_without_decoder(self, client):
        resp = _upload(client, "heic_sample.heic")
        assert resp.status_code == 422
        assert "HEIC" in resp.text

    def test_oversized_image_dimensions_are_a_typed_recoverable_error(self, tmp_path):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
        with _client(tmp_path, max_image_dimension=10) as client:
            resp = client.post("/upload", files={"file": ("wide.png", buffer.getvalue())})
        assert resp.status_code == 422
        assert "DOCUMENT_RESOURCE_LIMIT" in resp.text


class TestSessionTTL:
    def test_expiry_returns_410_and_cleans(self, tmp_path):
        root = tmp_path / "sessions"
        with _client(tmp_path, session_ttl_seconds=1) as client:
            _upload(client)
            assert client.get("/result").status_code == 200
            time.sleep(1.2)
            assert client.get("/result").status_code == 410
            assert not list(root.glob("coa_profiler_session_*"))  # temp dir gone

    def test_processing_time_counts_toward_ttl(self, tmp_path, monkeypatch):
        from coa_profiler.web import routes

        monkeypatch.setattr(routes, "process_upload", delayed_real_upload)
        with _client(tmp_path, session_ttl_seconds=30) as client:
            assert _upload(client).status_code == 200
            record = client.app.state.sessions.get(client.cookies.get("session"))
            assert record is not None
            worker_started_at = float(
                (Path(record.working_copy_path).parent / "worker-started-at").read_text(encoding="utf-8")
            )
            assert record.created_at <= worker_started_at
            assert time.time() - record.created_at >= 0.05

    def test_graceful_shutdown_deletes_live_working_copy(self, tmp_path):
        root = tmp_path / "sessions"
        with _client(tmp_path) as client:
            assert _upload(client).status_code == 200
            session_dirs = list(root.glob("coa_profiler_session_*"))
            assert len(session_dirs) == 1
            assert (session_dirs[0] / "working.pdf").is_file()
            assert len(client.app.state.sessions) == 1

        assert not list(root.glob("coa_profiler_session_*"))


class TestRateLimit:
    def test_upload_limit(self, tmp_path):
        with _client(tmp_path, rate_limit_per_minute=3) as client:
            codes = [_upload(client).status_code for _ in range(4)]
            assert codes[:3] == [200, 200, 200]
            assert codes[3] == 429
            assert "Retry-After" in client.post("/upload", files={"file": ("f.pdf", b"bad")}).headers

    def test_x_forwarded_for(self, tmp_path):
        with _client(tmp_path, rate_limit_per_minute=2, trusted_proxy_header="X-Forwarded-For") as client:
            headers = {"X-Forwarded-For": "10.0.0.1"}
            for _ in range(2):
                client.post("/upload", files={"file": ("a.pdf", b"%PDF-1.4 x")}, headers=headers)
            c3 = client.post("/upload", files={"file": ("a.pdf", b"%PDF-1.4 x")}, headers=headers)
            assert c3.status_code == 429
            other = client.post(
                "/upload", files={"file": ("a.pdf", b"%PDF-1.4 x")}, headers={"X-Forwarded-For": "10.0.0.2"}
            )
            assert other.status_code != 429


class TestPoolSaturation:
    def test_saturated_pool_returns_503(self, client):
        client.app.state.pool_in_flight = 4  # simulate saturation
        resp = _upload(client)
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "30"
        assert client.get("/readyz").json()["thread_pool_available"] is False
        client.app.state.pool_in_flight = 0
        assert client.get("/readyz").json()["thread_pool_available"] is True

    def test_timed_out_child_is_killed_and_capacity_is_released(self, tmp_path, monkeypatch):
        from coa_profiler.web import routes

        monkeypatch.setattr(routes, "process_upload", hang_upload)
        monkeypatch.setattr(routes, "ISOLATED_PIPELINE_TIMEOUT_S", 0.5)

        with _client(tmp_path, processing_thread_pool_size=1) as client:
            timed_out = _upload(client)
            assert timed_out.status_code == 422
            assert "PROCESSING_TIMEOUT" in timed_out.text
            assert client.app.state.pool_in_flight == 0
            assert client.app.state.upload_processes.active_count == 0

            session_root = Path(client.app.state.config.session_tmp_root)
            assert not list(session_root.glob("coa_profiler_session_*"))

            # Capacity is available immediately after the process group dies.
            invalid = client.post("/upload", files={"file": ("bad.pdf", b"bad")})
            assert invalid.status_code == 422
            assert "SERVER_BUSY" not in invalid.text


class TestFeedback:
    def test_schema_validation(self, client):
        _upload(client)
        bad = client.post(
            "/feedback",
            json={"helpful": True, "placement": 999, "completeness": "invalid", "lab_format": "x"},
        )
        assert bad.status_code == 422

    def test_requires_session_cookie(self, client):
        resp = client.post(
            "/feedback",
            json={
                "helpful": True,
                "placement": 95,
                "completeness": "full",
                "lab_format": "confident_cannabis",
            },
        )
        assert resp.status_code == 403

    def test_fake_session_cookie_cannot_record_feedback(self, client):
        client.cookies.set(SESSION_COOKIE, "a" * 32)
        resp = client.post(
            "/feedback",
            json={
                "helpful": True,
                "placement": 95,
                "completeness": "full",
                "lab_format": "confident_cannabis",
            },
        )
        assert resp.status_code == 403
        assert client.app.state.feedback.total_responses == 0

    def test_feedback_labels_must_match_live_server_result(self, client):
        _upload(client)
        mismatched = client.post(
            "/feedback",
            json={
                "helpful": True,
                "placement": 95,
                "completeness": "full",
                "lab_format": "sc_labs",
            },
        )
        assert mismatched.status_code == 422
        assert client.app.state.feedback.total_responses == 0

    def test_feedback_lab_format_is_a_bounded_enum(self, client):
        _upload(client)
        invalid = client.post(
            "/feedback",
            json={"helpful": True, "placement": 95, "completeness": "full", "lab_format": "attacker-label"},
        )
        assert invalid.status_code == 422
        assert client.app.state.feedback.buckets == {}

    def test_aggregate_logged(self, client, caplog):
        _upload(client)
        client.post(
            "/feedback",
            json={
                "helpful": True,
                "placement": 95,
                "completeness": "full",
                "lab_format": "confident_cannabis",
            },
        )
        client.post(
            "/feedback",
            json={
                "helpful": False,
                "placement": 95,
                "completeness": "full",
                "lab_format": "confident_cannabis",
            },
        )
        summary = client.app.state.feedback.summary()
        assert summary["global"] == {"yes": 1, "no": 1}
        assert summary["buckets"] == [
            {"completeness": "full", "lab_format": "confident_cannabis", "yes": 1, "no": 1}
        ]


class TestStaticSurfaces:
    def test_healthz_readyz(self, client):
        assert client.get("/healthz").json()["status"] == "ok"
        ready = client.get("/readyz")
        assert ready.status_code == 200
        body = ready.json()
        assert body["heic_ready"] is True  # HEIC dropped by config in tests

    def test_privacy_page(self, client):
        html = client.get("/privacy").text
        assert client.get("/privacy").status_code == 200
        for needle in ["no account", "no storage", "in memory", "discarded", "HttpOnly"]:
            assert needle in html.lower() or needle in html, needle
        assert re.search(r"IP.{0,120}correlat", html, re.DOTALL)  # correlation disclosure

    def test_algorithm_page_dynamic(self, client):
        html = client.get("/algorithm").text
        for needle in [
            "Myrcene",
            "Limonene",
            "Caryophyllene",
            "neutral",
            "weight",
            "Russo",
            "selection",
            "monitored",
        ]:
            assert needle in html, needle
        assert "0.15 × min(2, unreadable expected cannabinoids)" in html
        assert "0.10 × min(5, unreadable reported terpenes)" in html
        assert "0.30 × [degraded mode]" in html
        assert "CC = DC × MC" in html

    def test_landing_page_contact_link(self, client):
        client.app.state.config = Config(
            session_cookie_secure=False,
            heic_enabled=False,
            session_tmp_root=client.app.state.config.session_tmp_root,
            contact_email="operator@example.test",
        )
        client.app.state.templates.env.globals["contact_email"] = "operator@example.test"
        html = client.get("/").text
        assert "mailto:" in html and "batch processing" in html
        assert "operator@example.test" in html

    def test_landing_omits_placeholder_contact_when_unconfigured(self, client):
        html = client.get("/").text
        assert "mailto:" not in html
        assert ".example" not in html

    def test_inference_assist_disclosure_tracks_configuration(self, tmp_path):
        with _client(tmp_path, inference_assist_enabled=False) as client:
            assert "External inference is disabled" in client.get("/privacy").text
            assert "External inference is enabled" not in client.get("/").text
        with _client(
            tmp_path,
            inference_assist_enabled=True,
            inference_assist_url="https://inference.example",
        ) as client:
            assert "External inference is enabled" in client.get("/").text
            assert "External inference is enabled" in client.get("/privacy").text

    def test_no_auth_or_payment_endpoints(self, client):
        for path in [
            "/login",
            "/register",
            "/checkout",
            "/admin",
            "/accounts",
            "/billing",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]:
            assert client.get(path).status_code == 404, path

    def test_referrer_policy_header(self, client):
        assert client.get("/").headers.get("Referrer-Policy") == "no-referrer"

    def test_referrer_policy_on_all_responses(self, client):
        """FR-013: Referrer-Policy: no-referrer on ALL responses, not just landing."""
        for path in ["/", "/algorithm", "/privacy", "/healthz", "/readyz", "/nonexistent"]:
            assert client.get(path).headers.get("Referrer-Policy") == "no-referrer", path

    def test_baseline_security_headers(self, client):
        headers = client.get("/").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["Permissions-Policy"] == "camera=(), geolocation=(), microphone=()"

    def test_sensitive_routes_are_not_cacheable(self, client):
        _upload(client)
        for path in ["/result", "/result/profile.pdf"]:
            headers = client.get(path).headers
            assert headers["Cache-Control"] == "private, no-store, max-age=0"
            assert headers["Pragma"] == "no-cache"
            assert headers["Vary"] == "Cookie"

    def test_only_versioned_static_assets_are_immutable(self, client):
        active_version = client.app.state.config.version
        assert (
            client.get(f"/static/style.css?v={active_version}").headers["Cache-Control"]
            == "public, max-age=31536000, immutable"
        )
        stale = client.get("/static/style.css?v=not-the-active-build").headers["Cache-Control"]
        assert stale == "public, max-age=0, must-revalidate"
        assert "Cache-Control" not in client.get("/static/style.css").headers
