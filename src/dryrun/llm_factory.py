"""
llm_factory.py — Central LLM selection for DryRun.

Lets the whole crew switch providers from environment variables so the project
runs either against OpenAI (best quality) or a free local Ollama model (no API
key, no cost).

Env vars
--------
LLM_PROVIDER      "openai" (default) | "ollama"
OPENAI_MODEL_NAME model name for OpenAI   (default: gpt-4o-mini)
OLLAMA_MODEL      model name for Ollama    (default: llama3.1)
OLLAMA_BASE_URL   Ollama server URL        (default: http://localhost:11434)

Usage
-----
    from dryrun.llm_factory import build_llm
    agent = Agent(..., llm=build_llm())
"""

from __future__ import annotations

import os

from crewai import LLM


def build_llm() -> LLM:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3.1")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return LLM(
            model=f"ollama/{model}",
            base_url=base_url,
            # Local models need a nudge toward valid JSON and determinism.
            temperature=0.2,
        )

    # Default: OpenAI
    model = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    return LLM(model=model, temperature=0.3)
