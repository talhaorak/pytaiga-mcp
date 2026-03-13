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

# Run as non-root
USER appuser

ENTRYPOINT ["uv", "run", "--frozen", "python", "src/server.py"]
