<div align="center">

# Wah-Lah ProPulse AI

**Your app already knows what your user needs. It just never speaks up.**

Background, event-driven agent orchestrator. Native Android polling. FastAPI gateway.
MongoDB. Two-line integration. Boots offline with zero cloud accounts.

[![CI](https://github.com/tinysecrets/propulse/actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![CodeQL](https://github.com/tinysecrets/propulse/actions/workflows/codeql.yml/badge.svg)](../../actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/tinysecrets/propulse/badge)](https://securityscorecards.dev/viewer/?uri=github.com/tinysecrets/propulse)
[![License: AGPL-3.0](https://img.shields.io/badge/server-AGPL--3.0-blue.svg)](LICENSE)
[![SDK: Apache-2.0](https://img.shields.io/badge/SDK-Apache--2.0-green.svg)](LICENSES/Apache-2.0.txt)
[![PyPI](https://img.shields.io/pypi/v/wah-lah-propulse)](https://pypi.org/project/wah-lah-propulse/)
[![GHCR](https://img.shields.io/badge/ghcr.io-propulse--api-blueviolet)](https://github.com/tinysecrets/propulse/pkgs/container/propulse-api)

</div>

---

## The entire integration

```kotlin
ProPulse.start(this, BuildConfig.PROPULSE_PUBLIC_KEY)                      // line 1
ProPulse.on("cart_idle").after(15.minutes()).say("Still thinking? 10% off.")   // line 2
```

That is it. No dashboard. No YAML. No cloud account. `docker compose up` and you are live.

## 60-second quickstart

```bash
git clone https://github.com/tinysecrets/propulse && cd propulse
make up      # mongo + redis + api + 3 workers + scheduler, then seeds a demo tenant
make demo    # fires a real pulse through the whole pipeline
```

Defaults are free by construction: local Mongo and Redis, `echo` LLM, on-device TTS,
billing disabled. Add Stripe or an LLM only when you want them.

## Why this exists

Push notifications are reactive — you send when *you* decide. ProPulse inverts it.
Your app declares **triggers** (cart idle 15 min, battery dying, meeting in 5, streak
about to break). The server owns *when*, evaluates policy (quiet hours, daily caps,
coalescing, dedupe windows), and the phone speaks.

| Reactive | ProPulse |
|---|---|
| Fire on a cron you guessed | Fire on device truth |
| User must open the app | The phone talks to the user |
| 5 notifications in a row | One coalesced sentence |
| Burns battery polling | Push-first, adaptive, Doze-aware |
| Agent is a black box | Budgeted plan/act with deterministic replay |

## Architecture

