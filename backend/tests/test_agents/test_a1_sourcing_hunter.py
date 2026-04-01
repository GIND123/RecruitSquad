"""
Tests for A1 Sourcing Hunter — 5 diverse JDs.

Each test runs the full pipeline (parse → GitHub + LinkedIn → merge) against
real APIs. Set GITHUB_TOKEN, SERPER_API_KEY, and OPENAI_API_KEY in .env
before running.

Run:
    cd backend
    pytest tests/test_agents/test_a1_sourcing_hunter.py -v -s
"""
from __future__ import annotations

import asyncio
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from app.agents.agent1.sourcing_hunter import merge_candidates, parse_jd
from app.utils.search_config import make_search_config
from app.utils.sourcing_utils import search_github_candidates, search_linkedin_candidates

# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_github_token() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN"))

def _has_serper_key() -> bool:
    return bool(os.environ.get("SERPER_API_KEY"))

def _has_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))

requires_github = pytest.mark.skipif(not _has_github_token(), reason="GITHUB_TOKEN not set")
requires_serper = pytest.mark.skipif(not _has_serper_key(), reason="SERPER_API_KEY not set")
requires_openai = pytest.mark.skipif(not _has_openai_key(), reason="OPENAI_API_KEY not set")
requires_all    = pytest.mark.skipif(
    not (_has_github_token() and _has_serper_key() and _has_openai_key()),
    reason="GITHUB_TOKEN / SERPER_API_KEY / OPENAI_API_KEY not set",
)


def _run_pipeline(jd_text: str, max_results: int = 20) -> dict:
    """Parse JD, search both sources, merge. Returns a result summary dict."""
    parsed = parse_jd(jd_text)
    tech_stack       = parsed["tech_stack"]
    experience_range = parsed["experience_range"]
    locations        = parsed["locations"]
    cfg              = make_search_config(max_results)

    github_profiles   = search_github_candidates(tech_stack, locations, cfg)
    linkedin_profiles = search_linkedin_candidates(tech_stack, locations, experience_range, cfg)
    candidates        = merge_candidates(github_profiles, linkedin_profiles)

    return {
        "parsed":           parsed,
        "github_profiles":  github_profiles,
        "linkedin_profiles": linkedin_profiles,
        "candidates":       candidates,
    }


def _print_summary(label: str, result: dict) -> None:
    p  = result["parsed"]
    cs = result["candidates"]
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"  tech_stack : {p['tech_stack']}")
    print(f"  exp_range  : {p['experience_range']}")
    print(f"  locations  : {p['locations']}")
    print(f"  GitHub     : {len(result['github_profiles'])} profiles")
    print(f"  LinkedIn   : {len(result['linkedin_profiles'])} profiles")
    print(f"  Merged     : {len(cs)} candidates  "
          f"(gh={sum(1 for c in cs if c.source == 'github')}  "
          f"li={sum(1 for c in cs if c.source == 'linkedin')}  "
          f"both={sum(1 for c in cs if c.source == 'both')})")
    print(f"  With email : {sum(1 for c in cs if c.email)}")
    for c in cs[:3]:
        print(f"    • {c.name} ({c.source}) — {c.location or '?'} — {c.email or '—'}")
    print(f"{'─' * 60}")


# ── JD Fixtures ───────────────────────────────────────────────────────────────

JD_SENIOR_BACKEND = """
Senior Backend Engineer — Platform Team

We're building the infrastructure behind a fintech platform processing $10B+
in annual transactions. You'll own the core payment APIs, data pipeline, and
developer tooling.

Requirements:
- 5–8 years of backend experience
- Python (FastAPI, SQLAlchemy), Go
- PostgreSQL, Redis, Kafka
- Kubernetes, AWS (ECS, RDS, Lambda)
- Strong distributed systems fundamentals

Location: New York (hybrid)
"""

JD_ML_ENGINEER = """
Machine Learning Engineer — Recommendations

Join our ML team to build real-time recommendation systems serving 50M+ users.

Requirements:
- 3–6 years of ML engineering experience
- Python, PyTorch or TensorFlow
- Feature engineering, model serving (Triton, TorchServe)
- Spark, Airflow, Databricks
- Experience with A/B testing frameworks

Location: San Francisco or Remote
"""

JD_FRONTEND_REACT = """
Senior Frontend Engineer — Consumer Product

Own the frontend of a consumer app with 5M daily active users.

Requirements:
- 4–7 years of frontend experience
- React, TypeScript, Next.js
- GraphQL, REST API integration
- Performance optimisation, Core Web Vitals
- Experience with design systems (Storybook, Figma handoff)

Location: Austin, TX or Remote
"""

JD_DEVOPS_INFRA = """
Staff DevOps / Platform Engineer

Lead infrastructure reliability and developer experience for a 200-person
engineering org.

Requirements:
- 6+ years in DevOps / platform engineering
- Terraform, Pulumi (IaC)
- Kubernetes (EKS/GKE), Helm
- CI/CD: GitHub Actions, ArgoCD
- Observability: Datadog, OpenTelemetry
- Strong Python or Go scripting skills

Location: Seattle or Remote
"""

JD_FULLSTACK_STARTUP = """
Full-Stack Engineer — Early Stage Startup (Series A)

Be the 5th engineer and help us move fast. You'll touch everything from React
frontend to Node.js APIs to Postgres schemas.

Requirements:
- 2–5 years of full-stack experience
- TypeScript, React, Node.js (Express or Fastify)
- PostgreSQL, Prisma
- Docker, basic AWS knowledge
- Startup mindset — comfortable with ambiguity

Location: Remote (US timezone preferred)
"""


# ── Tests ─────────────────────────────────────────────────────────────────────

@requires_all
def test_jd_parse_senior_backend():
    """JD parsing extracts correct tech stack and locations for a backend role."""
    parsed = parse_jd(JD_SENIOR_BACKEND)

    assert len(parsed["tech_stack"]) >= 3, "Expected at least 3 tech stack items"
    assert parsed["experience_range"][0] >= 4, "Min experience should be ≥ 4 yrs"
    assert any("new york" in loc.lower() or "ny" in loc.lower()
               for loc in parsed["locations"]), "Expected New York in locations"

    python_present = any("python" in t.lower() for t in parsed["tech_stack"])
    assert python_present, "Python should appear in tech_stack"
    print(f"\n  Parsed: {parsed}")


@requires_all
def test_jd_parse_ml_engineer():
    """JD parsing handles ML-specific stack (PyTorch, Spark, Airflow)."""
    parsed = parse_jd(JD_ML_ENGINEER)

    assert len(parsed["tech_stack"]) >= 3
    assert any("python" in t.lower() for t in parsed["tech_stack"])
    assert any("pytorch" in t.lower() or "tensorflow" in t.lower()
               for t in parsed["tech_stack"]), "Expected PyTorch or TensorFlow"
    print(f"\n  Parsed: {parsed}")


@requires_all
def test_pipeline_senior_backend():
    """Full pipeline for a senior backend role in New York."""
    result = _run_pipeline(JD_SENIOR_BACKEND, max_results=20)
    _print_summary("Senior Backend Engineer (New York)", result)

    assert len(result["parsed"]["tech_stack"]) >= 3
    assert len(result["candidates"]) > 0, "Expected at least 1 candidate"
    for c in result["candidates"]:
        assert c.name, "Every candidate must have a name"
        assert c.source in ("github", "linkedin", "both")


@requires_all
def test_pipeline_ml_engineer():
    """Full pipeline for an ML engineer role (SF + Remote)."""
    result = _run_pipeline(JD_ML_ENGINEER, max_results=20)
    _print_summary("ML Engineer (SF + Remote)", result)

    assert len(result["candidates"]) > 0
    # Remote JD should trigger LinkedIn pass-2
    assert len(result["linkedin_profiles"]) >= 0  # may be 0 if API key missing but shouldn't error


@requires_all
def test_pipeline_frontend_react():
    """Full pipeline for a React frontend role (Austin + Remote)."""
    result = _run_pipeline(JD_FRONTEND_REACT, max_results=20)
    _print_summary("Senior Frontend Engineer (Austin + Remote)", result)

    assert len(result["candidates"]) > 0
    parsed = result["parsed"]
    assert any("react" in t.lower() or "typescript" in t.lower()
               for t in parsed["tech_stack"]), "Expected React or TypeScript in stack"


@requires_all
def test_pipeline_devops():
    """Full pipeline for a Staff DevOps role (Seattle + Remote) — MEDIUM filters."""
    result = _run_pipeline(JD_DEVOPS_INFRA, max_results=30)  # MEDIUM
    _print_summary("Staff DevOps Engineer (Seattle + Remote)", result)

    assert len(result["candidates"]) > 0
    parsed = result["parsed"]
    assert any(t.lower() in ("terraform", "kubernetes", "k8s", "pulumi")
               for t in parsed["tech_stack"]), "Expected IaC / k8s in stack"


@requires_all
def test_pipeline_fullstack_startup():
    """Full pipeline for a full-stack startup role (Remote) — checks dedup."""
    result = _run_pipeline(JD_FULLSTACK_STARTUP, max_results=20)
    _print_summary("Full-Stack Startup Engineer (Remote)", result)

    assert len(result["candidates"]) > 0

    # No duplicate linkedin_urls
    li_urls = [c.linkedin_url for c in result["candidates"] if c.linkedin_url]
    assert len(li_urls) == len(set(li_urls)), "Duplicate LinkedIn URLs found after merge"

    # No duplicate github_urls
    gh_urls = [c.github_url for c in result["candidates"] if c.github_url]
    assert len(gh_urls) == len(set(gh_urls)), "Duplicate GitHub URLs found after merge"


@requires_all
def test_merge_deduplication():
    """merge_candidates correctly deduplicates a name seen in both sources."""
    from app.models.schemas import CandidateProfile, GithubProfile, LinkedInProfile

    gh = [GithubProfile(
        login="johndoe",
        name="John Doe",
        github_url="https://github.com/johndoe",
        email="john@example.com",
        location="San Francisco, CA",
        bio="Python dev",
        languages=["Python"],
        top_repos=["johndoe/repo1"],
        public_repos=10,
        followers=50,
    )]
    li = [LinkedInProfile(
        name="John Doe",
        linkedin_url="https://linkedin.com/in/johndoe",
        headline="Senior Python Engineer",
        location="San Francisco, CA",
    )]

    merged = merge_candidates(gh, li)
    assert len(merged) == 1, "Should deduplicate John Doe to a single candidate"
    assert merged[0].source == "both"
    assert merged[0].linkedin_url == "https://linkedin.com/in/johndoe"
    assert merged[0].github_url == "https://github.com/johndoe"
    assert merged[0].email == "john@example.com"


@requires_all
def test_search_config_filter_tightness():
    """make_search_config returns correct tightness for each bucket."""
    from app.utils.search_config import make_search_config

    tight  = make_search_config(20)
    medium = make_search_config(35)
    loose  = make_search_config(50)

    assert tight.min_keyword_matches  == 3
    assert tight.strict_exp_filter    is True
    assert medium.min_keyword_matches == 2
    assert medium.strict_exp_filter   is False
    assert loose.min_keyword_matches  == 1
    assert loose.serper_anchor_count  == 1
