"""Shared LLM utilities for the LecGraph pipeline."""

import json
import re
import threading
import time

from openai import OpenAI
from rich.console import Console

from src.config import settings

console = Console(force_terminal=True)

_client = None
_client_lock = threading.Lock()


def get_client():
    """Get or create the OpenAI client instance (thread-safe)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(api_key=settings.openai_api_key)
    return _client


class QuotaExhaustedError(Exception):
    """Raised when the API key has no quota left. Retrying won't help."""
    pass


def call_llm(prompt: str, max_retries: int = 3) -> str:
    """Call OpenAI API with smart retry: only retry temporary rate limits."""
    client = get_client()

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.llm_max_tokens,
                temperature=0.2,
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "429" not in error_msg:
                if "insufficient_quota" in error_msg:
                    raise QuotaExhaustedError(
                        "API key quota exhausted. "
                        "Check your billing at https://platform.openai.com/account/billing"
                    )
                raise

            if "insufficient_quota" in error_msg:
                raise QuotaExhaustedError(
                    "API key quota exhausted. "
                    "Check your billing at https://platform.openai.com/account/billing"
                )

            match = re.search(r"retry after ([\d.]+)", error_msg, re.IGNORECASE)
            wait_time = min(float(match.group(1)) + 2 if match else 15.0, 30.0)
            console.print(
                f"  [yellow]Rate limited. Waiting {wait_time:.0f}s "
                f"(attempt {attempt + 1}/{max_retries})...[/]"
            )
            time.sleep(wait_time)

    raise RuntimeError(f"Failed after {max_retries} retries")


def parse_json_response(text: str) -> list | dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)
