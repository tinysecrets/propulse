# syntax=docker/dockerfile:1.7

FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /usr/local/bin/uv

# ---------- builder ----------
FROM base AS builder
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages/propulse-core/pyproject.toml packages/propulse-core/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
COPY apps/scheduler/pyproject.toml apps/scheduler/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --no-dev

COPY packages ./packages
COPY apps ./apps
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# ---------- api ----------
FROM base AS api
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /src/packages /app/packages
COPY --from=builder /src/apps/api /app/apps/api
ENV PATH="/opt/venv/bin:$PATH" PYTHONPATH="/app/apps/api:/app/packages/propulse-core/src" \
    GIT_SHA=${GIT_SHA:-unknown}
RUN useradd -r -u 10001 -s /sbin/nologin propulse
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=25s --retries=5 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["uvicorn","propulse_api.asgi:app","--host","0.0.0.0","--port","8080","--workers","2","--no-server-header","--no-access-log"]

# ---------- worker ----------
FROM api AS worker
ENV WORKER_ROLE=orchestrator PYTHONPATH="/app/apps/worker:/app/apps/api:/app/packages/propulse-core/src"
COPY --from=builder /src/apps/worker /app/apps/worker
HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=3 \
  CMD python -m propulse_worker.health
CMD ["python","-m","propulse_worker.main"]

# ---------- scheduler ----------
FROM api AS scheduler
ENV PYTHONPATH="/app/apps/scheduler:/app/apps/api:/app/packages/propulse-core/src"
COPY --from=builder /src/apps/scheduler /app/apps/scheduler
HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=3 \
  CMD python -m propulse_sched.health
CMD ["python","-m","propulse_sched.main"]
