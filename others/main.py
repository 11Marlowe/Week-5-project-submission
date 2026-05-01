"""
Lab 4.1 — entry point.
Run:  python main.py
"""

import asyncio
from instrumented_pipeline import run_instrumented_pipeline

REQUIREMENT = (
    "Write a Python function called word_count(path: str) -> dict[str, int] "
    "that reads a text file and returns a frequency map of every word. "
    "Words are case-insensitive and stripped of punctuation. "
    "Raise FileNotFoundError if the file does not exist."
)


async def main() -> None:
    print("=== Lab 4.1 — Distributed Tracing ===\n")
    state = await run_instrumented_pipeline(REQUIREMENT)

    print("\n--- Pipeline complete ---")
    print(f"run_id      : {state.get('run_id', 'not set')}")
    print(f"token_log   : {state.get('token_log', [])}")
    print(f"final_code  :\n{state.get('final_code', '')[:400]}")
    print(
        "\nOpen your LangSmith (or Phoenix) dashboard and verify "
        "a single trace with three child spans."
    )


if __name__ == "__main__":
    asyncio.run(main())
