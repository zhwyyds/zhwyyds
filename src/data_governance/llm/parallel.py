from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from data_governance.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)


def run_models_parallel_mock(
    clients: list[MockLLMClient],
    batch: list[Any],
) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    def _call(client: MockLLMClient) -> tuple[str, str]:
        return client.model_name, client.complete_for_batch(batch)

    with ThreadPoolExecutor(max_workers=len(clients) or 1) as pool:
        futures = [pool.submit(_call, c) for c in clients]
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda x: x[0])
    return results


def run_models_parallel_prompt(
    clients: list[Any],
    prompt: str,
    *,
    complete_fn: Callable[[Any, str], str] | None = None,
    retries: int = 1,
    cache_base_dir: Path | None = None,
) -> list[tuple[str, str]]:
    """Call each client's complete(prompt); skip failures; require ≥2 success."""

    from data_governance.llm.cache import get_cached_response, set_cached_response

    def _complete(client: Any) -> tuple[str, str]:
        name = client.model_name
        if cache_base_dir is not None:
            cached = get_cached_response(cache_base_dir, name, prompt)
            if cached is not None:
                return name, cached
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                text = complete_fn(client, prompt) if complete_fn else client.complete(prompt)
                if cache_base_dir is not None:
                    set_cached_response(cache_base_dir, name, prompt, text)
                return name, text
            except Exception as exc:
                last_err = exc
                logger.warning("LLM %s attempt %s failed: %s", name, attempt + 1, exc)
        raise last_err or RuntimeError(f"LLM {name} failed")

    results: list[tuple[str, str]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(clients) or 1) as pool:
        futures = {pool.submit(_complete, c): c for c in clients}
        for fut in as_completed(futures):
            client = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:
                errors.append(f"{client.model_name}: {exc}")
    results.sort(key=lambda x: x[0])
    if len(results) < 1:
        detail = "; ".join(errors) if errors else "no successful responses"
        raise RuntimeError(f"M3 needs at least 1 model response; got {len(results)}. {detail}")
    return results
