# Stage 1: Builder (compile and install dependencies via uv)
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.6.3 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cache dependencies before copying source code
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy project source and install the package into .venv
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable


# Stage 2: Runtime (lean production image without build tools)
FROM python:3.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST="0.0.0.0" \
    PORT="8000" \
    SEO_AUDIT_DB_PATH="/data/history.db"

WORKDIR /app

# Create non-root user and persistent data directory for SQLite
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/sh appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

USER appuser

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=3)" || exit 1

CMD ["seo-audit", "serve"]
