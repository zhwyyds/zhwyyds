# 数据治理平台（data_governance）

Python 包：词根/指标以 CSV + JSON 文件存储，大模型多路比对（默认 Mock；M3 可接 OpenAI / Anthropic / 智谱）。

## 环境

```bash
cd /Users/heyuan/DEVELOPMENT/data_go
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
data-governance version
data-governance root generate --domain cust --input examples/root_generation_cust.json
data-governance root generate --domain cust --input examples/root_generation_cust.json --write-roots
data-governance metric review --domain sale --input examples/metric_review_sale.json
data-governance acceptance run
data-governance acceptance run --json
```

### M3 真实大模型（可选）

| 变量 | 说明 |
|------|------|
| `DATA_GOV_LLM_MODE` | `mock` \| `live` \| `auto`（默认：有 Key 则 live，否则 mock） |
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `DASHSCOPE_API_KEY` / `QWEN_API_KEY` | **通义千问**（DashScope OpenAI 兼容接口） |
| `ZHIPUAI_API_KEY` / `GLM_API_KEY` | 智谱（可选，需在 `models.csv` 启用） |

`config/models.csv` 中至少 **2 个** 已配置 Key 的模型才会进入 live 并行比对。CLI 可加 `--live`：

```bash
data-governance root generate --domain cust --input examples/root_generation_cust.json --live
data-governance metric review --domain sale --input examples/metric_review_sale.json --live
```

`GET /api/llm/status` 查看当前模式与各厂商 Key 是否已配置（不返回密钥）。

**填写 Key（任选其一，值在 `=` 或 JSON 引号后面补充）：**

```bash
cp .env.example .env
# 编辑 .env：OPENAI_API_KEY=sk-...

cp config/secrets.example.json config/secrets.json
# 编辑 secrets.json 中 OPENAI_API_KEY 等字段
```

`config/models.csv` 的 `api_key_env` 列声明各模型读取的环境变量名（默认 OpenAI/Anthropic/智谱 三列）。

### 本地 API（需 `pip install -e ".[api]"`）

```bash
data-governance serve --port 8765
# http://127.0.0.1:8765/        — 治理 UI（接 API）
# http://127.0.0.1:8765/docs    — OpenAPI
# http://127.0.0.1:8765/ui/metric-spec-template.html — 指标规范表视觉模板
```

主要接口：`GET /api/metrics`、`PUT /api/metrics/{id}`、`POST /api/metrics`、`POST /api/metrics/{id}/review`（多模型评审，Mock/Live）、`GET /api/llm/status`、`GET /api/metrics/export`、`GET /api/metric-reviews/latest`、`GET /api/lineage`、`GET /api/modifier-rules`、`GET /api/metric-tree`、`GET /api/metrics/stats`。

## 目录

与 `数据治理项目方案_v2.md` §3.2 对齐：`config/`、`roots/`、`metrics/`、`lineage/`、`reviews/`。

词根字段与业务规则见 `docs/specs/词根字段与规则.md`。
