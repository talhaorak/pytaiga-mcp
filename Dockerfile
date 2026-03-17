FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# git is required for pytaigaclient (git source dependency)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies only (reproducible from lockfile)
RUN uv sync --frozen --no-install-project

# Copy application source
COPY src/ src/

# Install the project itself (non-editable) so uv run doesn't need to write at runtime
RUN uv sync --frozen --no-editable

# Disable uv cache so appuser doesn't need a writable cache dir
ENV UV_CACHE_DIR=/tmp/uv-cache

# Run as non-root
USER appuser

ENTRYPOINT ["/app/.venv/bin/python", "src/server.py"]
