from pathlib import Path

import pytest

from data_governance.config_loader import load_domains, load_models
from data_governance.paths import repo_root


def test_load_domains_from_repo():
    root = repo_root(Path(__file__).resolve().parent.parent)
    domains = load_domains(root / "config" / "domains.csv")
    assert len(domains) == 14
    assert domains[0].domain_code == "cust"


def test_load_root_generation_models():
    root = repo_root(Path(__file__).resolve().parent.parent)
    models = load_models("root_generation", config_path=root / "config" / "models.csv")
    assert len(models) >= 1  # 单模型 live：至少 1 个启用模型（当前仅 DeepSeek）
    assert models[0].priority <= models[-1].priority
    assert models[0].api_key_env  # 存环境变量名（非 key 值）


def test_load_models_requires_min_enabled(tmp_path: Path):
    csv_path = tmp_path / "models.csv"
    csv_path.write_text(
        "model_id,model_name,provider,use_case,priority,enabled,api_endpoint,remark\n"
        "1,gpt-4o,OpenAI,root_generation,1,false,,\n",  # 全停用 → 无启用模型
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least 1"):
        load_models("root_generation", config_path=csv_path)
