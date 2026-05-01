"""
Lab 4.1 — Distributed Tracing Across All Three Agents
======================================================
Your job: instrument every agent node so that a single pipeline run
produces ONE end-to-end trace in LangSmith (or Phoenix/Arize).

Tasks
-----
1. Wrap each agent node with @traceable (LangSmith) or an equivalent
   span context manager (Phoenix).
2. Propagate a shared run_id through PipelineState so every node links
   to the same root trace.
3. Attach custom metadata to each span:
       agent_name   – "pm" | "coder" | "qa"
       token_count  – total tokens used by this node
       tool_calls   – number of tool / MCP calls made
4. After a test run, open the LangSmith dashboard and verify:
       • One trace with three child spans (PM → Coder → QA).
       • Custom metadata visible on each span.
5. Identify the slowest span and the highest-token span from the trace
   and record them in TRACE_FINDINGS at the bottom of this file.

Constraints
-----------
- Do NOT modify pipeline.py, coder_agent.py, qa_agent.py, or a2a.py.
- All tracing instrumentation lives in THIS file and in the node
  wrappers you create in instrumented_pipeline.py.
- LangSmith SDK is already installed; LANGSMITH_API_KEY is injected
  as a Codespaces secret.

Imports you will need (uncomment as required)
---------------------------------------------
"""

# from langsmith import traceable, Client
# from langsmith.run_helpers import get_current_run_tree
# import opentelemetry  # if using Phoenix instead
# from openinference.instrumentation.langchain import LangChainInstrumentor

import uuid
from typing import Any


# ---------------------------------------------------------------------------
# 1. Tracing configuration
# ---------------------------------------------------------------------------

def configure_tracing() -> None:
    """
    Initialise the tracing backend.

    For LangSmith: set LANGCHAIN_TRACING_V2=true and LANGCHAIN_PROJECT
    via environment variables, or call the LangSmith client directly.

    For Phoenix: call LangChainInstrumentor().instrument() here.

    This function is called once at startup in main.py.
    """
    import os

    # Enable LangSmith tracing (LangChain v2 tracing flag)
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    # Ensure we have a project name. Prefer anything already configured.
    # (Students often have LANGSMITH_PROJECT set in .env; LANGCHAIN_PROJECT is
    # what the lab asks for explicitly.)
    project = (
        os.environ.get("LANGCHAIN_PROJECT")
        or os.environ.get("LANGSMITH_PROJECT")
        or "lab-4-1"
    )
    os.environ["LANGCHAIN_PROJECT"] = project


# ---------------------------------------------------------------------------
# 2. Span metadata helpers
# ---------------------------------------------------------------------------

def make_span_metadata(
    agent_name: str,
    token_count: int,
    tool_calls: int,
) -> dict[str, Any]:
    """
    Return a metadata dict that will be attached to a LangSmith span.

    Parameters
    ----------
    agent_name  : one of "pm", "coder", "qa"
    token_count : total tokens (prompt + completion) consumed by this node
    tool_calls  : number of tool / MCP calls issued by this node
    """
    return {
        "agent_name": agent_name,
        "token_count": int(token_count),
        "tool_calls": int(tool_calls),
    }


def new_run_id() -> str:
    """
    Return a fresh UUID4 string to use as the root trace run_id.
    This is called once per pipeline invocation in run_pipeline().
    """
    return str(uuid.uuid4())



# ---------------------------------------------------------------------------
# 4. TRACE_FINDINGS  (fill in after your first successful traced run)
# ---------------------------------------------------------------------------

TRACE_FINDINGS: dict[str, str] = {
    "slowest_span": "",          # e.g. "coder — 14.2 s"
    "highest_token_span": "",    # e.g. "pm — 1 840 tokens"
    "notes": "",                 # any other observations
}
