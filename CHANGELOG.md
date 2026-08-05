# 变更记录

> 本文件从 2026-08-05 起维护。格式：日期 + 版本/里程碑 + 变更摘要。

## 2026-08-05

### 迭代 3 — 治理闭环（v0.5.0）
- 发布增强：撤销发布（指标回退上一版本 + 历史留痕 + registry 标记 revoked）、版本差异对比、跨域发布总览（`/api/releases/overview`）
- 域级治理看板：`GET /api/dashboard/domains`（每域词根/指标/评分/血缘/口径/发布红绿灯）
- 黄金演示数据：`scripts/demo_data.py`（S/A/B/C 四级含反例）
- 文档体系：`docs/README.md` 索引、`docs/使用说明.md` 操作手册、本 CHANGELOG

### 迭代 2 — 核心产能 + 口径助手（v0.4.0）
- 批量生成后端：原子 × 修饰词派生（`generate.py`）、`POST /api/metrics/batch-generate`、CLI `metric generate`
- 词根写 API：`POST/PUT /api/roots`；修复 RootRecord 丢字段缺陷
- 血缘上传：`POST /api/lineage/upload`
- **口径助手**：12 个 caliber_* 结构化字段落地、三模型起草 + 共识比对（`caliber/draft.py`）、核查状态机（`caliber/review.py`：批准触发重评分/打回附原因/人工修改）、存量补全 `POST /api/caliber/backfill`、发布门禁（口径未核查禁发）、评分口径维度升级为结构化检查
- 前端：批量生成接真接口、词根维护 UI、口径核查中心页（`js/it2.js`）

### 迭代 1 — 质量与运维底线（v0.3.0）
- 测试补强：scoring/release/CLI 共 17 个新测试；覆盖率 76.6% → 80.8%；mypy 9 个历史错误清零
- 数据自检：`data-governance validate`（9 项检查）
- 备份脚本 `scripts/backup.sh`、GitHub Actions CI、运维手册
- 口径字段标准与迁移方案定稿

### 里程碑（v0.2.0 → v0.1.0 历史）
- 2026-08-04：工程基础设施（ruff/mypy/pre-commit）、Service 层重构、CORS/API Key 安全、前端 CSS/JS 拆分
- 2026-08-03~04：评分引擎、版本发布控制、多模型评审、验收引擎
