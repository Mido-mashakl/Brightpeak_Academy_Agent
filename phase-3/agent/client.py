"""
Brightpeak Academy - Gemini Client (Day 1)
===========================================

This module is intentionally scoped to ONE responsibility: sending a
prompt to Gemini and getting plain text back. It knows nothing about
MCP, the database, or tools -- that separation is deliberate.

Why this matters for the project architecture:

    User -> Gemini Client -> MCP Server -> SQLite Database

The Gemini Client's job is to talk to the model. It should never reach
past the MCP Server to touch the database directly. Keeping this file
free of any MCP- or database-specific code now means that when the
MCP handshake and tool-discovery logic are added later (once the
server skeleton exists), they can be layered on top of `GeminiClient`
without having to rewrite it.

Uses the official `google-genai` SDK (the successor to the deprecated
`google-generativeai` package).

UPDATE (Phase-3): generate() now retries automatically on:
  - 429 RESOURCE_EXHAUSTED (rate limit) -- reads the server's own
    `retryDelay` out of the error message and sleeps exactly that long
    (+1s buffer) before retrying, instead of every caller needing to
    hand-add time.sleep() around every LLM call in state_graph/ nodes.
  - Transient connection errors (e.g. "Server disconnected without
    sending a response") -- short fixed backoff, since these are not
    rate-limit related and usually clear on the next attempt.
Any other error still raises GeminiClientError immediately, unchanged.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai


logger = logging.getLogger(__name__)

_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s['\"]")
MAX_RETRIES = 5
CONNECTION_ERROR_BACKOFF_SECONDS = 5


class GeminiClientError(Exception):
    """Raised whenever GeminiClient cannot fulfill a request.

    Callers (later: the MCP-aware agent layer) only ever need to catch
    this one exception type, instead of knowing about every possible
    error the underlying Gemini SDK can raise.
    """


@dataclass
class GeminiConfig:
    """Configuration for GeminiClient, kept separate from the class
    itself so it's easy to see (and later unit-test) every knob without
    reading through client construction logic.
    """

    api_key: str
    model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_output_tokens: int = 1024


def load_gemini_config(env_path: str | None = None) -> GeminiConfig:
    """Loads GEMINI_API_KEY (and optional overrides) from a .env file.

    Parameters
    ----------
    env_path:
        Optional explicit path to a .env file. If not given, python-dotenv
        searches the current working directory upward, which is the
        standard behavior for local development.

    Raises
    ------
    GeminiClientError:
        If GEMINI_API_KEY is missing. We fail fast and loudly here
        rather than letting a confusing authentication error surface
        later, deep inside an API call.
    """
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiClientError(
            "GEMINI_API_KEY is missing. Add it to your .env file, e.g.:\n"
            "  GEMINI_API_KEY=your-key-here"
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1024"))

    return GeminiConfig(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


def _extract_retry_delay_seconds(exc: Exception) -> float | None:
    """Pulls the server-provided retryDelay (e.g. "retryDelay': '35s'")
    out of a 429 error's message, if present."""
    match = _RETRY_DELAY_RE.search(str(exc))
    return float(match.group(1)) if match else None


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def _is_transient_connection_error(exc: Exception) -> bool:
    text = str(exc)
    return "Server disconnected" in text or "RemoteProtocolError" in text


class GeminiClient:
    """A small, reusable wrapper around the Gemini API.

    This class does exactly one thing: send a prompt, get text back.
    It does not know about MCP, tools, or the database -- that keeps it
    safe to build and test today, independently of the MCP server work
    happening in parallel.

    Example
    -------
    >>> config = load_gemini_config()
    >>> client = GeminiClient(config)
    >>> client.generate("Say hello in one sentence.")
    'Hello there!'
    """

    def __init__(self, config: GeminiConfig):
        self._config = config
        try:
            self._client = genai.Client(api_key=config.api_key)
        except Exception as exc:  # noqa: BLE001 - normalized below
            raise GeminiClientError(
                f"Failed to initialize Gemini client: {exc}"
            ) from exc

    def generate(self, prompt: str) -> str:
        """Sends `prompt` to Gemini and returns the plain-text response.

        Retries automatically on 429 rate-limit errors (sleeping for the
        server's own retryDelay) and on transient connection drops, up to
        MAX_RETRIES attempts. Any other error raises immediately.

        Parameters
        ----------
        prompt:
            The text prompt to send. Must be non-empty.

        Returns
        -------
        str:
            The model's plain-text response.

        Raises
        ------
        GeminiClientError:
            If the prompt is empty, the API call fails after retries, or
            the model returns no usable text (e.g. blocked by a safety
            filter).
        """
        if not prompt or not prompt.strip():
            raise GeminiClientError("Prompt must not be empty.")

        logger.debug("Sending prompt to Gemini (model=%s)", self._config.model)

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._config.model,
                    contents=prompt,
                    config={
                        "temperature": self._config.temperature,
                        "max_output_tokens": self._config.max_output_tokens,
                    },
                )
                text = getattr(response, "text", None)
                if not text:
                    raise GeminiClientError(
                        "Gemini returned no text (the response may have "
                        "been blocked by a safety filter, or the model "
                        "produced an empty result)."
                    )
                return text

            except Exception as exc:
                last_exc = exc
                if attempt == MAX_RETRIES:
                    break

                if _is_rate_limit_error(exc):
                    delay = _extract_retry_delay_seconds(exc)
                    wait = (delay + 1) if delay is not None else 15
                    logger.warning(
                        "Gemini rate-limited (attempt %d/%d); waiting %.1fs before retry.",
                        attempt, MAX_RETRIES, wait,
                    )
                    time.sleep(wait)
                    continue

                if _is_transient_connection_error(exc):
                    logger.warning(
                        "Gemini connection dropped (attempt %d/%d); retrying in %ds.",
                        attempt, MAX_RETRIES, CONNECTION_ERROR_BACKOFF_SECONDS,
                    )
                    time.sleep(CONNECTION_ERROR_BACKOFF_SECONDS)
                    continue

                # Not a retryable error -- fail immediately, same as before.
                logger.error("Gemini request failed: %s", exc)
                raise GeminiClientError(f"Gemini request failed: {exc}") from exc

        logger.error("Gemini request failed after %d attempts: %s", MAX_RETRIES, last_exc)
        raise GeminiClientError(
            f"Gemini request failed after {MAX_RETRIES} attempts: {last_exc}"
        ) from last_exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        cfg = load_gemini_config()
        gemini_client = GeminiClient(cfg)

        response = gemini_client.generate(
            "In one short sentence, what is Brightpeak Academy?"
        )

        print(response)

    except GeminiClientError as e:
        print(f"Error: {e}")