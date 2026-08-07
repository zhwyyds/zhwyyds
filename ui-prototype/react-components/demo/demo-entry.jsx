/**
 * MetricCard Demo 入口 —— 用示例数据渲染指标卡网格
 * 构建：esbuild --bundle
 */
import { createRoot } from "react-dom/client";
import MetricCardLibrary from "../MetricCard.jsx";

/** 示例数据：覆盖 5 域 × 4 评分档 × 3 状态 × 异议有无，展示全部卡面形态 */
const SAMPLE_METRICS = [
  {
    metric_id: "M_SALE_001",
    metric_cn: "月度销售额",
    metric_en: "monthly_sales_amount",
    domain_code: "sale",
    review_status: "approved",
    score: 92,
    updated_at: "2026-08-06 14:30",
    caliber_desc: "自然月内已完成订单的销售总金额（含税），剔除退货与作废订单；含线上与线下渠道。",
    formula_cn: "Σ(订单金额) − 退货金额",
    frequency: "月度",
    unit: "元",
    dimensions: "渠道、门店、品类",
    data_sources: "dwd_sale_order_df",
    owner: "数据组",
  },
  {
    metric_id: "M_CUST_007",
    metric_cn: "会员复购率",
    metric_en: "member_repurchase_rate",
    domain_code: "cust",
    review_status: "pending",
    score: 80,
    updated_at: "2026-08-05 09:12",
    caliber_desc: "统计周期内，有≥2次有效订单的会员数占全部有效会员数的比例；剔除内部员工与测试账号。",
    formula_cn: "复购会员数 ÷ 有效会员数",
    frequency: "月度",
    unit: "%",
    dimensions: "会员等级、渠道",
    data_sources: "dwd_cust_member_df",
    owner: "待认领",
    objection: "口径存在争议：复购窗口期未定义，建议明确为滚动 90 天。",
  },
  {
    metric_id: "M_FIN_003",
    metric_cn: "净利率",
    metric_en: "net_profit_margin",
    domain_code: "fin",
    review_status: "approved",
    score: 75,
    updated_at: "2026-08-04 17:45",
    caliber_desc: "净利润占营业收入的比例；净利润=营业收入−营业成本−税费−期间费用，不含营业外收支。",
    formula_cn: "净利润 ÷ 营业收入",
    frequency: "季度",
    unit: "%",
    dimensions: "业态、区域",
    data_sources: "dws_fin_income_statement",
    owner: "财务数据组",
  },
  {
    metric_id: "M_MALL_012",
    metric_cn: "客流量",
    metric_en: "visitor_count",
    domain_code: "mall",
    review_status: "rejected",
    score: 45,
    updated_at: "2026-08-03 11:20",
    caliber_desc: "统计周期内进入商场范围的去重客流数；口径待定（出入口统计口径与画像口径存在冲突）。",
    formula_cn: "—",
    frequency: "日度",
    unit: "人次",
    dimensions: "入口、楼层",
    data_sources: "ods_mall_traffic",
    owner: "待认领",
    objection: "客流去重逻辑未定义：按天去重还是按入场会话去重，需业务确认。",
  },
  {
    metric_id: "M_HR_021",
    metric_cn: "员工离职率",
    metric_en: "employee_turnover_rate",
    domain_code: "hr",
    review_status: "pending",
    score: 62,
    updated_at: "2026-08-02 16:08",
    caliber_desc: "统计周期内离职人数占期初在册人数的比例；含主动离职与被动辞退，不含转岗与退休。",
    formula_cn: "离职人数 ÷ 期初在册人数",
    frequency: "月度",
    unit: "%",
    dimensions: "部门、职级",
    data_sources: "dwd_hr_employee_df",
    owner: "人力数据组",
  },
  {
    metric_id: "M_MKT_005",
    metric_cn: "活动参与人数",
    metric_en: "campaign_participants",
    domain_code: "mkt",
    review_status: "approved",
    score: 88,
    updated_at: "2026-07-30 10:00",
    caliber_desc: "统计周期内报名且实际参与活动的去重用户数；含线上报名线下到店，不含仅浏览未报名用户。",
    formula_cn: "COUNT(DISTINCT user_id)",
    frequency: "活动周期",
    unit: "人",
    dimensions: "活动类型、渠道",
    data_sources: "dwd_mkt_campaign_df",
    owner: "营销数据组",
  },
];

function App() {
  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 4px" }}>指标卡 · TCG 质感 × 企业可读性</h1>
        <p style={{ fontSize: 12.5, color: "#57606a", margin: 0 }}>
          设计参数：DESIGN_VARIANCE=5 / MOTION_INTENSITY=4 / VISUAL_DENSITY=7 · 点击卡片查看完整口径（可翻面）
        </p>
      </header>
      <MetricCardLibrary metrics={SAMPLE_METRICS} />
      <footer style={{ marginTop: 20, fontSize: 11.5, color: "#6e7781" }}>
        组件：MetricCard.jsx（React + Tailwind）· 无障碍：WCAG AA · 无粒子特效 / 无炫丽渐变
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
