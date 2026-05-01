"""
Lab 2.3 — LangGraph Graph Definition
======================================

This is the file you implement in Lab 2.3.

You will wire the PM and Coder agents into a single StateGraph and write
the two routing functions that control flow between them. Both agents are
already implemented in agents/pm_agent.py and agents/coder_agent.py —
your job is the graph architecture.

────────────────────────────────────────────────────────────────────────
THE GRAPH YOU ARE BUILDING
────────────────────────────────────────────────────────────────────────

    [START]
       │
       ▼
   [pm_node]           ← runs once; produces tech_spec + tasks
       │
       ▼  route_after_pm
   [coder_node] ◄──────────────────┐
       │                           │
       ▼  route_after_coder        │
    routing == "coder" ────────────┘   (more tasks remain — loop)
    routing == "done"  ──────────────► [END]

There are two decision points, each controlled by state["routing"]:

  route_after_pm      reads routing after pm_node returns
  route_after_coder   reads routing after each coder_node iteration

────────────────────────────────────────────────────────────────────────
TASK 1 — route_after_pm
────────────────────────────────────────────────────────────────────────

Decide where to go after pm_node finishes.

Rules:
  - If the PM succeeded: state["routing"] == "coder" and
    state["error"] == "" → return "coder_node"
  - If the PM failed:    state["error"] is non-empty, or
    state["routing"] != "coder"           → return END

Why check both routing AND error?
  The PM sets routing="coder" only on success. On failure it sets
  routing="done". Checking state["error"] as a second guard makes
  the failure path explicit and prevents a misconfigured PM from
  accidentally sending an empty task list to the Coder.

Signature:
  def route_after_pm(state: ProjectState) -> str

Return values:
  "coder_node"  — proceed to the Coder agent
  END           — terminate (import END from langgraph.graph)

────────────────────────────────────────────────────────────────────────
TASK 2 — route_after_coder
────────────────────────────────────────────────────────────────────────

Decide where to go after each coder_node iteration.

Rules:
  - If more tasks remain: state["routing"] == "coder" → return "coder_node"
  - If all tasks done:    state["routing"] == "done"  → return END

This is the self-loop. Returning "coder_node" from a conditional edge
that originates at "coder_node" sends control back to the same node for
the next task. LangGraph supports this natively.

Signature:
  def route_after_coder(state: ProjectState) -> str

Return values:
  "coder_node"  — loop back (more tasks remain)
  END           — terminate

────────────────────────────────────────────────────────────────────────
TASK 3 — build_graph
────────────────────────────────────────────────────────────────────────

Assemble the graph using the LangGraph StateGraph API.

Steps:
  1. Create a StateGraph with ProjectState as the state schema:
         builder = StateGraph(ProjectState)

  2. Register both nodes:
         builder.add_node("pm_node",    pm_node)
         builder.add_node("coder_node", coder_node)

  3. Add the entry edge from START to pm_node:
         builder.add_edge(START, "pm_node")

  4. Add a conditional edge from pm_node using route_after_pm:
         builder.add_conditional_edges("pm_node", route_after_pm)

  5. Add a conditional edge from coder_node using route_after_coder:
         builder.add_conditional_edges("coder_node", route_after_coder)

  6. Compile and return:
         return builder.compile()

Signature:
  def build_graph() -> StateGraph

Note on imports:
  StateGraph, START, END are all in langgraph.graph.
  pm_node and coder_node are in agents.pm_agent and agents.coder_agent.
  ProjectState is in state.

────────────────────────────────────────────────────────────────────────
TASK 4 — module-level graph instance
────────────────────────────────────────────────────────────────────────

After build_graph(), add this line at module level:

    graph = build_graph()

The test suite and main.py both import `graph` from this module. If this
line is missing, every import will fail.
"""

from langgraph.graph import StateGraph, START, END

from state import ProjectState
from agents.pm_agent import pm_node
from agents.coder_agent import coder_node


# ── Task 1 ───────────────────────────────────────────────────────────────────

def route_after_pm(state: ProjectState) -> str:
    """
    Route after pm_node: go to coder_node on success, END on failure.

    Parameters
    ----------
    state : ProjectState
        Current graph state after pm_node has returned.

    Returns
    -------
    str
        "coder_node" or END.
    """
    if state.get("routing") != "coder":
        return END
    if state.get("error"):
        return END
    tasks = state.get("tasks") or []
    if len(tasks) == 0:
        return END
    return "coder_node"


# ── Task 2 ───────────────────────────────────────────────────────────────────

def route_after_coder(state: ProjectState) -> str:
    """
    Route after coder_node: loop back on "coder", exit on "done".

    Parameters
    ----------
    state : ProjectState
        Current graph state after coder_node has returned.

    Returns
    -------
    str
        "coder_node" or END.
    """
    if state.get("error"):
        return END
    if state.get("routing") == "coder":
        return "coder_node"
    return END


# ── Task 3 ───────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Assemble and compile the PM + Coder pipeline graph.

    Returns
    -------
    StateGraph
        The compiled LangGraph graph ready to invoke.
    """
    builder = StateGraph(ProjectState)
    builder.add_node("pm_node", pm_node)
    builder.add_node("coder_node", coder_node)
    builder.add_edge(START, "pm_node")
    builder.add_conditional_edges("pm_node", route_after_pm)
    builder.add_conditional_edges("coder_node", route_after_coder)
    return builder.compile()


# ── Task 4 ───────────────────────────────────────────────────────────────────
# Add the module-level graph instance here after implementing build_graph:
#
#     graph = build_graph()
#
# The test suite and main.py import `graph` from this module.
graph = build_graph()
