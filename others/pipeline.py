"""
Lab 3.4 -- pipeline.py
======================
Wire PM, Coder, and QA into a LangGraph StateGraph.

PipelineState fields
--------------------
    requirement: str        -- set at start
    spec:        Spec|None  -- set by pm_node
    final_code:  str        -- set by coder_node

Graph:  START -> pm_node -> coder_node -> END

Do NOT change MCP_SERVER or the imports below.
"""

import asyncio
import pathlib
from typing import TypedDict

from langgraph.graph import StateGraph, END

from a2a import Broker
from coder_agent import run_coder_agent
from pm_agent import Spec, run_pm_agent
from qa_agent import run_qa_agent_a2a

MCP_SERVER = "./mcp_server.py"


# TODO 1 -- Define PipelineState
# class PipelineState(TypedDict):
#     requirement: str
#     spec:        Spec | None
#     final_code:  str
class PipelineState(TypedDict):
    requirement: str
    spec: Spec | None
    final_code: str


# TODO 2 -- pm_node
async def pm_node(state: "PipelineState") -> dict:
    """Call run_pm_agent(state["requirement"]), return {"spec": spec}."""
    spec = await run_pm_agent(state["requirement"])
    return {"spec": spec}


# TODO 3 -- coder_node
async def coder_node(state: "PipelineState") -> dict:
    """Create Broker, run Coder + QA via asyncio.gather, return {"final_code": str}."""
    broker = Broker()

    # Run coder + QA concurrently. QA agent listens/responds on the broker while
    # coder iterates until approved (or max iterations).
    coder_task = run_coder_agent(broker, MCP_SERVER)
    qa_task = run_qa_agent_a2a(broker, MCP_SERVER)

    final_code, _qa_result = await asyncio.gather(coder_task, qa_task)
    return {"final_code": final_code}


# TODO 4 -- build_pipeline
def build_pipeline():
    """Build and compile StateGraph: pm -> coder -> END."""
    graph = StateGraph(PipelineState)

    # Node *IDs* must match what tests expect
    graph.add_node("pm", pm_node)
    graph.add_node("coder", coder_node)

    graph.set_entry_point("pm")
    graph.add_edge("pm", "coder")
    graph.add_edge("coder", END)

    return graph.compile()


# TODO 5 -- run_pipeline
async def run_pipeline(requirement: str) -> "PipelineState":
    """Invoke compiled pipeline with initial state, return final state."""
    app = build_pipeline()
    initial_state: PipelineState = {
        "requirement": requirement,
        "spec": None,
        "final_code": "",
    }
    final_state = await app.ainvoke(initial_state)
    return final_state