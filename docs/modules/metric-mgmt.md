# 指标管理 metric-mgmt 模块

## 任务清单

| # | 任务 | 状态 | 验收标准 |
|---|---|---|---|
| 1 | 指标 CRUD（新增/编辑/下线/删除） | ✅ 完成 | 功能可正常使用 |
| 2 | 批量操作（批量发布/下线） | ✅ 完成 | 功能可正常使用 |
| 3 | 分页（每页 12 条，翻页/改每页数，H11） | ✅ 完成 | 功能可正常使用 |
| 4 | 主题域下拉动态 14 域 + 一级分类自动=主题域（H16） | ✅ 完成 | 功能可正常使用 |

## P1 批量导入流水线（H31）

| # | 任务 | 状态 |
|---|---|---|
| P1-1 | 待办任务实体 + CSV 50条/组切分（io/task_store.py） | ✅ 完成 |
| P1-2 | 去重比对（精确 + 归一化近似） | ✅ 完成 |
| P1-3 | AI 批量生成指标卡片（复用 suggest） | ✅ 完成 |
| P1-4 | 批量导入页（任务列表 + 卡片堆叠） | ✅ 完成 |
| P1-5 | 逐卡人工评审 → draft 草稿 | ✅ 完成 |
| P1-6 | draft 状态接入 + 全量验收 | ✅ 完成 |

- API：`/api/import-tasks/*`（upload/list/detail/process/review）
- 状态机新增 draft；测试 14 个（task_store 6 + import_tasks_api 8）
- 真实环境验收：上传→切分→去重→AI生成→评审通过→draft 入库全链路 ✅

### 质量审查修复（2026-08-06）

| # | 问题 | 级别 | 修复 |
|---|---|---|---|
| 1 | `task_path` 直接拼接 task_id → `../../etc/passwd.json` 路径遍历 | Critical | 安全字符白名单（`[A-Za-z0-9_]`）+ 路由 `_safe_task()` 兜底（非法→400，不存在→404）+ 2 个安全测试 |
| 2 | 前端 fetch 相对路径打到 8080 静态服务器 | High | `api()` 先探测 API base |
| 3 | `esc is not defined`（评审弹窗） | Medium | batch-import.js 增加本地 esc() |
| 4 | `tasks_dir` 不自动建目录 | Medium | mkdir parents |
| 5 | mypy：`task = update_import_task()` 变量覆盖导致类型推断错误 | Medium | 独立 `updated` 变量隔离 |
| 6 | ruff：未使用 `force` 变量 | Low | 删除 |
| 7 | `test_metric_review_pipeline` 断言依赖运行时 models.csv | Low | 测试自包含固定 models.csv（3 路 fixture 模型），解耦运行时配置 |
| 8 | 上传时遇到代理/网关 502 HTML 错误页抛 `Unexpected token 'I'...` 低层错误 | Medium | `fetchJson`/`api` 改用"先取 text 再 parse"，捕获 SyntaxError 给 `status + body 前缀` 友好提示 |
| 9 | `tasks/` 运行时产物未 .gitignore 屏蔽（仓库根残留 12 个测试 JSON） | Low | .gitignore 加 `tasks/`，删除 .gitkeep 占位 |
| 10 | AI 生成串行逐条调 DeepSeek，10 条 316s（单条 31.6s），50 条/组约 26 分钟 | High | `ThreadPoolExecutor` + `pool.map` 并发（默认 8 路，env `AI_GENERATE_PARALLEL` 可调），实测 10 条 123.3s（单条 12.3s，提速 2.57x），顺序保持 |

## 实现说明

- 后端：routes_metrics.py 25 端点 + metric-mgmt.js
- 前端：`ui-prototype/` 对应页面

## 测试结果

- 测试时间：2026-08-06（历史功能补档）
- 测试分支：dev
- 测试环境：真实环境（8080 页面 + 8765 API + 真实 DeepSeek）或本地单测

### 自动化测试

| 项 | 命令 | 结果 |
|---|---|---|
| pytest | `pytest -q` | ✅ 186 passed |
| ruff | `ruff check src tests` | ✅ All checks passed |
| mypy | `mypy src` | ✅ 0 error |
| JS 语法 | `node --check *.js` | ✅ 全部通过 |

### 真实环境验收

- 页面加载 pageerror：0 ✅
- 原生 alert：0 ✅（全量 alert→toast 清理）
- 截图：`tests/e2e/screenshots/`（对应功能验收图）

### 结论

✅ 全部通过（历史功能，已在迭代中验证）

---

## 变更记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-08-06 | H31 收尾 | 质量审查修复 10 项（含路径遍历 Critical、前端非 JSON 响应处理、tasks 产物屏蔽、AI 生成并发 8 路），回归 187 全绿 |
| 2026-08-06 | 补档 | 历史功能模块文档补建（H25 规范落地） |
