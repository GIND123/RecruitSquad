from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.models.schemas import ScoreBreakdown
from app.models.states import InterviewRoundState, ScreeningState, SourcingState
from app.services.firestore_service import (
    get_candidate,
    get_candidates,
    get_job,
    save_interview_round,
    update_candidate,
    update_job,
)

logger = logging.getLogger(__name__)

OA_PASS_THRESHOLD = 70.0


def _clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def compute_composite_score(
    source_score: float,
    oa_score: float,
    behavioral_score: float,
) -> tuple[float, ScoreBreakdown]:
    """Legacy composite helper retained for compatibility with the existing API."""
    source_score = _clamp_0_100(source_score)
    oa_score = _clamp_0_100(oa_score)
    behavioral_score = _clamp_0_100(behavioral_score)

    composite = source_score * 0.20 + oa_score * 0.40 + behavioral_score * 0.40
    breakdown = ScoreBreakdown(
        source_fit=source_score,
        oa_score=oa_score,
        behavioral_score=behavioral_score,
    )
    return round(composite, 2), breakdown


def _compute_composite(oa_score: float, **_: Any) -> float:
    """A5 scorecard composite: OA is the full ranking weight."""
    return round(_clamp_0_100(oa_score), 2)


def evaluate_behavioral_transcript(transcript: list[dict], jd_text: str) -> float:
    if not transcript:
        return 0.0

    keywords = [word.lower() for word in jd_text.split() if len(word) > 3][:15]
    if not keywords:
        return 60.0

    score = 50.0 + min(30.0, len(transcript) * 2.0)
    match_count = 0
    for message in transcript:
        text = str(message.get("content", "")).lower()
        for keyword in keywords:
            if keyword in text:
                match_count += 1

    score += min(40.0, (match_count / max(1, len(keywords))) * 10.0)
    return _clamp_0_100(score)


def _field(candidate: Any, name: str, default: Any = None) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _candidate_languages(candidate: Any) -> list[str]:
    languages = _field(candidate, "languages", None)
    if languages:
        return [str(language) for language in languages]
    github_signals = _field(candidate, "github_signals", {}) or {}
    return [str(language) for language in github_signals.get("languages", [])]


def _candidate_public_repos(candidate: Any) -> int:
    public_repos = _field(candidate, "public_repos", None)
    if public_repos not in (None, ""):
        return int(public_repos)
    github_signals = _field(candidate, "github_signals", {}) or {}
    return len(github_signals.get("top_repos", []) or [])


def _candidate_followers(candidate: Any) -> int:
    followers = _field(candidate, "followers", None)
    if followers not in (None, ""):
        return int(followers)
    github_signals = _field(candidate, "github_signals", {}) or {}
    return int(github_signals.get("followers", 0) or 0)


def _calculate_source_score(candidate: Any, tech_stack: list[str]) -> tuple[float, dict[str, Any]]:
    languages = [language.lower() for language in _candidate_languages(candidate)]
    public_repos = _candidate_public_repos(candidate)
    followers = _candidate_followers(candidate)
    source = str(_field(candidate, "source", "github") or "github").lower()

    base = {"both": 30.0, "github": 20.0, "linkedin": 10.0}.get(source, 10.0)

    matched_languages: list[str] = []
    lang_score = 0.0
    normalized_stack = [tech.lower() for tech in tech_stack]
    if normalized_stack and languages:
        for language in languages:
            if any(language in tech or tech in language for tech in normalized_stack):
                if language not in matched_languages:
                    matched_languages.append(language)
        lang_score = min(40.0, len(matched_languages) * (40.0 / len(normalized_stack)))

    repo_bonus = 15 if public_repos >= 20 else 10 if public_repos >= 5 else 5 if public_repos >= 1 else 0
    follower_bonus = 10 if followers >= 100 else 5 if followers >= 20 else 2 if followers >= 1 else 0
    github_bonus = 0 if source == "linkedin" else min(25, repo_bonus + follower_bonus)

    activity_label = (
        "HIGH"
        if public_repos >= 20
        else "MEDIUM"
        if public_repos >= 5
        else "LOW"
        if public_repos >= 1
        else "NONE"
    )

    source_score = round(min(95.0, base + lang_score + github_bonus), 2)
    signals = {
        "language_match_pct": round((lang_score / 40.0) * 100.0, 1) if normalized_stack else 0.0,
        "matched_languages": matched_languages,
        "github_activity": activity_label,
        "source_quality": source,
    }
    return source_score, signals


def compute_source_scores(job_or_state: str | SourcingState) -> SourcingState | None:
    """Support both the existing job_id call style and the uploaded state-driven flow."""
    if isinstance(job_or_state, str):
        job_id = job_or_state
        candidates = get_candidates(job_id)
        tech_stack: list[str] = []
        for candidate in candidates:
            candidate_id = candidate.get("candidate_id")
            if not candidate_id:
                continue
            score, signals = _calculate_source_score(candidate, tech_stack)
            update_candidate(
                job_id,
                candidate_id,
                {
                    "source_score": score,
                    "source_signals": signals,
                },
            )
        return None

    state = job_or_state
    job_id = state["job_id"]
    tech_stack = [str(tech).lower() for tech in state.get("tech_stack", [])]
    persisted_candidates = {
        (candidate.get("name") or ""): candidate.get("candidate_id")
        for candidate in get_candidates(job_id)
    }

    for candidate in state.get("sourced_candidates", []):
        candidate_name = str(_field(candidate, "name", "") or "")
        candidate_id = persisted_candidates.get(candidate_name)
        if not candidate_id:
            logger.warning("A5 source scoring skipped unknown candidate %s", candidate_name)
            continue

        score, signals = _calculate_source_score(candidate, tech_stack)
        update_candidate(
            job_id,
            candidate_id,
            {
                "source_score": score,
                "source_signals": signals,
            },
        )

    return {**state, "graph1_complete": True}


async def recompute_rankings(job_id: str) -> None:
    candidates = get_candidates(job_id)
    if not candidates:
        logger.info("A5 recompute_rankings: job %s has no candidates", job_id)
        return

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (candidate.get("composite_score") or 0.0),
        reverse=True,
    )

    for rank, candidate in enumerate(sorted_candidates, start=1):
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            continue
        update_candidate(job_id, candidate_id, {"rank": rank})


def update_scorecard_after_behavioral(
    job_id: str,
    candidate_id: str,
    behavioral_transcript: list[dict],
    salary_expected: float,
    years_experience: float,
    willing_to_relocate: bool,
    candidate_location: str,
    behavioral_summary: str = "",
    behavioral_score: float = 0.0,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    job = get_job(job_id) or {}

    experience_min = float(job.get("experience_min", 0) or 0.0)
    experience_max = float(job.get("experience_max", 99) or 99.0)
    budget_max = float(job.get("budget_max", 0) or 0.0)
    job_locations = [str(location).lower().strip() for location in job.get("locations", []) or []]
    job_is_remote = any("remote" in location for location in job_locations)

    base_fields = {
        "behavioral_complete": True,
        "behavioral_scored_at": now,
        "behavioral_transcript": behavioral_transcript,
        "behavioral_summary": behavioral_summary,
        "behavioral_score": round(_clamp_0_100(behavioral_score), 2),
        "years_experience": float(years_experience),
        "willing_to_relocate": bool(willing_to_relocate),
        "candidate_location": candidate_location,
        "salary_expected": float(salary_expected),
    }

    if years_experience < experience_min:
        reason = (
            f"Candidate has {years_experience:.1f} year(s) of experience but the role "
            f"requires at least {experience_min:.0f} year(s)."
        )
        update_candidate(
            job_id,
            candidate_id,
            {
                **base_fields,
                "experience_passed": False,
                "location_passed": None,
                "salary_within_budget": None,
                "pipeline_stage": "EXPERIENCE_REJECTED",
                "rejection_reason": reason,
            },
        )
        return {"proceed": False, "rejection_reason": reason}

    if years_experience > experience_max:
        reason = (
            f"Candidate has {years_experience:.1f} year(s) of experience but the role "
            f"caps experience at {experience_max:.0f} year(s)."
        )
        update_candidate(
            job_id,
            candidate_id,
            {
                **base_fields,
                "experience_passed": False,
                "location_passed": None,
                "salary_within_budget": None,
                "pipeline_stage": "OVERQUALIFIED_REJECTED",
                "rejection_reason": reason,
            },
        )
        return {"proceed": False, "rejection_reason": reason}

    candidate_location_normalized = str(candidate_location or "").lower().strip()
    location_match = any(
        candidate_location_normalized in location or location in candidate_location_normalized
        for location in job_locations
        if "remote" not in location
    )
    location_passed = job_is_remote or willing_to_relocate or location_match
    if not location_passed:
        location_list = ", ".join(
            location for location in (job.get("locations", []) or []) if "remote" not in location.lower()
        ) or "listed job locations"
        reason = (
            f"Candidate is located in '{candidate_location}' and is not willing to relocate. "
            f"The role requires presence in: {location_list}."
        )
        update_candidate(
            job_id,
            candidate_id,
            {
                **base_fields,
                "experience_passed": True,
                "location_passed": False,
                "salary_within_budget": None,
                "pipeline_stage": "LOCATION_REJECTED",
                "rejection_reason": reason,
            },
        )
        return {"proceed": False, "rejection_reason": reason}

    salary_within_budget = True if budget_max <= 0 else salary_expected <= budget_max
    if not salary_within_budget:
        reason = (
            f"Candidate requested salary ${salary_expected:,.0f} which exceeds the job "
            f"budget cap of ${budget_max:,.0f}."
        )
        update_candidate(
            job_id,
            candidate_id,
            {
                **base_fields,
                "experience_passed": True,
                "location_passed": True,
                "salary_within_budget": False,
                "pipeline_stage": "SALARY_REJECTED",
                "rejection_reason": reason,
            },
        )
        return {"proceed": False, "rejection_reason": reason}

    update_candidate(
        job_id,
        candidate_id,
        {
            **base_fields,
            "experience_passed": True,
            "location_passed": True,
            "salary_within_budget": True,
            "pipeline_stage": "BEHAVIORAL_COMPLETE",
            "rejection_reason": None,
        },
    )
    return {"proceed": True, "rejection_reason": None}


def update_scorecard_after_oa(job_id: str, candidate_id: str, oa_score: float) -> dict[str, Any]:
    oa_score = round(_clamp_0_100(oa_score), 2)
    oa_passed = oa_score >= OA_PASS_THRESHOLD
    update_candidate(
        job_id,
        candidate_id,
        {
            "oa_score": oa_score,
            "oa_passed": oa_passed,
            "oa_scored_at": datetime.now(timezone.utc),
            "pipeline_stage": "OA_SENT" if oa_passed else "OA_FAILED",
        },
    )
    return {"proceed": oa_passed, "oa_passed": oa_passed, "oa_score": oa_score}


def _derive_oa_score_from_state(state: ScreeningState) -> float:
    oa_questions = state.get("oa_questions", []) or []
    if not oa_questions:
        return float(state.get("oa_score", 0.0) or 0.0)

    oa_responses = state.get("oa_responses", []) or []
    answer_count = 0
    for response in oa_responses:
        answer = response.get("answer") if isinstance(response, dict) else getattr(response, "answer", None)
        if answer:
            answer_count += 1
    return (answer_count / len(oa_questions)) * 100.0


def compute_candidate_score(state: ScreeningState) -> ScreeningState:
    job_id = state["job_id"]
    candidate_id = state["candidate_id"]
    stored = get_candidate(job_id, candidate_id) or {}

    oa_score = float(stored.get("oa_score") or _derive_oa_score_from_state(state))
    source_score = float(stored.get("source_score") or state.get("source_score", 0.0) or 0.0)
    behavioral_score = float(
        stored.get("behavioral_score")
        or state.get("behavioral_score", 0.0)
        or evaluate_behavioral_transcript(state.get("behavioral_transcript", []) or [], state.get("jd_text", ""))
    )

    composite = _compute_composite(oa_score=oa_score, source_score=source_score, behavioral_score=behavioral_score)
    breakdown = ScoreBreakdown(
        source_fit=round(source_score, 2),
        oa_score=round(oa_score, 2),
        behavioral_score=round(behavioral_score, 2),
    )

    update_candidate(
        job_id,
        candidate_id,
        {
            "oa_score": round(oa_score, 2),
            "oa_passed": round(oa_score, 2) >= OA_PASS_THRESHOLD,
            "behavioral_score": round(behavioral_score, 2),
            "composite_score": composite,
            "score_breakdown": breakdown.model_dump(),
            "pipeline_stage": "SCORED",
        },
    )

    return {
        **state,
        "composite_score": composite,
        "score_breakdown": breakdown,
        "shortlisted": False,
        "graph2_complete": True,
    }


async def run_scoring_engine(state: ScreeningState) -> ScreeningState:
    job_id = state.get("job_id")
    candidate_id = state.get("candidate_id")
    if not job_id or not candidate_id:
        raise ValueError("ScreeningState must include job_id and candidate_id")

    updated_state = compute_candidate_score(state)
    await recompute_rankings(job_id)

    candidates = get_candidates(job_id)
    shortlist_ids = {
        candidate.get("candidate_id")
        for candidate in (candidates[:3] or [])
        if candidate.get("candidate_id")
    }
    shortlisted = candidate_id in shortlist_ids
    update_candidate(job_id, candidate_id, {"shortlisted": shortlisted})

    updated_state["shortlisted"] = shortlisted
    return updated_state


def run_scoring_ranking(state: dict[str, Any]) -> dict[str, Any]:
    job_id = state["job_id"]
    job = get_job(job_id) or {}
    headcount = int(job.get("headcount", 3) or 3)

    all_candidates = get_candidates(job_id)
    if not all_candidates:
        return {**state, "shortlisted_candidates": []}

    eligible: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []
    for candidate in all_candidates:
        exp_ok = bool(candidate.get("experience_passed"))
        loc_ok = bool(candidate.get("location_passed"))
        sal_ok = bool(candidate.get("salary_within_budget"))
        oa_ok = bool(candidate.get("oa_passed"))
        behavioral_complete = bool(candidate.get("behavioral_complete"))

        if exp_ok and loc_ok and sal_ok and oa_ok and behavioral_complete:
            composite = float(candidate.get("composite_score") or candidate.get("oa_score", 0.0) or 0.0)
            eligible.append({**candidate, "composite_score": composite})
        else:
            ineligible.append(candidate)

    for candidate in ineligible:
        candidate_id = candidate.get("candidate_id")
        if candidate_id:
            update_candidate(job_id, candidate_id, {"shortlisted": False, "rank": None})

    if not eligible:
        return {**state, "shortlisted_candidates": []}

    eligible.sort(key=lambda candidate: candidate["composite_score"], reverse=True)

    shortlisted_ids: list[str] = []
    for rank, candidate in enumerate(eligible, start=1):
        candidate_id = candidate["candidate_id"]
        shortlisted = rank <= headcount
        update_candidate(
            job_id,
            candidate_id,
            {
                "rank": rank,
                "composite_score": candidate["composite_score"],
                "shortlisted": shortlisted,
                "pipeline_stage": "SHORTLISTED" if shortlisted else "SCORED",
            },
        )
        if shortlisted:
            shortlisted_ids.append(candidate_id)

    update_job(job_id, {"status": "SCHEDULING"})
    return {**state, "shortlisted_candidates": shortlisted_ids}


def update_interview_scorecard(state: InterviewRoundState) -> InterviewRoundState:
    job_id = state["job_id"]
    candidate_id = state["candidate_id"]
    round_number = state["round_number"]
    round_result = state["round_result"]
    round_feedback = state["round_feedback"]
    interviewer_name = state.get("interviewer_name")
    total_rounds = state["total_rounds"]

    candidate = get_candidate(job_id, candidate_id)
    if not candidate:
        return {
            **state,
            "next_action": "REJECTED",
            "email_to_candidate": None,
            "email_to_manager": None,
            "salary_report": None,
        }

    candidate_name = candidate.get("name", "Candidate")
    candidate_email = candidate.get("email", "")

    save_interview_round(
        job_id=job_id,
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        round_number=round_number,
        result=round_result,
        feedback=round_feedback,
        interviewer_name=interviewer_name,
        total_rounds=total_rounds,
    )

    is_rejected = round_result == "REJECTED"
    is_last_round = round_number >= total_rounds
    if is_rejected:
        next_action = "REJECTED"
        new_stage = "REJECTED"
    elif is_last_round:
        next_action = "MARKET_ANALYSIS"
        new_stage = "INTERVIEW_DONE"
    else:
        next_action = "SCHEDULE_NEXT_ROUND"
        new_stage = "INTERVIEW_SCHEDULED"

    update_candidate(job_id, candidate_id, {"pipeline_stage": new_stage})

    job = get_job(job_id) or {}
    job_title = job.get("title", "the role")

    email_to_candidate: dict[str, Any] | None = None
    email_to_manager: dict[str, Any] | None = None

    if next_action == "REJECTED":
        email_to_candidate = {
            "to": candidate_email,
            "subject": f"Update on your application for {job_title}",
            "body": (
                f"Dear {candidate_name},\n\n"
                f"Thank you for your time interviewing for the {job_title} position. "
                f"After careful consideration, we have decided not to move forward "
                f"with your application at this time.\n\n"
                f"We appreciate the effort you put into the interview process and "
                f"encourage you to apply for future openings.\n\n"
                f"Best regards,\nThe Hiring Team"
            ),
            "type": "REJECTION_CANDIDATE",
        }
        email_to_manager = {
            "subject": f"[RecruitSquad] {candidate_name} - Rejected at Round {round_number}",
            "body": (
                f"Candidate {candidate_name} (ID: {candidate_id}) was rejected at "
                f"interview round {round_number} of {total_rounds} for the {job_title} role.\n\n"
                f"Interviewer feedback:\n{round_feedback}\n\n"
                f"Interviewer: {interviewer_name or 'Not specified'}"
            ),
            "type": "REJECTION_MANAGER",
        }
    elif next_action == "SCHEDULE_NEXT_ROUND":
        next_round = round_number + 1
        email_to_candidate = {
            "to": candidate_email,
            "subject": f"Congratulations! You passed Round {round_number} - {job_title}",
            "body": (
                f"Dear {candidate_name},\n\n"
                f"We are pleased to inform you that you have been selected in interview "
                f"round {round_number} for the {job_title} position.\n\n"
                f"You will receive a calendar invite shortly for interview round {next_round}. "
                f"Please confirm your availability.\n\n"
                f"Best regards,\nThe Hiring Team"
            ),
            "type": "ROUND_SELECTED_CANDIDATE",
            "next_round": next_round,
        }
        email_to_manager = {
            "subject": f"[RecruitSquad] {candidate_name} passed Round {round_number} - Schedule Round {next_round}",
            "body": (
                f"Candidate {candidate_name} (ID: {candidate_id}) passed interview round {round_number} "
                f"for {job_title}.\n\n"
                f"Interviewer feedback:\n{round_feedback}\n\n"
                f"Interviewer: {interviewer_name or 'Not specified'}\n\n"
                f"Next step: interview round {next_round} should be scheduled."
            ),
            "type": "ROUND_SELECTED_MANAGER",
            "next_round": next_round,
        }
    else:
        email_to_manager = {
            "subject": f"[RecruitSquad] {candidate_name} completed all {total_rounds} rounds - {job_title}",
            "body": (
                f"Candidate {candidate_name} (ID: {candidate_id}) has successfully completed all "
                f"{total_rounds} interview rounds for {job_title}.\n\n"
                f"Final round feedback:\n{round_feedback}\n\n"
                f"Interviewer: {interviewer_name or 'Not specified'}\n\n"
                f"Market salary analysis is being generated and will follow shortly."
            ),
            "type": "ALL_ROUNDS_DONE_MANAGER",
        }

    return {
        **state,
        "next_action": next_action,
        "email_to_candidate": email_to_candidate,
        "email_to_manager": email_to_manager,
        "salary_report": None,
    }