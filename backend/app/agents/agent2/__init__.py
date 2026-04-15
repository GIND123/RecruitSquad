"""
A2 — Behavioral Chat + OA Generator
=====================================
Triggered by Graph 1 (after A1 sources a candidate) or directly via the
/api/jobs/{job_id}/candidates/{candidate_id}/start-screening endpoint.

Steps:
  1. generate_oa_questions(jd_text, tech_stack) → list[OAQuestion]
  2. generate_behavioral_questions(jd_text)     → list[str]
  3. persist oa_questions + behavioral_questions + oa_token to Firestore
  4. update pipeline_stage → OA_SENT
  5. Return updated ScreeningState

For active behavioral chat (per-message calls):
  conduct_behavioral_chat(candidate_id, message, history) → str (next agent reply)

For OA scoring (called by A5 after candidate submits):
  evaluate_oa_responses(questions, responses) → float (0–100)

LLM: OpenAI GPT-4o-mini (OPENAI_API_KEY from .env — same key as A1 / A4)
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

from app.models.schemas import OAQuestion, OAResponse
from app.models.states import ScreeningState
from app.services.firestore_service import get_candidate, get_job, update_candidate

logger = logging.getLogger(__name__)

# ── OpenAI lazy singleton (same pattern as A1 / A4) ───────────────────────────
_openai: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI()   # reads OPENAI_API_KEY from env automatically
    return _openai


# ══════════════════════════════════════════════════════════════════════════════
# 1. OA Question Generation
# ══════════════════════════════════════════════════════════════════════════════

def generate_oa_questions(
    jd_text: str,
    tech_stack: list[str],
    n_mcq: int = 5,
    n_coding: int = 2,
    n_text: int = 3,
) -> list[OAQuestion]:
    """
    LLM call: generate a mixed Online Assessment for the given JD.
    Returns a list of OAQuestion objects ready to persist to Firestore.
    Falls back to a minimal hardcoded set if OpenAI is unavailable.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("[A2] OPENAI_API_KEY not set — using fallback OA questions")
        return _fallback_oa_questions(tech_stack)

    stack_str = ", ".join(tech_stack) if tech_stack else "software engineering"

    prompt = f"""You are a senior technical interviewer creating an Online Assessment.

Job Description (excerpt):
{jd_text[:2000]}

Tech Stack Required: {stack_str}

Generate a JSON object with exactly this structure:
{{
  "questions": [
    {{
      "question_text": "<question>",
      "type": "MCQ",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "time_limit_minutes": 2
    }},
    ... (repeat for {n_mcq} MCQ questions)
    {{
      "question_text": "<coding problem statement>",
      "type": "CODING",
      "options": null,
      "time_limit_minutes": 20
    }},
    ... (repeat for {n_coding} CODING questions)
    {{
      "question_text": "<open-ended question>",
      "type": "TEXT",
      "options": null,
      "time_limit_minutes": 5
    }}
    ... (repeat for {n_text} TEXT questions)
  ]
}}

Rules:
- MCQ questions must test specific knowledge of the tech stack ({stack_str}).
- CODING questions must be solvable in 20 minutes by a competent engineer.
- TEXT questions should assess problem-solving mindset and communication.
- Return ONLY valid JSON, no markdown, no explanation.
"""

    try:
        client = _get_openai()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior technical interviewer. "
                        "Return only valid JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        raw_questions: list[dict] = payload.get("questions", [])
    except Exception as exc:
        logger.warning("[A2] OA generation failed, using fallback: %s", exc)
        return _fallback_oa_questions(tech_stack)

    questions: list[OAQuestion] = []
    for q in raw_questions:
        try:
            questions.append(
                OAQuestion(
                    question_id=str(uuid.uuid4()),
                    question_text=str(q.get("question_text", "")).strip(),
                    type=q.get("type", "TEXT"),  # type: ignore[arg-type]
                    options=q.get("options") or None,
                    time_limit_minutes=q.get("time_limit_minutes"),
                )
            )
        except Exception as parse_exc:
            logger.warning("[A2] Skipping malformed OA question: %s | %s", q, parse_exc)

    if not questions:
        logger.warning("[A2] LLM returned no valid questions — using fallback")
        return _fallback_oa_questions(tech_stack)

    logger.info("[A2] Generated %d OA questions (MCQ=%d, CODING=%d, TEXT=%d)",
                len(questions),
                sum(1 for q in questions if q.type == "MCQ"),
                sum(1 for q in questions if q.type == "CODING"),
                sum(1 for q in questions if q.type == "TEXT"))
    return questions


def _fallback_oa_questions(tech_stack: list[str]) -> list[OAQuestion]:
    """Minimal hardcoded questions used when OpenAI is unavailable."""
    stack_str = ", ".join(tech_stack[:3]) if tech_stack else "your primary language"
    return [
        OAQuestion(
            question_id=str(uuid.uuid4()),
            question_text=f"Which of the following best describes the purpose of {stack_str}?",
            type="MCQ",
            options=[
                "A. Data serialisation only",
                "B. Building scalable software systems",
                "C. Hardware interfacing",
                "D. Network packet routing",
            ],
            time_limit_minutes=2,
        ),
        OAQuestion(
            question_id=str(uuid.uuid4()),
            question_text=(
                "Write a function that accepts a list of integers and returns "
                "the two indices whose values sum to a given target. "
                "Optimise for O(n) time complexity."
            ),
            type="CODING",
            options=None,
            time_limit_minutes=20,
        ),
        OAQuestion(
            question_id=str(uuid.uuid4()),
            question_text=(
                "Describe a technically challenging project you have worked on. "
                "What was the problem, your approach, and the outcome?"
            ),
            type="TEXT",
            options=None,
            time_limit_minutes=5,
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Behavioral Question Generation
# ══════════════════════════════════════════════════════════════════════════════

def generate_behavioral_questions(jd_text: str, n: int = 5) -> list[str]:
    """
    LLM call: generate STAR-format behavioral questions tailored to the JD.
    Falls back to generic questions if OpenAI is unavailable.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return _fallback_behavioral_questions()

    prompt = f"""You are an experienced behavioral interviewer.

Given this job description:
{jd_text[:2000]}

Generate exactly {n} behavioral interview questions using the STAR format (Situation, Task, Action, Result).
Focus on:
- Collaboration and communication
- Handling ambiguity and pressure
- Technical decision-making
- Leadership or mentorship (if applicable)
- Meeting deadlines / prioritisation

Return ONLY a JSON object with this exact structure:
{{
  "questions": ["<question 1>", "<question 2>", ..., "<question {n}>"]
}}
No markdown, no explanation — pure JSON only.
"""
    try:
        client = _get_openai()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an experienced behavioral interviewer. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        questions: list[str] = [str(q).strip() for q in payload.get("questions", []) if str(q).strip()]
    except Exception as exc:
        logger.warning("[A2] Behavioral question generation failed: %s", exc)
        return _fallback_behavioral_questions()

    if not questions:
        return _fallback_behavioral_questions()

    logger.info("[A2] Generated %d behavioral questions", len(questions))
    return questions[:n]


def _fallback_behavioral_questions() -> list[str]:
    return [
        "Tell me about a time you had to learn a new technology quickly. How did you approach it?",
        "Describe a situation where you disagreed with a team decision. What did you do?",
        "Give an example of a project where you had to meet a tight deadline. How did you manage it?",
        "Tell me about a time you received critical feedback. How did you respond?",
        "Describe a complex technical problem you solved. Walk me through your thinking process.",
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 3. Behavioral Chat (per-message, conversational)
# ══════════════════════════════════════════════════════════════════════════════

async def conduct_behavioral_chat(
    candidate_id: str,
    job_id: str,
    candidate_message: str,
    history: list[dict[str, str]],
) -> str:
    """
    Process one message from a candidate in the behavioral chat.
    Maintains conversational history. Returns the agent's next reply.

    History format: [{"role": "assistant"|"user", "content": str}, ...]
    """
    candidate = get_candidate(job_id, candidate_id) or {}
    job = get_job(job_id) or {}

    behavioral_questions: list[str] = candidate.get("behavioral_questions") or _fallback_behavioral_questions()
    role_title = job.get("title", "the role")
    questions_block = "\n".join(f"{i+1}. {q}" for i, q in enumerate(behavioral_questions))

    system_prompt = f"""You are a professional behavioral interviewer conducting a screening for the '{role_title}' position.

Your assigned questions are:
{questions_block}

Instructions:
- Ask one question at a time. Start with question 1 if history is empty.
- After the candidate answers, provide a brief warm acknowledgement (1 sentence), then ask the next unanswered question.
- If you have asked all {len(behavioral_questions)} questions and the candidate has answered them all, end the session: thank the candidate warmly and say "The interview session is now complete."
- Keep responses concise and professional.
- Do NOT reveal scores, evaluations, or internal assessments to the candidate.
- STRICT OFF-TOPIC RULE: If the candidate sends ANY message unrelated to answering the interview question (e.g. asking for code samples, trivia, general knowledge questions, jokes, or anything outside the interview), do NOT answer it. Respond only with: "I can only assist with the behavioral interview. Let's continue — " followed by re-asking the current unanswered question verbatim. Never write code, solve puzzles, or answer general knowledge questions under any circumstances.
"""

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in history[-20:]:   # cap context to last 20 turns
        role = "assistant" if turn.get("role") in ("assistant", "agent") else "user"
        messages.append({"role": role, "content": str(turn.get("content", ""))})
    messages.append({"role": "user", "content": candidate_message})

    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("[A2] OPENAI_API_KEY not set — returning fallback chat reply")
        return behavioral_questions[0] if history == [] else "Thank you for your response. Let us move on."

    try:
        client = _get_openai()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            temperature=0.5,
            max_tokens=400,
        )
        reply = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("[A2] Behavioral chat LLM call failed: %s", exc)
        reply = "I'm sorry, I'm having trouble processing that. Could you please repeat your answer?"

    return reply


# ══════════════════════════════════════════════════════════════════════════════
# 4. OA Evaluation (called by A5 after candidate submits)
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_oa_responses(
    questions: list[OAQuestion],
    responses: list[OAResponse],
) -> float:
    """
    LLM-powered OA scoring.
    Returns a normalised score 0–100.
    Falls back to completion-rate scoring if OpenAI is unavailable.
    """
    if not questions:
        return 0.0

    # Build answer lookup
    answer_map: dict[str, str] = {r.question_id: r.answer for r in responses}
    answered = sum(1 for q in questions if answer_map.get(q.question_id, "").strip())
    completion_rate = answered / len(questions)

    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("[A2] OPENAI_API_KEY not set — using completion-rate OA score")
        return round(completion_rate * 100.0, 2)

    qa_pairs = []
    for q in questions:
        answer = answer_map.get(q.question_id, "(No answer provided)")
        qa_pairs.append(
            f"[{q.type}] Q: {q.question_text}\nA: {answer}"
        )
    qa_block = "\n\n".join(qa_pairs)

    prompt = f"""You are an expert technical assessor scoring an Online Assessment.

Questions and candidate answers:
{qa_block}

Score the overall assessment on a scale of 0 to 100 considering:
- Correctness of MCQ answers
- Code quality, logic, and efficiency for CODING questions
- Clarity, depth, and relevance for TEXT questions
- Penalise blank or minimal answers heavily

Return ONLY a JSON object:
{{
  "score": <integer 0-100>,
  "rationale": "<one sentence summary>"
}}
No markdown, no extra keys — pure JSON only.
"""
    try:
        client = _get_openai()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise technical assessor. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        raw_score = payload.get("score", completion_rate * 100.0)
        score = max(0.0, min(100.0, float(raw_score)))
        rationale = str(payload.get("rationale", "")).strip()
        logger.info("[A2] OA score=%s rationale=%r", score, rationale)
        return round(score, 2)
    except Exception as exc:
        logger.warning("[A2] OA evaluation LLM call failed, using completion-rate: %s", exc)
        return round(completion_rate * 100.0, 2)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Main Entry Node (LangGraph node / direct call)
# ══════════════════════════════════════════════════════════════════════════════

async def run_behavioral_oa(state: ScreeningState) -> ScreeningState:
    """
    LangGraph node for Graph 1 fan-out and Graph 2 entry.

    For each candidate (identified by state['candidate_id']):
      1. Generate OA questions from the JD.
      2. Generate behavioral questions from the JD.
      3. Persist both sets + a unique oa_token to Firestore.
      4. Advance pipeline_stage to OA_SENT.
      5. Return updated state (oa_questions populated for downstream nodes).
    """
    job_id       = state["job_id"]
    candidate_id = state.get("candidate_id", "")
    jd_text      = state.get("jd_text", "")

    job = get_job(job_id) or {}
    tech_stack: list[str] = list(job.get("tech_stack") or state.get("tech_stack") or [])

    if not jd_text:
        jd_text = str(job.get("role_description") or "")

    logger.info("[A2] Starting OA generation: job=%s candidate=%s", job_id, candidate_id)

    oa_questions         = generate_oa_questions(jd_text, tech_stack)
    behavioral_questions = generate_behavioral_questions(jd_text)
    oa_token             = str(uuid.uuid4())

    app_url   = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")
    oa_link   = f"{app_url}/oa/{oa_token}"
    chat_link = f"{app_url}/oa/{oa_token}/chat"

    now = datetime.now(timezone.utc)

    persist_data: dict[str, Any] = {
        "oa_token":             oa_token,
        "oa_link":              oa_link,
        "chat_link":            chat_link,
        "oa_questions":         [q.model_dump() for q in oa_questions],
        "behavioral_questions": behavioral_questions,
        "pipeline_stage":       "OA_SENT",
        "oa_generated_at":      now,
    }

    if candidate_id:
        update_candidate(job_id, candidate_id, persist_data)
        logger.info("[A2] Persisted OA for candidate=%s oa_link=%s chat_link=%s",
                    candidate_id, oa_link, chat_link)

        # Send OA invite email with both the assessment link and behavioral chat link
        candidate = get_candidate(job_id, candidate_id) or {}
        email     = candidate.get("email", "")
        name      = candidate.get("name", "Candidate")
        if email:
            try:
                from app.services.a6_client import send_oa_invite
                await send_oa_invite(
                    candidate_name=name,
                    candidate_email=email,
                    role_title=str(job.get("title") or "the role"),
                    oa_link=oa_link,
                    chat_link=chat_link,
                )
                logger.info("[A2] OA invite sent to candidate=%s email=%s", candidate_id, email)
            except Exception as exc:
                logger.warning("[A2] OA invite email failed candidate=%s: %s", candidate_id, exc)
    else:
        logger.warning("[A2] No candidate_id in state — OA questions generated but not persisted")

    return {
        **state,
        "oa_questions":         oa_questions,
        "oa_responses":         [],
        "behavioral_transcript": [],
        "composite_score":       0.0,
        "score_breakdown":       None,   # type: ignore[assignment]
        "rank":                  0,
        "shortlisted":           False,
        "calendly_link":         "",
        "zoom_url":              "",
        "invite_sent":           False,
        "invite_status":         "PENDING",
        "graph2_complete":       False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. Batch initialiser — called from Graph 1 fan-out for all sourced candidates
# ══════════════════════════════════════════════════════════════════════════════

async def init_for_candidates(state: Any) -> Any:
    """
    Graph 1 fan-out node: generate OA + behavioral questions for every
    sourced candidate in SourcingState and persist to Firestore.

    This runs once after A1 completes so all candidates receive their OA link.
    """
    from app.services.firestore_service import get_candidates

    job_id  = state["job_id"]
    jd_text = str(state.get("jd_text") or "")

    job = get_job(job_id) or {}
    tech_stack: list[str] = list(job.get("tech_stack") or state.get("tech_stack") or [])
    if not jd_text:
        jd_text = str(job.get("role_description") or "")

    # Generate the question bank once for the whole job (same questions per role)
    oa_questions         = generate_oa_questions(jd_text, tech_stack)
    behavioral_questions = generate_behavioral_questions(jd_text)

    candidates = get_candidates(job_id)
    logger.info("[A2] init_for_candidates: job=%s → %d candidates", job_id, len(candidates))

    app_url = os.environ.get("APP_URL", "http://localhost:5173")
    now     = datetime.now(timezone.utc)

    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            continue
        oa_token = str(uuid.uuid4())
        oa_link  = f"{app_url}/oa/{oa_token}"
        update_candidate(job_id, candidate_id, {
            "oa_token":             oa_token,
            "oa_link":              oa_link,
            "oa_questions":         [q.model_dump() for q in oa_questions],
            "behavioral_questions": behavioral_questions,
            "pipeline_stage":       "OA_SENT",
            "oa_generated_at":      now,
        })
        logger.info("[A2] OA set for candidate=%s link=%s", candidate_id, oa_link)

    return {**state, "graph1_complete": True}
