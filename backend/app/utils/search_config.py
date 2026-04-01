"""
Shared search configuration — used by both github_utils and serp_utils.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_RESULTS = 20


@dataclass
class SearchConfig:
    max_results:          int
    min_keyword_matches:  int    # min JD keywords in profile text
    serper_anchor_count:  int    # how many top skills to AND in Serper query
    strict_exp_filter:    bool   # hard-reject if stated exp < JD minimum
    min_account_years:    float  # GitHub account age floor (experience proxy)
    local_fraction:       float  # fraction of budget for local-first pass


def make_search_config(max_results: int = DEFAULT_MAX_RESULTS) -> SearchConfig:
    """
    Derive filter tightness from the requested result count.

    max_results ≤ 20  → TIGHT  (quality over quantity)
    max_results ≤ 35  → MEDIUM
    max_results > 35  → LOOSE  (quantity over quality)
    """
    if max_results <= 20:
        return SearchConfig(
            max_results=max_results,
            min_keyword_matches=3,
            serper_anchor_count=2,
            strict_exp_filter=True,
            min_account_years=3.0,
            local_fraction=0.7,
        )
    elif max_results <= 35:
        return SearchConfig(
            max_results=max_results,
            min_keyword_matches=2,
            serper_anchor_count=2,
            strict_exp_filter=False,
            min_account_years=2.0,
            local_fraction=0.7,
        )
    else:
        return SearchConfig(
            max_results=max_results,
            min_keyword_matches=1,
            serper_anchor_count=1,
            strict_exp_filter=False,
            min_account_years=1.0,
            local_fraction=0.6,
        )


def count_keyword_matches(text: str, tech_stack: list[str]) -> int:
    lower = text.lower()
    return sum(1 for kw in tech_stack if kw.lower() in lower)


def exp_years_from_text(text: str) -> int | None:
    matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)", text, re.IGNORECASE)
    return max(int(m) for m in matches) if matches else None


METRO_ALIASES: dict[str, list[str]] = {
    "san francisco": ["bay area", "silicon valley", "sf bay", "san jose", "oakland",
                      "berkeley", "palo alto", "mountain view", "sunnyvale", "santa clara"],
    "new york":      ["nyc", "manhattan", "brooklyn", "new jersey", "jersey city"],
    "los angeles":   ["la", "socal", "southern california", "santa monica"],
    "seattle":       ["bellevue", "redmond", "kirkland", "puget sound"],
    "boston":        ["cambridge", "massachusetts"],
    "chicago":       ["illinois", "evanston"],
    "austin":        ["texas", "round rock"],
    "london":        ["greater london", "uk", "england"],
    "bangalore":     ["bengaluru", "india", "karnataka"],
}
