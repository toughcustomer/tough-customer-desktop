// SPDX-License-Identifier: AGPL-3.0-only
// Tough Customer: device sign-in card for the Connections dialog.

import { Button } from "@/components/ui/button";
import {
  type ProviderAuthStatus,
  type TcSignInFlow,
  cancelTcSignInFlow,
  getTcSignInFlow,
  startTcSignIn,
  tcSignOut,
} from "@/features/chat/api/providers-api";
import { openLink } from "@/lib/open-link";
import { useEffect, useRef, useState } from "react";
import { refreshTcBalance } from "./balance-store";
import { TC_CLOUD_ENABLED, TC_COMING_SOON_TEXT } from "./cloud-flag";

interface Props {
  providerId: string | null;
  authStatus?: ProviderAuthStatus;
  onChanged: () => void | Promise<void>;
  ensureProvider?: () => Promise<string>;
}

export function ToughCustomerConnect({
  providerId,
  authStatus,
  onChanged,
  ensureProvider,
}: Props) {
  const [flow, setFlow] = useState<TcSignInFlow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [activeProviderId, setActiveProviderId] = useState(providerId);
  const [locallySignedOut, setLocallySignedOut] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (providerId) setActiveProviderId(providerId);
  }, [providerId]);

  useEffect(() => {
    if (!flow || flow.status !== "pending" || !activeProviderId) return;
    const timer = window.setInterval(() => {
      if (Date.now() >= flow.expires_at * 1000) {
        setFlow((current) =>
          current
            ? {
                ...current,
                status: "error",
                message: "Sign-in expired. Start again.",
              }
            : current,
        );
        return;
      }
      void getTcSignInFlow(activeProviderId, flow.flow_id)
        .then((next) => {
          if (!mounted.current) return;
          setFlow(next);
          if (next.status === "connected") {
            void refreshTcBalance();
            void onChanged();
          }
          if (next.status === "error")
            setError(next.message || "Sign-in failed.");
        })
        .catch(
          (cause) =>
            mounted.current &&
            setError(
              cause instanceof Error ? cause.message : "Sign-in failed.",
            ),
        );
    }, 2500);
    return () => window.clearInterval(timer);
  }, [flow, activeProviderId, onChanged]);

  async function start() {
    setBusy(true);
    setError("");
    setLocallySignedOut(false);
    try {
      const id = activeProviderId ?? (await ensureProvider?.());
      if (!id)
        throw new Error("Could not create the Tough Customer connection.");
      setActiveProviderId(id);
      const next = await startTcSignIn(id);
      setFlow(next);
      const url = next.verification_uri_complete || next.verification_uri;
      if (url) openLink(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!flow || !activeProviderId || flow.status !== "pending") return;
    setBusy(true);
    try {
      await cancelTcSignInFlow(activeProviderId, flow.flow_id);
      setFlow({ ...flow, status: "cancelled", message: "Sign-in cancelled." });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (!activeProviderId) return;
    setBusy(true);
    setError("");
    try {
      await tcSignOut(activeProviderId);
      setFlow(null);
      setLocallySignedOut(true);
      void refreshTcBalance();
      await onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-out failed.");
    } finally {
      setBusy(false);
    }
  }

  const connected =
    !locallySignedOut &&
    (authStatus === "connected" || flow?.status === "connected");
  const visibleError =
    error ||
    (flow?.status === "error" ? flow.message || "Sign-in failed." : "");

  if (!TC_CLOUD_ENABLED) {
    return (
      <section className="space-y-3 rounded-[8px] border border-border/70 bg-background/45 p-4">
        <div>
          <p className="text-sm font-medium">Tough Customer account</p>
          <p className="text-xs text-muted-foreground">{TC_COMING_SOON_TEXT}</p>
        </div>
        <Button type="button" size="sm" disabled={true}>
          Coming soon
        </Button>
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded-[8px] border border-border/70 bg-background/45 p-4">
      <div>
        <p className="text-sm font-medium">Tough Customer account</p>
        <p className="text-xs text-muted-foreground">
          {connected
            ? "Signed in. Model usage is billed in dollars from your Tough Customer balance."
            : authStatus === "reauthorization_required"
              ? "Your saved sign-in is no longer valid. Sign in again to continue."
              : "Approve this device in your browser. New accounts start with $5 of free credit."}
        </p>
      </div>
      {flow?.status === "pending" ? (
        <div
          data-reload-snapshot-sensitive={true}
          className="space-y-2 text-sm"
        >
          <p>Confirm this code in your browser:</p>
          <code className="block w-fit rounded bg-muted px-3 py-2 font-mono text-base">
            {flow.user_code}
          </code>
          <p className="text-xs text-muted-foreground">
            Expires {new Date(flow.expires_at * 1000).toLocaleTimeString()}.
          </p>
        </div>
      ) : null}
      {flow?.status === "cancelled" ? (
        <p className="text-xs text-muted-foreground">Sign-in cancelled.</p>
      ) : null}
      {visibleError ? (
        <p role="alert" className="text-xs text-destructive">
          {visibleError}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {connected ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void signOut()}
          >
            Sign out on this device
          </Button>
        ) : (
          <>
            <Button
              type="button"
              size="sm"
              disabled={busy || flow?.status === "pending"}
              onClick={() => void start()}
            >
              {authStatus === "reauthorization_required"
                ? "Sign in again"
                : "Sign in to Tough Customer"}
            </Button>
            {flow?.status === "pending" ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => void cancel()}
              >
                Cancel
              </Button>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}
