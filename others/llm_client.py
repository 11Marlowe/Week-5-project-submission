"""
Shared LLM client — routes through the Helicone proxy.
API key and proxy URL are injected via GitHub Codespaces org-level secrets.
Students do not interact with this file directly.
"""

import os
from openai import AsyncOpenAI

_client: AsyncOpenAI | None = None


from dotenv import load_dotenv
load_dotenv(override=True)
_HELICONE_BASE = os.getenv("HELICONE_BASE_URL")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_HELICONE_API_KEY = os.getenv("HELICONE_API_KEY")

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=_OPENROUTER_API_KEY,
            base_url=_HELICONE_BASE,
            default_headers={
                "Helicone-Auth": f"Bearer {_HELICONE_API_KEY}"
            },
        )
    return _client
