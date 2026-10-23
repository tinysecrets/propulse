// SPDX-License-Identifier: Apache-2.0
import { createHash, createHmac, randomBytes } from "node:crypto";

/** Body digest — the exact bytes hashed, so the server agrees byte-for-byte. */
export function digest(body: string): string {
  return createHash("sha256").update(body, "utf8").digest("hex");
}

export function canonical(ts: string | number, nonce: string, body: string): string {
  return `${ts}.${nonce}.${digest(body)}`;
}

export function sign(secret: string, ts: string | number, nonce: string, body: string): string {
  return createHmac("sha256", secret).update(canonical(ts, nonce, body), "utf8").digest("base64");
}

export function newNonce(): string {
  return randomBytes(16).toString("base64url");
}
