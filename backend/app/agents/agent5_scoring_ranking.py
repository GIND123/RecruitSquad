from __future__ import annotations

import logging

from app.models.schemas import ScoreBreakdown
from app.models.states import ScreeningState
from app.services.firestore_service import get_candidates, update_candidate
from app.utils.stackexchange import search_users_by_tag

logger = logging.getLogger(__name__)


def _clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def compute_composite_score(
    source_score: float,
    oa_score: float,
    behavioral_score: float,
) -> tuple[float, ScoreBreakdown]:
    source_score = _clamp_0_100(source_score)
    oa_score = _clamp_0_100(oa_score)
    behavioral_score = _clamp_0_100(behavioral_score)

    composite = (
        source_score * 0.20 +
        oa_score * 0.40 +
        behavioral_score * 0.40
    )

    breakdown = ScoreBreakdown(
        source_fit=source_score,
        oa_score=oa_score,
        behavioral_score=behavioral_score,
    )

    return round(composite, 2), breakdown


def evaluate_behavioral_transcript(
    transcript: list[dict],
    jd_text: str,
) -> float:
    if not transcript:
        return 0.0

    keywords = [w.lower() for w in jd_text.split() if len(w) > 3][:15]
    if not keywords:
        return 60.0

    score = 50.0
    total_lines = len(transcript)
    if total_lines > 0:
        score += min(30.0, total_lines * 2.0)

    match_count = 0
    for message in transcript:
        text = str(message.get("content", "")).lower()
        for kw in keywords:
            if kw in text:
                match_count += 1

    score += min(40.0, (match_count / max(1, len(keywords))) * 10.0)

    return _clamp_0_100(score)


async def recompute_rankings(job_id: str) -> None:
    candidates = get_candidates(job_id)
    if not candidates:
        logger.info("A5 recompute_rankings: job %s has no candidates", job_id)
        return

    sorted_candidates = sorted(
        candidates,
        key=lambda c: (c.get("composite_score") or 0.0),
        reverse=True,
    )

    for rank, candidate in enumerate(sorted_candidates, start=1):
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            continue

        update_candidate(job_id, candidate_id, {"rank": rank})


def compute_source_scores(job_id: str) -> None:
    candidates = get_candidates(job_id)
    if not candidates:
        logger.info("A5 compute_source_scores: no candidates for job %s", job_id)
        return

    # Simple source-quality estimate via GitHub signals.
    for candidate in candidates:
        cid = candidate.get("candidate_id")
        if not cid:
            continue

        github_signals = candidate.get("github_signals", {})
    followers = float(candidate.get("followers") or github_signals.get("followers", 0))
    repo_count = float(candidate.get("public_repos") or len(github_signals.get("top_repos", [])))

    if not followers and not repo_count:
        # fallback to Stack Exchange ranking if GitHub signal is unavailable
        se_candidates = search_users_by_tag("python")
        if se_candidates:
            # novice heuristic: top answerer (score) -> source_score
            top = se_candidates[0]
            score = min(100.0, (top.get("score", 0) / 200.0) * 100.0)
        else:
            score = 20.0
    else:
        score = min(100.0, (min(followers, 200.0) / 200.0) * 50.0 + min(repo_count, 20.0) / 20.0 * 50.0)

    update_candidate(job_id, cid, {"source_score": round(score, 2)})


async def run_scoring_engine(state: ScreeningState) -> ScreeningState:
    job_id = state.get("job_id")
    candidate_id = state.get("candidate_id")
    if not job_id or not candidate_id:
        raise ValueError("ScreeningState must include job_id and candidate_id")

    source_score = float(state.get("source_score", 0.0))
    if source_score == 0.0:
        # Fall back to candidate-level stored score.
        candidates = get_candidates(job_id)
        for c in candidates or []:
            if c.get("candidate_id") == candidate_id:
                source_score = float(c.get("source_score", 0.0))
                break

    oa_responses = state.get("oa_responses", []) or []
    oa_questions = state.get("oa_questions", []) or []
    oa_score = 0.0
    if oa_questions:
        answer_count = len([r for r in oa_responses if r.get("answer")])
        oa_score = (answer_count / len(oa_questions)) * 100.0

    behavioral_score = evaluate_behavioral_transcript(
        state.get("behavioral_transcript", []) or [],
        state.get("jd_text", ""),
    )

    composite_score, breakdown = compute_composite_score(source_score, oa_score, behavioral_score)

    update_candidate(job_id, candidate_id, {
        "oa_score": round(oa_score, 2),
        "behavioral_score": round(behavioral_score, 2),
        "composite_score": composite_score,
        "score_breakdown": breakdown.model_dump(),
        "pipeline_stage": "SCORED",
    })

    await recompute_rankings(job_id)

    # shortlist top 3 for now (or count relevant to headcount if available)
    candidates = get_candidates(job_id)
    top_rank = 3
    shortlist = {c.get("candidate_id") for c in (candidates[:top_rank] or []) if c.get("candidate_id")}

    shortlisted = candidate_id in shortlist
    update_candidate(job_id, candidate_id, {"shortlisted": shortlisted})

    state.update({
        "oa_score": oa_score,
        "behavioral_score": behavioral_score,
        "composite_score": composite_score,
        "score_breakdown": breakdown,
        "shortlisted": shortlisted,
    })

    return state
