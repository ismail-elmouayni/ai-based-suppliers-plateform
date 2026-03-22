#!/bin/bash
# Idempotent Superset initialisation script
# Runs: db upgrade → create admin → superset init → register datasets → import dashboards
set -e

ADMIN_USER="${SUPERSET_ADMIN_USER:-admin}"
ADMIN_PASSWORD="${SUPERSET_ADMIN_PASSWORD:-Admin1234!}"
ADMIN_EMAIL="${SUPERSET_ADMIN_EMAIL:-admin@supplierintelligence.local}"
MSSQL_HOST="${MSSQL_HOST:-sqlserver}"
MSSQL_PORT="${MSSQL_PORT:-1433}"
MSSQL_DATABASE="${MSSQL_DATABASE:-SupplierIntelligence}"
MSSQL_USER="${MSSQL_USER:-sa}"
MSSQL_SA_PASSWORD="${MSSQL_SA_PASSWORD:-}"

echo "[1/5] Running superset db upgrade..."
superset db upgrade

echo "[2/5] Creating admin user (idempotent)..."
superset fab create-admin \
    --username "${ADMIN_USER}" \
    --firstname "Supplier" \
    --lastname "Intelligence" \
    --email "${ADMIN_EMAIL}" \
    --password "${ADMIN_PASSWORD}" 2>/dev/null || echo "Admin user already exists."

echo "[3/5] Running superset init..."
superset init

echo "[4/5] Registering SQL Server database connection..."
python3 - <<PYEOF || echo "  Warning: DB registration step failed (non-fatal — configure manually in UI)"
import os
from superset import app, db
from superset.models.core import Database

with app.app_context():
    existing = db.session.query(Database).filter_by(
        database_name="Supplier Intelligence SQL Server"
    ).first()

    if not existing:
        host = os.environ.get("MSSQL_HOST", "sqlserver")
        port = os.environ.get("MSSQL_PORT", "1433")
        database = os.environ.get("MSSQL_DATABASE", "SupplierIntelligence")
        user = os.environ.get("MSSQL_USER", "sa")
        password = os.environ.get("MSSQL_SA_PASSWORD", "")
        uri = (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes&Encrypt=yes"
        )
        new_db = Database(
            database_name="Supplier Intelligence SQL Server",
            sqlalchemy_uri=uri,
        )
        db.session.add(new_db)
        db.session.commit()
        print("Database connection registered.")
    else:
        print("Database connection already registered.")
PYEOF

echo "[5/5] Importing dashboards (if present)..."
for f in /app/dashboards/*.json; do
    if [ -f "$f" ]; then
        echo "Importing dashboard: $f"
        superset import-dashboards --path "$f" 2>/dev/null || echo "  Could not import $f (may already exist)"
    fi
done

echo "Superset initialisation complete."
