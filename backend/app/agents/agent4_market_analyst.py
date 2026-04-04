from __future__ import annotations

import logging
from statistics import mean
from typing import List

import numpy as np

from app.models.schemas import SalaryReport
from app.models.states import CoordinationState
from app.services.firestore_service import get_job, update_job

logger = logging.getLogger(__name__)


def fetch_salary_benchmarks(
    role_title: str,
    location: str,
    tech_stack: List[str],
    experience_years: tuple[int, int],
) -> List[float]:
    """Mocked salary benchmarking aggregator.

    Real implementation should call:
      - Levels.fyi
      - BLS Occupational Employment Stats
      - LinkedIn Salary Insights

    Returns raw salary data points in USD.
    """
    base = 90000
    seniority = max(0, min(10, experience_years[0] - 1))
    stack_boost = min(0.35, len(tech_stack) * 0.04)

    city_multiplier = 1.0
    if "san francisco" in location.lower() or "bay area" in location.lower():
        city_multiplier = 1.35
    elif "new york" in location.lower():
        city_multiplier = 1.25
    elif "austin" in location.lower() or "seattle" in location.lower():
        city_multiplier = 1.15

    raw_points: list[float] = []
    for delta in (-10, -5, 0, 5, 10, 15, 20):
        point = base * (1 + seniority * 0.06 + stack_boost) * city_multiplier
        point *= 1 + (delta / 100)
        raw_points.append(round(point, 2))

    # Add a small spread for data variance
    raw_points += [round(x * 1.05, 2) for x in raw_points[:3]]

    logger.debug(
        "A4 salary benchmark raw points for role=%s location=%s: %s",
        role_title,
        location,
        raw_points,
    )

    return raw_points


def compute_percentiles(salary_data: List[float]) -> SalaryReport:
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
        data_sources=["levels.fyi", "bls", "linkedin"],
        generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )


def check_budget_warning(budget_max: float, p25: float) -> bool:
    return budget_max < p25


async def run_market_analyst(state: CoordinationState) -> CoordinationState:
    job_id = state.get("job_id")
    if not job_id:
        raise ValueError("CoordinationState must include job_id")

    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    role_title = job.get("title", "")
    locations = job.get("locations", [""])
    primary_location = locations[0] if locations else "Remote"
    tech_stack = job.get("tech_stack", []) or []
    experience_range = (
        job.get("experience_min", 0),
        job.get("experience_max", 0),
    )

    raw = fetch_salary_benchmarks(role_title, primary_location, tech_stack, experience_range)
    salary_report = compute_percentiles(raw)

    salary_report.job_id = job_id
    salary_report.location = primary_location
    salary_report.role_title = role_title
    salary_report.budget_min = job.get("budget_min", 0.0)
    salary_report.budget_max = job.get("budget_max", 0.0)
    salary_report.data_sources = ["levels.fyi", "bls", "linkedin"]

    salary_report.budget_warning = check_budget_warning(salary_report.budget_max, salary_report.p25)

    update_job(job_id, {
        "salary_report": salary_report.model_dump(),
        "graph3_complete": True,
    })

    state["salary_report"] = salary_report
    state["graph3_complete"] = True
    return state
