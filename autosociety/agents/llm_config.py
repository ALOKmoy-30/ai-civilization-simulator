"""Centralized LLM factory — single place for Ollama config.

num_ctx is baked into the custom Ollama Modelfile (autosociety-qwen)
so it never needs to be passed at call time — avoids the
'Completions.create() got an unexpected keyword argument num_ctx'
TypeError that occurs when CrewAI forwards it to litellm.
"""

import logging
import os
from crewai import LLM

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.7) -> LLM:
    """Build a CrewAI LLM pointed at a local Ollama instance."""
    model = os.getenv("OLLAMA_MODEL", "autosociety-qwen")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", 240))

    full_model = f"ollama/{model}"
    logger.info("get_llm() → model=%s  base_url=%s  timeout=%s", full_model, base_url, timeout)

    return LLM(
        model=full_model,
        base_url=base_url,
        timeout=timeout,
        temperature=temperature,
    )
