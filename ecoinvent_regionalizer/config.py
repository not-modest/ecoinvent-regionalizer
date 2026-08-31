"""
Central config. Must be imported before any bw2data import anywhere in the
app, since BRIGHTWAY_DIR has to be set before bw2data picks its data
directory.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ecoinvent is licensed data (EULA prohibits third-party/AI access) so it is
# kept OUTSIDE this project folder entirely, in a location the Claude Code
# session working in this directory has no reason to ever browse into.
# Both the raw ecospold2 export and the imported brightway project (which
# becomes licensed content once populated) live here.
EXTERNAL_DATA_ROOT = Path.home() / "ecoinvent_data"

BRIGHTWAY_DIR = EXTERNAL_DATA_ROOT / "brightway_projects"
BRIGHTWAY_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("BRIGHTWAY2_DIR", str(BRIGHTWAY_DIR))

ECOINVENT_RAW_DIR = EXTERNAL_DATA_ROOT / "raw_export"
ECOINVENT_RAW_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_BW_PROJECT = "ecoinvent-regionalizer"
DEFAULT_ECOINVENT_DB = "ecoinvent-3.12-cutoff"
REGIONALIZED_DB = "regionalized-scenarios"

# ecoinvent geography codes that are aggregates, not real countries/regions.
# Surfaced separately in the UI so users don't confuse them with specific
# geographies when building a priority ranking.
AGGREGATE_LOCATIONS = {"GLO", "RoW", "RER", "RNA", "RAS", "RAF", "RLA"}
