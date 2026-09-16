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

## What M2 changed (sell model access)

| Area | Change |
| --- | --- |
| Auth kind | `toughcustomer_device` (registry + `models/providers.py` Literal + frontend `ProviderAuthKind`/`isManagedAuthKind`) — no API-key field; the backend holds the credential |
| `core/inference/toughcustomer_auth.py` | Device flow against the cloud (`/v1/auth/device` → background poll → tokens), session in the encrypted credential store (`toughcustomer_session` kind), the access token saved as the provider's API key so the unchanged proxy path sends it as Bearer; `ensure_access_token` refreshes near expiry (refresh tokens rotate) and flags `reauthorization_required` when the cloud rejects the refresh |
| `routes/toughcustomer.py` → `/api/toughcustomer/providers/{id}/…` | `auth/start`, `auth/flows/{flow}`, `auth/status`, `DELETE auth` (sign out), `account/balance`, `account/usage`, `billing/checkout` |
| `routes/inference.py` | one hook before saved-key resolution: refresh the Tough Customer token |
| `routes/providers.py` | `auth_kind`/`auth_status` from the registry + Tough Customer session |
| Frontend `features/sales/` | `tough-customer-connect.tsx` (sign-in card in Connections), `balance-store.ts` (balance fed by the usage chunk's `usage.toughcustomer`), `balance-pill.tsx` (sidebar footer: balance, last-turn cost, top-up via Stripe Checkout) |
| `chat-api.ts` / `chat-adapter.ts` | `StreamProviderError` carries upstream `code`; native toasts for `credit_exhausted` (Add credits action), `reauth_required`, `rate_limited` |

Verified end to end against the real cloud (`tough-customer-cloud`, mock model): device sign-in → balance → paid streamed turns with retail cost + balance → `credit_exhausted` at zero → sign-out → `reauth_required`.

Not yet: Tough Customer auto-selected as the default model after sign-in, and sign-in inside the Tauri onboarding window (today it lives in Settings → Connections and the sidebar pill points there).

## Skin, logo, and "coming soon" stubs

- **Brand**: colors and mark pulled from toughcustomer.ai — purple `#9333ea`
  (light) / `#a855f7` (dark), `#7e22ce`→`#9333ea` gradient on the app icon; the
  speech-bubble wordmark is painted white via a luminance ink mask so the
  lettering survives on the purple ground. Theme tokens edited in
  `studio/frontend/src/index.css` (`--primary`, `--secondary`, `--chart-1`,
  `--sidebar-primary`, light + dark). Site font is Outfit; not bundled yet.
- **Assets**: `studio/src-tauri/icons/*` regenerated with `tauri icon` from a
  1024px composite; `frontend/public/tc-mark.png` (sidebar), `favicon.png`,
  `tc-wordmark-{dark,light}.png` for later use. Source logo:
  `https://toughcustomer.ai/src/logo.png`.
- **Full de-brand (Sept 16)**: the Tauri startup/installer screen
  (`components/tauri/startup-screen.tsx`) now shows the Tough Customer mark +
  wordmark; all 45 mascot/logo images under `public/` (Sloth emojis, sticker,
  unsloth-gem, rounded, circle-logo-small, logotext, colab banner) are
  overwritten in place with the brand mark at their original dimensions (same
  filenames, so no code churn); `unsloth.ico` is the brand icon; the dmg
  background is a purple brand tile; every standalone "Unsloth" word in
  frontend/backend/Rust/installer strings became "Tough Customer" (guarded:
  license headers, `X-Unsloth-*` wire headers, the `Unsloth UI Backend`
  health-probe token, and the library's `Unsloth:` log prefix are untouched);
  lowercase CLI mentions (`unsloth studio update`, `unsloth start`,
  `@unsloth`) were rephrased; the default admin username is `toughcustomer`
  (backend `DEFAULT_ADMIN_USERNAME` + frontend `HIDDEN_LOGIN_USERNAME`); the
  shipped binary is `tough-customer` (`mainBinaryName`); the gradient-
  checkpointing option labelled "Unsloth" reads "Optimized"; HF-org avatars
  no longer special-case the `unsloth` org. The commercial **Hellix** font
  (licensed to Unsloth, not us) is deleted and `--font-heading` is
  **Outfit** (brand font, via `@fontsource-variable/outfit`).
  Still Unsloth by design: the Hugging Face repo ids in the Model Hub
  (`unsloth/…-GGUF`) — those are the real upstream model repos; swapping the
  curated catalog to other publishers is a product decision.
- **Trademark sweep**: `components/mascot-img.tsx` renders the brand mark in
  every mascot slot (login, greetings, overlays) and the bundled fallback
  `assets/mascot-fallback.webp` is the mark too; document title default and
  every capitalised "Unsloth" product mention in `i18n/locales/*.ts` now read
  "Tough Customer" (license headers and the lowercase `unsloth` CLI/username
  references are untouched — they are real command names).
- **Cloud stubs**: `features/sales/cloud-flag.ts` — `VITE_TC_CLOUD_ENABLED`
  (build-time, default off). Off → the Connections card and the sidebar pill
  show "coming soon" and make no cloud calls; the M2 code is intact behind the
  flag. Build with `VITE_TC_CLOUD_ENABLED=1` once the cloud is live.
- **Build**: `studio/scripts/tc-build-dmg.sh` → `studio/src-tauri/target/release/bundle/dmg/Tough Customer_<version>_<arch>.dmg`.
  It runs `tauri build --bundles app` then packages the dmg with `hdiutil`
  directly, because Tauri's `bundle_dmg.sh` Finder-AppleScript step times out
  ("AppleEvent timed out (-1712)") when Finder automation isn't authorised for
  the terminal. Ad-hoc signed by default: internal use (right-click → Open);
  Developer ID signing + notarization is M4. Version comes from
  `tauri.conf.json` (`0.1.0`), not upstream's Cargo version.

## Installer: how the desktop gets *this* backend

The Tauri app installs the Python runtime at first launch by running the
bundled `install.sh` (`Resources/install.sh`, mapped in
`tauri.macos.conf.json`). Upstream's script installs the **PyPI `unsloth`**
package into `~/.unsloth/studio`, which is why the first Tough Customer build
installed Unsloth's backend and then reported "binary not found" (the Rust
side looks under `~/.toughcustomer/studio`). Fixed by:

- `install.sh` / `install.ps1` / `studio/setup.sh` / `setup.ps1` default root
  → `~/.toughcustomer/studio` (Rust strips `UNSLOTH_STUDIO_HOME` in Tauri
  mode, so the script default is what counts); LaunchAgent label
  `ai.toughcustomer.studio`; banners rebranded.
- `tc-build-dmg.sh` builds this fork as a wheel (`pip wheel --no-deps` →
  `dist-backend/unsloth-<ver>-py3-none-any.whl`, ~30 MB; the package name
  stays `unsloth` because the whole runtime imports it) and the macOS/Linux
  Tauri configs bundle it at `Resources/backend/`.
- `install.rs` passes `TOUGHCUSTOMER_BACKEND_DIR` (that resource dir) to the
  installer; after the base install, `install.sh` overlays the wheel with
  `uv pip install --no-deps --reinstall-package unsloth <wheel>` — the same
  shape as upstream's `--local` editable overlay. The base PyPI install is kept
  because it resolves the entire dependency stack (torch, MLX, unsloth-zoo…).
- Default backend port is **8890** (scan 8890–8910) so Tough Customer can run
  next to an Unsloth install on 8888.

Known leftovers: `llama.cpp`/`whisper.cpp` prebuilts still download from
`unslothai` GitHub releases; the installer's `.unsloth-studio-owned` marker
file name and docs.unsloth.ai links in AMD warnings are internal.

## Local development

```sh
# one-time
/opt/homebrew/bin/python3.11 -m venv .venv-tc
.venv-tc/bin/pip install -r studio/backend/requirements/studio.txt
.venv-tc/bin/pip install --no-deps -r studio/backend/requirements/no-torch-runtime.txt
.venv-tc/bin/pip install --no-deps -e .
npm ci --prefix studio/frontend

# real cloud in dev mode (from ../tough-customer-cloud; mock model, built-in approval page)
PORT=4141 TC_PUBLIC_URL=http://127.0.0.1:4141 TC_MOCK_MODEL=1 TC_DEV_APPROVE=1 TC_DEV_TOPUP=1 npm run dev

# backend against it, with an isolated runtime home
UNSLOTH_STUDIO_HOME=/tmp/tc-home \
TOUGHCUSTOMER_CLOUD_URL=http://127.0.0.1:4141/v1 \
  .venv-tc/bin/python studio/backend/run.py --host 127.0.0.1 --port 8899
# bootstrap password: /tmp/tc-home/auth/.bootstrap_password (must be changed once via /api/auth/change-password)

# desktop shell
cd studio/src-tauri && cargo build      # needs studio/frontend/dist (npx vite build)
```

Updater signing key: `~/.tauri/toughcustomer-updater.key` (private, keep out of git);
public key is in `tauri.conf.json`. Set `TAURI_SIGNING_PRIVATE_KEY_PATH` when building releases.
