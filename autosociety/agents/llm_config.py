"""Centralized LLM factories — separate configs for citizens vs government.

Design rationale:
  - Citizens use qwen2.5-coder:0.5b  → ultra-fast, minimal CPU usage,
    low context window (good for simple reactive decisions).
  - Government agents use qwen2.5-coder:3b → higher reasoning quality
    for multi-step structural policy analysis.

num_ctx is baked into the Ollama Modelfile (autosociety-qwen) to avoid
the 'Completions.create() got an unexpected keyword argument num_ctx'
TypeError from LiteLLM forwarding it as an unsupported kwarg.
"""

import logging
import os
from crewai import LLM

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ── Model tags ───────────────────────────────────────────────────────────────
# Override via .env if needed:
#   OLLAMA_CITIZEN_MODEL=qwen2.5-coder:0.5b
#   OLLAMA_GOVERNMENT_MODEL=qwen2.5-coder:3b
_CITIZEN_MODEL   = os.getenv("OLLAMA_CITIZEN_MODEL",    "qwen2.5-coder:0.5b")
_GOVERNMENT_MODEL = os.getenv("OLLAMA_GOVERNMENT_MODEL", "qwen2.5-coder:3b")


def get_citizen_llm(temperature: float = 0.7) -> LLM:
    """Lightweight 0.5B model for standard citizen agents.

    Lower timeout (120 s) keeps individual agents from blocking the
    sequential CPU queue if the model stalls.
    """
    model = f"ollama/{_CITIZEN_MODEL}"
    timeout = int(os.getenv("OLLAMA_CITIZEN_TIMEOUT", 120))
    logger.info("get_citizen_llm() → model=%s  base_url=%s  timeout=%s",
                model, OLLAMA_BASE_URL, timeout)
    return LLM(
        model=model,
        base_url=OLLAMA_BASE_URL,
        timeout=timeout,
        temperature=temperature,
    )


def get_government_llm(temperature: float = 0.4) -> LLM:
    """3B model for government agents — higher reasoning quality.

    Longer timeout (180 s) allows complex multi-step policy synthesis.
    """
    model = f"ollama/{_GOVERNMENT_MODEL}"
    timeout = int(os.getenv("OLLAMA_GOVERNMENT_TIMEOUT", 180))
    logger.info("get_government_llm() → model=%s  base_url=%s  timeout=%s",
                model, OLLAMA_BASE_URL, timeout)
    return LLM(
        model=model,
        base_url=OLLAMA_BASE_URL,
        timeout=timeout,
        temperature=temperature,
    )


# ── Backwards-compat alias (existing call-sites that use get_llm()) ──────────
def get_llm(temperature: float = 0.7) -> LLM:
    """Legacy alias — defaults to the government (3B) model.
    Prefer get_citizen_llm() or get_government_llm() directly.
    """
    return get_government_llm(temperature=temperature)
