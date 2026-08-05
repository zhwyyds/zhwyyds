from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from data_governance.llm.bootstrap import bootstrap_llm_env, load_secrets_json
from data_governance.llm.env import provider_api_key


def test_load_secrets_json_does_not_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps({"OPENAI_API_KEY": "from-file", "ANTHROPIC_API_KEY": "anth"}),
        encoding="utf-8",
    )
    assert load_secrets_json(secrets) is True
    assert os.environ["OPENAI_API_KEY"] == "from-env"
    assert os.environ["ANTHROPIC_API_KEY"] == "anth"


def test_bootstrap_dotenv_and_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OPENAI_API_KEY", "ZHIPUAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-key\n", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "secrets.json").write_text(
        json.dumps({"ZHIPUAI_API_KEY": "zhipu-secret"}),
        encoding="utf-8",
    )
    meta = bootstrap_llm_env(tmp_path)
    assert meta["dotenv"] is True
    assert meta["secrets_json"] is True
    assert os.environ["OPENAI_API_KEY"] == "dotenv-key"
    assert os.environ["ZHIPUAI_API_KEY"] == "zhipu-secret"


def test_provider_api_key_env_var_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MY_CUSTOM_OPENAI", "custom")
    assert provider_api_key("OpenAI", env_var="MY_CUSTOM_OPENAI") == "custom"
