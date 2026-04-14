#!/usr/bin/env python3
"""
Standalone Supplier Intelligence Pipeline
==========================================
Run the full AI pipeline (entity resolution → vendor scoring →
consolidation clustering → anomaly detection) using a local Excel file
as input and producing a rich Excel report as output.

No database or network connection is required.

Usage
-----
::

    # From the workspace root:
    python standalone/main.py --input data.xlsx --output output.xlsx

    # Override the config path (defaults to config/model_config.yml):
    python standalone/main.py --input data.xlsx --config /path/to/model_config.yml

    # Short form:
    python standalone/main.py -i data.xlsx -o output.xlsx
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the workspace root is on sys.path so both ``standalone.*`` and the
# shared algorithm packages (entity_resolution, vendor_scoring, etc.) can be
# imported regardless of the current working directory.
# ---------------------------------------------------------------------------
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

import yaml  # noqa: E402 — after sys.path fix

from standalone.pipeline.runner import StandalonePipeline  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("standalone")

# ---------------------------------------------------------------------------
# Default paths (relative to the workspace root)
# ---------------------------------------------------------------------------

DEFAULT_INPUT  = _WORKSPACE_ROOT / "data.xlsx"
DEFAULT_OUTPUT = _WORKSPACE_ROOT / "output.xlsx"
DEFAULT_CONFIG = _WORKSPACE_ROOT / "config" / "model_config.yml"


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict:
    """Load and return the YAML configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: '{config_path}'. "
            "Use --config to specify an alternative path."
        )
    with config_path.open("r") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="standalone",
        description=(
            "Standalone Supplier Intelligence Pipeline — "
            "reads data.xlsx, writes output.xlsx."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input",
        default=str(DEFAULT_INPUT),
        metavar="PATH",
        help="Path to the input Excel file (data.xlsx).",
    )
    parser.add_argument(
        "-o", "--output",
        default=str(DEFAULT_OUTPUT),
        metavar="PATH",
        help="Path for the output Excel report.",
    )
    parser.add_argument(
        "-c", "--config",
        default=str(DEFAULT_CONFIG),
        metavar="PATH",
        help="Path to model_config.yml.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on error."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        config = load_config(Path(args.config))
        pipeline = StandalonePipeline(config)
        pipeline.run(input_path=args.input, output_path=args.output)
        return 0

    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        return 1
    except ValueError as exc:
        logger.error("Invalid input data: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed with unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
