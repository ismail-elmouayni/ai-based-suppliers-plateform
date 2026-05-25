#!/usr/bin/env python3
"""
ML Engine — Pipeline Orchestrator + Flask trigger server.

Usage:
    python main.py --serve        # Start Flask on :5001 (GET /health, POST /run)
    python main.py --run-once     # Execute pipeline once and exit
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import yaml
from flask import Flask, jsonify, request

from db.repository import DataRepository
from entity_resolution.resolver import VendorResolver
from vendor_scoring.vendor_scorer import VendorScorer
from consolidation.clusterer import VendorClusterer
from anomaly_detection.detector import AnomalyDetector
from config_types import (
    AnomalyConfig,
    ConsolidationConfig,
    EntityResolutionConfig,
    VendorScoringConfig,
)
from data_source_columns import DataSourceColumns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ml_engine")

CONFIG_PATH = os.getenv("MODEL_CONFIG_PATH", "/config/model_config.yml")

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    def __init__(self, repo: DataRepository, config: dict[str, Any]) -> None:
        self.repo = repo
        self.config = config
        self.resolver  = VendorResolver(config)
        self.scorer    = VendorScorer(VendorScoringConfig.from_dict(config.get("vendor_scoring", {})))
        self.clusterer = VendorClusterer(config)
        self.detector  = AnomalyDetector(config)

    def run(self, run_id: int, triggered_by: str = "SYSTEM") -> None:
        start_ms = int(time.time() * 1000)
        try:
            self.repo.update_run_log_running(run_id)

            # 1. Load raw procurement records
            logger.info("Step 1/7: Loading procurement records...")
            raw_df = self.repo.load_procurement_records()
            if raw_df.empty:
                raise ValueError("No procurement records found — run data-seed first.")

            # 2. Entity resolution
            logger.info("Step 2/7: Running entity resolution...")
            mapping_df = self.resolver.resolve(raw_df, run_id=run_id)
            self.repo.write_resolved_vendors(mapping_df)

            # 3. Attach canonical names to raw data
            logger.info("Step 3/7: Attaching canonical vendor names...")
            name_map = mapping_df.set_index("RawVendorName")[DataSourceColumns.CANONICAL_VENDOR].to_dict()
            raw_df[DataSourceColumns.CANONICAL_VENDOR] = raw_df[DataSourceColumns.VENDOR].map(name_map).fillna(raw_df[DataSourceColumns.VENDOR])

            # 4. Clean categories (normalise NULL sentinels)
            null_sentinels = {"NULL", "None", "nan", ""}
            raw_df[DataSourceColumns.CATEGORY] = raw_df[DataSourceColumns.CATEGORY].where(
                ~raw_df[DataSourceColumns.CATEGORY].astype(str).isin(null_sentinels), other=None
            )

            # 5. Vendor scoring
            logger.info("Step 4/7: Running vendor scoring...")
            scores = self.scorer.score(raw_df, run_id=run_id)
            self.repo.write_vendor_scores(scores)

            # 6. Consolidation clustering
            logger.info("Step 5/7: Running consolidation clustering...")
            clusters_df, members_df = self.clusterer.cluster(raw_df, run_id=run_id)
            self.repo.write_consolidation(clusters_df, members_df)

            # 7. Anomaly detection
            logger.info("Step 6/7: Running anomaly detection...")
            flags_df = self.detector.detect(raw_df, run_id=run_id)
            self.repo.write_anomaly_flags(flags_df)

            # Update run log COMPLETED
            duration_ms = int(time.time() * 1000) - start_ms
            self.repo.update_run_log_completed(run_id, duration_ms)
            logger.info(
                f"Step 7/7: Pipeline completed successfully in {duration_ms}ms "
                f"(RunId={run_id})."
            )

        except Exception as exc:
            logger.exception(f"Pipeline failed (RunId={run_id}): {exc}")
            try:
                self.repo.update_run_log_failed(run_id, str(exc))
            except Exception:
                pass
            raise


# ---------------------------------------------------------------------------
# Flask trigger server
# ---------------------------------------------------------------------------

app = Flask(__name__)
_current_run_id: Optional[int] = None
_run_lock = threading.Lock()


def _run_pipeline_bg(run_id: int) -> None:
    global _current_run_id
    try:
        config = load_config()
        repo = DataRepository()
        pipeline = Pipeline(repo, config)
        pipeline.run(run_id, triggered_by="API")
    finally:
        with _run_lock:
            _current_run_id = None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ml-engine"}), 200


@app.route("/run", methods=["POST"])
def trigger_run():
    global _current_run_id
    with _run_lock:
        if _current_run_id is not None:
            return jsonify({
                "status": "already_running",
                "run_id": _current_run_id,
                "message": "A pipeline run is already in progress.",
            }), 409

        try:
            config = load_config()
            repo = DataRepository()
            run_type = (request.get_json(silent=True) or {}).get("runType", "FULL")
            run_id = repo.create_run_log(
                run_type=run_type,
                triggered_by="API",
                config_snapshot=config,
            )
            _current_run_id = run_id
        except Exception as e:
            logger.exception("Failed to create run log")
            return jsonify({"status": "error", "message": str(e)}), 500

    thread = threading.Thread(target=_run_pipeline_bg, args=(run_id,), daemon=True)
    thread.start()

    return jsonify({
        "status": "accepted",
        "run_id": run_id,
        "message": "ML pipeline started in background.",
    }), 202


@app.route("/status", methods=["GET"])
def status():
    try:
        config = load_config()
        repo = DataRepository()
        latest = repo.get_latest_run_log()
        return jsonify(latest or {"status": "no_runs"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Supplier Intelligence ML Engine")
    parser.add_argument("--serve", action="store_true", help="Start Flask trigger server on :5001")
    parser.add_argument("--run-once", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--port", type=int, default=5001, help="Flask port (default: 5001)")
    args = parser.parse_args()

    if args.serve:
        logger.info(f"Starting ML Engine trigger server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)

    elif args.run_once:
        config = load_config()
        repo = DataRepository()
        run_id = repo.create_run_log(run_type="FULL", triggered_by="CLI", config_snapshot=config)
        pipeline = Pipeline(repo, config)
        pipeline.run(run_id, triggered_by="CLI")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
