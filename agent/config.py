from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEALS_PATH = ROOT / "data" / "deals.json"
TAXONOMY_PATH = ROOT / "taxonomy" / "taxonomy.json"
RECORDINGS_DIR = ROOT / "recordings"
RESULTS_DIR = ROOT / "results"

# Models. Sonnet codes and writes; Haiku does quick data gathering.
MODEL_SONNET = "claude-sonnet-5-5"
MODEL_HAIKU = "claude-haiku-5-5"

QUARTERS = ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]
SEGMENTS = ["50-99", "100-199", "200-500"]
SLOW_DEMO_DAYS = 10            # "waits more than 10 days"

# Verdict thresholds for the three theories (fixed in code before the run)
PRICE_MAJORITY = 0.50          # price is the main reason for at least half of a segment's losses
THEORY_SUPPORTED = 0.40        # a theory is "supported" if its reason explains >= 40% of all losses
THEORY_PARTLY = 0.15           # "partly supported" if >= 15% overall, or a majority inside one segment
