// SPDX-License-Identifier: AGPL-3.0-only
// Tough Customer: credit balance in the sidebar footer with a top-up action.

import { startTcCheckout } from "@/features/chat/api/providers-api";
import { openLink } from "@/lib/open-link";
import { cn } from "@/lib/utils";
import { useEffect } from "react";
import { toast } from "sonner";
import { formatMicros, refreshTcBalance, useTcBalance } from "./balance-store";
import { TC_CLOUD_ENABLED, TC_COMING_SOON_TEXT } from "./cloud-flag";

const DEFAULT_TOP_UP_URL = "https://toughcustomer.ai/billing";

export function TcBalancePill({ className }: { className?: string }) {
  const balance = useTcBalance();

  useEffect(() => {
    if (!TC_CLOUD_ENABLED) return;
    void refreshTcBalance();
    const timer = window.setInterval(() => void refreshTcBalance(), 5 * 60_000);
    return () => window.clearInterval(timer);
  }, []);

  async function topUp() {
    if (balance.providerId) {
      try {
        const { url } = await startTcCheckout(balance.providerId, "p10");
        if (url) {
          openLink(url);
          return;
        }
      } catch {
        // Fall through to the billing portal when Checkout isn't configured.
      }
    }
    openLink(balance.topUpUrl ?? DEFAULT_TOP_UP_URL);
  }

  if (!TC_CLOUD_ENABLED) {
    return (
      <button
        type="button"
        className={cn("text-left hover:underline", className)}
        onClick={() =>
          toast.info("Tough Customer Cloud — coming soon", {
            description: TC_COMING_SOON_TEXT,
          })
        }
      >
        Tough Customer · cloud coming soon
      </button>
    );
  }

  if (!balance.signedIn) {
    return (
      <button
        type="button"
        className={cn("text-left hover:underline", className)}
        onClick={() =>
          toast.info("Sign in to Tough Customer", {
            description: "Settings → Connections → Tough Customer → Sign in.",
          })
        }
      >
        Tough Customer · sign in
      </button>
    );
  }

  const low =
    balance.balanceMicros !== null && balance.balanceMicros <= 500_000;
  return (
    <button
      type="button"
      className={cn(
        "text-left hover:underline",
        low && "text-destructive",
        className,
      )}
      title={
        balance.lastRetailMicros !== null
          ? `Last turn cost ${formatMicros(balance.lastRetailMicros)}. Click to add credits.`
          : "Click to add credits."
      }
      onClick={() => void topUp()}
    >
      {balance.balanceMicros === null
        ? "Tough Customer"
        : `Balance ${formatMicros(balance.balanceMicros)}`}
      {balance.balanceMicros !== null && balance.balanceMicros <= 0
        ? " · add credits"
        : ""}
    </button>
  );
}
