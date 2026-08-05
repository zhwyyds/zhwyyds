from pathlib import Path

from data_governance.llm.cache import get_cached_response, set_cached_response


def test_llm_response_cache_roundtrip(tmp_path: Path) -> None:
    set_cached_response(tmp_path, "qwen-plus", "prompt-a", "response-a")
    assert get_cached_response(tmp_path, "qwen-plus", "prompt-a") == "response-a"
    assert get_cached_response(tmp_path, "qwen-plus", "other") is None
