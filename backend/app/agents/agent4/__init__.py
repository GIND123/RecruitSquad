from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import numpy as np

from app.models.schemas import SalaryReport
from app.models.states import CoordinationState
from app.services.firestore_service import (
    get_candidate,
    get_job,
    update_candidate,
    update_job,
)
from app.services.serp_service import search

logger = logging.getLogger(__name__)

_GEMINI_MODEL: Any | None = None
_GEMINI_DISABLED_REASON: str | None = None


def fetch_salary_benchmarks(
    role_title: str,
    location: str,
    tech_stack: list[str],
    experience_years: tuple[int, int],
) -> list[float]:
    """Return deterministic fallback salary points in USD."""
    base = 90000
    seniority = max(0, min(10, experience_years[0] - 1))
    stack_boost = min(0.35, len(tech_stack) * 0.04)

    city_multiplier = 1.0
    lowered_location = location.lower()
    if "san francisco" in lowered_location or "bay area" in lowered_location:
        city_multiplier = 1.35
    elif "new york" in lowered_location:
        city_multiplier = 1.25
    elif "austin" in lowered_location or "seattle" in lowered_location:
        city_multiplier = 1.15

    raw_points: list[float] = []
    for delta in (-10, -5, 0, 5, 10, 15, 20):
        point = base * (1 + seniority * 0.06 + stack_boost) * city_multiplier
        point *= 1 + (delta / 100)
        raw_points.append(round(point, 2))

    raw_points += [round(point * 1.05, 2) for point in raw_points[:3]]

    logger.debug(
        "A4 fallback salary points for role=%s location=%s: %s",
        role_title,
        location,
        raw_points,
    )
    return raw_points


def compute_percentiles(salary_data: list[float]) -> SalaryReport:
    if not salary_data:
        raise ValueError("salary_data must contain at least one value")

    p25, p50, p75, p90 = np.percentile(salary_data, [25, 50, 75, 90]).tolist()

    return SalaryReport(
        job_id="",
        location="",
        role_title="",
        p25=float(p25),
        p50=float(p50),
        p75=float(p75),
        p90=float(p90),
        budget_min=0.0,
        budget_max=0.0,
        budget_warning=False,
        data_sources=["heuristic_fallback"],
        analysis_summary=None,
        generated_at=datetime.now(timezone.utc),
    )


def check_budget_warning(budget_max: float, p25: float) -> bool:
    return budget_max > 0 and budget_max < p25


def _get_gemini_model() -> Any | None:
    global _GEMINI_MODEL, _GEMINI_DISABLED_REASON

    if _GEMINI_MODEL is not None:
        return _GEMINI_MODEL
    if _GEMINI_DISABLED_REASON is not None:
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _GEMINI_DISABLED_REASON = "GEMINI_API_KEY not set"
        logger.info("A4 Gemini disabled: %s", _GEMINI_DISABLED_REASON)
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        _GEMINI_DISABLED_REASON = "google.generativeai package not installed"
        logger.info("A4 Gemini disabled: %s", _GEMINI_DISABLED_REASON)
        return None

    try:
        genai.configure(api_key=api_key)
        _GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as exc:
        _GEMINI_DISABLED_REASON = str(exc)
        logger.warning("A4 Gemini init failed: %s", exc)
        return None

    return _GEMINI_MODEL


def _search_salary_data(role_title: str, location: str) -> list[dict]:
    current_year = datetime.now().year
    next_year = current_year + 1
    queries = [
        f"{role_title} salary {location} site:glassdoor.com",
        f"{role_title} salary {location} site:linkedin.com/salary",
        f"{role_title} compensation {location} levels.fyi",
        f"{role_title} average salary {location} {current_year} {next_year}",
        f"{role_title} total compensation range {location} {current_year}",
    ]

    results: list[dict] = []
    for query in queries:
        hits = search(query, num=5)
        logger.info("A4 Serper query=%r returned %d results", query, len(hits))
        results.extend(hits)

    logger.info(
        "A4 collected %d salary snippets for role=%s location=%s",
        len(results),
        role_title,
        location,
    )
    return results


def _extract_domains(search_results: list[dict]) -> list[str]:
    domains: list[str] = []
    for result in search_results:
        link = str(result.get("link") or "").strip()
        if not link:
            continue
        domain = urlparse(link).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def _coerce_salary_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(float(value))
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def _default_analysis_summary(
    role_title: str,
    location: str,
    budget_min: float,
    budget_max: float,
    p25: int,
    p50: int,
) -> str:
    current_year = datetime.now().year
    if budget_max > 0 and budget_max < p25:
        return (
            f"The {current_year} budget for {role_title} in {location} looks below "
            f"market entry pay because the top of budget is under the P25 benchmark."
        )
    if budget_max >= p50:
        return (
            f"The {current_year} budget for {role_title} in {location} appears "
            f"competitive because it reaches or exceeds the market median."
        )
    if budget_min <= p25 <= budget_max:
        return (
            f"The {current_year} budget for {role_title} in {location} is broadly "
            f"market-aligned and overlaps the lower half of observed salary ranges."
        )
    return (
        f"The {current_year} budget for {role_title} in {location} is somewhat below "
        f"the market median and may reduce offer competitiveness."
    )


def _fallback_salary_data(
    role_title: str,
    location: str,
    tech_stack: list[str],
    experience_range: tuple[int, int],
    budget_min: float,
    budget_max: float,
    search_results: list[dict],
) -> dict[str, Any]:
    fallback_report = compute_percentiles(
        fetch_salary_benchmarks(role_title, location, tech_stack, experience_range)
    )
    p25 = int(round(fallback_report.p25))
    p50 = int(round(fallback_report.p50))
    p75 = int(round(fallback_report.p75))
    p90 = int(round(fallback_report.p90))
    sources = _extract_domains(search_results) or ["heuristic_fallback"]

    return {
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p90": p90,
        "data_sources": sources,
        "analysis_summary": _default_analysis_summary(
            role_title,
            location,
            budget_min,
            budget_max,
            p25,
            p50,
        ),
    }


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _synthesize_salary_data(
    role_title: str,
    location: str,
    budget_min: float,
    budget_max: float,
    search_results: list[dict],
    fallback_data: dict[str, Any],
) -> dict[str, Any]:
    model = _get_gemini_model()
    if model is None:
        return fallback_data

    current_year = datetime.now().year
    snippets = "\n".join(
        f"- [{item.get('title', '')}] {item.get('snippet', '')} ({item.get('link', '')})"
        for item in search_results[:15]
    )

    prompt = f"""
You are a compensation analyst for a recruiting platform.
Estimate annual salary percentiles in USD for the current US market.

Role Title: {role_title}
Location: {location}
Reference Year: {current_year}
Company Budget: ${budget_min:,.0f} to ${budget_max:,.0f}

Search Results:
{snippets if snippets else "No search results available. Use conservative market knowledge."}

Return only valid JSON with these keys:
{{
  "p25": <integer>,
  "p50": <integer>,
  "p75": <integer>,
  "p90": <integer>,
  "data_sources": ["source1", "source2"],
  "analysis_summary": "<one sentence>"
}}
"""

    try:
        response = model.generate_content(prompt)
        text = _strip_code_fences(str(getattr(response, "text", "") or ""))
        payload = json.loads(text)
    except Exception as exc:
        logger.warning("A4 Gemini synthesis failed, using fallback: %s", exc)
        return fallback_data

    p25 = _coerce_salary_int(payload.get("p25"), fallback_data["p25"])
    p50 = _coerce_salary_int(payload.get("p50"), fallback_data["p50"])
    p75 = _coerce_salary_int(payload.get("p75"), fallback_data["p75"])
    p90 = _coerce_salary_int(payload.get("p90"), fallback_data["p90"])

    ordered = sorted([p25, p50, p75, p90])
    p25, p50, p75, p90 = ordered

    data_sources = payload.get("data_sources")
    if not isinstance(data_sources, list) or not data_sources:
        data_sources = fallback_data["data_sources"]
    else:
        data_sources = [str(item) for item in data_sources if str(item).strip()]
        if not data_sources:
            data_sources = fallback_data["data_sources"]

    analysis_summary = str(payload.get("analysis_summary") or "").strip()
    if not analysis_summary:
        analysis_summary = fallback_data["analysis_summary"]

    return {
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p90": p90,
        "data_sources": data_sources,
        "analysis_summary": analysis_summary,
    }


def _build_manager_email(
    role_title: str,
    location: str,
    candidate_name: str,
    budget_min: float,
    budget_max: float,
    salary_report: SalaryReport,
) -> dict[str, Any]:
    current_year = datetime.now().year
    if salary_report.budget_warning:
        budget_note = (
            f"Budget warning: company max (${budget_max:,.0f}) is below "
            f"market P25 (${salary_report.p25:,.0f})."
        )
    else:
        budget_note = (
            f"Budget range (${budget_min:,.0f} to ${budget_max:,.0f}) is within or "
            f"above the lower market band for {current_year}."
        )

    return {
        "subject": (
            f"[RecruitSquad] Market Salary Report - {role_title} | "
            f"Candidate: {candidate_name}"
        ),
        "body": (
            f"Dear Hiring Manager,\n\n"
            f"Below is the {current_year} market salary analysis for the {role_title} "
            f"role in {location}, generated after {candidate_name} completed the "
            f"interview process.\n\n"
            f"P25: ${salary_report.p25:,.0f}\n"
            f"P50: ${salary_report.p50:,.0f}\n"
            f"P75: ${salary_report.p75:,.0f}\n"
            f"P90: ${salary_report.p90:,.0f}\n\n"
            f"Budget: ${budget_min:,.0f} to ${budget_max:,.0f}\n"
            f"{budget_note}\n\n"
            f"Summary: {salary_report.analysis_summary or 'No summary available.'}\n"
            f"Sources: {', '.join(salary_report.data_sources)}\n\n"
            f"Best regards,\nRecruitSquad AI"
        ),
        "type": "SALARY_REPORT_MANAGER",
        "salary_report": salary_report.model_dump(),
        "budget_warning": salary_report.budget_warning,
    }


async def run_market_analyst(state: CoordinationState) -> CoordinationState:
    job_id = state.get("job_id")
    if not job_id:
        raise ValueError("CoordinationState must include job_id")

    candidate_id = state.get("candidate_id")

    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    role_title = job.get("title") or "Software Engineer"
    locations = job.get("locations", ["Remote"])
    primary_location = locations[0] if locations else "Remote"
    tech_stack = job.get("tech_stack", []) or []
    experience_range = (
        int(job.get("experience_min", 0) or 0),
        int(job.get("experience_max", 0) or 0),
    )
    budget_min = float(job.get("budget_min", 0.0) or 0.0)
    budget_max = float(job.get("budget_max", 0.0) or 0.0)

    logger.info(
        "A4 market analysis started job=%s candidate=%s role=%s location=%s",
        job_id,
        candidate_id,
        role_title,
        primary_location,
    )

    search_results = _search_salary_data(role_title, primary_location)
    fallback_data = _fallback_salary_data(
        role_title,
        primary_location,
        tech_stack,
        experience_range,
        budget_min,
        budget_max,
        search_results,
    )
    salary_data = _synthesize_salary_data(
        role_title,
        primary_location,
        budget_min,
        budget_max,
        search_results,
        fallback_data,
    )

    salary_report = SalaryReport(
        job_id=job_id,
        location=primary_location,
        role_title=role_title,
        p25=float(salary_data["p25"]),
        p50=float(salary_data["p50"]),
        p75=float(salary_data["p75"]),
        p90=float(salary_data["p90"]),
        budget_min=budget_min,
        budget_max=budget_max,
        budget_warning=check_budget_warning(budget_max, float(salary_data["p25"])),
        data_sources=list(salary_data["data_sources"]),
        analysis_summary=str(salary_data["analysis_summary"]),
        generated_at=datetime.now(timezone.utc),
    )

    update_job(
        job_id,
        {
            "salary_report": salary_report.model_dump(),
            "graph3_complete": True,
        },
    )

    candidate_name = "the candidate"
    if candidate_id:
        candidate = get_candidate(job_id, candidate_id)
        if candidate:
            candidate_name = candidate.get("name") or candidate_name
            update_candidate(
                job_id,
                candidate_id,
                {"salary_report": salary_report.model_dump()},
            )
        else:
            logger.warning(
                "A4 candidate %s not found under job %s, skipping candidate update",
                candidate_id,
                job_id,
            )

    state["salary_report"] = salary_report
    state["graph3_complete"] = True
    state["email_to_manager"] = _build_manager_email(
        role_title,
        primary_location,
        candidate_name,
        budget_min,
        budget_max,
        salary_report,
    )
    state["email_to_candidate"] = None

    logger.info(
        "A4 market analysis complete job=%s candidate=%s budget_warning=%s",
        job_id,
        candidate_id,
        salary_report.budget_warning,
    )
    return state