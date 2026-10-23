// SPDX-License-Identifier: Apache-2.0
import { createHash, createHmac } from "node:crypto";
import { describe, expect, it } from "vitest";
import { canonical, digest, newNonce, sign } from "./sign.js";

describe("request signing", () => {
  it("hashes the exact UTF-8 request body", async () => {
    const body = '{"pulse":"cart_idle","install_id":"ins_1"}';
    expect(await digest(body)).toBe(createHash("sha256").update(body, "utf8").digest("hex"));
  });

  it("matches the server HMAC canonical format", async () => {
    const secret = "test-signing-secret";
    const ts = "1730000000";
    const nonce = "bm9uY2U";
    const body = '{"ok":true}';
    const expected = createHmac("sha256", secret)
      .update(`${ts}.${nonce}.${createHash("sha256").update(body, "utf8").digest("hex")}`, "utf8")
      .digest("base64");
    expect(await canonical(ts, nonce, body)).toBe(
      `${ts}.${nonce}.${createHash("sha256").update(body, "utf8").digest("hex")}`,
    );
    expect(await sign(secret, ts, nonce, body)).toBe(expected);
  });

  it("creates a 22-character URL-safe nonce", () => {
    const nonce = newNonce();
    expect(nonce).toMatch(/^[A-Za-z0-9_-]{22}$/);
  });
});
