"""
GPT Sourcing Agent — MCP Bridge
================================
Connects to the A1 MCP server via stdio, exposes its tools to GPT-4o
via OpenAI function calling, and lets GPT drive the full sourcing pipeline.

GPT decides:
  - Which tools to call and in what order
  - What max_results to use
  - Whether to retry with looser filters if results are thin
  - When to merge and stop

Usage:
  cd backend
  python gpt_sourcing_agent.py
  python gpt_sourcing_agent.py --max-results 35 --output candidates.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

_MCP_SERVER = Path(__file__).parent / "mcp_server.py"

_SYSTEM_PROMPT = """\
You are a technical recruiting assistant with access to sourcing tools.

When given a job description your job is to find the best matching candidates.

Follow this process:
1. Call parse_job_description to extract tech_stack, experience_range, and locations.
2. Call search_github_candidates and search_linkedin_candidates using those fields.
   - Start with max_results=20 (TIGHT filters).
   - If either search returns fewer than 5 results, retry that search with max_results=40
     (LOOSE filters) before moving on.
3. Call merge_sourced_candidates with the results from both searches.
4. Return a concise sourcing summary: total candidates, breakdown by source,
   and a ranked list with name, location, source, and key skills.

Do not skip any step. Always merge before summarising.\
"""


def _to_openai_tools(mcp_tools) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        }
        for t in mcp_tools
    ]


async def run_agent(jd_text: str, max_results: int) -> list[dict]:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(_MCP_SERVER)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = (await session.list_tools()).tools
            openai_tools = _to_openai_tools(mcp_tools)

            client = AsyncOpenAI()
            messages: list[dict] = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Source candidates (target ~{max_results}) for this role:\n\n{jd_text}"
                    ),
                },
            ]

            print(f"[agent] connected to MCP server — {len(mcp_tools)} tools available")

            # ── Agentic loop ──────────────────────────────────────────────────
            final_candidates: list[dict] = []

            while True:
                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    parallel_tool_calls=True,
                )

                msg = response.choices[0].message
                messages.append(msg.model_dump(exclude_unset=True))

                if not msg.tool_calls:
                    # GPT is done — print its summary
                    print("\n" + "─" * 60)
                    print(msg.content)
                    break

                # Execute each tool call via MCP
                tool_results: list[dict] = []
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)
                    print(f"[tool] {name}({_fmt_args(args)})")

                    result = await session.call_tool(name, args)
                    content = result.content[0].text if result.content else "{}"

                    # Capture merged candidates if this is the merge step
                    if name == "merge_sourced_candidates":
                        try:
                            final_candidates = json.loads(content)
                        except json.JSONDecodeError:
                            pass

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": content,
                    })

                messages.extend(tool_results)

            return final_candidates


def _fmt_args(args: dict) -> str:
    short = {
        k: (f"[{len(v)} items]" if isinstance(v, list) and len(str(v)) > 60 else v)
        for k, v in args.items()
    }
    return ", ".join(f"{k}={v!r}" for k, v in short.items())


# ── CLI ───────────────────────────────────────────────────────────────────────

_DEMO_JD = """\
We are hiring a Senior Backend Engineer to join our platform team.

Requirements:
- 4–7 years of backend engineering experience
- Strong Python skills (FastAPI, SQLAlchemy, Pydantic)
- PostgreSQL, Redis
- Docker and AWS (ECS, Lambda)
- Bonus: LangChain or LLM integrations

Location: San Francisco (hybrid) or Remote
"""


def main():
    parser = argparse.ArgumentParser(description="GPT-powered A1 sourcing agent")
    parser.add_argument("--jd", default=None, help="Path to a .txt file with the job description")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--output", default=None, help="Save candidates JSON to this file")
    args = parser.parse_args()

    jd_text = Path(args.jd).read_text() if args.jd else _DEMO_JD

    candidates = asyncio.run(run_agent(jd_text, args.max_results))

    if args.output and candidates:
        Path(args.output).write_text(json.dumps(candidates, indent=2))
        print(f"\n[agent] {len(candidates)} candidates saved to {args.output}")


if __name__ == "__main__":
    main()
