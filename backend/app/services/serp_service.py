"""
Generic Serper (Google Search) API utilities.

Thin wrapper around the Serper REST API — returns raw organic result dicts.
No candidate / LinkedIn / sourcing logic here.

Other agents can use these for:
  - Salary and market research queries               (A4)
  - Company profile or news lookups                  (A3, A4)
  - General FAQ / knowledge search                   (A6)
  - Any site-scoped or open-ended Google search

Requires SERPER_API_KEY env var.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_SERPER_URL = "https://google.serper.dev/search"


def search(query: str, num: int = 10) -> list[dict]:
    """Run a plain Google search via Serper and return organic results.

    Args:
        query: Any search query string.
        num:   Number of results to request (max 100 per Serper docs).

    Returns:
        list of raw organic result dicts with keys:
        title, link, snippet, position, and any extras Serper returns.
    """
    return _request(query, num)


def search_site(site: str, query: str, num: int = 10) -> list[dict]:
    """Search within a specific site via Serper.

    Equivalent to prefixing the query with 'site:<site>'.

    Args:
        site:  Domain or path prefix (e.g. 'linkedin.com/in', 'github.com').
        query: Additional search terms.
        num:   Number of results to request.

    Returns:
        Same raw organic result dicts as search().

    Example:
        search_site("linkedin.com/in", '"Python" "FastAPI" "San Francisco"')
    """
    return _request(f"site:{site} {query}", num)


# ── Internal ──────────────────────────────────────────────────────────────────

def _request(query: str, num: int) -> list[dict]:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        logger.warning("SERPER_API_KEY not set — Serper search skipped.")
        return []
    try:
        r = httpx.post(
            _SERPER_URL,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("organic", [])
    except httpx.HTTPStatusError as e:
        logger.error("Serper request failed: %s | query=%r | body=%s", e, query, e.response.text)
        return []
    except Exception as e:
        logger.error("Serper request failed: %s", e)
        return []
