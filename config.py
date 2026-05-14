# Shared config + constants. Most things are tweakable via env vars.
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / os.environ.get("AEGIS_DATA_DIR", "data")
REPORTS_DIR = PROJECT_ROOT / "reports_output"
REPORTS_DIR.mkdir(exist_ok=True)

# Seed everything off this so MC runs are reproducible.
RANDOM_SEED = int(os.environ.get("AEGIS_RANDOM_SEED", "42"))
DEFAULT_N_SIMULATIONS = 10000

# score >= threshold -> level. Order matters when iterating.
RISK_LEVELS = {
    "Critical": 80,
    "High": 65,
    "Moderate": 45,
    "Low": 0,
}

FIXABILITY_LABELS = {
    "High-conviction fixable target": 75,
    "Fixable target": 60,
    "Watchlist": 40,
    "Value trap": 0,
}

# Sector buckets used by a couple of the scoring engines for narrative tweaks.
ENERGY_SECTORS = {"Energy", "Utilities", "Materials"}
CONSUMER_SECTORS = {"Retail", "Consumer Discretionary", "Consumer Staples"}
HEALTHCARE_SECTORS = {"Healthcare", "Pharmaceuticals", "Biotech"}
TECH_SECTORS = {"Technology", "Communication Services"}
FINANCIAL_SECTORS = {"Financials", "Banks"}

APP_TITLE = "Aegis ControlRisk OS v2 — CASCADE-2"
APP_TAGLINE = "Corporate Activism Simulation, Causal Action, Defense & Engagement Engine"

# Keep this verbatim - legal asked us not to weaken it.
COMPLIANCE_NOTE = (
    "This platform produces analytical estimates from synthetic data for board "
    "preparedness and advisory exploration only. It is not legal advice, "
    "investment advice, or trading advice. All deadlines, fiduciary "
    "considerations, and disclosure obligations require qualified counsel."
)
