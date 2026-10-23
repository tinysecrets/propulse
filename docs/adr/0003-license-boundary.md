# ADR 0003: Keep the open-core license boundary explicit

- **Status:** Accepted
- **Date:** 2026-10-23

## Context

ProPulse offers an AGPL server and separately licensed SDKs. The repository must make the license of each component visible and prevent SDK packages from depending on server implementation details.

## Decision

The server and core engine use AGPL-3.0-or-later. The Android, JavaScript, and Python SDKs use Apache-2.0. Any future closed-source `propulse-pro` package is distributed separately under a commercial license and may depend on the core only through a narrow published interface. Automated boundary checks run in CI.

## Consequences

Every shipped component must have an explicit SPDX license declaration and corresponding license text. Dependencies and imports crossing component boundaries require review. The commercial license does not grant rights to the Wah-Lah or ProPulse trademarks.
