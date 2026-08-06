# 功能测试报告

**生成时间**：2026-08-06 13:36  
**测试环境**：headless Chromium + 真实后端 API（127.0.0.1:8765） + 真实 DeepSeek LLM  
**测试数据基线**：HEAD 原始（sale 15 行 + mall 1 行 + 29 个历史评审文件），未新增任何测试指标

---

## 一、测试概览

| # | 功能页/操作 | 结果 | 截图 |
|---|---|---|---|
| 1 | 页面加载 + 导航 | ✅ | page-dashboard.png |
| 2 | F1 治理总览 | ✅ | page-dashboard.png |
| 3 | F2 指标库列表 | ✅ | page-metrics.png |
| 4 | F2 详情抽屉（M_SALE_001）| ✅ | page-metrics-detail-drawer.png |
| 5 | F3 指标管理表格 | ✅ | page-metric-mgmt.png |
| 6 | F3 「+ 新增指标」抽屉 | ✅ | page-mgmt-new-drawer.png |
| 7 | F4 单指标评审（真实 DeepSeek，48s 完成）| ✅ | page-review-click-toast.png + page-review-result.png |
| 8 | F5 模型评审页（查看历史评审）| ✅ | page-review.png |
| 9 | F6 词根库 | ✅ | page-roots.png |
| 10 | F7 批量生成页 | ✅ | page-batch-gen.png |
| 11 | F8 验收页 | ✅ | page-acceptance.png |

**11/11 全部通过** / **0 个 pageerror** / **0 个浏览器原生 alert**

---

## 二、测试过程详细步骤

### Step 1. 服务 & 环境核查
```
✓ API 8765 健康检查 200
✓ 页面 8080 健康检查 200
✓ HEAD 数据基线：sale 15 行 / mall 1 行 / 29 历史评审（原始未动）
✓ .cache/llm 清空（无缓存依赖）
```

### Step 2. 页面加载 & 路由切换（dashboard → 8 个页面）
- 进入 dashboard（默认页）
- 切换到 7 个页面（metrics / metric-mgmt / roots / batch-gen / review / acceptance）
- 每个页面验证：DOM 渲染正常、无 pageerror、无 4xx

### Step 3. 指标库详情抽屉（核心交互）
- 打开 `metrics` 页面
- 调用 `loadMetricDetail('M_SALE_001')`
- 验证 `#metricDetailDrawer` 出现并显示完整字段

### Step 4. 指标管理 → 「+ 新增」抽屉
- 打开 `metric-mgmt` 页面
- 点击「+ 新增指标」按钮 → 抽屉弹出（`#metricNewDrawer` show=true）
- 验证抽屉打开完整流程

### Step 5. 单指标评审（真实 DeepSeek AI 调用）
- 找到第一个非 approved 状态指标的「🤖 评审」按钮
- 点击 → 立即弹出进度提示 toast「🤖 评审进行中…」
- 后台调用真实 DeepSeek 完成评审（48 秒）
- 弹出完成 toast「✅ 评审完成，结果已写入 reviews/...」
- 页面自动切到 `review` 模型评审页
- 评价详情卡（多模型评分 + 评审批次 + 结论）正确渲染

### Step 6. 模型评审页内容
- 切到 `review` 页
- `#reviewDetailHost` 渲染历史评审的 4 个模型评分卡

### Step 7. 验收页 / 批量生成页 / 词根库
- 三个页面分别打开 → 截图保存
- 验证渲染正常

---

## 三、关键验证点

✅ **真实环境而非 mock**：脚本用 Playwright headless Chromium 连真实 API（127.0.0.1:8765），AI 调用走真实 DeepSeek key。  
✅ **唯一测试产物**：本次测试新增 1 个评审文件 `sale_metric_review_030.json`（F4 评审的输出），未生成新指标。  
✅ **无原生 alert**：所有 alert/toast 改造（H7/H10 后的新代码）已覆盖，包括本次新增的评审完成 toast。  
✅ **页面无 JS 报错**：所有页面切到后 `pageerror=[]`。

---

## 四、截图目录

所有截图位于 `tests/e2e/screenshots/`：

| 截图文件 | 对应页面 |
|---|---|
| page-dashboard.png | 治理总览（首屏） |
| page-metrics.png | 指标库列表 |
| page-metrics-detail-drawer.png | 指标详情抽屉（M_SALE_001） |
| page-metric-mgmt.png | 指标管理表格 |
| page-mgmt-new-drawer.png | 新增指标抽屉 |
| page-review-click-toast.png | 评审点击 + 进度 toast |
| page-review-result.png | 评审完成结果（跳到 review 页） |
| page-review.png | 模型评审页（历史评审详情） |
| page-roots.png | 词根库 |
| page-batch-gen.png | 批量生成 |
| page-acceptance.png | 验收页 |
