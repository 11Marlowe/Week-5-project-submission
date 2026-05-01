"""
Lab 3.4 -- pm_agent.py
======================
Implement a lightweight PM agent that analyses a user requirement and
produces a structured Spec for the Coder agent.

Spec schema
-----------
    goal:        str        -- one-sentence restatement of the task
    constraints: list[str]  -- specific requirements the code must satisfy
    filename:    str        -- always "word_counter.py" here

Do NOT change _get_client(), MODEL, or TARGET_FILE.
"""

import os

from openai import AsyncOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv(override=True)

_HELICONE_BASE = os.getenv("HELICONE_BASE_URL")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_HELICONE_API_KEY = os.getenv("HELICONE_API_KEY")

TARGET_FILE = "./project_files/word_counter.py"
_client: AsyncOpenAI | None = None
MODEL = "gpt-4.1-mini"


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=_OPENROUTER_API_KEY,
            base_url=_HELICONE_BASE,
        )
    return _client


# TODO 1 -- Define the Spec Pydantic model
# class Spec(BaseModel):
#     goal:        str
#     constraints: list[str]
#     filename:    str
class Spec(BaseModel):
    goal: str
    constraints: list[str]
    filename: str


# TODO 2 -- Implement run_pm_agent
async def run_pm_agent(requirement: str) -> "Spec":
    """Analyse requirement, return Spec via structured LLM output.
    Use _get_client().beta.chat.completions.parse with response_format=Spec.
    Prompt must extract goal, constraints, and set filename=TARGET_FILE.
    """
    client = _get_client()

    system_prompt = (
        "You are a PM agent. Convert the user's requirement into a structured Spec.\n"
        "Return only fields required by the Spec schema:\n"
        "- goal: one-sentence restatement of the task\n"
        "- constraints: a list of specific, testable requirements the code must satisfy\n"
        "- filename: must be exactly the provided target file path\n"
        "Be concise, avoid implementation details, and ensure constraints are actionable."
    )

    user_prompt = (
        f"Target file (must be used verbatim for filename): {TARGET_FILE}\n\n"
        f"User requirement:\n{requirement}\n"
    )

    completion = await client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=Spec,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        # Defensive guard: parse() should normally populate this.
        raise RuntimeError("LLM did not return a parsable Spec.")

    # Optional hardening: enforce filename exactly, even if the model deviates.
    parsed.filename = TARGET_FILE
    return parsed