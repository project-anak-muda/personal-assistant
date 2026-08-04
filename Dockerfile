FROM python:3.13-slim

# uv binary from the official distroless image (pinned).
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer) from the lockfile only.
COPY pyproject.toml uv.lock .python-version ./
# No BuildKit cache mount here: Cloud Build's default `gcr.io/cloud-builders/docker`
# runs the legacy builder, which rejects `RUN --mount`. It would buy nothing there
# anyway — each Cloud Build run starts with an empty cache. `--no-cache` then keeps
# uv's download cache out of the layer, which trims the pushed image.
RUN uv sync --frozen --no-dev --no-cache

COPY . .

# Default to the webhook transport, which is what Cloud Run runs. The compose
# files override this with `python telegram_bot.py` for always-on hosts, where
# long polling needs no public HTTPS endpoint.
CMD ["python", "webhook_app.py"]
