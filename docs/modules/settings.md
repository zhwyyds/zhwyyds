# 系统设置（环境标识）模块

> 本模块 = 页面显示「分支 · 版本」标识，区分 dev/main 环境。

## 任务清单

| # | 任务 | 状态 | 验收标准 |
|---|---|---|---|
| 1 | 后端 /api/meta 增加 version + branch 字段 | ✅ 完成 | API 返回 `{"version":"0.2.0","branch":"dev"}` |
| 2 | `__version__` 对齐 pyproject（0.1.0→0.2.0） | ✅ 完成 | 两处版本一致 |
| 3 | 前端顶栏加 env-badge 容器 | ✅ 完成 | header 出现 #envBadge 元素 |
| 4 | renderEnvBadge 拉取 /api/meta 填充 | ✅ 完成 | dev 蓝 / main 绿 / 未连接红 |
| 5 | env-badge 样式（dev/main/off 三态） | ✅ 完成 | CSS 3 组样式 |
| 6 | 真实环境验收 | ✅ 完成 | 徽标显示 `dev · v0.2.0`，pageerror 0 |

## 测试结果

- 测试时间：2026-08-06 16:50
- 测试分支：dev（H26）
- 测试环境：真实环境（8080 页面 + 8765 API）

### 自动化测试

| 项 | 命令 | 结果 |
|---|---|---|
| pytest | `pytest -q` | ✅ 172 passed |
| ruff | `ruff check src` | ✅ All checks passed |
| mypy | `mypy src` | ✅ 0 error |
| JS 语法 | `node --check` | ✅ 全部通过 |

### 真实环境验收

- API：`/api/meta` → `{"version":"0.2.0","branch":"dev"}` ✅
- 页面徽标：`dev · v0.2.0`（class=`env-badge env-badge--dev` 蓝色）✅
- pageerror：0 ✅
- 截图：`tests/e2e/screenshots/h26-env-badge.png`

### 结论

✅ 全部通过

---

## 变更记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-08-06 | H26 | 新增环境标识：页面显示「分支 · 版本」，dev 蓝 / main 绿 |
