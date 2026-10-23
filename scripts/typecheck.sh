#!/usr/bin/env bash
set -euo pipefail
export MYPYPATH="apps/api:apps/worker:apps/scheduler:packages/propulse-core/src:packages/sdk-python"
uv run mypy --strict --explicit-package-bases \
  apps/api/propulse_api \
  apps/worker/propulse_worker \
  apps/scheduler/propulse_sched \
  packages/propulse-core/src/propulse_core \
  packages/sdk-python/propulse_sdk
