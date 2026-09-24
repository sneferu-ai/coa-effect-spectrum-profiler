"""Regression contracts for the production build and proxy topology."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_docker_context_is_allowlisted():
    rules = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert rules[0] == "**"
    assert "!src/**" in rules
    assert not any(rule in {"!.env", "!.git", "!.venv", "!tests/**"} for rule in rules)


def test_production_version_has_no_silent_default():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ARG COA_PROFILER_VERSION\n" in dockerfile
    assert "ARG COA_PROFILER_VERSION=" not in dockerfile
    assert dockerfile.count("COA_PROFILER_VERSION build arg is required") == 1
    assert compose.count("${COA_PROFILER_VERSION:?") == 2


def test_compose_keeps_proxy_boundary_and_tmpfs_bounded():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:8080:8080"' in compose
    assert 'FORWARDED_ALLOW_IPS: "${FORWARDED_ALLOW_IPS:-*}"' in compose
    assert "/tmp:size=512m,mode=1777" in compose


def test_documented_proxy_timeout_encloses_route_but_not_server():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    routes = (ROOT / "src/coa_profiler/web/routes.py").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "proxy_read_timeout 115s;" in readme
    assert "110s application guard < 115s proxy read < 120s Gunicorn timeout" in readme
    assert "client_body_timeout 15s;" in readme
    assert "access_log off;" in readme
    assert "client_body_buffer_size 16m;" in readme
    assert "client_body_temp_path /var/lib/nginx/body 1 2;" in readme
    assert "tmpfs /var/lib/nginx/body 256m,mode=0700" in readme
    assert "proxy_request_buffering on;" in readme
    assert "location = /feedback" in readme
    assert "client_max_body_size 4k;" in readme

    proxy_timeout = int(re.search(r"proxy_read_timeout (\d+)s;", readme).group(1))
    route_timeout = float(re.search(r"PROCESSING_TIMEOUT_S = ([\d.]+)", routes).group(1))
    server_timeout = int(re.search(r'"--timeout", "(\d+)"', dockerfile).group(1))
    assert route_timeout < proxy_timeout < server_timeout
