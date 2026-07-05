from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
SITE_DIR = ROOT_DIR / "site"
DB_PATH = DATA_DIR / "autism_research.sqlite3"

APP_EMAIL = os.environ.get("PUBMED_CONTACT_EMAIL", "your-email@example.com")
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

DEFAULT_THRESHOLD = 0.70
WATCHLIST_THRESHOLD = 0.50

SCORE_WEIGHTS = {
    "venue": 0.278,
    "article_impact": 0.222,
    "methods_quality": 0.389,
    "novelty": 0.111,
}


def ensure_workspace_path(path: Path | str) -> Path | str:
    if str(path) == ":memory:":
        return ":memory:"

    resolved = Path(path).expanduser().resolve()
    root = ROOT_DIR.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Refusing to read or write outside this workspace: {resolved}")
    return resolved
