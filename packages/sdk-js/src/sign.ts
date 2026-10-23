// SPDX-License-Identifier: Apache-2.0

const encoder = new TextEncoder();

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Body digest over the exact UTF-8 bytes sent to the server. */
export async function digest(body: string): Promise<string> {
  const result = await globalThis.crypto.subtle.digest("SHA-256", encoder.encode(body));
  return bytesToHex(new Uint8Array(result));
}

export async function canonical(
  ts: string | number,
  nonce: string,
  body: string,
): Promise<string> {
  return `${ts}.${nonce}.${await digest(body)}`;
}

export async function sign(
  secret: string,
  ts: string | number,
  nonce: string,
  body: string,
): Promise<string> {
  const key = await globalThis.crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await globalThis.crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(await canonical(ts, nonce, body)),
  );
  return bytesToBase64(new Uint8Array(signature));
}

export function newNonce(): string {
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  return bytesToBase64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
