"""
Domain type for entity resolution results.

VendorMapping — one resolved vendor name row returned by VendorResolver.resolve().
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VendorMapping:
    RAW_VENDOR_NAME       = "raw_vendor_name"
    CANONICAL_VENDOR_NAME = "canonical_vendor_name"
    MATCH_SCORE           = "match_score"
    MATCH_METHOD          = "match_method"
    RESOLUTION_RUN_ID     = "resolution_run_id"

    raw_vendor_name: str
    canonical_vendor_name: str
    match_score: float
    match_method: str
    resolution_run_id: int | None
