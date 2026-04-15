"""
A1 — Sourcing Hunter
====================
Entry node for Graph 1.

Steps:
  1. parse_jd(jd_text)              → tech_stack, experience_range, locations
  2. search_github(...)             → list[GithubProfile]   (local-first, two-pass, filtered)
  3. search_linkedin_via_serp(...)  → list[LinkedInProfile] (local-first, two-pass, filtered)
  4. merge_candidates(...)          → deduplicated list[CandidateProfile]
  5. persist_to_firestore(...)      → writes candidates sub-collection
  6. return updated SourcingState

Filter tightness scales with max_results:
  ≤ 20  TIGHT   — min 3 JD keywords, 2 AND-ed anchor skills, strict exp filter
  ≤ 35  MEDIUM  — min 2 JD keywords, 2 AND-ed anchor skills, soft exp filter
  > 35  LOOSE   — min 1 JD keyword,  1 anchor + OR others,   no exp filter
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import OpenAI

from app.models.schemas import CandidateProfile, GithubProfile, LinkedInProfile
from app.models.states import SourcingState
from app.services.firestore_service import persist_candidates, update_job
from app.utils.search_config import DEFAULT_MAX_RESULTS, make_search_config
from app.utils.sourcing_utils import search_github_candidates, search_linkedin_candidates

logger = logging.getLogger(__name__)


# ── OpenAI client ─────────────────────────────────────────────────────────────

_openai: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI()
    return _openai


# ── 1. JD Parsing ─────────────────────────────────────────────────────────────

def parse_jd(jd_text: str, fallback_exp: tuple[int, int] = (0, 5)) -> dict[str, Any]:
    response = _get_openai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a technical recruiter assistant. "
                    "Given a job description, extract the following as JSON:\n"
                    "  - tech_stack: list of specific technologies, languages, frameworks\n"
                    "  - experience_range: [min_years, max_years] as integers\n"
                    "  - locations: list of locations or ['Remote'] if remote-friendly\n"
                    "Respond ONLY with valid JSON, no explanation."
                ),
            },
            {"role": "user", "content": jd_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    result = json.loads(response.choices[0].message.content)
    tech_stack: list[str] = result.get("tech_stack", [])
    exp = result.get("experience_range") or []
    exp_min = int(exp[0]) if len(exp) > 0 and exp[0] is not None else fallback_exp[0]
    exp_max = int(exp[1]) if len(exp) > 1 and exp[1] is not None else fallback_exp[1]
    experience_range: tuple[int, int] = (exp_min, exp_max)
    locations: list[str] = result.get("locations", [])

    logger.info("JD parsed — tech_stack=%s exp=%s locations=%s",
                tech_stack, experience_range, locations)
    return {"tech_stack": tech_stack, "experience_range": experience_range, "locations": locations}


# ── 2. Merge ──────────────────────────────────────────────────────────────────

def merge_candidates(
    github_profiles: list[GithubProfile],
    linkedin_profiles: list[LinkedInProfile],
) -> list[CandidateProfile]:
    results: list[CandidateProfile] = []
    name_index: dict[str, int] = {}

    for gh in github_profiles:
        cp = CandidateProfile(
            name=gh.name,
            email=gh.email,
            github_url=gh.github_url,
            location=gh.location,
            bio=gh.bio,
            top_repos=gh.top_repos,
            languages=gh.languages,
            public_repos=gh.public_repos,
            followers=gh.followers,
            source="github",
        )
        results.append(cp)
        name_index[_name_key(gh.name)] = len(results) - 1

    for li in linkedin_profiles:
        key = _name_key(li.name)
        if key in name_index:
            cp = results[name_index[key]]
            cp.linkedin_url = li.linkedin_url
            cp.headline     = li.headline
            if not cp.location and li.location:
                cp.location = li.location
            cp.source = "both"
        else:
            results.append(CandidateProfile(
                name=li.name,
                linkedin_url=li.linkedin_url,
                location=li.location,
                bio=li.snippet,
                headline=li.headline,
                source="linkedin",
            ))
            name_index[key] = len(results) - 1

    return results


def _name_key(name: str) -> str:
    parts = name.lower().strip().split()
    return f"{parts[0]}_{parts[-1]}" if len(parts) >= 2 else name.lower().strip()


# ── 3. Main Entry Node ────────────────────────────────────────────────────────

import os as _os

_TEST_MODE   = _os.environ.get("TEST_MODE", "false").lower() in ("1", "true", "yes")
_TEST_GITHUB = _os.environ.get("TEST_CANDIDATE_GITHUB", "abhinavkumar333")


def _fetch_test_candidate() -> CandidateProfile:
    """Fetch the real GitHub profile for the test account and return a CandidateProfile."""
    from app.services.github_service import get_user_profile
    from app.utils.sourcing_utils import _dict_to_github_profile

    raw = get_user_profile(_TEST_GITHUB)
    if raw:
        gh = _dict_to_github_profile(raw)
        if gh:
            return CandidateProfile(
                name=gh.name,
                email=gh.email,
                github_url=gh.github_url,
                location=gh.location,
                bio=gh.bio,
                top_repos=gh.top_repos,
                languages=gh.languages,
                public_repos=gh.public_repos,
                followers=gh.followers,
                source="github",
            )
    # Fallback if GitHub API is unavailable
    logger.warning("[A1] TEST_MODE — could not fetch GitHub profile for %s, using minimal fallback", _TEST_GITHUB)
    return CandidateProfile(
        name=_TEST_GITHUB,
        github_url=f"https://github.com/{_TEST_GITHUB}",
        source="github",
    )


async def run_sourcing_hunter(
    state: SourcingState,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> SourcingState:
    job_id  = state["job_id"]
    jd_text = state["jd_text"]

    if _TEST_MODE:
        logger.info("[A1] TEST_MODE — fetching real GitHub profile for %s", _TEST_GITHUB)
        candidate = _fetch_test_candidate()
        logger.info("[A1] TEST_MODE — sourced name=%s email=%s", candidate.name, candidate.email or "(none)")
        persist_candidates(job_id, [candidate])
        update_job(job_id, {"status": "SOURCING", "tech_stack": []})
        return {
            **state,
            "tech_stack": [],
            "experience_range": state.get("experience_range", (0, 10)),
            "locations": state.get("locations", []),
            "sourced_candidates": [candidate],
            "outreach_sent": False,
            "graph1_complete": False,
        }

    cfg = make_search_config(max_results)
    logger.info("[A1] job=%s max_results=%d → %s", job_id, max_results,
                "TIGHT" if max_results <= 20 else "MEDIUM" if max_results <= 35 else "LOOSE")

    # parse_jd is a blocking OpenAI call — run in thread to avoid blocking the event loop
    parsed           = await asyncio.to_thread(parse_jd, jd_text, state.get("experience_range", (0, 5)))
    tech_stack       = parsed["tech_stack"]
    experience_range = parsed["experience_range"]
    locations        = parsed["locations"]

    loop = asyncio.get_event_loop()
    gh_task = loop.run_in_executor(
        None, lambda: search_github_candidates(tech_stack, locations, cfg)
    )
    li_task = loop.run_in_executor(
        None, lambda: search_linkedin_candidates(tech_stack, locations, experience_range, cfg)
    )
    github_profiles, linkedin_profiles = await asyncio.gather(gh_task, li_task)
    logger.info("[A1] GitHub: %d, LinkedIn: %d", len(github_profiles), len(linkedin_profiles))

    sourced_candidates = merge_candidates(github_profiles, linkedin_profiles)
    logger.info("[A1] Merged: %d unique candidates", len(sourced_candidates))

    if sourced_candidates:
        # Firestore writes are synchronous — run in thread
        await asyncio.to_thread(persist_candidates, job_id, sourced_candidates)
        await asyncio.to_thread(update_job, job_id, {"status": "SOURCING", "tech_stack": tech_stack})

    return {
        **state,
        "tech_stack": tech_stack,
        "experience_range": experience_range,
        "locations": locations,
        "sourced_candidates": sourced_candidates,
        "outreach_sent": False,
        "graph1_complete": False,
    }
