# Multi-stage Dockerfile for data-seed utility
# Stage: base    – Python + ODBC Driver 18 + dependencies
# Stage: migrate – runs V001-V004 SQL migrations only
# Stage: seed    – runs seed with sample_data.csv

FROM python:3.11-slim-bookworm AS base

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
COPY seed.py .

ENV MIGRATIONS_DIR=/migrations
ENV SEED_FILE_PATH=/data/data.xlsx

# ── migrate stage ──────────────────────────────────────────────────────────
FROM base AS migrate
CMD ["python", "seed.py", "--mode", "migrate"]

# ── seed stage ─────────────────────────────────────────────────────────────
FROM base AS seed
COPY sample_data.csv /data/sample_data.csv
ENV SEED_FILE_PATH=/data/sample_data.csv
CMD ["python", "seed.py", "--mode", "seed"]
