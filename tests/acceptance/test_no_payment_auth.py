"""AC-013: no auth, payment, or account code — grep + AST + behavioral probes."""

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "coa_profiler"

GREP_PATTERN = re.compile(
    r"(stripe|paypal|auth_login|user_account|password_hash|billing|subscription)",
    re.IGNORECASE,
)
BANNED_MODULE_ROOTS = {"stripe", "paypal", "braintree", "square", "flask_login", "django"}


def test_grep_scan_clean():
    hits = []
    for path in SRC.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if GREP_PATTERN.search(line):
                hits.append(f"{path}:{lineno}: {line.strip()}")
    assert hits == [], "\n".join(hits)


def test_ast_scan_clean():
    hits = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in BANNED_MODULE_ROOTS:
                        hits.append(f"{path}: import {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] in BANNED_MODULE_ROOTS
            ):
                hits.append(f"{path}: from {node.module}")
    assert hits == [], "\n".join(hits)


def test_behavioral_probes_return_404(client):
    for path in (
        "/login",
        "/register",
        "/checkout",
        "/admin",
        "/accounts",
        "/billing",
        "/docs",
        "/redoc",
        "/openapi.json",
    ):
        assert client.get(path).status_code == 404, path
