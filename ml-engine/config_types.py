"""
config_types
============
Typed, immutable configuration dataclasses for each ML sub-module.

Each class is created via ``from_dict()`` from the raw YAML config dict that
is loaded by the application entry points.  The existing classes (AnomalyDetector,
VendorScorer, etc.) parse their config through these dataclasses so that all
defaults and type conversions live in one place.

Example
-------
::

    cfg = AnomalyConfig.from_dict(yaml_config)
    cfg.contamination_factor   # float, default 0.05
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnomalyConfig:
    """Configuration for :class:`anomaly_detection.detector.AnomalyDetector`."""
    CONFIG_KEY = "anomaly_detection"
    contamination_factor: float = 0.05
    severity_high_zscore: float = 3.0
    severity_medium_zscore: float = 2.0
    n_estimators: int = 100
    random_state: int = 42

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnomalyConfig:
        d = d.get(cls.CONFIG_KEY, {})
        return cls(
            contamination_factor=float(d.get("contamination_factor", 0.05)),
            severity_high_zscore=float(d.get("severity_high_zscore", 3.0)),
            severity_medium_zscore=float(d.get("severity_medium_zscore", 2.0)),
            n_estimators=int(d.get("n_estimators", 100)),
            random_state=int(d.get("random_state", 42)),
        )


@dataclass(frozen=True)
class EntityResolutionConfig:
    """Configuration for :class:`entity_resolution.resolver.VendorResolver`."""
    CONFIG_KEY = "entity_resolution"
    match_threshold: float = 85.0
    top_k_candidates: int = 5
    normalize_before_match: bool = True
    strip_suffixes: tuple[str, ...] = field(default_factory=tuple)
    token_aliases: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def token_aliases_dict(self) -> dict[str, str]:
        """Return token_aliases as a plain dict for lookup."""
        return dict(self.token_aliases)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EntityResolutionConfig:
        d = d.get(cls.CONFIG_KEY, {})
        raw_aliases: dict[str, str] = d.get("token_aliases", {})
        return cls(
            match_threshold=float(d.get("match_threshold", 85)),
            top_k_candidates=int(d.get("top_k_candidates", 5)),
            normalize_before_match=bool(d.get("normalize_before_match", True)),
            strip_suffixes=tuple(s.upper() for s in d.get("strip_suffixes", [])),
            token_aliases=tuple(
                (k.upper(), v.upper()) for k, v in raw_aliases.items()
            ),
        )


@dataclass
class VendorScoringConfig:
    """Configuration for :class:`vendor_scoring.scorer.VendorScorer`."""
    CONFIG_KEY = "vendor_scoring"
    saving_pct_weight: float = 0.50
    spend_weight: float = 0.30
    specialization_weight: float = 0.20
    min_purchase_count: int = 3
    band_green_min: float = 70.0
    band_amber_min: float = 40.0

    def __post_init__(self) -> None:
        """Normalise weights to sum = 1 so the scorer never has to."""
        total = self.saving_pct_weight + self.spend_weight + self.specialization_weight
        if total > 0:
            self.saving_pct_weight     /= total
            self.spend_weight          /= total
            self.specialization_weight /= total

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VendorScoringConfig:
        d = d.get(cls.CONFIG_KEY, {})
        return cls(
            saving_pct_weight=float(d.get("saving_pct_weight", 0.50)),
            spend_weight=float(d.get("spend_weight", 0.30)),
            specialization_weight=float(d.get("specialization_weight", 0.20)),
            min_purchase_count=int(d.get("min_purchase_count_for_scoring", 3)),
            band_green_min=float(d.get("band_green_min", 70)),
            band_amber_min=float(d.get("band_amber_min", 40)),
        )


@dataclass(frozen=True)
class ConsolidationConfig:
    """Configuration for :class:`consolidation.clusterer.VendorClusterer`."""
    CONFIG_KEY = "consolidation"
    min_cluster_size: int = 2
    algorithm: str = "kmeans"
    n_clusters: int | str = "auto"
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 2

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConsolidationConfig:
        d = d.get(cls.CONFIG_KEY, {})
        return cls(
            min_cluster_size=int(d.get("min_cluster_size", 2)),
            algorithm=str(d.get("algorithm", "kmeans")).lower(),
            n_clusters=d.get("n_clusters", "auto"),
            dbscan_eps=float(d.get("dbscan_eps", 0.5)),
            dbscan_min_samples=int(d.get("dbscan_min_samples", 2)),
        )