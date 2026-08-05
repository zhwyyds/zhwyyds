# 指标信息规范表 · 视觉规范

> 与用户提供的 **Excel 指标卡片参考图** 对齐，勿改为圆角/渐变/SaaS 风。

## 预览

```bash
data-governance serve --port 8765
# http://127.0.0.1:8765/ui/metric-spec-template.html
```

## 色板（与 `css/metric-spec.css` 一致）

| 区域 | 色值 |
|------|------|
| 外框 / 网格线 | `#5B9BD5`（2px 外框 + 1px 单元格） |
| 分类标签格 | `#C00000` 白字 |
| 分类取值格 | `#FF0000` 白字 |
| 字段标签 | `#FCE4D6` 黑字 |
| 字段取值 | `#FFFFFF` 黑字 |
| 底衬 | `#E8E8E8` |

## 字段行（18 项）

一级分类、二级分类 → 指标名称/编号 → 计量单位/值类型 → 时间周期/统计维度 → 应用场景/指标负责单位 → 应用报表、指标描述、计算公式、分析方法、预警标准、精度、数据来源、技术口径。

## 为何曾「复现不了」

1. 样式曾写在 `index.html` 内且不完整，后又改成 Tailwind 式圆角/渐变，偏离参考图。  
2. 指标库外层仍叠 Mock 顶栏/AI/异议，第一眼不像「一张表」。  
3. 未先固定 `metric-spec-template.html` 再接数据，反复改方向。

**单一真相源**：`metric-spec-template.html` + `css/metric-spec.css` + `js/metric-spec.js`（同 DOM）。
