// SPDX-License-Identifier: AGPL-3.0-only
// Tough Customer: live credit balance shared between the chat stream and the UI.

import {
  getTcBalance,
  listProviderConfigs,
} from "@/features/chat/api/providers-api";
import { useSyncExternalStore } from "react";

export interface TcUsageExtension {
  request_id?: string;
  retail_cost_micros?: number;
  balance_micros?: number;
  cost_authority?: string;
  top_up_url?: string;
}

export interface TcBalanceState {
  providerId: string | null;
  signedIn: boolean;
  balanceMicros: number | null;
  lastRetailMicros: number | null;
  topUpUrl: string | null;
  loadedAt: number | null;
}

let state: TcBalanceState = {
  providerId: null,
  signedIn: false,
  balanceMicros: null,
  lastRetailMicros: null,
  topUpUrl: null,
  loadedAt: null,
};
const listeners = new Set<() => void>();

function set(patch: Partial<TcBalanceState>): void {
  state = { ...state, ...patch };
  for (const l of listeners) l();
}

export function formatMicros(micros: number): string {
  const dollars = micros / 1_000_000;
  if (Math.abs(dollars) >= 1) return `$${dollars.toFixed(2)}`;
  return `$${dollars.toFixed(4).replace(/0+$/, "").replace(/\.$/, ".00")}`;
}

/** Called by the chat adapter when a Tough Customer usage chunk arrives. */
export function publishTcUsage(
  usage: TcUsageExtension | undefined | null,
): void {
  if (!usage || typeof usage !== "object") return;
  set({
    balanceMicros:
      typeof usage.balance_micros === "number"
        ? usage.balance_micros
        : state.balanceMicros,
    lastRetailMicros:
      typeof usage.retail_cost_micros === "number"
        ? usage.retail_cost_micros
        : state.lastRetailMicros,
    topUpUrl: usage.top_up_url ?? state.topUpUrl,
    signedIn: true,
    loadedAt: Date.now(),
  });
}

/** Find the Tough Customer provider and fetch its balance. Safe to call often. */
export async function refreshTcBalance(): Promise<void> {
  try {
    const configs = await listProviderConfigs();
    const tc = configs.find((c) => c.provider_type === "toughcustomer");
    if (!tc) {
      set({
        providerId: null,
        signedIn: false,
        balanceMicros: null,
        loadedAt: Date.now(),
      });
      return;
    }
    if (tc.auth_status !== "connected") {
      set({
        providerId: tc.id,
        signedIn: false,
        balanceMicros: null,
        loadedAt: Date.now(),
      });
      return;
    }
    const balance = await getTcBalance(tc.id);
    set({
      providerId: tc.id,
      signedIn: true,
      balanceMicros: balance.balance_micros,
      topUpUrl: balance.top_up_url ?? state.topUpUrl,
      loadedAt: Date.now(),
    });
  } catch {
    set({ loadedAt: Date.now() });
  }
}

export function useTcBalance(): TcBalanceState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}
