"""
Lab 3.2 — qa_agent.py
======================
Your task: implement a QA agent that reads a Python file via the MCP server
from Lab 3.1, reviews it with an LLM, and returns a structured IssueList.

Architecture reminder
---------------------
The MCP server (mcp_server.py from Lab 3.1) is the shared file layer.
The QA agent connects to it as a client and calls read_file -- it does NOT
import the file directly. This is the same pattern from mcp_client.py in
Lab 3.1, now applied to a real agent.

What to implement
-----------------
1. Issue      -- Pydantic model for a single code issue
2. IssueList  -- Pydantic model for structured review output
3. _read_file_via_mcp(server_script_path, filename) -- read via MCP
4. _review_code(code) -- LLM review returning IssueList
5. run_qa_agent(server_script_path, filename) -- orchestrate 3 and 4

The agent flow
--------------
    MCP server (Lab 3.1)
          |  read_file via MCP
          v
    QA agent reads file contents
          |  sends to LLM with review prompt
          v
    LLM returns structured issue list
          |  parsed into IssueList
          v
    approved = True only if no High-severity issues

Severity levels
---------------
    "High"   -- logic errors, incorrect output, crashes
    "Medium" -- edge cases not handled, wrong algorithm behaviour
    "Low"    -- style issues, missing type annotations, docstring gaps

Issue schema (each issue must have all three fields)
-----------------------------------------------------
    severity:    Literal["High", "Medium", "Low"]
    location:    str  -- function name or line description
    description: str  -- specific, actionable description of the problem

IssueList schema
----------------
    issues:   list[Issue]
    approved: bool  -- True only if len(High-severity issues) == 0
                      Use a model_validator to enforce this invariant.

Do NOT change _get_client(), MODEL, LAB31_SERVER, or _main().
"""

import asyncio
import os
import pathlib
import sys
from typing import Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Helicone-proxied OpenAI client -- do not change
# ---------------------------------------------------------------------------
_client: AsyncOpenAI | None = None
MODEL = "gpt-4.1-mini"

_HELICONE_BASE = os.getenv("HELICONE_BASE_URL")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_HELICONE_API_KEY = os.getenv("HELICONE_API_KEY")


def _get_client() -> AsyncOpenAI:
    """Lazy-initialised client -- avoids import-time errors in tests."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key= _OPENROUTER_API_KEY,
            base_url= _HELICONE_BASE,
        )
    return _client


# ---------------------------------------------------------------------------
# MCP server path -- points to Lab 3.1
# ---------------------------------------------------------------------------
LAB31_SERVER = "./mcp_server.py"

# ---------------------------------------------------------------------------
# TODO 1 -- Define the Issue Pydantic model
# ---------------------------------------------------------------------------
# class Issue(BaseModel):
#     severity:    Literal["High", "Medium", "Low"]
#     location:    str
#     description: str
class Issue(BaseModel):
    """A single code review issue found by the QA agent."""

    severity: Literal["High", "Medium", "Low"] = Field(
        ...,
        description='Severity of the issue: "High", "Medium", or "Low".',
    )
    location: str = Field(
        ...,
        description="Where the issue occurs (e.g., function name or line range).",
    )
    description: str = Field(
        ...,
        description="Specific, actionable description of the problem.",
    )


# ---------------------------------------------------------------------------
# TODO 2 -- Define the IssueList Pydantic model
# ---------------------------------------------------------------------------
# class IssueList(BaseModel):
#     issues:   list[Issue]
#     approved: bool
#
# Add a @model_validator(mode="after") that sets approved=False whenever
# any issue has severity == "High", regardless of what the LLM returned.
class IssueList(BaseModel):
    """Structured output for a code review."""

    issues: list[Issue] = Field(
        default_factory=list,
        description="List of issues found in the reviewed code.",
    )
    approved: bool = Field(
        ...,
        description="True only if there are zero High-severity issues.",
    )

    @model_validator(mode="after")
    def _enforce_approval_invariant(self) -> "IssueList":
        # Force approved=False if any High issues exist (ignore LLM's approved value).
        any_high = any(issue.severity == "High" for issue in self.issues)
        self.approved = not any_high
        return self

# ---------------------------------------------------------------------------
# TODO 3 -- Implement _read_file_via_mcp
# ---------------------------------------------------------------------------
async def _read_file_via_mcp(server_script_path: str, filename: str) -> str:
    """Read a file from the Lab 3.1 MCP server and return its contents.

    Parameters
    ----------
    server_script_path:
        Absolute path to mcp_server.py from Lab 3.1.
    filename:
        Relative filename inside project_files/, e.g. "word_counter.py".

    Returns
    -------
    str
        File contents as returned by the MCP server.

    Implementation notes
    --------------------
    Use the same pattern from Lab 3.1 mcp_client.py:
        params = StdioServerParameters(command=sys.executable, args=[server_script_path])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("read_file", {"path": filename})
                return result.content[0].text
    """
    server_script_path = str(pathlib.Path(server_script_path).resolve())

    params = StdioServerParameters(
        command=sys.executable,
        args=[server_script_path],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("read_file", {"path": filename})
            return result.content[0].text


# ---------------------------------------------------------------------------
# TODO 4 -- Implement _review_code
# ---------------------------------------------------------------------------
async def _review_code(code: str) -> "IssueList":
    """Send code to the LLM for structured review and return an IssueList.

    Parameters
    ----------
    code:
        Python source code to review.

    Returns
    -------
    IssueList
        Structured list of issues with severities and approved flag.

    Implementation notes
    --------------------
    Write a REVIEW_PROMPT that instructs the LLM to:
        - Find every bug, style issue, and missing edge case
        - Assign severity: High / Medium / Low
        - Give the location (function name and brief description)
        - Set approved=True only if there are zero High-severity issues

    Use structured output:
        response = await _get_client().beta.chat.completions.parse(
            model=MODEL,
            messages=[{"role": "user", "content": REVIEW_PROMPT.format(code=code)}],
            response_format=IssueList,
        )
        return response.choices[0].message.parsed
    """
    REVIEW_PROMPT = (
        "You are a meticulous Python code reviewer.\n"
        "Review the code and return a structured IssueList.\n\n"
        "Rules:\n"
        '- Each issue MUST include: severity ("High"|"Medium"|"Low"), location, description.\n'
        "- High: crashes, exceptions, incorrect output, logic errors.\n"
        "- Medium: edge cases, incorrect behavior in some scenarios.\n"
        "- Low: style, readability, docstrings, type hints.\n"
        "- If there are NO issues, return issues=[] and approved=True.\n"
        "- approved must be True only if there are zero High-severity issues.\n\n"
        "Code to review:\n"
        "-----\n"
        "{code}\n"
        "-----\n"
    )

    response = await _get_client().beta.chat.completions.parse(
        model=MODEL,
        messages=[{"role": "user", "content": REVIEW_PROMPT.format(code=code)}],
        response_format=IssueList,
    )
    return response.choices[0].message.parsed


# ---------------------------------------------------------------------------
# TODO 5 -- Implement run_qa_agent
# ---------------------------------------------------------------------------
async def run_qa_agent_a2a(
    server_script_path: str = LAB31_SERVER,
    filename: str = "word_counter.py",
) -> "IssueList":
    """Orchestrate the QA agent: read file via MCP, review with LLM.

    Parameters
    ----------
    server_script_path:
        Path to mcp_server.py from Lab 3.1.
    filename:
        File inside project_files/ to review.

    Returns
    -------
    IssueList
        Structured review result.

    Implementation notes
    --------------------
    1. Call _read_file_via_mcp(server_script_path, filename).
    2. Call _review_code(code).
    3. Return the IssueList.
    """
    code = await _read_file_via_mcp(server_script_path, filename)
    result = await _review_code(code)
    return result


# ---------------------------------------------------------------------------
# Entry point -- do not modify
# ---------------------------------------------------------------------------
async def _main() -> None:
    print("QA Agent reviewing: word_counter.py\n")
    result = await run_qa_agent()
    print(f"Approved: {result.approved}")
    print(f"Issues found: {len(result.issues)}\n")
    for issue in result.issues:
        print(f"  [{issue.severity}] {issue.location}")
        print(f"    {issue.description}\n")


if __name__ == "__main__":
    asyncio.run(_main())