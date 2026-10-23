#!/usr/bin/env bash
set -euo pipefail

url="${HEALTH_URL:-http://127.0.0.1:8080/healthz}"
attempts="${HEALTH_ATTEMPTS:-60}"
delay="${HEALTH_DELAY_SECONDS:-2}"

for ((attempt = 1; attempt <= attempts; attempt++)); do
  if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
    printf 'ProPulse API healthy at %s (attempt %s/%s)\n' "$url" "$attempt" "$attempts"
    exit 0
  fi
  sleep "$delay"
done

printf 'ProPulse API did not become healthy: %s\n' "$url" >&2
docker compose ps >&2 || true
docker compose logs --tail=100 api >&2 || true
exit 1
