# Use Python 3.10 slim image for production
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install production dependencies only
RUN uv pip install --system -e . --no-deps

# Install dependencies from pyproject.toml (production only)
RUN uv pip install --system -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose port (configurable via PORT env var)
EXPOSE ${PORT:-8000}

# Set default environment variables
ENV PORT=8000 \
    TAIGA_TRANSPORT=sse \
    LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run the server in SSE mode
CMD ["python", "src/server.py", "--sse"]
