# SPDX-License-Identifier: AGPL-3.0-only
# Tough Customer: thin local routes (/api/toughcustomer/*) in front of the private cloud.

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.authentication import authenticated_via_api_key, get_current_credential
from core.inference import toughcustomer_auth as tc_auth
from routes.provider_credentials import current_credential_write, require_ui_session
from storage import credential_secrets, providers_db

router = APIRouter()
logger = structlog.get_logger(__name__)


class CheckoutRequest(BaseModel):
    pack: str = Field(..., min_length = 1, max_length = 16)


def _provider(provider_id: str) -> dict:
    row = providers_db.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code = 404, detail = "Provider not found")
    if row["provider_type"] != tc_auth.PROVIDER_TYPE:
        raise HTTPException(status_code = 400, detail = "This provider is not Tough Customer.")
    return row


def _forward(status: int, body: Any):
    if status >= 400:
        detail = body.get("error", {}).get("message") if isinstance(body, dict) else None
        raise HTTPException(status_code = status if status in (401, 402, 403, 404, 429) else 502, detail = detail or "Tough Customer Cloud request failed.")
    return body


@router.post("/providers/{provider_id}/auth/start")
async def start_sign_in(
    provider_id: str,
    via_api_key: bool = Depends(authenticated_via_api_key),
    credential: tuple = Depends(get_current_credential),
):
    require_ui_session(via_api_key)
    _provider(provider_id)

    def persist(session: dict) -> None:
        # The first secret ever written creates the installation encryption key in
        # auth.db; do that before the generation guard takes its immediate write
        # lock on the same database, or the two connections deadlock.
        credential_secrets.get_or_create_credential_encryption_key()
        with current_credential_write(credential):
            tc_auth.save_session(provider_id, session)

    try:
        return await tc_auth.start_flow(provider_id, persist)
    except tc_auth.ToughCustomerAuthError as exc:
        raise HTTPException(status_code = 502, detail = str(exc)) from exc


@router.get("/providers/{provider_id}/auth/flows/{flow_id}")
async def get_sign_in_flow(provider_id: str, flow_id: str, via_api_key: bool = Depends(authenticated_via_api_key)):
    require_ui_session(via_api_key)
    try:
        return tc_auth.get_flow(provider_id, flow_id)
    except tc_auth.ToughCustomerAuthError as exc:
        raise HTTPException(status_code = 404, detail = str(exc)) from exc


@router.delete("/providers/{provider_id}/auth/flows/{flow_id}", status_code = 204)
async def cancel_sign_in_flow(provider_id: str, flow_id: str, via_api_key: bool = Depends(authenticated_via_api_key)):
    require_ui_session(via_api_key)
    tc_auth.cancel_flow(provider_id, flow_id)
    return None


@router.get("/providers/{provider_id}/auth/status")
async def sign_in_status(provider_id: str, via_api_key: bool = Depends(authenticated_via_api_key)):
    require_ui_session(via_api_key)
    _provider(provider_id)
    return {"status": tc_auth.auth_status(provider_id), "email": tc_auth.session_email(provider_id)}


@router.delete("/providers/{provider_id}/auth", status_code = 204)
async def sign_out(
    provider_id: str,
    via_api_key: bool = Depends(authenticated_via_api_key),
    credential: tuple = Depends(get_current_credential),
):
    require_ui_session(via_api_key)
    _provider(provider_id)
    with current_credential_write(credential):
        await tc_auth.logout(provider_id)
    return None


@router.get("/providers/{provider_id}/account/balance")
async def account_balance(provider_id: str, via_api_key: bool = Depends(authenticated_via_api_key)):
    require_ui_session(via_api_key)
    _provider(provider_id)
    status, body = await tc_auth.cloud_request(provider_id, "GET", "/account/balance")
    return _forward(status, body)


@router.get("/providers/{provider_id}/account/usage")
async def account_usage(provider_id: str, via_api_key: bool = Depends(authenticated_via_api_key)):
    require_ui_session(via_api_key)
    _provider(provider_id)
    status, body = await tc_auth.cloud_request(provider_id, "GET", "/account/usage")
    return _forward(status, body)


@router.post("/providers/{provider_id}/billing/checkout")
async def billing_checkout(provider_id: str, payload: CheckoutRequest, via_api_key: bool = Depends(authenticated_via_api_key)):
    require_ui_session(via_api_key)
    _provider(provider_id)
    status, body = await tc_auth.cloud_request(provider_id, "POST", "/billing/checkout", {"pack": payload.pack})
    return _forward(status, body)
