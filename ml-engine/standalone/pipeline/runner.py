"""
StandalonePipeline
==================
Orchestrates the four AI operations — entity resolution, vendor scoring,
consolidation clustering, and anomaly detection — reading from an Excel file
and writing all results to a formatted output workbook.

This mirrors the step-by-step logic of ``main.py:Pipeline`` in the main
codebase but replaces the database layer with :class:`ExcelReader` /
:class:`ExcelWriter`.

No database connection or Flask server is needed.

Usage
-----
::

    from standalone.pipeline.runner import StandalonePipeline

    pipeline = StandalonePipeline(config)
    pipeline.run("data.xlsx", "output.xlsx")
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Ensure the workspace root (parent of standalone/) is on sys.path so that
# the shared algorithm modules can be imported without installation.
# ---------------------------------------------------------------------------
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from entity_resolution.vendor_resolver import VendorResolver     # noqa: E402
from vendor_scoring.vendor_scorer import VendorScorer             # noqa: E402
from consolidation.vendor_clusterer import VendorClusterer        # noqa: E402
from anomaly_detection.anomaly_detector import AnomalyDetector     # noqa: E402
from config_types import ConsolidationConfig, EntityResolutionConfig, VendorScoringConfig  # noqa: E402

from standalone.io.excel_reader import ExcelReader         # noqa: E402
from standalone.io.excel_writer import ExcelWriter         # noqa: E402
from data_source_columns import DataSourceColumns          # noqa: E402

logger = logging.getLogger(__name__)

# Sentinel strings treated as missing category values (mirrors main pipeline)
_NULL_SENTINELS: frozenset[str] = frozenset({"NULL", "None", "nan", ""})


class StandalonePipeline:
    """Run the full AI pipeline end-to-end on an Excel input file.

    Parameters
    ----------
    config:
        Configuration dict as loaded from ``model_config.yml``.
        Must contain the keys ``entity_resolution``, ``vendor_scoring``,
        ``consolidation``, and ``anomaly_detection``.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.resolver  = VendorResolver(EntityResolutionConfig.from_dict(config.get("entity_resolution", {})))
        self.scorer    = VendorScorer(VendorScoringConfig.from_dict(config.get("vendor_scoring", {})))
        self.clusterer = VendorClusterer(ConsolidationConfig.from_dict(config.get("consolidation", {})))
        self.detector  = AnomalyDetector(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_path: str | Path, output_path: str | Path) -> None:
        """Execute all pipeline steps and write results to *output_path*.

        Parameters
        ----------
        input_path:
            Path to the ``data.xlsx`` input file.
        output_path:
            Path for the generated ``output.xlsx`` report.

        Raises
        ------
        FileNotFoundError
            If *input_path* does not exist.
        ValueError
            If the input file is missing required columns or contains invalid
            data.
        RuntimeError
            If any pipeline step fails unexpectedly.
        """
        t0 = time.time()
        logger.info("=" * 60)
        logger.info("Standalone Supplier Intelligence Pipeline")
        logger.info("  Input : %s", input_path)
        logger.info("  Output: %s", output_path)
        logger.info("=" * 60)

        # Step 1 — Load procurement records
        logger.info("Step 1/7: Loading procurement records...")
        raw_df = self._load(input_path)

        # Step 2 — Entity resolution
        logger.info("Step 2/7: Running entity resolution...")
        mapping_df = self._resolve_vendors(raw_df)

        # Step 3 — Attach canonical vendor names
        logger.info("Step 3/7: Attaching canonical vendor names...")
        raw_df = self._attach_canonical_names(raw_df, mapping_df)

        # Step 4 — Normalise NULL category sentinels
        logger.info("Step 4/7: Cleaning category values...")
        raw_df = self._clean_categories(raw_df)

        # Step 5 — Vendor scoring
        logger.info("Step 5/7: Running vendor scoring...")
        scores_df = self._score_vendors(raw_df)

        # Step 6 — Consolidation clustering
        logger.info("Step 6/7: Running consolidation clustering...")
        clusters_df, members_df = self._cluster_vendors(raw_df)

        # Step 7 — Anomaly detection
        logger.info("Step 7/7: Running anomaly detection...")
        flags = self._detect_anomalies(raw_df)

        # Write output workbook
        self._write_output(
            output_path=output_path,
            raw_df=raw_df,
            mapping_df=mapping_df,
            scores_df=scores_df,
            clusters_df=clusters_df,
            members_df=members_df,
            flags=flags,
        )

        elapsed = time.time() - t0
        logger.info("Pipeline completed in %.1f s — report saved to '%s'.", elapsed, output_path)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _load(self, input_path: str | Path) -> pd.DataFrame:
        reader = ExcelReader(input_path)
        df = reader.load()
        logger.info("  Loaded %d records.", len(df))
        return df

    def _resolve_vendors(self, raw_df: pd.DataFrame) -> list:
        mappings = self.resolver.resolve(raw_df, run_id=0)
        unique_canonical = len({m.canonical_vendor_name for m in mappings})
        logger.info(
            "  Resolved %d raw names \u2192 %d canonical vendors.",
            len(mappings), unique_canonical,
        )
        return mappings

    def _attach_canonical_names(
        self, raw_df: pd.DataFrame, mappings: list
    ) -> pd.DataFrame:
        name_map = {m.raw_vendor_name: m.canonical_vendor_name for m in mappings}
        df = raw_df.copy()
        df[DataSourceColumns.CANONICAL_VENDOR] = df[DataSourceColumns.VENDOR].map(name_map).fillna(df[DataSourceColumns.VENDOR])
        return df

    def _clean_categories(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        df = raw_df.copy()
        df[DataSourceColumns.CATEGORY] = df[DataSourceColumns.CATEGORY].where(
                ~df[DataSourceColumns.CATEGORY].astype(str).isin(_NULL_SENTINELS), other=None
            )
        return df

    def _score_vendors(self, raw_df: pd.DataFrame) -> list:
        scores_df = self.scorer.score(raw_df, run_id=0)
        logger.info("  Scored %d vendor+category pairs.", len(scores_df))
        return scores_df

    def _cluster_vendors(
        self, raw_df: pd.DataFrame
    ) -> tuple[list, list]:
        result = self.clusterer.cluster(raw_df, run_id=0)
        logger.info("  Found %d consolidation clusters.", len(result.clusters))
        return result.clusters, result.members

    def _detect_anomalies(self, raw_df: pd.DataFrame) -> list:
        flags = self.detector.detect(raw_df, run_id=0)
        logger.info("  Flagged %d anomalous POs.", len(flags))
        return flags

    def _write_output(
        self,
        output_path: str | Path,
        raw_df: pd.DataFrame,
        mapping_df: list,
        scores_df: list,
        clusters_df: list,
        members_df: list,
        flags: list,
    ) -> None:
        stats = {
            "total_vendors": len({m.canonical_vendor_name for m in mapping_df}),
            "total_spend":   raw_df[DataSourceColumns.SPEND].sum() if DataSourceColumns.SPEND in raw_df.columns else 0,
            "anomaly_count": len(flags),
            "cluster_count": len(clusters_df),
        }
        with ExcelWriter(output_path) as writer:
            writer.write_summary(stats, raw_df)
            writer.write_entity_resolution(mapping_df)
            writer.write_vendor_scores(scores_df)
            writer.write_consolidation(clusters_df, members_df)
            writer.write_anomaly_flags(flags)
        logger.info("  Wrote 6 sheets to '%s'.", output_path)
