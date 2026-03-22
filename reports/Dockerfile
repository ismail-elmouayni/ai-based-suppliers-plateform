# Apache Superset 3.1.3 with SQL Server (ODBC Driver 18) support
FROM apache/superset:3.1.3

USER root

# Install ODBC Driver 18 for SQL Server (detect Debian version dynamically)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg2 \
        unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && . /etc/os-release \
    && echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
        https://packages.microsoft.com/debian/${VERSION_ID}/prod ${VERSION_CODENAME} main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pyodbc for SQL Server ODBC connectivity.
# Do NOT install sqlalchemy/alembic extras — Superset ships pinned versions
# and upgrading them breaks the alembic migration bootstrap.
RUN pip install --no-cache-dir pyodbc

# Copy Superset config
COPY superset_config.py /app/pythonpath/superset_config.py

# Copy init script and entrypoint
COPY init_superset.sh /app/init_superset.sh
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /app/init_superset.sh /usr/local/bin/docker-entrypoint.sh

# Copy dashboard exports
COPY dashboards/ /app/dashboards/

USER superset
EXPOSE 8088
ENTRYPOINT ["docker-entrypoint.sh"]
