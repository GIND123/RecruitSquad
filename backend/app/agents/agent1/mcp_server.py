"""
A1 Sourcing Hunter — MCP Server
================================
Exposes Agent 1's GitHub and Serper (LinkedIn) candidate-sourcing logic
as MCP tools consumable by Claude or any MCP-compatible client.

Tools:
  parse_job_description     — extract tech_stack / experience / locations from a JD
  search_github_candidates  — GitHub user search with two-pass local + broad strategy
  search_linkedin_candidates — LinkedIn search via Serper (Google) API
  source_candidates         — full pipeline: parse → search both → merge & deduplicate

Environment variables required (see .env.example):
  OPENAI_API_KEY   — for JD parsing (gpt-4o-mini)
  GITHUB_TOKEN     — for GitHub search
  SERPER_API_KEY   — for Serper / LinkedIn search

Run:
  cd backend
  python a1_mcp_server.py

Claude Desktop config:
  {
    "mcpServers": {
      "recruitsquad-a1": {
        "command": "python",
        "args": ["/absolute/path/to/backend/a1_mcp_server.py"],
        "env": {
          "OPENAI_API_KEY": "...",
          "GITHUB_TOKEN": "...",
          "SERPER_API_KEY": "..."
        }
      }
    }
  }
"""
from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path

# Ensure the backend package is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP

from app.agents.agent1.sourcing_hunter import merge_candidates, parse_jd
from app.utils.search_config import make_search_config
from app.utils.sourcing_utils import (
    search_github_candidates as _search_github_candidates,
    search_linkedin_candidates as _search_linkedin_candidates,
)

mcp = FastMCP("RecruitSquad A1 Sourcing Hunter")


# ── Tool 1: Parse JD ──────────────────────────────────────────────────────────

@mcp.tool()
def parse_job_description(jd_text: str) -> dict:
    """Parse a job description and extract structured fields.

    Args:
        jd_text: Raw job description text.

    Returns:
        dict with keys:
          tech_stack       — list of technologies/languages/frameworks
          experience_range — [min_years, max_years]
          locations        — list of cities or ['Remote']
    """
    result = parse_jd(jd_text)
    return {
        "tech_stack": result["tech_stack"],
        "experience_range": list(result["experience_range"]),
        "locations": result["locations"],
    }


# ── Tool 2: GitHub Search ─────────────────────────────────────────────────────

@mcp.tool()
def search_github_candidates(
    tech_stack: list[str],
    locations: list[str],
    max_results: int = 20,
) -> list[dict]:
    """Search GitHub for engineers matching the given tech stack and location.

    Uses a two-pass strategy: first searches locally (city-scoped), then broader.
    Filter tightness scales with max_results (≤20 TIGHT, ≤35 MEDIUM, >35 LOOSE).

    Requires GITHUB_TOKEN env var.

    Args:
        tech_stack:       List of technologies to match (e.g. ['Python', 'FastAPI']).
        locations:        List of locations from the JD (e.g. ['San Francisco', 'Remote']).
        experience_range: [min_years, max_years] integers.
        max_results:      Maximum number of profiles to return (default 20).

    Returns:
        List of dicts with keys: login, name, email, location, bio, github_url,
        languages, top_repos, public_repos, followers.
    """
    cfg = make_search_config(max_results)
    profiles = _search_github_candidates(tech_stack, locations, cfg)
    return [
        {
            "login": p.login,
            "name": p.name,
            "email": p.email,
            "location": p.location,
            "bio": p.bio,
            "github_url": p.github_url,
            "languages": p.languages,
            "top_repos": p.top_repos,
            "public_repos": p.public_repos,
            "followers": p.followers,
        }
        for p in profiles
    ]


# ── Tool 3: LinkedIn / Serper Search ─────────────────────────────────────────

@mcp.tool()
def search_linkedin_candidates(
    tech_stack: list[str],
    locations: list[str],
    experience_range: list[int],
    max_results: int = 20,
) -> list[dict]:
    """Search LinkedIn profiles via the Serper (Google) API.

    Builds targeted site:linkedin.com/in queries with skill anchors and
    experience signals. Two-pass: local city first, then remote (if applicable).

    Requires SERPER_API_KEY env var.

    Args:
        tech_stack:       List of technologies to match.
        locations:        List of locations from the JD.
        experience_range: [min_years, max_years] integers.
        max_results:      Maximum number of profiles to return (default 20).

    Returns:
        List of dicts with keys: name, linkedin_url, headline, location, snippet.
    """
    cfg = make_search_config(max_results)
    exp = (int(experience_range[0]), int(experience_range[1])) if len(experience_range) >= 2 else (0, 99)
    profiles = _search_linkedin_candidates(tech_stack, locations, exp, cfg)
    return [
        {
            "name": p.name,
            "linkedin_url": p.linkedin_url,
            "headline": p.headline,
            "location": p.location,
            "snippet": p.snippet,
        }
        for p in profiles
    ]


# ── Tool 4: Full Pipeline ─────────────────────────────────────────────────────

@mcp.tool()
def source_candidates(jd_text: str, max_results: int = 20) -> dict:
    """Run the full A1 sourcing pipeline for a job description.

    Steps: parse JD → search GitHub + LinkedIn in parallel → merge & deduplicate.

    Requires OPENAI_API_KEY, GITHUB_TOKEN, and SERPER_API_KEY env vars.

    Args:
        jd_text:     Raw job description text.
        max_results: Target number of candidates (controls filter tightness).
                     ≤20 → TIGHT, ≤35 → MEDIUM, >35 → LOOSE.

    Returns:
        dict with keys:
          tech_stack, experience_range, locations — parsed JD fields
          total, github_count, linkedin_count     — sourcing stats
          candidates                              — list of merged CandidateProfile dicts
    """
    parsed = parse_jd(jd_text)
    tech_stack = parsed["tech_stack"]
    experience_range = parsed["experience_range"]
    locations = parsed["locations"]
    cfg = make_search_config(max_results)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        gh_future = executor.submit(_search_github_candidates, tech_stack, locations, cfg)
        li_future = executor.submit(_search_linkedin_candidates, tech_stack, locations, experience_range, cfg)
        github_profiles = gh_future.result()
        linkedin_profiles = li_future.result()

    candidates = merge_candidates(github_profiles, linkedin_profiles)

    return {
        "tech_stack": tech_stack,
        "experience_range": list(experience_range),
        "locations": locations,
        "total": len(candidates),
        "github_count": len(github_profiles),
        "linkedin_count": len(linkedin_profiles),
        "candidates": [
            {
                "name": c.name,
                "email": c.email,
                "source": c.source,
                "location": c.location,
                "github_url": c.github_url,
                "linkedin_url": c.linkedin_url,
                "headline": c.headline,
                "bio": c.bio,
                "languages": c.languages,
                "top_repos": c.top_repos,
                "public_repos": c.public_repos,
                "followers": c.followers,
            }
            for c in candidates
        ],
    }


# ── Tool 5: Merge ─────────────────────────────────────────────────────────────

@mcp.tool()
def merge_sourced_candidates(
    github_profiles: list[dict],
    linkedin_profiles: list[dict],
) -> list[dict]:
    """Merge and deduplicate GitHub and LinkedIn candidate profiles.

    Call this after search_github_candidates and search_linkedin_candidates.
    Pass the raw list outputs from those tools directly.

    Args:
        github_profiles:  Output list from search_github_candidates.
        linkedin_profiles: Output list from search_linkedin_candidates.

    Returns:
        Deduplicated list of candidate dicts. Profiles found on both sources
        are merged into one entry with source='both'.
    """
    from app.models.schemas import GithubProfile, LinkedInProfile

    gh_objects = [GithubProfile(**p) for p in github_profiles]
    li_objects = [LinkedInProfile(**p) for p in linkedin_profiles]
    candidates = merge_candidates(gh_objects, li_objects)
    return [
        {
            "name": c.name,
            "email": c.email,
            "source": c.source,
            "location": c.location,
            "github_url": c.github_url,
            "linkedin_url": c.linkedin_url,
            "headline": c.headline,
            "bio": c.bio,
            "languages": c.languages,
            "top_repos": c.top_repos,
            "public_repos": c.public_repos,
            "followers": c.followers,
        }
        for c in candidates
    ]


if __name__ == "__main__":
    mcp.run()
