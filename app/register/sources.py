"""ESMA MiCA register CSV sources (mirrors mica-dashboard/workers/sync-esma.js)."""
from __future__ import annotations

ESMA_BASE = "https://www.esma.europa.eu/sites/default/files/2024-12"

# dataset -> (csv filename, target table)
DATASETS = {
    "CASPS": ("CASPS.csv", "casps"),            # authorised crypto-asset service providers
    "EMTWP": ("EMTWP.csv", "emt_issuers"),      # e-money token issuers / white papers
    "ARTZZ": ("ARTZZ.csv", "art_issuers"),      # asset-referenced token issuers
    "OTHER": ("OTHER.csv", "other_whitepapers"),# Title II "other crypto-asset" white papers
    "NCASP": ("NCASP.csv", "non_compliant"),    # non-compliant entities / warnings
}

USER_AGENT = "mica-copilot/0.2 (+educational; non-commercial)"


def url(dataset: str) -> str:
    return f"{ESMA_BASE}/{DATASETS[dataset][0]}"
