// SPDX-License-Identifier: Apache-2.0
import { newNonce, sign } from "./sign.js";
import { PROTOCOL_VERSION, VERSION } from "./version.js";
import type { DeviceState, Plan, ProPulseOptions, SignalResult, Trigger } from "./types.js";

export class ProPulseError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly body: unknown = null,
  ) {
    super(message);
    this.name = "ProPulseError";
  }
}

export class QuotaExceededError extends ProPulseError {
  constructor(
    message: string,
    readonly upgradeUrl: string,
    readonly limit: number,
    readonly used: number,
  ) {
    super(message, 429, "quota_exceeded");
    this.name = "QuotaExceededError";
  }
}

/**
 * ProPulse client.
 *
 * Two lines:
 * ```ts
 * const pp = new ProPulse({ key: process.env.PP_PUB_KEY!, secret: process.env.PP_SECRET! });
 * await pp.signal("cart_idle", { install_id: "ins_1" });
 * ```
 */
export class ProPulse {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;
  private readonly timeoutMs: number;

  constructor(private readonly options: ProPulseOptions) {
    if (!options.key) throw new ProPulseError("options.key is required", 0, "config");
    this.baseUrl = (options.baseUrl ?? "https://api.propulse.wah-lah.com").replace(/\/$/, "");
    this.fetcher = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
    this.timeoutMs = options.timeoutMs ?? 15_000;
  }

  async signal(
    pulse: string,
    opts: { install_id: string; trigger?: Trigger; device_state?: DeviceState } = {
      install_id: "server",
    },
  ): Promise<SignalResult> {
    const body = JSON.stringify({
      pulse,
      install_id: opts.install_id,
      trigger: opts.trigger ?? { kind: "signal", key: pulse },
      device_state: opts.device_state ?? {},
      client_ts: Date.now() / 1000,
    });
    return this.request<SignalResult>("POST", "/v1/pulses:signal", body);
  }

  async registerDevice(opts: {
    install_id: string;
    platform?: "web" | "server";
    app_version?: string;
  }): Promise<{ device_id: string; next_poll_in: number }> {
    const body = JSON.stringify({
      install_id: opts.install_id,
      platform: opts.platform ?? "server",
      app_version: opts.app_version ?? "0",
      sdk_version: VERSION,
    });
    return this.request("POST", "/v1/devices/register", body);
  }

  async ack(runId: string, channel = "web"): Promise<{ ok: boolean }> {
    const body = JSON.stringify({ run_id: runId, delivered_at: Date.now() / 1000, channel });
    return this.request("POST", "/v1/pulses/ack", body);
  }

  async createPulse(input: {
    key: string;
    name?: string;
    trigger: Trigger;
    action?: Record<string, unknown>;
    policy?: Record<string, unknown>;
  }): Promise<{ id: string; state: string }> {
    return this.request("POST", "/v1/pulses", JSON.stringify(input));
  }

  async entitlements(): Promise<Record<string, unknown>> {
    return this.request("GET", "/v1/billing/entitlements", "");
  }

  async plans(): Promise<{ plans: Plan[] }> {
    return this.request("GET", "/v1/billing/plans", "");
  }

  /** Upgrade URL for a tenant hitting the free tier. */
  async upgradeUrl(plan = "pro"): Promise<string> {
    const res = await this.request<{ url: string }>(
      "POST",
      "/v1/billing/checkout",
      JSON.stringify({ plan }),
    );
    return res.url;
  }

  private async request<T>(method: string, path: string, body: string): Promise<T> {
    const ts = Math.floor(Date.now() / 1000).toString();
    const nonce = newNonce();
    const headers: Record<string, string> = {
      "x-pp-key": this.options.key,
      "x-pp-ts": ts,
      "x-pp-nonce": nonce,
      "x-pp-protocol": String(this.options.protocolVersion ?? PROTOCOL_VERSION),
      "user-agent": `wah-lah-propulse-js/${VERSION}`,
      "idempotency-key": `${method}:${path}:${ts}:${nonce}`,
    };

    if (body) headers["content-type"] = "application/json";
    if (this.options.secret) {
      headers["x-pp-sig"] = sign(this.options.secret, ts, nonce, body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: body || undefined,
        signal: controller.signal,
      });

      const text = await response.text();
      const parsed = text ? JSON.parse(text) : {};

      if (response.status === 429) {
        const upgrade = (parsed.upgrade_url as string) ?? response.headers.get("x-pp-upgrade-url") ?? "";
        if (upgrade) {
          throw new QuotaExceededError(
            parsed.detail ?? "quota exceeded",
            upgrade,
            parsed.limit ?? 0,
            parsed.used ?? 0,
          );
        }
      }
      if (!response.ok) {
        throw new ProPulseError(
          parsed.detail ?? response.statusText,
          response.status,
          parsed.title ?? "error",
          parsed,
        );
      }
      return parsed as T;
    } finally {
      clearTimeout(timer);
    }
  }
}
