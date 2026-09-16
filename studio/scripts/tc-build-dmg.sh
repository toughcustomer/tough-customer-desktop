#!/bin/bash
# Tough Customer: build the macOS app bundle and package it as a dmg without
# the Finder AppleScript step (Tauri's bundle_dmg.sh "make Finder stuff pretty"
# times out on machines where Finder automation isn't authorised).
#
#   studio/scripts/tc-build-dmg.sh              # ad-hoc signed, cloud stubbed
#   VITE_TC_CLOUD_ENABLED=1 APPLE_SIGNING_IDENTITY="Developer ID Application: …" studio/scripts/tc-build-dmg.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.cargo/bin:$PATH"
export APPLE_SIGNING_IDENTITY="${APPLE_SIGNING_IDENTITY:--}"
export VITE_TC_CLOUD_ENABLED="${VITE_TC_CLOUD_ENABLED:-0}"
# Updater artifacts are signed with the M1 minisign key when it is present.
if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ] && [ -f "$HOME/.tauri/toughcustomer-updater.key" ]; then
  export TAURI_SIGNING_PRIVATE_KEY="$(cat "$HOME/.tauri/toughcustomer-updater.key")"
  export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}"
fi

cd "$HERE"
npx tauri build --bundles app

BUNDLE="$HERE/src-tauri/target/release/bundle"
APP="$BUNDLE/macos/Tough Customer.app"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
ARCH="$(uname -m)"
OUT="$BUNDLE/dmg/Tough Customer_${VERSION}_${ARCH}.dmg"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ditto "$APP" "$STAGE/Tough Customer.app"
ln -s /Applications "$STAGE/Applications"
mkdir -p "$BUNDLE/dmg"
hdiutil create -volname "Tough Customer" -srcfolder "$STAGE" -ov -format UDZO "$OUT" >/dev/null
hdiutil verify "$OUT" >/dev/null
echo "built: $OUT ($(du -h "$OUT" | cut -f1))"
