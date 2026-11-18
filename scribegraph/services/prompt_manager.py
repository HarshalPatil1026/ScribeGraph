"""Prompt management with optional Opik prompt library support.

If ``OPIK_API_KEY`` is set and the ``opik`` extra is installed (``uv sync --extra opik``),
prompts are fetched by name from Opik so they can be versioned and edited without a
deploy. Otherwise, or if anything goes wrong, the local prompt in the code is used.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)


class PromptManager:
    def __init__(self) -> None:
        self._client: Any = None
        self._initialized = False

    def _get_client(self) -> Any:
        if self._initialized:
            return self._client
        self._initialized = True
        if not os.getenv("OPIK_API_KEY"):
            return None
        try:
            from opik import Opik
        except ImportError:
            log.info("OPIK_API_KEY is set but opik is not installed (uv sync --extra opik).")
            return None
        try:
            self._client = Opik(project_name=os.getenv("OPIK_PROJECT_NAME", "scribegraph"))
            log.info("Opik prompt library enabled.")
        except Exception as exc:  # network or auth problems must not stop the pipeline
            log.warning("Could not initialise Opik (%s); using local prompts.", exc)
        return self._client

    def get_prompt(self, prompt_name: str, fallback_prompt: str, **variables: Any) -> str:
        """Render ``prompt_name`` from Opik if available, else ``fallback_prompt``."""
        client = self._get_client()
        if client is not None:
            try:
                prompt = client.get_prompt(name=prompt_name)
                if prompt is not None:
                    return prompt.format(**variables)
                log.info("Prompt %r not found in Opik; using the local version.", prompt_name)
            except Exception as exc:
                log.warning(
                    "Opik prompt %r failed (%s); using the local version.", prompt_name, exc
                )
        return fallback_prompt.format(**variables)


prompt_manager = PromptManager()
