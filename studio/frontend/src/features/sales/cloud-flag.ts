// SPDX-License-Identifier: AGPL-3.0-only
// Tough Customer: build-time switch for the cloud-backed features (sign-in,
// balance, top-up). Off by default so the desktop ships with "coming soon"
// stubs; set VITE_TC_CLOUD_ENABLED=1 at build time once the cloud is live.

const env = import.meta.env as Record<string, string | undefined>;

export const TC_CLOUD_ENABLED = env.VITE_TC_CLOUD_ENABLED === "1";
export const TC_COMING_SOON_TEXT =
  "Coming soon: sign in with your Tough Customer account for pay-as-you-go access to the best models, with $5 of free credit to start.";
