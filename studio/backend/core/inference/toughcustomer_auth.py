# SPDX-License-Identifier: AGPL-3.0-only
# Tough Customer: device-authorization session for the first-class cloud provider.
#
# The cloud access token is saved as the provider's API key so the ordinary
# external-provider chat path sends it as a Bearer without modification; the
# refresh token lives in the encrypted credential store under its own kind and
# is rotated by the cloud on every refresh.

from __future__ import annotations

import asyncio
import json
import secrets
import socket
import time
from typing import Any

import httpx
import structlog

from core.inference.providers import get_provider_info
from storage import credential_secrets

logger = structlog.get_logger(__name__)

TC_SESSION_KIND = "toughcustomer_session"
PROVIDER_TYPE = "toughcustomer"
_REFRESH_SKEW_S = 60
_FLOW_TTL_S = 900

_flows: dict[str, dict[str, Any]] = {}


class ToughCustomerAuthError(Exception):
    pass


def cloud_base() -> str:
    info = get_provider_info(PROVIDER_TYPE) or {}
    return str(info.get("base_url") or "https://api.toughcustomer.ai/v1").rstrip("/")


# ── Session persistence ────────────────────────────────────────────────────


def load_session(provider_id: str) -> dict[str, Any] | None:
    raw = credential_secrets.get_secret(TC_SESSION_KIND, provider_id)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("refresh_token") else None


def save_session(provider_id: str, session: dict[str, Any]) -> None:
    credential_secrets.upsert_secret(TC_SESSION_KIND, provider_id, json.dumps(session, separators = (",", ":")))
    if session.get("access_token"):
        credential_secrets.save_provider_api_key(provider_id, str(session["access_token"]))


def delete_session(provider_id: str) -> None:
    credential_secrets.delete_secret(TC_SESSION_KIND, provider_id)
    try:
        credential_secrets.delete_provider_api_key(provider_id)
    except Exception:
        pass


def auth_status(provider_id: str) -> str:
    session = load_session(provider_id)
    if not session:
        return "disconnected"
    return "reauthorization_required" if session.get("reauthorization_required") else "connected"


def session_email(provider_id: str) -> str | None:
    session = load_session(provider_id)
    return str(session.get("email")) if session and session.get("email") else None


# ── Device flow ────────────────────────────────────────────────────────────


def _safe_flow(flow: dict[str, Any]) -> dict[str, Any]:
    return {
        "flow_id": flow["flow_id"],
        "status": flow["status"],
        "user_code": flow.get("user_code"),
        "verification_uri": flow.get("verification_uri"),
        "verification_uri_complete": flow.get("verification_uri_complete"),
        "expires_at": flow["expires_at"],
        "message": flow.get("message"),
    }


async def start_flow(provider_id: str, persist) -> dict[str, Any]:
    """Start a device grant at the cloud and poll it in the background.

    ``persist(session)`` is called on success inside the caller's credential
    write context so the background task can store secrets.
    """
    device_name = f"{socket.gethostname()} (Tough Customer desktop)"
    async with httpx.AsyncClient(timeout = 20) as client:
        try:
            res = await client.post(f"{cloud_base()}/auth/device", json = {"device_name": device_name})
        except httpx.HTTPError as exc:
            raise ToughCustomerAuthError(f"Could not reach Tough Customer Cloud: {exc}") from exc
    if res.status_code != 200:
        raise ToughCustomerAuthError(f"Tough Customer Cloud refused the sign-in request ({res.status_code}).")
    grant = res.json()

    for stale in [f for f in _flows.values() if f["provider_id"] == provider_id and f["status"] == "pending"]:
        stale["status"] = "cancelled"
        task = stale.get("task")
        if task:
            task.cancel()

    flow: dict[str, Any] = {
        "flow_id": secrets.token_urlsafe(16),
        "provider_id": provider_id,
        "status": "pending",
        "device_code": grant["device_code"],
        "user_code": grant["user_code"],
        "verification_uri": grant.get("verification_uri"),
        "verification_uri_complete": grant.get("verification_uri_complete"),
        "interval": max(int(grant.get("interval", 3)), 2),
        "expires_at": time.time() + min(int(grant.get("expires_in", _FLOW_TTL_S)), _FLOW_TTL_S),
        "message": None,
    }
    _flows[flow["flow_id"]] = flow
    flow["task"] = asyncio.create_task(_poll(flow, persist))
    return _safe_flow(flow)


async def _poll(flow: dict[str, Any], persist) -> None:
    interval = flow["interval"]
    try:
        async with httpx.AsyncClient(timeout = 20) as client:
            while flow["status"] == "pending":
                await asyncio.sleep(interval)
                if time.time() >= flow["expires_at"]:
                    flow["status"] = "error"
                    flow["message"] = "Sign-in expired. Start again."
                    return
                try:
                    res = await client.post(
                        f"{cloud_base()}/auth/token",
                        json = {
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                            "device_code": flow["device_code"],
                        },
                    )
                except httpx.HTTPError:
                    continue
                if res.status_code == 200:
                    token = res.json()
                    session = _session_from_token(token)
                    # Learn the account email for the UI; best effort.
                    try:
                        me = await client.get(f"{cloud_base()}/account/me", headers = {"authorization": f"Bearer {session['access_token']}"})
                        if me.status_code == 200:
                            session["email"] = me.json().get("email")
                            session["account_id"] = me.json().get("id")
                    except httpx.HTTPError:
                        pass
                    persist(session)
                    flow["status"] = "connected"
                    return
                body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                err = body.get("error")
                if err == "authorization_pending":
                    continue
                if err == "slow_down":
                    interval += 5
                    continue
                flow["status"] = "error"
                flow["message"] = body.get("error_description") or f"Sign-in failed ({err or res.status_code})."
                return
    except asyncio.CancelledError:
        flow["status"] = "cancelled"
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("toughcustomer.poll_failed", error = str(exc))
        flow["status"] = "error"
        flow["message"] = "Sign-in failed. Please try again."


def get_flow(provider_id: str, flow_id: str) -> dict[str, Any]:
    flow = _flows.get(flow_id)
    if not flow or flow["provider_id"] != provider_id:
        raise ToughCustomerAuthError("Sign-in flow not found.")
    return _safe_flow(flow)


def cancel_flow(provider_id: str, flow_id: str) -> None:
    flow = _flows.get(flow_id)
    if not flow or flow["provider_id"] != provider_id:
        return
    flow["status"] = "cancelled"
    task = flow.get("task")
    if task:
        task.cancel()


def _session_from_token(token: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "expires_at": time.time() + float(token.get("expires_in", 900)),
    }


# ── Token lifecycle ────────────────────────────────────────────────────────


async def ensure_access_token(provider_id: str) -> str | None:
    """Return a valid access token, refreshing (and re-saving the provider key) when near expiry."""
    session = load_session(provider_id)
    if not session or session.get("reauthorization_required"):
        return None
    if float(session.get("expires_at", 0)) - _REFRESH_SKEW_S > time.time():
        return str(session["access_token"])
    async with httpx.AsyncClient(timeout = 20) as client:
        try:
            res = await client.post(
                f"{cloud_base()}/auth/token",
                json = {"grant_type": "refresh_token", "refresh_token": session["refresh_token"]},
            )
        except httpx.HTTPError:
            # Network blip: let the request try with the current token; the cloud
            # answers reauth_required if it is truly dead.
            return str(session["access_token"])
    if res.status_code != 200:
        session["reauthorization_required"] = True
        credential_secrets.upsert_secret(TC_SESSION_KIND, provider_id, json.dumps(session, separators = (",", ":")))
        try:
            credential_secrets.delete_provider_api_key(provider_id)
        except Exception:
            pass
        return None
    refreshed = _session_from_token(res.json())
    refreshed["email"] = session.get("email")
    refreshed["account_id"] = session.get("account_id")
    save_session(provider_id, refreshed)
    return str(refreshed["access_token"])


async def cloud_request(provider_id: str, method: str, path: str, json_body: Any = None) -> tuple[int, Any]:
    token = await ensure_access_token(provider_id)
    if not token:
        return 401, {"error": {"code": "reauth_required", "message": "Please sign in to Tough Customer again."}}
    async with httpx.AsyncClient(timeout = 30) as client:
        try:
            res = await client.request(method, f"{cloud_base()}{path}", json = json_body, headers = {"authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            return 502, {"error": {"code": "unreachable", "message": f"Could not reach Tough Customer Cloud: {exc}"}}
    try:
        body = res.json()
    except Exception:
        body = {"error": {"code": "bad_response", "message": res.text[:200]}}
    return res.status_code, body


async def logout(provider_id: str) -> None:
    session = load_session(provider_id)
    if session and session.get("access_token"):
        async with httpx.AsyncClient(timeout = 10) as client:
            try:
                await client.post(f"{cloud_base()}/auth/logout", headers = {"authorization": f"Bearer {session['access_token']}"})
            except httpx.HTTPError:
                pass
    delete_session(provider_id)
