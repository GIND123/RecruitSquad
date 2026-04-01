"""
Candidate-sourcing utilities for A1 Sourcing Hunter.

Builds on top of the generic github_utils and serp_utils with
sourcing-specific logic:
  - Two-pass local + broad GitHub candidate search with SearchConfig filters
  - Two-pass local + remote LinkedIn search via Serper
  - GithubProfile / LinkedInProfile construction from raw dicts
  - Keyword and experience filters
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.models.schemas import GithubProfile, LinkedInProfile
from app.services.github_service import get_user_profile, search_users
from app.utils.search_config import (
    SearchConfig,
    count_keyword_matches,
    exp_years_from_text,
)
from app.services.serp_service import search_site

logger = logging.getLogger(__name__)

_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}


# ── GitHub candidate search ───────────────────────────────────────────────────

def _github_passes_filter(
    profile: GithubProfile,
    tech_stack: list[str],
    cfg: SearchConfig,
) -> bool:
    profile_text = " ".join(filter(None, [
        profile.bio or "",
        " ".join(profile.languages),
        " ".join(profile.top_repos),
    ]))
    if count_keyword_matches(profile_text, tech_stack) < cfg.min_keyword_matches:
        logger.debug("GitHub rejected %s — keyword mismatch (need %d)",
                     profile.login, cfg.min_keyword_matches)
        return False
    if profile.account_created_at:
        age_years = (datetime.now(timezone.utc) - profile.account_created_at).days / 365
        if age_years < cfg.min_account_years:
            logger.debug("GitHub rejected %s — account age %.1f yrs < %.1f",
                         profile.login, age_years, cfg.min_account_years)
            return False
    return True


def _dict_to_github_profile(raw: dict) -> GithubProfile | None:
    if not raw:
        return None
    created_at = None
    if raw.get("account_created_at"):
        try:
            created_at = datetime.fromisoformat(raw["account_created_at"])
        except ValueError:
            pass
    return GithubProfile(
        login=raw["login"],
        name=raw["name"],
        email=raw.get("email"),
        location=raw.get("location"),
        bio=raw.get("bio"),
        github_url=raw["github_url"],
        top_repos=raw.get("top_repos", []),
        languages=raw.get("languages", []),
        public_repos=raw.get("public_repos", 0),
        followers=raw.get("followers", 0),
        account_created_at=created_at,
    )


def _fetch_github_candidates(
    query: str,
    budget: int,
    seen: set[str],
    tech_stack: list[str],
    cfg: SearchConfig,
) -> list[GithubProfile]:
    profiles: list[GithubProfile] = []
    for raw in search_users(query, max_results=budget * 3):
        if len(profiles) >= budget:
            break
        login = raw["login"]
        if login in seen:
            continue
        seen.add(login)
        full = get_user_profile(login)
        profile = _dict_to_github_profile(full)
        if profile and _github_passes_filter(profile, tech_stack, cfg):
            profiles.append(profile)
    return profiles


def search_github_candidates(
    tech_stack: list[str],
    jd_locations: list[str],
    cfg: SearchConfig,
) -> list[GithubProfile]:
    """Two-pass GitHub candidate search (local city → broad skill query).

    Pass 1 — city-scoped query for the primary non-remote location.
    Pass 2 — skill-only query for the remaining budget.

    Args:
        tech_stack:       Technologies extracted from the JD.
        jd_locations:     Locations extracted from the JD.
        experience_range: (min_years, max_years) tuple.
        cfg:              SearchConfig controlling filter tightness.

    Returns:
        Filtered list of GithubProfile objects.
    """
    seen: set[str] = set()
    stack = " ".join(tech_stack[:2])
    primary_city = next((l for l in jd_locations if "remote" not in l.lower()), None)
    local_budget = int(cfg.max_results * cfg.local_fraction)
    broad_budget = cfg.max_results - local_budget

    local_profiles: list[GithubProfile] = []
    if primary_city:
        q = f'{stack} location:"{primary_city}"'
        logger.info("GitHub pass-1 [max=%d] query: %s", cfg.max_results, q)
        local_profiles = _fetch_github_candidates(q, local_budget, seen, tech_stack, cfg)
        logger.info("GitHub pass-1: %d matched", len(local_profiles))

    logger.info("GitHub pass-2 [max=%d] query: %s", cfg.max_results, stack)
    broad_profiles = _fetch_github_candidates(stack, broad_budget, seen, tech_stack, cfg)
    logger.info("GitHub pass-2: %d new matched", len(broad_profiles))

    return local_profiles + broad_profiles


# ── LinkedIn (Serper) candidate search ───────────────────────────────────────

def _build_linkedin_query(
    tech_stack: list[str],
    location_str: str,
    experience_range: tuple[int, int],
    cfg: SearchConfig,
) -> str:
    """Build a site:linkedin.com/in query with skill anchors and experience signals.

    TIGHT / MEDIUM: both top skills AND-ed.
    LOOSE: one anchor + OR of remaining skills.
    """
    anchors = tech_stack[:cfg.serper_anchor_count]
    anchor_str = " ".join(f'"{t}"' for t in anchors)

    rest_str = ""
    if cfg.serper_anchor_count < len(tech_stack):
        rest = tech_stack[cfg.serper_anchor_count:cfg.serper_anchor_count + 3]
        if rest:
            rest_str = "(" + " OR ".join(f'"{t}"' for t in rest) + ")"

    min_exp, max_exp = experience_range
    exp_year_terms = " OR ".join(
        f'"{y}+ years"' for y in range(min_exp, min(max_exp + 1, min_exp + 4))
    )
    seniority = '"Senior" OR "Lead" OR "Staff" OR "Principal"'
    exp_str = (
        f'({exp_year_terms})'
        if cfg.strict_exp_filter
        else f'({exp_year_terms} OR {seniority})'
    )

    parts = [anchor_str]
    if rest_str:
        parts.append(rest_str)
    parts += [location_str, exp_str]
    return " ".join(p for p in parts if p).strip()


def _linkedin_passes_filter(
    profile: LinkedInProfile,
    tech_stack: list[str],
    experience_range: tuple[int, int],
    cfg: SearchConfig,
) -> bool:
    text = " ".join(filter(None, [profile.headline or "", profile.snippet or ""]))
    if count_keyword_matches(text, tech_stack) < cfg.min_keyword_matches:
        logger.debug("LinkedIn rejected %s — keyword mismatch (need %d)",
                     profile.name, cfg.min_keyword_matches)
        return False
    if cfg.strict_exp_filter:
        years = exp_years_from_text(text)
        if years is not None and years < experience_range[0]:
            logger.debug("LinkedIn rejected %s — exp %d yrs < min %d",
                         profile.name, years, experience_range[0])
            return False
    return True


def _parse_linkedin_result(item: dict) -> LinkedInProfile | None:
    link: str = item.get("link", "")
    if not re.match(r"https?://([a-z]+\.)?linkedin\.com/in/[^/]+/?$", link):
        return None
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    return LinkedInProfile(
        name=_name_from_title(title),
        linkedin_url=link,
        headline=title,
        location=_location_from_snippet(snippet),
        snippet=snippet,
    )


def _name_from_title(title: str) -> str:
    if " - " in title:
        return title.split(" - ")[0].strip()
    if " | " in title:
        return title.split(" | ")[0].strip()
    return title.strip()


def _location_from_snippet(snippet: str) -> str | None:
    for m in re.finditer(r"\b([A-Z][a-zA-Z\s]{2,25}),\s*([A-Z]{2})\b", snippet):
        city, code = m.group(1).strip(), m.group(2)
        if code in _US_STATES:
            return f"{city}, {code}"
    m = re.search(r"\b(Greater\s+)?([A-Z][a-zA-Z\s]{2,25}(?:Area|Region|City))\b", snippet)
    if m:
        return m.group(0).strip()
    return None


def search_linkedin_candidates(
    tech_stack: list[str],
    jd_locations: list[str],
    experience_range: tuple[int, int] | None,
    cfg: SearchConfig,
) -> list[LinkedInProfile]:
    """Two-pass LinkedIn candidate search via Serper (local city → remote).

    Pass 1 — primary non-remote city.
    Pass 2 — remote (only if JD allows remote).

    Args:
        tech_stack:       Technologies extracted from the JD.
        jd_locations:     Locations extracted from the JD.
        experience_range: (min_years, max_years) tuple or None.
        cfg:              SearchConfig controlling filter tightness.

    Returns:
        Filtered list of LinkedInProfile objects.
    """
    exp_range        = experience_range or (0, 99)
    primary_city     = next((l for l in jd_locations if "remote" not in l.lower()), None)
    jd_allows_remote = any("remote" in l.lower() for l in jd_locations)
    local_budget     = int(cfg.max_results * cfg.local_fraction)
    remote_budget    = cfg.max_results - local_budget
    seen_urls: set[str] = set()
    profiles: list[LinkedInProfile] = []

    # Pass 1 — local
    if primary_city:
        q = _build_linkedin_query(tech_stack, f'"{primary_city}"', exp_range, cfg)
        logger.info("LinkedIn pass-1 [max=%d] query: %s", cfg.max_results, q)
        for item in search_site("linkedin.com/in", q, local_budget + 10):
            p = _parse_linkedin_result(item)
            if p and p.linkedin_url not in seen_urls:
                seen_urls.add(p.linkedin_url)
                if _linkedin_passes_filter(p, tech_stack, exp_range, cfg):
                    profiles.append(p)
                    if len(profiles) >= local_budget:
                        break
        logger.info("LinkedIn pass-1: %d matched", len(profiles))

    # Pass 2 — remote
    if jd_allows_remote:
        q = _build_linkedin_query(tech_stack, '"Remote"', exp_range, cfg)
        logger.info("LinkedIn pass-2 [max=%d] query: %s", cfg.max_results, q)
        remote_new: list[LinkedInProfile] = []
        for item in search_site("linkedin.com/in", q, remote_budget + 10):
            p = _parse_linkedin_result(item)
            if p and p.linkedin_url not in seen_urls:
                seen_urls.add(p.linkedin_url)
                if _linkedin_passes_filter(p, tech_stack, exp_range, cfg):
                    remote_new.append(p)
                    if len(remote_new) >= remote_budget:
                        break
        logger.info("LinkedIn pass-2: %d new matched", len(remote_new))
        profiles.extend(remote_new)

    return profiles
