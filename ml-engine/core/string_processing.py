"""
core.string_processing
======================
Generic string-manipulation utilities shared across pipeline modules.
"""

from __future__ import annotations

import re


class StringProcessing:
    """Shared string helpers for raw text fields."""

    @staticmethod
    def normalize(
        name: str,
        strip_suffixes: list[str] | None = None,
        normalize_before_match: bool = True,
    ) -> str:
        """Uppercase, collapse whitespace, optionally strip legal suffixes.

        Parameters
        ----------
        name:
            Raw vendor name to normalise.
        strip_suffixes:
            Legal-form suffixes to remove (e.g. ``["LTD", "SARL", "GMBH"]``).
            Stripped only when *normalize_before_match* is ``True``.
        normalize_before_match:
            When ``False``, suffix stripping is skipped even if *strip_suffixes*
            is provided.
        """
        name = str(name).upper().strip()
        name = re.sub(r"\s+", " ", name)
        name = name.rstrip(",").strip()

        if strip_suffixes and normalize_before_match:
            for suffix in sorted(strip_suffixes, key=len, reverse=True):
                pattern = rf"\b{re.escape(suffix)}\.?\s*$"
                name = re.sub(pattern, "", name).strip().rstrip(",").strip()

        return name
