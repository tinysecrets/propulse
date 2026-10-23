// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it, vi } from "vitest";
import { createHash, createHmac } from "node:crypto";
import { ProPulse, ProPulseError, QuotaExceededError } from "./client.js";
import { canonical, sign } from "./sign.js";

describe("ProPulse JavaScript SDK", () => {
  it("requires a public key", () => {
    expect(() => new ProPulse({ key: "" })).toThrowError(ProPulseError);
  });

  it("uses a deterministic canonical HMAC signature", async () => {
    const body = '{"pulse":"cart_idle"}';
    const digest = createHash("sha256").update(body, "utf8").digest("hex");
    const expectedCanonical = `1700000000.nonce-1.${digest}`;
    expect(await canonical("1700000000", "nonce-1", body)).toBe(expectedCanonical);
    expect(await sign("secret", "1700000000", "nonce-1", body)).toBe(
      createHmac("sha256", "secret").update(expectedCanonical, "utf8").digest("base64"),
    );
  });

  it("sends signed signal requests and parses successful responses", async () => {
    const payload = {
      accepted: true,
      pulse_run_id: "run_123",
      state: "queued",
      next_poll_in: 10,
      upgrade_url: "",
      quota: { limit: 1000, used: 1, remaining: 999, plan: "free" },
    };
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify(payload), { status: 200, headers: { "content-type": "application/json" } }),
    );
    const client = new ProPulse({
      key: "pp_pub_test",
      secret: "test-secret",
      baseUrl: "https://example.test/",
      fetchImpl: fetchImpl as typeof fetch,
    });

    await expect(client.signal("cart_idle", { install_id: "install-1" })).resolves.toEqual(payload);
    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(url).toBe("https://example.test/v1/pulses:signal");
    expect(init.method).toBe("POST");
    expect(headers["x-pp-key"]).toBe("pp_pub_test");
    expect(headers["x-pp-sig"]).toBeTruthy();
    expect(headers["x-pp-nonce"]).toBeTruthy();
    expect(headers["x-pp-ts"]).toMatch(/^\d+$/);
  });

  it("surfaces upgrade details when the free quota is exceeded", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "monthly quota exceeded", upgrade_url: "https://example.test/upgrade", limit: 1000, used: 1000 }), {
        status: 429,
        headers: { "content-type": "application/json" },
      }),
    );
    const client = new ProPulse({ key: "pp_pub_test", fetchImpl: fetchImpl as typeof fetch });
    await expect(client.signal("cart_idle")).rejects.toMatchObject({
      name: "QuotaExceededError",
      status: 429,
      code: "quota_exceeded",
      upgradeUrl: "https://example.test/upgrade",
      limit: 1000,
      used: 1000,
    });
  });

  it("preserves structured API errors", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "bad request", title: "invalid_request" }), {
        status: 400,
        statusText: "Bad Request",
        headers: { "content-type": "application/json" },
      }),
    );
    const client = new ProPulse({ key: "pp_pub_test", fetchImpl: fetchImpl as typeof fetch });
    await expect(client.plans()).rejects.toMatchObject({
      name: "ProPulseError",
      status: 400,
      code: "invalid_request",
    });
  });
});
