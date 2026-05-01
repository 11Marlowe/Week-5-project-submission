"""
Lab 3.3 -- coder_agent.py
=========================
Implement the Coder agent A2A loop.

Do NOT change MAX_ITERATIONS, FILENAME, PROJECT_DIR, _get_client(),
MODEL, or _read_original_code().
"""

import asyncio
import pathlib
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from openai import AsyncOpenAI
from a2a import Broker, Message

MAX_ITERATIONS = 3
FILENAME = "word_counter.py"
PROJECT_DIR = pathlib.Path(__file__).parent / "project_files"

_client: AsyncOpenAI | None = None
MODEL = "gpt-4.1-mini"

_HELICONE_BASE = os.getenv("HELICONE_BASE_URL")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_HELICONE_API_KEY = os.getenv("HELICONE_API_KEY")


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=_OPENROUTER_API_KEY,
            base_url=_HELICONE_BASE,
        )
    return _client


def _read_original_code() -> str:
    return (PROJECT_DIR / FILENAME).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TODO 1 -- Implement write_file
# ---------------------------------------------------------------------------
def write_file(filename: str, code: str) -> None:
    """Write code to PROJECT_DIR / filename using Path.write_text."""
    out_path = PROJECT_DIR / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)  # ensure directory exists
    out_path.write_text(code, encoding="utf-8")


# ---------------------------------------------------------------------------
# TODO 2 -- Implement _generate_initial_code
# ---------------------------------------------------------------------------
async def _generate_initial_code(original_code: str) -> str:
    """Prompt the LLM to fix all bugs. Return corrected code string.
    Use _get_client().chat.completions.create (plain text, not structured).
    """
    client = _get_client()

    system_msg = (
        "You are a senior Python engineer. "
        "Fix all bugs in the provided code. "
        "Return ONLY the full corrected Python source code with no markdown, "
        "no backticks, and no extra commentary."
    )

    user_msg = (
        "Fix all bugs in this file. Preserve intended functionality.\n\n"
        "----- BEGIN CODE -----\n"
        f"{original_code}\n"
        "----- END CODE -----\n"
    )

    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
    )

    # Plain-text (non-structured) response handling
    code = (resp.choices[0].message.content or "").strip()
    return code


# ---------------------------------------------------------------------------
# TODO 3 -- Implement _apply_fixes
# ---------------------------------------------------------------------------
async def _apply_fixes(code: str, issues: list[dict]) -> str:
    """Prompt the LLM to fix the specific issues. Return updated code string.
    Format issues clearly: "Issue N [severity] location: description"
    """
    client = _get_client()

    system_msg = (
        "You are a senior Python engineer. "
        "Fix all bugs in the provided code. Return ONLY the full corrected Python source code "
        "with no markdown, no backticks, and no extra commentary."
    )

    # Build a human-readable list of issues
    issue_lines = []
    for idx, issue in enumerate(issues, start=1):
        sev = issue.get("severity")
        loc = issue.get("location")
        desc = issue.get("description")
        issue_lines.append(f"Issue {idx} [{sev}] {loc}: {desc}")
    issues_text = "\n".join(issue_lines)

    user_msg = (
        "Fix the following issues in this file. "
        "Format issues clearly as: 'Issue N [severity] location: description'.\n\n"
        "----- BEGIN CODE -----\n"
        f"{code}\n"
        "----- END CODE -----\n\n"
        "Issues to fix:\n" + issues_text
    )

    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
    )

    updated = (resp.choices[0].message.content or "").strip()
    return updated


# ---------------------------------------------------------------------------
# TODO 4 -- Implement run_coder_agent
# ---------------------------------------------------------------------------
async def run_coder_agent(broker: Broker, server_script_path: str) -> str:
    """A2A loop: generate/fix -> write -> send review_request -> receive -> repeat.

    Returns the final code string (approved or last attempt).

    Loop:
        for iteration in range(MAX_ITERATIONS):
            code = _generate_initial_code or _apply_fixes
            write_file(FILENAME, code)
            send review_request (store correlation_id)
            response = await broker.receive("coder")
            if approved: return code
            if fix_instruction: extract issues, continue
        return code
    """
    original_code = _read_original_code()

    code: str = original_code
    issues: list[dict] = []

    for iteration in range(MAX_ITERATIONS):
        # Generate on first pass; apply QA-requested fixes on subsequent passes
        if iteration == 0:
            code = await _generate_initial_code(original_code)
        else:
            code = await _apply_fixes(code, issues)

        # Must write before requesting review (tests assert this ordering)
        write_file(FILENAME, code)

        # Send review request to QA
        review_request = Message(
            sender="coder",
            receiver="qa",
            intent="review_request",
            payload={"filename": FILENAME},
        )
        await broker.send(review_request)

        # Wait for QA response
        response = await broker.receive("coder")

        # (Optional safety) If something else arrives first, wait for matching correlation_id
        while response.correlation_id != review_request.correlation_id:
            response = await broker.receive("coder")

        # Handle QA outcome
        if response.intent == "approved" or response.payload.get("approved") is True:
            return code

        if response.intent == "fix_instruction":
            issues = response.payload.get("issues", []) or []
            continue

        # Unknown response type: stop and return last code
        break

    return code