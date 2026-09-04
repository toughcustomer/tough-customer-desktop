# SPDX-License-Identifier: AGPL-3.0-only
# Tough Customer: upstream actionable error codes must survive the SSE error
# mapping so the desktop can render native actions (top up, sign in, back off).

from pathlib import Path
import importlib.util
import json
import sys

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_EXTERNAL_PROVIDER_PATH = (
    Path(__file__).resolve().parent.parent / "core/inference/external_provider.py"
)


def _load_external_provider_module():
    spec = importlib.util.spec_from_file_location(
        "external_provider_under_test",
        _EXTERNAL_PROVIDER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse(line: str) -> dict:
    assert line.startswith("data: ")
    return json.loads(line[len("data: "):])["error"]


def test_credit_exhausted_code_is_preserved():
    ep = _load_external_provider_module()
    body = json.dumps({"error": {"code": "credit_exhausted", "message": "Add credits to continue."}})
    error = _parse(ep._error_sse_line(402, body, "toughcustomer"))
    assert error["code"] == "credit_exhausted"
    assert error["status"] == "402"
    assert error["type"] == "provider_error"
    assert "Add credits" in error["message"]


def test_reauth_and_rate_limited_are_preserved_with_retry_after():
    ep = _load_external_provider_module()
    reauth = _parse(ep._error_sse_line(
        401, json.dumps({"error": {"code": "reauth_required", "message": "Sign in again."}}), "toughcustomer",
    ))
    assert reauth["code"] == "reauth_required"

    rate = _parse(ep._error_sse_line(
        429, json.dumps({"error": {"code": "rate_limited", "message": "Slow down."}}), "toughcustomer", "5",
    ))
    assert rate["code"] == "rate_limited"
    assert rate["retry_after"] == "5"


def test_unknown_codes_keep_upstream_status_behaviour():
    ep = _load_external_provider_module()
    body = json.dumps({"error": {"code": "invalid_api_key", "message": "bad key"}})
    error = _parse(ep._error_sse_line(401, body, "openai"))
    assert error["code"] == "401"
    assert "status" not in error

    plain = _parse(ep._error_sse_line(500, "<html>oops</html>", "openai"))
    assert plain["code"] == "500"
