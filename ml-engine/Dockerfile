# Multi-stage Dockerfile — ML Engine
# Stage: base       – Python + ODBC Driver 18 + pip deps
# Stage: production – production image (Flask trigger server)
# Stage: test       – runs pytest unit + integration tests

FROM python:3.11-slim-bookworm AS base

# Install ODBC Driver 18 for SQL Server (pinned to Debian 12 / Bookworm)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg2 \
        unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
        https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source
COPY . .

ENV MODEL_CONFIG_PATH=/config/model_config.yml
ENV PYTHONPATH=/app

# ── production stage ───────────────────────────────────────────────────────
FROM base AS production
EXPOSE 5001
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1
CMD ["python", "main.py", "--serve"]

# ── test stage ─────────────────────────────────────────────────────────────
FROM base AS test
ENV PYTEST_ARGS="--tb=short -v"
CMD ["sh", "-c", "pytest $PYTEST_ARGS"]
