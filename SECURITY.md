# Security Policy

## Reporting a vulnerability

Do not disclose exploitable vulnerabilities in public issues. Contact **security@wah-lah.com** with a concise report, affected component/version, reproduction steps, and impact. Do not include real customer data or live credentials.

If that mailbox is not yet configured, report the issue privately to the repository owner and request a secure contact channel before sending sensitive details.

## Supported versions

Security fixes target the latest supported release on the default branch. Older versions may require upgrading before a fix is available.

## Operational guidance

- Never commit real API keys, signing secrets, database credentials, or production environment files.
- Rotate any credential that may have been exposed.
- Keep dependencies patched and run the repository security workflow before releases.
- Treat public client keys as extractable; use scopes, HMAC request signing, and per-device limits rather than relying on key secrecy.
