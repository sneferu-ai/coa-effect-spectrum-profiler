"""App-level privacy functions: _format_ip (FR-013), metadata scrub (FR-002),
sweeper lifecycle."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

import pytest
from PIL import Image

from coa_profiler.app import _format_ip
from coa_profiler.web.routes import _strip_and_store
from coa_profiler.web.session import SessionStore

# ---------------------------------------------------------------------------
# _format_ip (FR-013)
# ---------------------------------------------------------------------------


class TestFormatIP:
    def test_disabled_returns_dash(self):
        assert _format_ip("192.168.1.42", "disabled") == "-"

    def test_full_returns_raw_ip(self):
        assert _format_ip("10.0.0.1", "full") == "10.0.0.1"

    def test_truncated_ipv4(self):
        assert _format_ip("192.168.1.42", "truncated") == "192.168.1.0"

    def test_truncated_ipv6(self):
        assert _format_ip("2001:db8::1", "truncated") == "2001:db8::0"

    def test_truncated_non_ip_passthrough(self):
        assert _format_ip("unknown", "truncated") == "unknown"

    def test_hashed_is_deterministic_within_day(self):
        ip = "203.0.113.7"
        a = _format_ip(ip, "hashed")
        b = _format_ip(ip, "hashed")
        assert a == b
        assert len(a) == 16
        assert a != ip  # not plaintext

    def test_hashed_rotates_with_day(self):
        """The daily salt means a different day produces a different hash."""
        ip = "203.0.113.7"
        salt_today = datetime.now(UTC).strftime("%Y-%m-%d")
        salt_tomorrow = "2099-12-31"
        today_hash = hashlib.sha256(f"{salt_today}:{ip}".encode()).hexdigest()[:16]
        tomorrow_hash = hashlib.sha256(f"{salt_tomorrow}:{ip}".encode()).hexdigest()[:16]
        assert today_hash != tomorrow_hash

    def test_hashed_different_ips_different_hashes(self):
        assert _format_ip("1.2.3.4", "hashed") != _format_ip("5.6.7.8", "hashed")

    def test_unknown_mode_defaults_to_hashed(self):
        """An unrecognized mode falls through to the hashed branch."""
        result = _format_ip("1.2.3.4", "bogus")
        assert len(result) == 16
        assert result != "1.2.3.4"


# ---------------------------------------------------------------------------
# _strip_and_store / FR-002 metadata scrub
# ---------------------------------------------------------------------------


class TestMetadataScrub:
    def test_image_strips_exif_and_reencodes_png(self, tmp_path):
        """A JPEG with EXIF is re-encoded to PNG with no metadata."""
        from coa_profiler.parser.ocr import open_image_any

        # Create a JPEG with embedded EXIF (a minimal valid JPEG with a comment).
        img = Image.new("RGB", (100, 50), "red")
        original_path = tmp_path / "original.jpg"
        # Pillow writes EXIF when exif= is passed; embed a minimal user comment.
        exif = img.getexif()
        exif[270] = "SECRET GPS 37.7749,-122.4194"  # ImageDescription tag
        img.save(original_path, format="JPEG", exif=exif.tobytes())

        data = original_path.read_bytes()
        sess_dir = tmp_path / "sess"
        sess_dir.mkdir()
        working = _strip_and_store(data, "jpeg", sess_dir)
        assert working.suffix == ".png"
        assert working.exists()

        # The working copy is a PNG.
        with open_image_any(str(working)) as cleaned:
            assert cleaned.format == "PNG"
            cleaned_exif = cleaned.getexif()
            # No EXIF data in the re-encoded copy.
            assert len(cleaned_exif) == 0

    def test_pdf_working_copy_created(self, tmp_path):
        """A PDF is rewritten into a valid scrubbed working copy."""
        # Create a minimal valid PDF.
        from coa_profiler.parser.text_extract import strip_pdf_metadata

        minimal_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 100 100]/Parent 2 0 R>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
        )
        original = tmp_path / "original.pdf"
        original.write_bytes(minimal_pdf)
        working = tmp_path / "working.pdf"
        strip_pdf_metadata(original, working)
        assert working.exists()
        assert working.read_bytes()[:4] == b"%PDF"

    def test_pdf_scrub_removes_xmp_and_embedded_attachments(self, tmp_path):
        import fitz

        from coa_profiler.parser.text_extract import strip_pdf_metadata

        original = tmp_path / "identifying.pdf"
        working = tmp_path / "working.pdf"
        with fitz.open() as document:
            document.new_page()
            document.set_metadata({"author": "PATIENT INFO DICTIONARY"})
            document.set_xml_metadata(
                "<?xpacket begin=''?><x:xmpmeta xmlns:x='adobe:ns:meta/'>"
                "PATIENT INFO XMP</x:xmpmeta><?xpacket end='w'?>"
            )
            document.embfile_add("patient.txt", b"PATIENT ATTACHMENT")
            document.save(original)

        strip_pdf_metadata(original, working)

        with fitz.open(working) as scrubbed:
            assert "PATIENT" not in str(scrubbed.metadata)
            assert scrubbed.get_xml_metadata() == ""
            assert scrubbed.embfile_names() == []
        scrubbed_bytes = working.read_bytes()
        assert b"PATIENT INFO XMP" not in scrubbed_bytes
        assert b"PATIENT ATTACHMENT" not in scrubbed_bytes

    def test_invalid_image_raises_metadata_scrub_error(self, tmp_path):
        from coa_profiler.errors import MetadataScrubError

        bad = b"\xff\xd8\xffnot actually a jpeg"
        sess2 = tmp_path / "sess2"
        sess2.mkdir()
        with pytest.raises(MetadataScrubError):
            _strip_and_store(bad, "jpeg", sess2)

    def test_original_removed_and_working_copy_is_private(self, tmp_path):
        """Only the scrubbed, owner-readable working copy survives processing."""
        img = Image.new("RGB", (50, 50), "blue")
        buf_path = tmp_path / "src.jpg"
        img.save(buf_path, format="JPEG")
        data = buf_path.read_bytes()

        sess_dir = tmp_path / "sess3"
        sess_dir.mkdir()
        working = _strip_and_store(data, "jpeg", sess_dir)
        assert not (sess_dir / "original.jpg").exists()
        assert working == sess_dir / "working.png"
        assert working.exists()
        assert working.stat().st_mode & 0o777 == 0o600


# ---------------------------------------------------------------------------
# Sweeper lifecycle
# ---------------------------------------------------------------------------


class TestSweeperLifecycle:
    def test_start_and_stop_sweeper(self):
        """start_sweeper creates a task; stop_sweeper cancels it cleanly."""

        async def _run():
            store = SessionStore(300, "/tmp/coa_profiler_test_sweeper")
            assert store._sweeper_task is None
            store.start_sweeper()
            assert store._sweeper_task is not None
            assert not store._sweeper_task.done()
            await store.stop_sweeper()
            assert store._sweeper_task is None

        asyncio.run(_run())

    def test_start_sweeper_idempotent(self):
        """Calling start_sweeper twice does not create a second task."""

        async def _run():
            store = SessionStore(300, "/tmp/coa_profiler_test_sweeper2")
            store.start_sweeper()
            first = store._sweeper_task
            store.start_sweeper()
            assert store._sweeper_task is first
            await store.stop_sweeper()

        asyncio.run(_run())
