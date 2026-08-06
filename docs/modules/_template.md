# 模块开发文档模板

> 复制本文件为 `docs/modules/<module>.md` 使用。开发前填「任务清单」，开发后填「测试结果」。

# <模块名> 模块

## 任务清单

| # | 任务 | 状态 | 验收标准 |
|---|---|---|---|
| 1 | 描述要做什么 | ☐ 待办 | 如何判定完成 |
| 2 | ... | ☐ 待办 | ... |

## 测试结果

- 测试时间：YYYY-MM-DD HH:MM
- 测试分支：dev / feature-xxx
- 测试环境：真实环境 / 本地单测

### 自动化测试

| 项 | 命令 | 结果 |
|---|---|---|
| pytest | `pytest -q` |  |
| ruff | `ruff check src` |  |
| mypy | `mypy src` |  |
| JS 语法 | `node --check *.js` |  |

### 真实环境验收

- Playwright 截图：`tests/e2e/screenshots/xxx.png`
- pageerror / console error / 4xx：0 / 0 / 0
- 关键交互验证：
  - [ ] 步骤描述 + 结果

### 结论

✅ 全部通过 / 🚧 开发中 / ⚠️ 部分待修 / ❌ 未通过

---

## 变更记录

| 日期 | 版本 | 说明 |
|---|---|---|
|  |  |  |
