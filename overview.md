# 数据治理平台重构报告

> 重构日期：2026-08-04 | 执行者：资深开发工程师

## 重构成果总览

| 指标 | 重构前 | 重构后 | 变化 |
|------|--------|--------|------|
| 测试用例 | 33 | 51 | +55% |
| 测试覆盖率 | ~18% (行数比) | 76.6% (stmt cov) | +58pp |
| index.html 行数 | 5,157 | 2,111 | -59% |
| 内联 CSS/JS | 3,046 行 | 0 | 消除 |
| DRY 违例 | 2 处 | 0 | 消除 |
| CORS 安全 | `allow_origins=["*"]` | 配置化 + 白名单 | 修复 |
| API 认证 | 无 | API Key 中间件 | 新增 |
| API 请求校验 | `dict=Body()` | Pydantic 模型 | 修复 |
| Lint 工具 | 无 | ruff + mypy | 新增 |
| Pre-commit | 无 | ruff + mypy + pytest | 新增 |
| 文件锁 | 无 | fcntl.flock | 新增 |
| Python 版本 | 3.9+ | 3.10+ | 升级 |

---

## Phase 1: 工程基础设施

### 新增配置

**pyproject.toml** — 完全重写，统一配置入口：
- `ruff` lint (E/W/F/I/B/UP/SIM/RUF) + format
- `mypy` 静态类型检查
- `pytest-cov` 覆盖率，`fail_under=40`
- Python 3.10+，dev/api 依赖分组

**`.pre-commit-config.yaml`** — 三阶段 hooks：
- ruff check --fix + format（代码风格）
- mypy（类型检查）
- pytest（测试门禁，push 阶段）

**`.env.example`** — 环境变量文档：CORS origins、API Key、LLM 模式

### 效果
- 66 个 lint 问题自动修复（Optional→X|None、unused vars、SIM 简化等）
- 12 个文件自动格式化
- 全量 ruff check + format 零报错

---

## Phase 2: 后端重构

### 2.1 消除 DRY 违例

**问题**：`MetricRecord` 从 dict 构建逻辑在 `catalog.py` 和 `metrics_csv.py` 各写了一遍，30+ 字段手动映射。

**方案**：`from_row()` classmethod + `dataclasses.fields()` 自动映射

```python
# catalog.py — 重构后
@classmethod
def from_row(cls, row: dict[str, str]) -> MetricRecord:
    return cls(**{f.name: (row.get(f.name) or "").strip() for f in fields(cls)})
```

**效果**：
- `load_catalog` 从 140 行手动映射 → 10 行循环
- `row_to_record` 委托 `from_row`，零重复
- 新增字段只需改 dataclass，映射自动适配

### 2.2 API Pydantic 请求模型

**问题**：`dict = Body(...)` 无请求校验，OpenAPI 缺 schema。

**方案**：`api/schemas.py` 定义 `MetricCreateRequest` / `MetricUpdateRequest`

```python
class MetricCreateRequest(BaseModel):
    metric_id: str = Field(..., min_length=1)
    metric_cn: str = Field(..., min_length=1)
    # ... 20+ 字段带默认值和描述
```

**效果**：
- 请求体自动校验（空 metric_id → 422 而非 400）
- OpenAPI 文档自动生成 schema
- `exclude_unset=True` 支持部分更新

### 2.3 Service 层

**新增**：`services/metric_service.py` — `MetricService` 类封装业务逻辑

```python
class MetricService:
    def list_metrics(self, domain: str | None = None) -> list[dict]: ...
    def get_stats(self) -> dict[str, int]: ...
    def create(self, payload: dict) -> dict: ...
    def update(self, metric_id: str, payload: dict) -> dict: ...
    def export_csv(self) -> str: ...
    def find_record(self, metric_id: str) -> MetricRecord | None: ...
```

**效果**：API 层只管 HTTP 协议，业务逻辑可测试、可复用

### 2.4 文件锁

**问题**：CSV 读写无锁，多人并发会丢数据。

**方案**：`fcntl.flock` 上下文管理器

```python
@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    with lock_path.open("w") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
```

应用于 `metrics_csv._write_rows` 和 `roots_csv.append_root_row`

---

## Phase 3: 安全加固

### CORS 收敛

```python
# 重构前
allow_origins=["*"]

# 重构后
allow_origins=get_cors_origins()  # env 驱动，默认本地开发端口
```

### API Key 认证

```python
class APIKeyMiddleware(BaseHTTPMiddleware):
    # 环境变量 DATA_GOV_API_KEY 未设置 → 不启用（开发模式）
    # 设置后 → 除白名单路径外需 X-API-Key 头
```

---

## Phase 4: 前端拆分

**问题**：`index.html` 5,157 行，内联 CSS 1,669 行 + 内联 JS 1,377 行。

**方案**：脚本提取为独立文件

| 文件 | 内容 | 行数 |
|------|------|------|
| `css/app.css` | 设计系统 + 布局 + 组件样式 | 1,669 |
| `js/app.js` | 页面交互逻辑 | 1,377 |
| `index.html` | 纯 HTML 结构 | 2,111 |

---

## 新增测试

`tests/test_refactored.py` — 18 个测试，4 个测试类：

| 测试类 | 用例数 | 覆盖内容 |
|--------|--------|----------|
| TestPydanticSchemas | 5 | 请求模型校验、默认值、exclude_unset |
| TestMetricService | 6 | 列表查询、统计、查找、导出 |
| TestAPIValidation | 5 | 422 校验错误、创建成功、部分更新 |
| TestCORSConfiguration | 2 | 非通配符、env 覆盖 |

---

## 改动文件清单

### 新增文件 (9)
- `src/data_governance/api/schemas.py` — Pydantic 请求/响应模型
- `src/data_governance/api/middleware.py` — CORS + API Key 中间件
- `src/data_governance/services/__init__.py` — Service 包
- `src/data_governance/services/metric_service.py` — 指标业务服务
- `tests/test_refactored.py` — 重构测试 (18 用例)
- `ui-prototype/css/app.css` — 提取的 CSS
- `ui-prototype/js/app.js` — 提取的 JS
- `.pre-commit-config.yaml` — Pre-commit hooks
- `.env.example` — 环境变量文档

### 修改文件 (8)
- `pyproject.toml` — 完全重写，统一配置
- `setup.cfg` — 废弃（保留指向 pyproject.toml）
- `src/data_governance/io/catalog.py` — from_row + 简化 load_catalog
- `src/data_governance/io/metrics_csv.py` — 委托 from_row + 文件锁
- `src/data_governance/io/roots_csv.py` — 文件锁
- `src/data_governance/io/reviews.py` — 清理 unused var
- `src/data_governance/api/app.py` — Pydantic 模型 + 中间件 + Service
- `src/data_governance/llm/env.py` — SIM 简化
- `src/data_governance/llm/parallel.py` — SIM 简化
- `ui-prototype/index.html` — CSS/JS 外部化
- 12 个文件 ruff format 自动格式化

---

## 后续建议

| 优先级 | 事项 | 说明 |
|--------|------|------|
| P1 | CI/CD pipeline | GitHub Actions: ruff + mypy + pytest on PR |
| P1 | CLI 测试 | cli.py 0% 覆盖率，需补端到端测试 |
| P2 | LLM 模块测试 | parallel.py 36%、factory.py 32% 覆盖率 |
| P2 | 前端 ES module 化 | app.js 可拆分为 import/export 模块 |
| P3 | Repository 模式完善 | 当前 Service 层已分离，可进一步抽 Repository |
| P3 | API v1 版本化 | 添加 /api/v1/ 前缀路由 |
