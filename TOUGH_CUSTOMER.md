# Tough Customer Desktop — fork notes

This repository is a **vendored fork** of [unslothai/unsloth](https://github.com/unslothai/unsloth)
(pinned at upstream commit `5eef8a7`, branch `upstream-main`). Product work lives on
`tc-main`. The `studio/` app is AGPL-3.0 (see `studio/LICENSE.AGPL-3.0`); this fork is
published under the same license. Cloud services are a separate private repository
and contain no code from this tree.

## Fork strategy

- Track upstream on `upstream-main`; merge security/runtime fixes selectively on a
  release cadence. Do not rebase product UX onto every upstream UI change.
- Keep internal Unsloth names (crate `unsloth-studio`, `unsloth_studio` venv,
  `UNSLOTH_STUDIO_HOME`) where users never see them.
- New product code goes in isolated modules:
  - `studio/frontend/src/features/sales/` (M3)
  - `studio/backend/routes/toughcustomer*.py` → `/api/toughcustomer/*` (M2+)

## What M1 changed (fork feasibility)

| Area | Change |
| --- | --- |
| `studio/src-tauri/tauri.conf.json` | productName/identifier `ai.toughcustomer.desktop`, window title, deep-link scheme `toughcustomer://`, updater pubkey + endpoint (`toughcustomer/tough-customer-desktop` releases), bundle metadata |
| Runtime root | `~/.toughcustomer/studio` instead of `~/.unsloth/studio` — Rust (`".unsloth"` → `".toughcustomer"` across `src-tauri/src`), Python fallback in `utils/paths/storage_roots.py`, `run.py`, `main.py`; diagnostics redaction regex covers both |
| Provider | `toughcustomer` entry in `core/inference/providers.py`: fixed base URL (`TOUGHCUSTOMER_CLOUD_URL` env override for dev), `base_url_editable: false`, `model_ids_editable: false`, `model_list_mode: remote` |
| Error passthrough | `_error_sse_line` in `core/inference/external_provider.py` preserves upstream `credit_exhausted`, `rate_limited`, `reauth_required` codes (HTTP status moves to `error.status`) — test: `backend/tests/test_toughcustomer_error_passthrough.py` |
| Branding | Sidebar wordmark + logo (`public/tc-logo.svg`), provider logo (`public/provider-logos/toughcustomer.svg`) |

## Local development

```sh
# one-time
/opt/homebrew/bin/python3.11 -m venv .venv-tc
.venv-tc/bin/pip install -r studio/backend/requirements/studio.txt
.venv-tc/bin/pip install --no-deps -r studio/backend/requirements/no-torch-runtime.txt
.venv-tc/bin/pip install --no-deps -e .
npm ci --prefix studio/frontend

# mock cloud (from ../tough-customer-cloud)
node mock/openai-mock.mjs                       # :4141

# backend against the mock, with an isolated runtime home
UNSLOTH_STUDIO_HOME=/tmp/tc-home \
TOUGHCUSTOMER_CLOUD_URL=http://127.0.0.1:4141/v1 \
  .venv-tc/bin/python studio/backend/run.py --host 127.0.0.1 --port 8899
# bootstrap password: /tmp/tc-home/auth/.bootstrap_password (must be changed once via /api/auth/change-password)

# desktop shell
cd studio/src-tauri && cargo build      # needs studio/frontend/dist (npx vite build)
```

Updater signing key: `~/.tauri/toughcustomer-updater.key` (private, keep out of git);
public key is in `tauri.conf.json`. Set `TAURI_SIGNING_PRIVATE_KEY_PATH` when building releases.
