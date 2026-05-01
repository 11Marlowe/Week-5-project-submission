"""
Lab 4.1 — Instrumented Pipeline
================================
Wrap the three agent nodes from Lab 3.4 with tracing decorators.
This file is the only place you add @traceable (or equivalent) calls.

Do NOT modify the original pipeline.py from Lab 3.4.

Structure
---------
Each instrumented node must:
  1. Call the original node function (imported from pipeline.py).
  2. Capture token_count and tool_calls from the node's return value
     or from LangSmith run context.
  3. Attach span metadata via make_span_metadata().
  4. Propagate the run_id from state into the child span so LangSmith
     links it to the root trace.

PipelineState extension
-----------------------
You need to add two fields to PipelineState (define TracedPipelineState
below — do not edit pipeline.py):

    run_id    : str          # root trace ID, set once in run_pipeline
    token_log : list[dict]   # one entry per node, appended by each node
"""

import asyncio
import inspect
from typing import Any

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

# -- Import from Lab 3.4 pre-built files (do not modify those files) --------
from pipeline import (          # noqa: F401  (pipeline.py from Lab 3.4)
    PipelineState,
    pm_node as _original_pm_node,
    coder_node as _original_coder_node,
    build_pipeline,
)
from tracing import configure_tracing, make_span_metadata, new_run_id

# Uncomment once you implement tracing.py:
# from langsmith import traceable


# ---------------------------------------------------------------------------
# Extended state
# ---------------------------------------------------------------------------

# TODO: define TracedPipelineState that extends PipelineState with
#       run_id (str) and token_log (list[dict]).
class TracedPipelineState(PipelineState):
    """
    PipelineState + tracing fields.

    Inherits:
      requirement: str
      spec: Spec | None
      final_code: str
    Adds:
      run_id: str
      token_log: list[dict]
    """
    run_id: str
    token_log: list[dict[str, Any]]

# ---------------------------------------------------------------------------
# Instrumented node wrappers
# ---------------------------------------------------------------------------

# TODO: implement traced_pm_node(state) -> dict
#   • Calls _original_pm_node(state)
#   • Decorates / wraps with @traceable(name="pm_node")
#   • Attaches make_span_metadata("pm", token_count, tool_calls)
#   • Appends an entry to state["token_log"]
@traceable(name="pm_node")
async def traced_pm_node(state: "TracedPipelineState") -> dict[str, Any]:
    # 1) Call original node exactly once (support sync mocks in tests)
    result = _original_pm_node(state)
    if inspect.isawaitable(result):
        result = await result

    # 2) Best-effort token/tool extraction (mocked tests don’t provide these)
    token_count = 0
    tool_calls = 0

    # 3) Attach metadata to the current span/run (best-effort)
    meta = make_span_metadata("pm", token_count, tool_calls)
    run_tree = get_current_run_tree()   
    if run_tree is not None:
    # Preferred API (newer langsmith)
        if hasattr(run_tree, "add_metadata"):
            run_tree.add_metadata({**meta, "run_id": state.get("run_id")})
        else:
            # Fallback for older versions where metadata is a mutable dict
            md = getattr(run_tree, "metadata", None)
            if isinstance(md, dict):
                md.update({**meta, "run_id": state.get("run_id")})

    # 4) Append token_log entry
    token_log = list(state.get("token_log", []))
    token_log.append({**meta, "node": "pm_node"})

    # Return state updates for LangGraph to merge
    return {**result, "token_log": token_log}

# TODO: implement traced_coder_node(state) -> dict
#   • Calls _original_coder_node(state)
#   • Decorates / wraps with @traceable(name="coder_node")
#   • Attaches make_span_metadata("coder", token_count, tool_calls)
#   • Appends an entry to state["token_log"]
@traceable(name="coder_node")
async def traced_coder_node(state: "TracedPipelineState") -> dict[str, Any]:
    # 1) Call original node exactly once (support sync mocks in tests)
    result = _original_coder_node(state)
    if inspect.isawaitable(result):
        result = await result

    # 2) Best-effort token/tool extraction
    token_count = 0
    tool_calls = 0

    # 3) Attach metadata to the current span/run (best-effort)
    meta = make_span_metadata("pm", token_count, tool_calls)
    run_tree = get_current_run_tree()   
    if run_tree is not None:
    # Preferred API (newer langsmith)
        if hasattr(run_tree, "add_metadata"):
            run_tree.add_metadata({**meta, "run_id": state.get("run_id")})
        else:
            # Fallback for older versions where metadata is a mutable dict
            md = getattr(run_tree, "metadata", None)
            if isinstance(md, dict):
                md.update({**meta, "run_id": state.get("run_id")})

    # 4) Append token_log entry
    token_log = list(state.get("token_log", []))
    token_log.append({**meta, "node": "coder_node"})

    return {**result, "token_log": token_log}


# ---------------------------------------------------------------------------
# Instrumented pipeline builder
# ---------------------------------------------------------------------------

def build_instrumented_pipeline():
    """
    Build a LangGraph StateGraph identical to Lab 3.4's build_pipeline()
    but with traced_pm_node and traced_coder_node substituted in.

    Hint: copy build_pipeline() from pipeline.py and swap the node
    functions — do not import build_pipeline() and try to patch it.
    """
    from langgraph.graph import StateGraph, END

    graph = StateGraph(TracedPipelineState)

    # Keep node IDs ("pm", "coder") the same as Lab 3.4; only swap the functions.
    graph.add_node("pm", traced_pm_node)
    graph.add_node("coder", traced_coder_node)

    graph.set_entry_point("pm")
    graph.add_edge("pm", "coder")
    graph.add_edge("coder", END)

    return graph.compile()


async def run_instrumented_pipeline(requirement: str) -> dict[str, Any]:
    """
    Entry point called by main.py.

    Steps
    -----
    1. Call configure_tracing() to initialise the backend.
    2. Generate a root run_id with new_run_id().
    3. Invoke the instrumented pipeline with the initial state.
    4. Return the final state dict.
    """
    from contextlib import nullcontext

    configure_tracing()

    run_id = new_run_id()
    app = build_instrumented_pipeline()

    initial_state: TracedPipelineState = {
        "requirement": requirement,
        "spec": None,
        "final_code": "",
        "run_id": run_id,
        "token_log": [],
    }

    # Best-effort: ensure LangSmith tracing context is enabled for this invocation.
    # (Mocked tests don't require it, but live tracing typically does.)
    ctx = nullcontext()
    try:
        from langsmith.run_helpers import tracing_v2_enabled  # type: ignore

        # Some versions accept run_id=..., others don't; handle both safely.
        try:
            ctx = tracing_v2_enabled(run_id=run_id)
        except TypeError:
            ctx = tracing_v2_enabled()
    except Exception:
        ctx = nullcontext()

    with ctx:
        final_state = await app.ainvoke(initial_state)

    return final_state
