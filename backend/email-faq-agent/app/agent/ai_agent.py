import json
import google.generativeai as genai
import google.generativeai.protos as protos
from pydantic import BaseModel
from typing import Any
from app.agent.tools import GEMINI_TOOLS, execute_tool
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an intelligent email agent. You receive natural language tasks and \
execute them by calling tools to look up users, pick templates, and send or queue emails.

Rules:
- Always call list_users first if a recipient is mentioned by name or role — never guess an email.
- Always call list_templates before sending with a template so you know the exact required fields.
- If no template fits, write clean HTML in body_html and pass it to send_email directly.
- template_data must be a JSON string, e.g. {"name": "Alice", "email": "alice@example.com"}.
- For urgent or high-priority tasks, use send_email. For bulk or explicitly async tasks, use enqueue_email.
- If you cannot complete the task (user not found, missing info), explain clearly why.
- After all actions, give a short plain-English summary of exactly what you did.
"""


# ── Response model ─────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    tool: str
    input: dict[str, Any]
    result: dict[str, Any]


class AgentResult(BaseModel):
    status: str          # "success" | "failed" | "partial"
    summary: str
    actions: list[ToolCall]
    total_steps: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_text(response: genai.types.GenerateContentResponse) -> str:
    for part in response.parts:
        if hasattr(part, "text") and part.text:
            return part.text
    return "Task completed."


def _extract_function_calls(response: genai.types.GenerateContentResponse) -> list:
    calls = []
    for part in response.parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            calls.append(fc)
    return calls


# ── Agent loop ─────────────────────────────────────────────────────────────────

async def run_agent(task: str) -> AgentResult:
    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=[GEMINI_TOOLS],
        generation_config=genai.types.GenerationConfig(temperature=0),
    )

    chat = model.start_chat()
    actions: list[ToolCall] = []

    logger.info(f"Agent starting | task={task!r}")

    # Kick off the conversation
    response = await chat.send_message_async(task)

    while True:
        fn_calls = _extract_function_calls(response)

        # ── No more tool calls → Claude is done ───────────────────────────────
        if not fn_calls:
            summary = _extract_text(response)
            status = "failed" if any("error" in a.result for a in actions) else "success"
            logger.info(f"Agent done | steps={len(actions)} status={status}")
            return AgentResult(
                status=status,
                summary=summary,
                actions=actions,
                total_steps=len(actions),
            )

        # ── Execute every tool call Gemini requested ───────────────────────────
        response_parts = []
        for fc in fn_calls:
            raw_inputs = dict(fc.args)
            result = await execute_tool(fc.name, raw_inputs)
            actions.append(ToolCall(tool=fc.name, input=raw_inputs, result=result))

            response_parts.append(
                protos.Part(
                    function_response=protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result)},
                    )
                )
            )

        # Feed results back and continue the loop
        response = await chat.send_message_async(response_parts)


# ── FAQ agent ──────────────────────────────────────────────────────────────────

FAQ_SYSTEM_PROMPT = """You are a helpful FAQ agent. You are given a user's profile data and a question \
about that user. Answer the question clearly and concisely based only on the information provided. \
If the question cannot be answered from the available data, say so honestly."""


async def run_faq_agent(question: str, user: dict) -> str:
    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=FAQ_SYSTEM_PROMPT,
        generation_config=genai.types.GenerationConfig(temperature=0),
    )

    prompt = f"User profile:\n{json.dumps(user, indent=2)}\n\nQuestion: {question}"
    response = await model.generate_content_async(prompt)
    return response.text.strip()