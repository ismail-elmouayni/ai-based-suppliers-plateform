"""
Apache Superset configuration for AI-Powered Supplier Intelligence Platform.
"""
import os

# Secret key — override in production via SUPERSET_SECRET_KEY env var
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "supplier-intelligence-secret-key-change-in-prod")

# SQLAlchemy URI for Superset's own metadata DB (SQLite by default for simplicity)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_META_DB_URI",
    "sqlite:////app/superset_home/superset.db",
)

# Feature flags
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
}

# Disable CSRF for API access (enable in production)
WTF_CSRF_ENABLED = False

# Allow embedding
TALISMAN_ENABLED = False
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["*"],
}

# Row limit for queries
ROW_LIMIT = 50000
VIZ_ROW_LIMIT = 10000

# Cache (memory for dev; use Redis in production)
CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}

# Logging
ENABLE_TIME_ROTATE = True
