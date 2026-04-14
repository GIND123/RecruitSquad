from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models.schemas import ScoreBreakdown
from app.models.states import InterviewRoundState, ScreeningState, SourcingState
from app.services.firestore_service import (
    get_all_interview_feedbacks,
    get_candidate,
    get_candidates,
    get_job,
    save_interview_round,
    update_candidate,
    update_job,
)

logger = logging.getLogger(__name__)

OA_PASS_THRESHOLD        = 70.0   # minimum OA score to proceed past OA stage
SHORTLIST_SCORE_THRESHOLD = 75.0  # minimum composite score to receive an interview invite
INVITE_MULTIPLIER         = 5     # invite up to headcount × this many candidates


# ── New per-dimension scoring helpers ─────────────────────────────────────────

def compute_salary_fit(salary_expected: float, budget_min: float, budget_max: float) -> float:
    """Return 0-100 score for how well salary_expected fits within the job budget."""
    if budget_max <= 0:
        return 50.0  # no budget specified — neutral
    if salary_expected <= 0:
        return 50.0  # candidate didn't specify — neutral
    if salary_expected <= budget_max:
        # Within budget; a slight bonus for being closer to min (saves money)
        if salary_expected <= budget_min:
            return 90.0  # under-budget — very attractive
        # Linearly scale from 80 (at budget_max) to 90 (at budget_min)
        span = max(budget_max - budget_min, 1.0)
        return _clamp_0_100(90.0 - ((salary_expected - budget_min) / span) * 10.0)
    # Over budget — penalty proportional to how much they exceed budget_max
    overage_pct = (salary_expected - budget_max) / budget_max
    return _clamp_0_100(80.0 - overage_pct * 200.0)


def compute_experience_fit(years: float, exp_min: float, exp_max: float) -> float:
    """Return 0-100 score for how well years of experience matches the range."""
    if exp_max <= 0:
        exp_max = 99.0
    if years < exp_min:
        shortfall = exp_min - years
        return _clamp_0_100(100.0 - shortfall * 25.0)
    if years > exp_max:
        excess = years - exp_max
        return _clamp_0_100(85.0 - excess * 5.0)  # mild penalty for overqualified
    return 100.0


def compute_location_fit(
    candidate_location: str,
    job_locations: list[str],
    willing_to_relocate: bool,
) -> float:
    """Return 0 or 100 based on location compatibility."""
    job_locs_lower = [str(loc).lower().strip() for loc in job_locations]
    if any("remote" in loc for loc in job_locs_lower):
        return 100.0
    if willing_to_relocate:
        return 100.0
    cand_loc = str(candidate_location or "").lower().strip()
    if any(cand_loc in loc or loc in cand_loc for loc in job_locs_lower if cand_loc):
        return 100.0
    return 0.0


def score_feedback_form(feedback_data: dict) -> float:
    """
    Convert a structured interview feedback form into a 0-100 score.
    Weights: technical (30%), communication (20%), problem_solving (25%),
             cultural_fit (15%), recommendation (10%).
    Missing fields are skipped and the available weight is renormalised.
    """
    _RECOMMENDATION_MAP = {
        "strong_yes": 100.0,
        "yes":        80.0,
        "neutral":    60.0,
        "no":         40.0,
        "strong_no":  20.0,
    }
    _WEIGHTS = {
        "technical_score":       0.30,
        "communication_score":   0.20,
        "problem_solving_score": 0.25,
        "cultural_fit_score":    0.15,
        "recommendation":        0.10,
    }

    weighted_sum   = 0.0
    total_weight   = 0.0

    for field, weight in _WEIGHTS.items():
        raw = feedback_data.get(field)
        if raw is None:
            continue
        if field == "recommendation":
            value = _RECOMMENDATION_MAP.get(str(raw).lower(), 60.0)
        else:
            value = _clamp_0_100(float(raw) * 10.0)  # 1-10 → 0-100
        weighted_sum  += value * weight
        total_weight  += weight

    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def compute_interview_aggregate_score(feedbacks: list[dict]) -> float:
    """Average score across all rounds' structured feedback forms."""
    if not feedbacks:
        return 0.0
    scores = [score_feedback_form(f) for f in feedbacks]
    return round(sum(scores) / len(scores), 2)


def compute_composite_v2(
    source_score: float,
    oa_score: float,
    behavioral_score: float,
    salary_fit: float,
    experience_fit: float,
    location_fit: float,
    is_referred: bool,
    interview_score: float,
) -> float:
    """Legacy v2 — retained for any callers that haven't migrated yet."""
    referral_score = 100.0 if is_referred else 0.0
    composite = (
        _clamp_0_100(source_score)    * 0.10
        + _clamp_0_100(oa_score)      * 0.20
        + _clamp_0_100(behavioral_score) * 0.15
        + _clamp_0_100(salary_fit)    * 0.15
        + _clamp_0_100(experience_fit) * 0.15
        + _clamp_0_100(location_fit)  * 0.10
        + referral_score              * 0.05
        + _clamp_0_100(interview_score) * 0.10
    )
    return round(composite, 2)


# ── v3 composite (current) ────────────────────────────────────────────────────

def compute_composite_v3(
    resume_jd_score: float,          # 0-100  → 10 pts
    budget_fit: float,               # 0-100  → 5 pts
    location_fit: float,             # 0-100  → 5 pts
    experience_fit: float,           # 0-100  → 5 pts
    is_referred: bool,               # bool   → 5 pts if True
    oa_score: float,                 # 0-100  → 5 pts
    behavioral_score: float,         # 0-100  → 5 pts
    interview_scores: list[float],   # per-round 0-100 from structured feedback
    total_rounds: int,               # configured rounds for this job
) -> float:
    """
    Scoring breakdown (max 100 pts):

      Resume vs JD    10 pts   keyword / CMS match between resume and JD
      Budget fit       5 pts   salary expectation within job budget
      Location         5 pts   candidate location matches job locations
      Experience       5 pts   years of experience within required range
      Referral         5 pts   was referred via a sourced-candidate link
      OA               5 pts   online assessment performance
      Behavioral       5 pts   behavioral interview performance
      Interview rounds 60 pts  60 / total_rounds per completed round
                                (each round scored via structured feedback form)
    """
    pts = 0.0
    pts += _clamp_0_100(resume_jd_score)   * 0.10          # 0–10
    pts += _clamp_0_100(budget_fit)        * 0.05          # 0–5
    pts += _clamp_0_100(location_fit)      * 0.05          # 0–5
    pts += _clamp_0_100(experience_fit)    * 0.05          # 0–5
    pts += (100.0 if is_referred else 0.0) * 0.05          # 0–5
    pts += _clamp_0_100(oa_score)          * 0.05          # 0–5
    pts += _clamp_0_100(behavioral_score)  * 0.05          # 0–5

    # Interview rounds: 60 pts total, evenly split per configured round
    if total_rounds > 0 and interview_scores:
        pts_per_round = 60.0 / total_rounds          # e.g. 20 pts for 3-round job
        for round_score in interview_scores:
            pts += _clamp_0_100(round_score) * (pts_per_round / 100.0)

    return round(pts, 2)


# ── Resume vs JD (CMS) scoring ────────────────────────────────────────────────

_STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "that", "with", "this", "from", "have", "are",
    "will", "your", "you", "our", "their", "they", "been", "also", "can",
    "has", "but", "not", "all", "any", "more", "into", "use", "work",
    "team", "role", "able", "well", "both", "such", "each", "may", "must",
    "should", "would", "strong", "good", "new", "seeking", "looking",
    "required", "requirements", "responsibilities", "experience", "skills",
    "position", "candidate", "company", "join", "about", "including",
})


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        logger.warning("[A5] pypdf not installed — PDF text extraction skipped")
        return ""
    except Exception as exc:
        logger.warning("[A5] PDF extraction error: %s", exc)
        return ""


def _extract_docx_text(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        logger.warning("[A5] python-docx not installed — DOCX text extraction skipped")
        return ""
    except Exception as exc:
        logger.warning("[A5] DOCX extraction error: %s", exc)
        return ""


def _extract_text(data: bytes, filename: str) -> str:
    fname = (filename or "").lower()
    if fname.endswith(".pdf"):
        return _extract_pdf_text(data)
    if fname.endswith(".docx"):
        return _extract_docx_text(data)
    # .doc or plain text — best-effort UTF-8
    return data.decode("utf-8", errors="ignore")


def _cms_score(resume_text: str, jd_text: str) -> float:
    """
    Keyword Content Match Score (0–100).
    Extracts meaningful terms from the JD and counts how many appear in the resume.
    """
    jd_terms = {
        w.lower().strip(".,;:()[]\"'/\\")
        for w in jd_text.split()
        if len(w) > 3 and w.lower().strip(".,;:()[]\"'/\\") not in _STOP_WORDS
    }
    if not jd_terms:
        return 50.0   # no meaningful JD terms — neutral

    resume_lower = resume_text.lower()
    matched = sum(1 for term in jd_terms if term in resume_lower)
    return round(_clamp_0_100((matched / len(jd_terms)) * 100.0), 2)


async def score_resume_vs_jd(
    resume_url: str,
    resume_filename: str,
    jd_text: str,
) -> float:
    """
    Download the candidate's resume from Firebase Storage and compute
    a keyword-based CMS (Content Match Score) against the job description.
    Returns 0–100. Falls back to 0.0 on any download or parse failure.
    """
    if not resume_url or not jd_text:
        return 0.0
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(resume_url)
            resp.raise_for_status()
            file_bytes = resp.content
        resume_text = _extract_text(file_bytes, resume_filename or "")
        if not resume_text.strip():
            logger.warning("[A5] resume text empty after extraction url=%s", resume_url)
            return 0.0
        score = _cms_score(resume_text, jd_text)
        logger.info("[A5] CMS score=%.1f for %s", score, resume_filename)
        return score
    except Exception as exc:
        logger.warning("[A5] resume scoring failed url=%s: %s", resume_url, exc)
        return 0.0


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


def _compute_composite(source_score: float, oa_score: float, behavioral_score: float) -> float:
    """Composite score: source 20% + OA 40% + behavioral 40%."""
    return round(
        _clamp_0_100(source_score) * 0.20
        + _clamp_0_100(oa_score) * 0.40
        + _clamp_0_100(behavioral_score) * 0.40,
        2,
    )


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


async def compute_candidate_score(state: ScreeningState) -> ScreeningState:
    job_id = state["job_id"]
    candidate_id = state["candidate_id"]
    stored  = get_candidate(job_id, candidate_id) or {}
    job     = get_job(job_id) or {}

    jd_text = str(state.get("jd_text") or job.get("role_description") or "")

    oa_score = float(stored.get("oa_score") or _derive_oa_score_from_state(state))
    source_score = float(stored.get("source_score") or state.get("source_score", 0.0) or 0.0)
    behavioral_score = float(
        stored.get("behavioral_score")
        or state.get("behavioral_score", 0.0)
        or evaluate_behavioral_transcript(state.get("behavioral_transcript", []) or [], jd_text)
    )

    # Resume vs JD (CMS) — portal candidates have resume_url; sourced candidates
    # fall back to source_score as a proxy for profile-vs-JD match
    resume_url      = str(stored.get("resume_url") or "")
    resume_filename = str(stored.get("resume_filename") or "")
    if resume_url:
        resume_jd_score = await score_resume_vs_jd(resume_url, resume_filename, jd_text)
    else:
        resume_jd_score = source_score   # GitHub/LinkedIn profile fit as proxy

    budget_fit = compute_salary_fit(
        salary_expected=float(stored.get("salary_expected") or 0.0),
        budget_min=float(job.get("budget_min") or 0.0),
        budget_max=float(job.get("budget_max") or 0.0),
    )
    experience_fit = compute_experience_fit(
        years=float(stored.get("years_experience") or 0.0),
        exp_min=float(job.get("experience_min") or 0.0),
        exp_max=float(job.get("experience_max") or 99.0),
    )
    location_fit = compute_location_fit(
        candidate_location=str(stored.get("candidate_location") or ""),
        job_locations=list(job.get("locations") or []),
        willing_to_relocate=bool(stored.get("willing_to_relocate", False)),
    )
    is_referred   = bool(stored.get("is_referred", False))
    total_rounds  = int(job.get("total_interview_rounds") or 3)

    # No interview rounds completed at screening stage
    composite = compute_composite_v3(
        resume_jd_score=resume_jd_score,
        budget_fit=budget_fit,
        location_fit=location_fit,
        experience_fit=experience_fit,
        is_referred=is_referred,
        oa_score=oa_score,
        behavioral_score=behavioral_score,
        interview_scores=[],
        total_rounds=total_rounds,
    )
    breakdown = ScoreBreakdown(
        source_fit=round(source_score, 2),
        oa_score=round(oa_score, 2),
        behavioral_score=round(behavioral_score, 2),
    )

    update_candidate(
        job_id,
        candidate_id,
        {
            "oa_score":        round(oa_score, 2),
            "oa_passed":       round(oa_score, 2) >= OA_PASS_THRESHOLD,
            "behavioral_score": round(behavioral_score, 2),
            "resume_jd_score": round(resume_jd_score, 2),
            "composite_score": composite,
            "score_breakdown": {
                **breakdown.model_dump(),
                "resume_jd_score":  round(resume_jd_score, 2),
                "budget_fit":       round(budget_fit, 2),
                "experience_fit":   round(experience_fit, 2),
                "location_fit":     round(location_fit, 2),
                "is_referred":      is_referred,
                "interview_scores": [],
                "total_rounds":     total_rounds,
            },
            "pipeline_stage": "SCORED",
        },
    )

    return {
        **state,
        "composite_score": composite,
        "score_breakdown":  breakdown,
        "shortlisted":      False,
        "graph2_complete":  True,
    }


async def run_scoring_engine(state: ScreeningState) -> ScreeningState:
    job_id = state.get("job_id")
    candidate_id = state.get("candidate_id")
    if not job_id or not candidate_id:
        raise ValueError("ScreeningState must include job_id and candidate_id")

    updated_state = await compute_candidate_score(state)
    await recompute_rankings(job_id)

    job      = get_job(job_id) or {}
    headcount = int(job.get("headcount", 1) or 1)
    invite_cap = headcount * INVITE_MULTIPLIER

    candidates = get_candidates(job_id)
    # Sort by composite_score descending, filter by threshold, cap at invite_cap
    scored = sorted(
        [c for c in candidates if (c.get("composite_score") or 0.0) >= SHORTLIST_SCORE_THRESHOLD],
        key=lambda c: c.get("composite_score") or 0.0,
        reverse=True,
    )
    shortlist_ids = {
        c.get("candidate_id")
        for c in scored[:invite_cap]
        if c.get("candidate_id")
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

    invite_cap = headcount * INVITE_MULTIPLIER
    shortlisted_ids: list[str] = []
    for rank, candidate in enumerate(eligible, start=1):
        candidate_id = candidate["candidate_id"]
        # Shortlist if within invite_cap AND composite score meets threshold
        shortlisted = (
            rank <= invite_cap
            and candidate["composite_score"] >= SHORTLIST_SCORE_THRESHOLD
        )
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


async def update_interview_scorecard(state: InterviewRoundState) -> InterviewRoundState:
    """
    Process a single interview round submitted from the interviewer portal.

    Portal drill-down:  Job ID → Candidate → form(result, feedback, completed_at)

    round_number  is auto-derived from candidate.current_round + 1 so the
                  caller never needs to track it manually.
    total_rounds  is resolved in priority order:
                  state['total_rounds'] → candidate.total_rounds → job.total_interview_rounds → 3

    Multiple candidates' rounds can be processed concurrently — each
    candidate owns its own Firestore document so there is no shared state.
    """
    job_id         = state["job_id"]
    candidate_id   = state["candidate_id"]
    round_result   = state["round_result"]
    round_feedback = state["round_feedback"]
    interviewer_name = state.get("interviewer_name")
    interviewer_id   = state.get("interviewer_id")
    completed_at     = state.get("completed_at")   # from interviewer form; None → now()

    # ── Read candidate from Firestore ────────────────────────────────────────
    candidate = get_candidate(job_id, candidate_id)
    if not candidate:
        return {
            **state,
            "next_action": "REJECTED",
            "email_to_candidate": None,
            "email_to_manager": None,
            "salary_report": None,
        }

    candidate_name  = candidate.get("name", "Candidate")
    candidate_email = candidate.get("email", "")

    # ── Auto-derive round_number ─────────────────────────────────────────────
    # Interviewer portal never sends round_number; we compute it from the
    # candidate's persisted current_round so parallel calls stay consistent.
    current_round = int(candidate.get("current_round") or 0)
    round_number  = int(state.get("round_number") or (current_round + 1))

    # ── Auto-derive total_rounds ─────────────────────────────────────────────
    total_rounds = int(state.get("total_rounds") or candidate.get("total_rounds") or 0)
    if not total_rounds:
        job = get_job(job_id) or {}
        total_rounds = int(job.get("total_interview_rounds") or 3)

    logger.info(
        "[A5] interview round: job=%s cid=%s round=%d/%d result=%s interviewer=%s",
        job_id, candidate_id, round_number, total_rounds, round_result, interviewer_name,
    )

    save_interview_round(
        job_id=job_id,
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        round_number=round_number,
        result=round_result,
        feedback=round_feedback,
        interviewer_name=interviewer_name,
        total_rounds=total_rounds,
        completed_at=completed_at,
        interviewer_id=interviewer_id,
    )

    is_rejected   = round_result == "REJECTED"
    is_last_round = round_number >= total_rounds
    if is_rejected:
        next_action = "REJECTED"
        new_stage   = "REJECTED"
    elif is_last_round:
        next_action = "MARKET_ANALYSIS"
        new_stage   = "INTERVIEW_DONE"
    else:
        next_action = "SCHEDULE_NEXT_ROUND"
        new_stage   = "INTERVIEW_SCHEDULED"

    update_candidate(job_id, candidate_id, {"pipeline_stage": new_stage})

    # ── Recompute composite using v3 formula after each round ────────────────
    job       = get_job(job_id) or {}
    job_title = job.get("title", "the role")
    try:
        # Pull all completed-round feedback JSONs from Storage (rounds 1..round_number)
        feedbacks        = get_all_interview_feedbacks(job_id, candidate_id, round_number)
        interview_scores = [score_feedback_form(f) for f in feedbacks]

        resume_jd_score  = float(candidate.get("resume_jd_score") or candidate.get("source_score") or 0.0)
        oa_score         = float(candidate.get("oa_score") or 0.0)
        behavioral_score = float(candidate.get("behavioral_score") or 0.0)
        budget_fit       = compute_salary_fit(
            float(candidate.get("salary_expected") or 0.0),
            float(job.get("budget_min") or 0.0),
            float(job.get("budget_max") or 0.0),
        )
        experience_fit   = compute_experience_fit(
            float(candidate.get("years_experience") or 0.0),
            float(job.get("experience_min") or 0.0),
            float(job.get("experience_max") or 99.0),
        )
        location_fit     = compute_location_fit(
            str(candidate.get("candidate_location") or ""),
            list(job.get("locations") or []),
            bool(candidate.get("willing_to_relocate", False)),
        )
        is_referred  = bool(candidate.get("is_referred", False))
        total_rounds_cfg = int(job.get("total_interview_rounds") or total_rounds or 3)

        new_composite = compute_composite_v3(
            resume_jd_score  = resume_jd_score,
            budget_fit       = budget_fit,
            location_fit     = location_fit,
            experience_fit   = experience_fit,
            is_referred      = is_referred,
            oa_score         = oa_score,
            behavioral_score = behavioral_score,
            interview_scores = interview_scores,
            total_rounds     = total_rounds_cfg,
        )
        update_candidate(job_id, candidate_id, {
            "composite_score":    new_composite,
            "interview_scores":   [round(s, 2) for s in interview_scores],
            "score_breakdown": {
                "resume_jd_score":  round(resume_jd_score, 2),
                "budget_fit":       round(budget_fit, 2),
                "location_fit":     round(location_fit, 2),
                "experience_fit":   round(experience_fit, 2),
                "is_referred":      is_referred,
                "oa_score":         round(oa_score, 2),
                "behavioral_score": round(behavioral_score, 2),
                "interview_scores": [round(s, 2) for s in interview_scores],
                "total_rounds":     total_rounds_cfg,
            },
        })
        logger.info(
            "[A5] v3 composite updated job=%s cid=%s round=%d/%d composite=%.2f "
            "interview_scores=%s",
            job_id, candidate_id, round_number, total_rounds_cfg,
            new_composite, [round(s, 1) for s in interview_scores],
        )
    except Exception as exc:
        logger.warning("[A5] composite v3 recompute failed round=%d: %s", round_number, exc)

    email_to_candidate: dict[str, Any] | None = None
    email_to_manager:   dict[str, Any] | None = None

    if next_action == "REJECTED":
        email_to_candidate = {
            "to":      candidate_email,
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
            "to":      candidate_email,
            "subject": f"Congratulations! You passed Round {round_number} - {job_title}",
            "body": (
                f"Dear {candidate_name},\n\n"
                f"We are pleased to inform you that you have been selected in interview "
                f"round {round_number} for the {job_title} position.\n\n"
                f"You will receive a calendar invite shortly for interview round {next_round}. "
                f"Please confirm your availability.\n\n"
                f"Best regards,\nThe Hiring Team"
            ),
            "type":       "ROUND_SELECTED_CANDIDATE",
            "next_round": next_round,
        }
        email_to_manager = {
            "subject": (
                f"[RecruitSquad] {candidate_name} passed Round {round_number} "
                f"- Schedule Round {next_round}"
            ),
            "body": (
                f"Candidate {candidate_name} (ID: {candidate_id}) passed interview round "
                f"{round_number} for {job_title}.\n\n"
                f"Interviewer feedback:\n{round_feedback}\n\n"
                f"Interviewer: {interviewer_name or 'Not specified'}\n\n"
                f"Next step: schedule interview round {next_round}."
            ),
            "type":       "ROUND_SELECTED_MANAGER",
            "next_round": next_round,
        }
    else:  # MARKET_ANALYSIS
        email_to_manager = {
            "subject": (
                f"[RecruitSquad] {candidate_name} completed all {total_rounds} "
                f"rounds - {job_title}"
            ),
            "body": (
                f"Candidate {candidate_name} (ID: {candidate_id}) has successfully "
                f"completed all {total_rounds} interview rounds for {job_title}.\n\n"
                f"Final round feedback:\n{round_feedback}\n\n"
                f"Interviewer: {interviewer_name or 'Not specified'}\n\n"
                f"Market salary analysis is being generated and will follow shortly."
            ),
            "type": "ALL_ROUNDS_DONE_MANAGER",
        }

    return {
        **state,
        "round_number":       round_number,
        "total_rounds":       total_rounds,
        "next_action":        next_action,
        "email_to_candidate": email_to_candidate,
        "email_to_manager":   email_to_manager,
        "salary_report":      None,
    }