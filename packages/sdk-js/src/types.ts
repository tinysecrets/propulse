// SPDX-License-Identifier: Apache-2.0
export type Priority = "low" | "normal" | "high" | "urgent";

export interface ProPulseOptions {
  key: string;
  secret?: string;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  protocolVersion?: number;
}

export interface DeviceState {
  battery?: number;
  charging?: boolean;
  network?: "any" | "wifi" | "cellular" | "none";
  screen_on?: boolean;
  locale?: string;
  timezone?: string;
}

export type Trigger =
  | { kind: "time"; every_seconds?: number; at?: number }
  | { kind: "signal"; key: string; threshold?: number }
  | {
      kind: "device_state";
      battery_below?: number;
      charging?: boolean;
      network?: DeviceState["network"];
    }
  | { kind: "compound"; op: "and" | "or" | "n_of_m"; n: number; window_seconds: number };

export interface SignalResult {
  accepted: boolean;
  pulse_run_id: string;
  state: string;
  next_poll_in: number;
  upgrade_url: string;
  quota: { limit: number; used: number; remaining: number; plan: string };
}

export interface Plan {
  id: string;
  name: string;
  price_usd: number;
  monthly_pulses: number;
  features: string[];
  overage_allowed: boolean;
}
