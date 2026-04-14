"""
A7 — Audit Agent
=================
Reads Firestore state and emits a structured audit trail for a job.
Does NOT mutate any data — pure read + report.

Responsibilities:
  1. build_audit_report(job_id) → AuditReport
     - Counts sourced / screened / shortlisted / scheduled / hired / rejected
     - Flags anomalies (e.g. candidates stuck in a stage, missing scores)
     - Summary written by GPT-4o-mini (falls back to template summary)

  2. run_audit(job_id) → dict
     - Thin wrapper: builds report, persists to Firestore under jobs/{job_id}/audit,
       and returns serialisable dict.

Called from:
  - GET /api/jobs/{job_id}/report  (job_controller)
  - Manually triggered cron / admin endpoint (future)
  - LangGraph audit node (future Graph 5)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic models for the audit report
# ══════════════════════════════════════════════════════════════════════════════

class StageCounts(BaseModel):
    sourced: int = 0
    oa_sent: int = 0
    oa_failed: int = 0
    behavioral_complete: int = 0
    scored: int = 0
    shortlisted: int = 0
    interview_scheduled: int = 0
    interview_done: int = 0
    offered: int = 0
    hired: int = 0
    rejected: int = 0
    experience_rejected: int = 0
    location_rejected: int = 0
    salary_rejected: int = 0
    overqualified_rejected: int = 0


class AnomalyFlag(BaseModel):
    candidate_id: str
    name: str
    issue: str


class AuditReport(BaseModel):
    job_id: str
    job_title: str
    generated_at: datetime
    total_candidates: int
    stage_counts: StageCounts
    shortlisted_count: int
    hired_count: int
    rejection_count: int
    conversion_rate_pct: float             # shortlisted / sourced * 100
    avg_composite_score: float | None
    avg_oa_score: float | None
    avg_behavioral_score: float | None
    anomalies: list[AnomalyFlag]
    summary: str


# ══════════════════════════════════════════════════════════════════════════════
# Stage mapping
# ══════════════════════════════════════════════════════════════════════════════

_STAGE_FIELD_MAP: dict[str, str] = {
    "SOURCED":               "sourced",
    "OA_SENT":               "oa_sent",
    "OA_FAILED":             "oa_failed",
    "BEHAVIORAL_COMPLETE":   "behavioral_complete",
    "SCORED":                "scored",
    "SHORTLISTED":           "shortlisted",
    "INTERVIEW_SCHEDULED":   "interview_scheduled",
    "INTERVIEW_DONE":        "interview_done",
    "OFFERED":               "offered",
    "HIRED":                 "hired",
    "REJECTED":              "rejected",
    "EXPERIENCE_REJECTED":   "experience_rejected",
    "LOCATION_REJECTED":     "location_rejected",
    "SALARY_REJECTED":       "salary_rejected",
    "OVERQUALIFIED_REJECTED":"overqualified_rejected",
}


# ══════════════════════════════════════════════════════════════════════════════
# Anomaly detection rules
# ══════════════════════════════════════════════════════════════════════════════

def _detect_anomalies(candidates: list[dict]) -> list[AnomalyFlag]:
    """
    Flag candidates that look stuck or have data issues.
    Rules:
    - OA_SENT but oa_submitted_at is None and created > 7 days ago → stale
    - SCORED but composite_score is None → score missing
    - SHORTLISTED but interview_scheduled is False → scheduling lag
    - BEHAVIORAL_COMPLETE but behavioral_score == 0  → evaluation incomplete
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    flags: list[AnomalyFlag] = []

    for c in candidates:
        cid  = c.get("candidate_id", "?")
        name = c.get("name", "Unknown")
        stage = (c.get("pipeline_stage") or "").upper()

        created_at = c.get("created_at")
        age_days: float | None = None
        if isinstance(created_at, datetime):
            age_days = (now - created_at).total_seconds() / 86400
        elif isinstance(created_at, dict):
            # Firestore Timestamp serialised as dict
            try:
                ts = datetime.fromtimestamp(created_at.get("_seconds", 0), tz=timezone.utc)
                age_days = (now - ts).total_seconds() / 86400
            except Exception:
                pass

        if stage == "OA_SENT" and not c.get("oa_submitted_at"):
            if age_days is not None and age_days > 7:
                flags.append(AnomalyFlag(
                    candidate_id=cid,
                    name=name,
                    issue=(
                        f"OA link sent {age_days:.0f} day(s) ago but candidate "
                        "has not submitted the assessment yet."
                    ),
                ))

        if stage == "SCORED" and c.get("composite_score") is None:
            flags.append(AnomalyFlag(
                candidate_id=cid,
                name=name,
                issue="Pipeline stage is SCORED but composite_score is missing in Firestore.",
            ))

        if stage == "SHORTLISTED" and not c.get("interview_scheduled"):
            flags.append(AnomalyFlag(
                candidate_id=cid,
                name=name,
                issue="Candidate is shortlisted but no interview has been scheduled yet.",
            ))

        if stage == "BEHAVIORAL_COMPLETE":
            b_score = c.get("behavioral_score")
            if b_score is None or float(b_score) == 0.0:
                flags.append(AnomalyFlag(
                    candidate_id=cid,
                    name=name,
                    issue=(
                        "Behavioral round is marked complete but behavioral_score is 0 "
                        "or missing — evaluation may not have run."
                    ),
                ))

    return flags


# ══════════════════════════════════════════════════════════════════════════════
# LLM summary
# ══════════════════════════════════════════════════════════════════════════════

def _generate_summary(
    job_title: str,
    total: int,
    stage_counts: StageCounts,
    shortlisted: int,
    hired: int,
    conversion_rate: float,
    anomalies: list[AnomalyFlag],
    avg_composite: float | None,
) -> str:
    """GPT-4o-mini one-paragraph audit summary. Falls back to template string."""
    if not os.environ.get("OPENAI_API_KEY"):
        return _template_summary(job_title, total, shortlisted, hired, conversion_rate, anomalies)

    try:
        from openai import OpenAI
        client = OpenAI()
        anomaly_block = (
            "\n".join(f"- {a.name}: {a.issue}" for a in anomalies)
            if anomalies else "None detected."
        )
        prompt = f"""You are an HR audit assistant. Write a concise 2-3 sentence audit summary.

Job Title: {job_title}
Total candidates sourced: {total}
Shortlisted: {shortlisted}
Hired: {hired}
Conversion rate: {conversion_rate:.1f}%
Average composite score: {f'{avg_composite:.1f}' if avg_composite is not None else 'N/A'}
Stage breakdown: {stage_counts.model_dump()}
Anomalies:
{anomaly_block}

Write a plain English paragraph summarising the recruitment funnel health, notable metrics,
and any concerns. Avoid bullet points — use flowing prose.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise HR audit assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("[A7] LLM summary failed, using template: %s", exc)
        return _template_summary(job_title, total, shortlisted, hired, conversion_rate, anomalies)


def _template_summary(
    job_title: str,
    total: int,
    shortlisted: int,
    hired: int,
    conversion_rate: float,
    anomalies: list[AnomalyFlag],
) -> str:
    parts = [
        f"Audit for '{job_title}': {total} candidates sourced, "
        f"{shortlisted} shortlisted ({conversion_rate:.1f}% conversion), "
        f"{hired} hired."
    ]
    if anomalies:
        parts.append(f"{len(anomalies)} anomaly(ies) detected requiring attention.")
    else:
        parts.append("No anomalies detected — pipeline is healthy.")
    return " ".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# Core audit builder
# ══════════════════════════════════════════════════════════════════════════════

def build_audit_report(job_id: str) -> AuditReport:
    """
    Read Firestore, compute metrics, detect anomalies, and return an AuditReport.
    Raises ValueError if the job is not found.
    """
    from app.services.firestore_service import get_candidates, get_job

    job = get_job(job_id)
    if not job:
        raise ValueError(f"[A7] Job not found: {job_id}")

    job_title  = str(job.get("title") or "Unknown Role")
    candidates = get_candidates(job_id)
    total      = len(candidates)

    # ── Stage counts ──────────────────────────────────────────────────────────
    counts_dict: dict[str, int] = {v: 0 for v in _STAGE_FIELD_MAP.values()}
    for c in candidates:
        stage = (c.get("pipeline_stage") or "SOURCED").upper()
        field = _STAGE_FIELD_MAP.get(stage, "sourced")
        counts_dict[field] = counts_dict.get(field, 0) + 1
    stage_counts = StageCounts(**counts_dict)

    shortlisted_count = sum(1 for c in candidates if c.get("shortlisted"))
    hired_count       = counts_dict.get("hired", 0)
    rejection_count   = sum(
        counts_dict.get(f, 0)
        for f in ("rejected", "experience_rejected", "location_rejected",
                  "salary_rejected", "overqualified_rejected", "oa_failed")
    )

    # ── Conversion rate ───────────────────────────────────────────────────────
    conversion_rate = (shortlisted_count / total * 100.0) if total > 0 else 0.0

    # ── Score averages ────────────────────────────────────────────────────────
    def _avg(field: str) -> float | None:
        values = [
            float(c[field])
            for c in candidates
            if c.get(field) is not None
        ]
        return round(sum(values) / len(values), 2) if values else None

    avg_composite  = _avg("composite_score")
    avg_oa         = _avg("oa_score")
    avg_behavioral = _avg("behavioral_score")

    # ── Anomaly detection ─────────────────────────────────────────────────────
    anomalies = _detect_anomalies(candidates)

    # ── LLM summary ───────────────────────────────────────────────────────────
    summary = _generate_summary(
        job_title, total, stage_counts, shortlisted_count,
        hired_count, conversion_rate, anomalies, avg_composite,
    )

    return AuditReport(
        job_id=job_id,
        job_title=job_title,
        generated_at=datetime.now(timezone.utc),
        total_candidates=total,
        stage_counts=stage_counts,
        shortlisted_count=shortlisted_count,
        hired_count=hired_count,
        rejection_count=rejection_count,
        conversion_rate_pct=round(conversion_rate, 2),
        avg_composite_score=avg_composite,
        avg_oa_score=avg_oa,
        avg_behavioral_score=avg_behavioral,
        anomalies=anomalies,
        summary=summary,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main entry — run_audit
# ══════════════════════════════════════════════════════════════════════════════

async def run_audit(job_id: str) -> dict[str, Any]:
    """
    Build an AuditReport, persist it to Firestore under jobs/{job_id}.audit,
    and return the serialisable dict.

    Called from the API controller — safe to call multiple times
    (each call refreshes the persisted report).
    """
    from app.services.firestore_service import update_job

    logger.info("[A7] Starting audit for job=%s", job_id)

    report = build_audit_report(job_id)
    report_dict = report.model_dump(mode="json")

    # Persist at the job level so the frontend can read it without re-running
    update_job(job_id, {"audit": report_dict})

    logger.info(
        "[A7] Audit complete: job=%s total=%d shortlisted=%d hired=%d anomalies=%d",
        job_id,
        report.total_candidates,
        report.shortlisted_count,
        report.hired_count,
        len(report.anomalies),
    )

    return report_dict
