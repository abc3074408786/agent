# Multi-stage Dockerfile for production deployment
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml .
COPY agent/ agent/

# Build wheel
RUN pip wheel --no-deps --wheel-dir /app/wheels .

# Stage 2: Runtime
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies
COPY --from=builder /app/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/*.whl && \
    pip install --no-cache-dir "agent[all]" || true && \
    rm -rf /tmp/wheels

# Copy configuration
COPY config.yaml /app/config.yaml

# Non-root user
RUN useradd --create-home --shell /bin/bash agent
USER agent

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV AGENT_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); assert r.status_code == 200"

# Expose port
EXPOSE 8000

# Run
CMD ["python", "-m", "uvicorn", "agent.api:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
