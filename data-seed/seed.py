#!/usr/bin/env python3
"""
Data Seed Utility — AI-Powered Supplier Intelligence Platform
Supports --mode migrate|seed|both
Idempotent: migrate uses IF NOT EXISTS guards; seed checks row count before inserting.
"""

import argparse
import logging
import os
import sys
import glob
import time

import pandas as pd
import pyodbc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection_string() -> str:
    host = os.getenv("MSSQL_HOST", "sqlserver")
    port = os.getenv("MSSQL_PORT", "1433")
    db = os.getenv("MSSQL_DATABASE", "SupplierIntelligence")
    user = os.getenv("MSSQL_USER", "sa")
    password = os.getenv("MSSQL_SA_PASSWORD", "")
    return (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={host},{port};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=yes;"
    )


def wait_for_db(max_retries: int = 30, delay: int = 5) -> pyodbc.Connection:
    """Wait until SQL Server is ready and return a connection."""
    conn_str = get_connection_string()
    for attempt in range(1, max_retries + 1):
        try:
            conn = pyodbc.connect(conn_str, timeout=10)
            logger.info("Database connection established.")
            return conn
        except pyodbc.Error as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    raise RuntimeError("Could not connect to database after maximum retries.")


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = os.getenv("MIGRATIONS_DIR", "/migrations")


def run_migrations(conn: pyodbc.Connection) -> None:
    """Execute all V*.sql migration scripts in ascending order."""
    scripts = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "V*.sql")))
    if not scripts:
        logger.warning(f"No migration scripts found in {MIGRATIONS_DIR}")
        return

    cursor = conn.cursor()
    for script_path in scripts:
        script_name = os.path.basename(script_path)
        logger.info(f"Running migration: {script_name}")
        with open(script_path, "r", encoding="utf-8") as f:
            sql = f.read()

        # Split on GO statements (T-SQL batch separator)
        batches = [b.strip() for b in sql.split("\nGO") if b.strip()]
        for batch in batches:
            # Skip comment-only batches
            lines = [ln for ln in batch.splitlines() if not ln.strip().startswith("--")]
            if not "".join(lines).strip():
                continue
            try:
                cursor.execute(batch)
                conn.commit()
            except pyodbc.Error as e:
                err_msg = str(e)
                # Ignore "already exists" errors for idempotency
                if "already exists" in err_msg or "There is already an object" in err_msg:
                    logger.debug(f"Skipping (already exists): {batch[:80]}")
                    conn.rollback()
                else:
                    logger.error(f"Error in {script_name}: {e}\nBatch: {batch[:200]}")
                    raise

    logger.info("All migrations completed successfully.")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

COLUMN_MAPPING = {
    "PO Number": "PO_Number",
    "Saving %": "Saving_Pct",
    "Item Description": "Item_Description",
    "Original Spend": "Original_Spend",
    "OPEX/CAPEX": "OPEX_CAPEX",
}

NULL_SENTINELS = {"NULL", "None", "nan", ""}


def normalize_nulls(val):
    """Convert null sentinels to Python None."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if str(val) in NULL_SENTINELS:
        return None
    return val


def load_data_file(file_path: str) -> pd.DataFrame:
    """Load .xlsx or .csv into a DataFrame."""
    ext = os.path.splitext(file_path)[1].lower()
    logger.info(f"Loading data from {file_path} (format: {ext})")

    if ext == ".xlsx":
        try:
            df = pd.read_excel(file_path, sheet_name="Export", engine="openpyxl")
            logger.info(f"Loaded sheet 'Export' with {len(df)} rows.")
        except Exception:
            df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl")
            logger.info(f"Loaded first sheet with {len(df)} rows.")
    elif ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
        logger.info(f"Loaded CSV with {len(df)} rows.")
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    return df


def prepare_dataframe(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    """Rename columns, normalize nulls, coerce numeric types."""
    df = df.rename(columns=COLUMN_MAPPING)

    expected = [
        "Country", "Vendor", "Category", "PO_Number", "Item_Description",
        "Original_Spend", "OPEX_CAPEX", "Saving", "Saving_Pct", "Spend",
    ]

    existing = [c for c in expected if c in df.columns]
    df = df[existing].copy()

    # Normalize null sentinels
    for col in df.columns:
        df[col] = df[col].apply(normalize_nulls)

    # Drop rows with no Vendor
    df = df[df["Vendor"].notna()].copy()

    # Coerce numeric columns
    for col in ["Original_Spend", "Saving", "Saving_Pct", "Spend"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["SourceFile"] = source_file
    logger.info(f"Prepared {len(df)} rows for insertion.")
    return df


def insert_records(conn: pyodbc.Connection, df: pd.DataFrame) -> int:
    """Bulk insert DataFrame rows into procurement.ProcurementRecords."""
    cursor = conn.cursor()

    cols = [c for c in df.columns]
    placeholders = ", ".join(["?" for _ in cols])
    col_list = ", ".join(cols)
    insert_sql = (
        f"INSERT INTO procurement.ProcurementRecords ({col_list}) VALUES ({placeholders})"
    )

    inserted = 0
    chunk_size = 500
    rows = df.values.tolist()

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        chunk_cleaned = [
            [
                None if (v is None or (isinstance(v, float) and pd.isna(v))) else v
                for v in row
            ]
            for row in chunk
        ]
        cursor.executemany(insert_sql, chunk_cleaned)
        conn.commit()
        inserted += len(chunk)
        logger.info(f"Inserted {inserted}/{len(rows)} rows...")

    return inserted


def run_seed(conn: pyodbc.Connection, force: bool = False) -> None:
    """Seed procurement data from SEED_FILE_PATH."""
    seed_file = os.getenv("SEED_FILE_PATH", "/data/data.xlsx")

    if not os.path.exists(seed_file):
        logger.error(f"Seed file not found: {seed_file}")
        sys.exit(1)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(1) FROM procurement.ProcurementRecords")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0 and not force:
        logger.info(
            f"Skipping seed: {existing_count} rows already exist in ProcurementRecords. "
            f"Pass --force to re-seed."
        )
        return

    if existing_count > 0 and force:
        logger.info(f"Force re-seed: truncating {existing_count} existing rows.")
        cursor.execute("TRUNCATE TABLE procurement.ProcurementRecords")
        conn.commit()

    df = load_data_file(seed_file)
    df = prepare_dataframe(df, os.path.basename(seed_file))
    count = insert_records(conn, df)
    logger.info(f"Seed complete: {count} rows inserted into ProcurementRecords.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Supplier Intelligence Data Seed Utility")
    parser.add_argument(
        "--mode",
        choices=["migrate", "seed", "both"],
        default="both",
        help="Operation mode: migrate, seed, or both (default: both)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-seed even if data already exists",
    )
    args = parser.parse_args()

    conn = wait_for_db()
    try:
        if args.mode in ("migrate", "both"):
            run_migrations(conn)
        if args.mode in ("seed", "both"):
            run_seed(conn, force=args.force)
    finally:
        conn.close()

    logger.info(f"Mode '{args.mode}' completed successfully.")


if __name__ == "__main__":
    main()
