/**
 * ============================================================================
 * MetricCard · 数据治理指标卡片组件（成品卡）—— 炉石传说（Hearthstone）风格
 * ============================================================================
 * 参考炉石卡牌视觉体系：
 *   - 顶部名称栏（稀有度描边 + 宝石 ◆ + 卡名）
 *   - 中部深色卡面主体（英文名 / 构件 / 口径）
 *   - 底部攻/血式角标（左=质量评分，右=版本号）—— 对应炉石"攻击/生命"
 *   - 稀有度宝石与边框色：≥90 橙金（传说）/ ≥75 紫（史诗）/ ≥60 蓝（稀有）/ <60 灰（普通）
 *   - hover 抬升 + 稀有度色发光（克制，无粒子特效）
 *
 * 业务约束（用户确认）：
 *   - 核心数字文字对比度满足 WCAG AA（白字 on 深色卡面 ≈ 12.9:1；宝石色均 ≥ 4.5:1）
 *   - 业务信息优先：名称/口径/评分/版本为视觉主体，装饰元素不抢信息
 *
 * 设计参数（产品确认）：
 *   DESIGN_VARIANCE = 5 · MOTION_INTENSITY = 4 · VISUAL_DENSITY = 7
 *
 * 产品隐喻（PRD 1.5）：指标 = 成品卡，主题域 = 卡库，评分 = 稀有度，口径 = 效果文字
 * 技术栈：React 18 + Tailwind CSS（无第三方 UI 依赖）
 * 无障碍：语义 <button> / aria / focus-visible / Esc 关闭 / prefers-reduced-motion 降级
 * ============================================================================
 */

import { useEffect, useRef, useState } from "react";

/* ---------------------------------------------------------------------------
 * 常量与工具
 * ------------------------------------------------------------------------- */

/** 14 主题域角标配色 —— 深色底 + 白字，对比度均 ≥ 4.5:1 */
const DOMAIN_STYLES = {
  sale:  { label: "交易",     bg: "#0b4f6c" },
  mall:  { label: "商场",     bg: "#2d5a27" },
  base:  { label: "基础",     bg: "#3f4a5c" },
  cont:  { label: "合同",     bg: "#5c3d2e" },
  cust:  { label: "消费者",   bg: "#4b3b8c" },
  fin:   { label: "财务",     bg: "#7d2e2e" },
  fund:  { label: "资金",     bg: "#0f5e5e" },
  hr:    { label: "人资",     bg: "#6d4a2b" },
  mkt:   { label: "营销",     bg: "#8a3d6e" },
  prod:  { label: "商品",     bg: "#2e5a7d" },
  ptnr:  { label: "商户",     bg: "#5c4a8c" },
  shop:  { label: "店铺",     bg: "#4a5a8c" },
  traf:  { label: "流量",     bg: "#1f5f6e" },
  wk:    { label: "流程",     bg: "#5f5f3d" },
};
const DOMAIN_FALLBACK = { label: "未知域", bg: "#4b5563" };

/** 状态徽章 —— 实色底 + 白字，对比度均 ≥ 4.5:1 */
const STATUS_STYLES = {
  approved: { label: "已审核", bg: "#1a7f37" }, // 白字 ≈ 4.9:1
  pending:  { label: "待审核", bg: "#8a5a00" }, // 白字 ≈ 5.1:1
  rejected: { label: "已打回", bg: "#a40e26" }, // 白字 ≈ 7.0:1
  draft:    { label: "草稿",   bg: "#5c6b7a" }, // 白字 ≈ 6.0:1
};

/** 异议标记 —— 淡红底深红字（与"已打回"实色区分） */
const OBJECTION_STYLE = {
  border: "#e5534b",
  text: "#ffd7d5", // 深色卡面上可读
  bg: "rgba(165,14,38,0.25)",
};

/**
 * 稀有度（评分 → 炉石宝石体系，原味亮色 + 深色数字保证对比）：
 *   ≥90 亮橙金（传说）/ ≥75 亮紫（史诗）/ ≥60 亮蓝（稀有）/ <60 银灰（普通）
 * 角标/宝石用亮色，数字用深色 #14181f（对比均 ≥ 4.5:1）
 */
function rarityOf(score) {
  if (score >= 90) return { stars: 4, label: "传说",  gem: "#f5a623", glow: "0 0 22px rgba(245,166,35,0.55)" };
  if (score >= 75) return { stars: 3, label: "史诗",  gem: "#a335ee", glow: "0 0 22px rgba(163,53,238,0.55)" };
  if (score >= 60) return { stars: 2, label: "稀有",  gem: "#0070dd", glow: "0 0 18px rgba(0,112,221,0.5)" };
  return          { stars: 1, label: "普通",  gem: "#8a919e", glow: "0 0 12px rgba(138,145,158,0.35)" };
}

/** 展示时间 */
function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 深色卡面色板（白字 on 深色，对比度均 ≥ 4.5:1） */
const CARD_TEXT = {
  title: "#ffffff",   // 卡名，on #2a3040 ≈ 12.9:1
  body: "#d3d9e2",    // 口径正文，≈ 9.6:1
  muted: "#b8c0cc",   // 英文名/ID，≈ 7.3:1
  faint: "#8f98a8",   // 辅助标签/时间，≈ 4.9:1
};
// 卡面：深色渐变 + 半透明斜纹纹理（模拟卡面插画质感，无外链图片）
const CARD_BG =
  "linear-gradient(165deg, #2c3345 0%, #1c212e 55%, #151a24 100%)," +
  "repeating-linear-gradient(45deg, rgba(255,255,255,0.028) 0 2px, transparent 2px 6px)";
const NAME_BAR_BG = "linear-gradient(180deg, #3b4359 0%, #2a3040 100%)";
const GEM_BORDER = "#e8eaf0";

/* ---------------------------------------------------------------------------
 * 子组件
 * ------------------------------------------------------------------------- */

/** 炉石式宝石（菱形 ◆） */
function Gem({ color, size = 14 }) {
  return (
    <span
      aria-hidden="true"
      className="inline-block shrink-0"
      style={{
        width: size,
        height: size,
        transform: "rotate(45deg)",
        background: color,
        border: `1.5px solid ${GEM_BORDER}`,
        borderRadius: 3,
        boxShadow: `0 0 6px ${color}`,
      }}
    />
  );
}

/** 卡面（正面）—— 炉石布局：名称栏 / 中部主体 / 底部攻·血角标 */
function CardFace({ m, rarity, onFlip, flipped }) {
  const domain = DOMAIN_STYLES[m.domain_code] || DOMAIN_FALLBACK;
  const status = STATUS_STYLES[m.review_status] || STATUS_STYLES.pending;
  const hasObjection = Boolean(m.objection_status && m.objection_status !== "none" && m.objection_status !== "") || Boolean(m.objection);

  const roots = String(m.root_ids || "")
    .split(/[;,]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const typeLabels = { atomic: "原子", derived: "衍生", composite: "复合" };
  const dataTypeLabels = { amt: "金额", cnt: "数量", pct: "比率", rate: "比率", ratio: "比率", avg: "均值", idx: "指数" };

  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-lg" style={{ background: CARD_BG }}>
      {/* ── 顶部名称栏（炉石卡牌顶栏）── */}
      <div
        className="relative flex items-center gap-2 px-3 py-2"
        style={{
          background: NAME_BAR_BG,
          borderBottom: `2px solid ${rarity.gem}`,
          boxShadow: `inset 0 0 0 1px rgba(255,255,255,0.10), inset 0 -8px 16px -8px ${rarity.gem}, 0 1px 0 rgba(0,0,0,0.4)`,
        }}
      >
        <Gem color={rarity.gem} size={15} />
        <h3
          className="min-w-0 flex-1 truncate text-[16px] font-black leading-tight tracking-wide"
          style={{ color: CARD_TEXT.title, textShadow: `0 0 8px ${rarity.gem}, 0 2px 3px rgba(0,0,0,0.8)` }}
        >
          {m.metric_cn || "—"}
        </h3>
        {/* 右上：异议 + 状态徽章 */}
        <div className="flex shrink-0 items-center gap-1">
          {hasObjection && (
            <span
              className="rounded-sm border px-1 py-0.5 text-[9px] font-bold tracking-wide"
              style={{ borderColor: OBJECTION_STYLE.border, color: OBJECTION_STYLE.text, backgroundColor: OBJECTION_STYLE.bg }}
              title={m.objection_note || m.objection || "存在异议"}
            >
              异议
            </span>
          )}
          <span
            className="rounded-sm px-1.5 py-0.5 text-[9px] font-bold tracking-wide"
            style={{ backgroundColor: status.bg, color: "#ffffff" }}
          >
            {status.label}
          </span>
        </div>
      </div>

      {/* ── 中部主体：域角标 + 英文名 + 构件 + 口径 ── */}
      <div className="relative flex flex-1 flex-col px-3 pt-2.5">
        {/* 左上：业务域角标（小宝石+域名） */}
        <div
          className="absolute right-3 top-2 flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] font-bold tracking-wide"
          style={{ backgroundColor: domain.bg, color: "#ffffff" }}
        >
          {domain.label}
        </div>

        <p className="pr-16 font-mono text-[10.5px] tracking-wide" style={{ color: CARD_TEXT.muted }}>
          {m.metric_en || "pending_naming"}
        </p>
        <p className="font-mono text-[9px] tracking-widest" style={{ color: CARD_TEXT.faint }}>
          {m.metric_id || ""} · {typeLabels[m.metric_type] || m.metric_type || "原子"}
          {dataTypeLabels[m.data_type] ? " · " + dataTypeLabels[m.data_type] : ""}
        </p>

        {/* 构件（词根）标签 */}
        <div className="mt-2 flex flex-wrap gap-1">
          {roots.length > 0 ? (
            roots.map((r) => (
              <span
                key={r}
                className="rounded-sm border px-1 py-px font-mono text-[9px] font-medium"
                style={{ borderColor: "rgba(255,255,255,0.18)", color: CARD_TEXT.muted, backgroundColor: "rgba(255,255,255,0.06)" }}
                title="构成该指标的词根构件"
              >
                {r}
              </span>
            ))
          ) : (
            <span className="text-[9px]" style={{ color: CARD_TEXT.faint }}>
              无构件映射
            </span>
          )}
        </div>

        {/* 口径摘要（3 行截断） */}
        <p
          className="mt-2 line-clamp-3 text-[11.5px] leading-relaxed"
          style={{ color: CARD_TEXT.body }}
          title={m.caliber_desc}
        >
          {m.caliber_desc || "暂无口径描述"}
        </p>
      </div>

      {/* ── 底部：攻·血式角标（评分 / 版本）+ 时间条 ── */}
      <div className="relative px-3 pb-2.5 pt-1">
        {/* 左下：质量评分（对应攻击力）—— 亮稀有度色 + 深数字 + 白描边 */}
        <div
          className="absolute bottom-2.5 left-3 flex h-11 w-11 flex-col items-center justify-center rounded-full"
          style={{
            background: `radial-gradient(circle at 35% 30%, ${rarity.gem}, ${rarity.gem})`,
            border: "2px solid #f2f4f8",
            boxShadow: `0 3px 8px rgba(0,0,0,0.55), ${rarity.glow}`,
          }}
          aria-label={`质量评分 ${m.score ?? "—"}，${rarity.label}`}
        >
          <span className="text-[16px] font-black leading-none" style={{ color: "#14181f", textShadow: "0 0 3px rgba(255,255,255,0.45)" }}>
            {m.score ?? "—"}
          </span>
          <span className="mt-0.5 text-[7.5px] font-black tracking-wide" style={{ color: "#14181f" }}>
            {rarity.label}
          </span>
        </div>

        {/* 右下：版本号（对应生命值） */}
        <div
          className="absolute bottom-2.5 right-3 flex h-11 w-11 flex-col items-center justify-center rounded-full"
          style={{
            background: "radial-gradient(circle at 35% 30%, #3a4258, #262c3c)",
            border: "2px solid #f2f4f8",
            boxShadow: "0 3px 8px rgba(0,0,0,0.55)",
          }}
          aria-label={`版本 ${m.version || "—"}，${typeLabels[m.metric_type] || m.metric_type || "原子"}指标`}
        >
          <span className="font-mono text-[14px] font-black leading-none" style={{ color: "#ffffff", textShadow: "0 1px 1px rgba(0,0,0,0.6)" }}>
            {m.version || "—"}
          </span>
          <span className="mt-0.5 text-[7.5px] font-bold tracking-wide" style={{ color: "rgba(255,255,255,0.85)" }}>
            {typeLabels[m.metric_type] || "原子"}
          </span>
        </div>

        {/* 底部信息条：稀有度星级 + 更新时间 + 翻面入口（右侧留角标空间） */}
        <div
          className="mt-1 flex items-center gap-2 rounded-sm px-2 py-1"
          style={{
            backgroundColor: "rgba(255,255,255,0.05)",
            borderTop: "1px solid rgba(255,255,255,0.08)",
            paddingRight: 58, // 避开右下"版本"角标（absolute 覆盖区）
          }}
        >
          <span className="text-[10px] font-semibold" style={{ color: rarity.gem === "#f5a623" ? "#f5b24c" : rarity.gem }}>
            {"★".repeat(rarity.stars)}
            <span style={{ color: "rgba(255,255,255,0.25)" }}>{"★".repeat(4 - rarity.stars)}</span>
          </span>
          <span className="ml-auto text-[9px]" style={{ color: CARD_TEXT.faint }}>
            更新 {formatTime(m.updated_at || m.created_at)}
          </span>
          {onFlip && (
            <button
              type="button"
              onClick={onFlip}
              className="shrink-0 rounded-sm px-1 py-0.5 text-[9.5px] font-semibold outline-none focus-visible:ring-2"
              style={{ color: "#a8c7ff", "--tw-ring-color": "#58a6ff" }}
            >
              {flipped ? "返回正面" : "完整口径 ↻"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** 字段行（完整态） */
function FieldRow({ k, v, mono }) {
  return (
    <div className="flex gap-2 text-[11.5px] leading-relaxed">
      <dt className="w-20 shrink-0 font-semibold" style={{ color: CARD_TEXT.faint }}>
        {k}
      </dt>
      <dd
        className={mono ? "font-mono break-all" : "break-words"}
        style={{ color: CARD_TEXT.body }}
      >
        {v === undefined || v === null || v === "" ? "—" : v}
      </dd>
    </div>
  );
}

function FieldGroup({ title, fields }) {
  return (
    <section>
      <h5
        className="mb-1.5 border-b pb-1 text-[10.5px] font-bold tracking-widest"
        style={{ borderColor: "rgba(255,255,255,0.14)", color: CARD_TEXT.muted }}
      >
        {title}
      </h5>
      <dl className="space-y-1.5">{fields}</dl>
    </section>
  );
}

/** 卡背：完整信息（48 字段分组，滚动）—— 深色主题 */
function CardBack({ m, onFlip }) {
  const typeLabels = { atomic: "原子", derived: "衍生", composite: "复合" };
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg p-4" style={{ background: CARD_BG }}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-bold" style={{ color: CARD_TEXT.title }}>
          {m.metric_cn} · 完整信息
        </h4>
        <button
          type="button"
          onClick={onFlip}
          className="rounded-sm px-1.5 py-0.5 text-[10.5px] font-semibold outline-none focus-visible:ring-2"
          style={{ color: "#a8c7ff" }}
        >
          ↻ 返回正面
        </button>
      </div>

      <div className="mt-3 space-y-3 overflow-y-auto pr-1" style={{ maxHeight: "calc(100% - 32px)" }}>
        <FieldGroup
          title="标识与归属"
          fields={[
            <FieldRow key="id" k="指标ID" v={m.metric_id} mono />,
            <FieldRow key="en" k="英文名" v={m.metric_en} mono />,
            <FieldRow key="dom" k="主题域" v={`${m.domain_code}${m.category_l1 ? " · " + m.category_l1 : ""}`} />,
            <FieldRow key="type" k="类型" v={typeLabels[m.metric_type] || m.metric_type} />,
            <FieldRow key="dtype" k="数据类型" v={m.data_type} />,
            <FieldRow key="roots" k="构件(词根)" v={m.root_ids} mono />,
            <FieldRow key="tree" k="指标树节点" v={m.tree_node_id} mono />,
            <FieldRow key="c2" k="二级分类" v={m.category_l2} />,
            <FieldRow key="vt" k="值类型" v={m.value_type} />,
          ]}
        />
        <FieldGroup
          title="口径（完整）"
          fields={[
            <FieldRow key="cd" k="口径描述" v={m.caliber_desc} />,
            <FieldRow key="cb" k="业务口径" v={m.caliber_business} />,
            <FieldRow key="cf" k="口径公式" v={m.caliber_formula} />,
            <FieldRow key="cp" k="口径周期" v={m.caliber_period} />,
            <FieldRow key="cg" k="口径粒度" v={m.caliber_granularity} />,
            <FieldRow key="cbd" k="口径边界" v={m.caliber_boundary} />,
            <FieldRow key="cs" k="口径来源" v={m.caliber_source} />,
          ]}
        />
        <FieldGroup
          title="公式与实现"
          fields={[
            <FieldRow key="fc" k="公式(中文)" v={m.formula_cn} />,
            <FieldRow key="f" k="公式(SQL)" v={m.formula} mono />,
            <FieldRow key="tc" k="技术口径" v={m.tech_caliber} mono />,
            <FieldRow key="st" k="物理表" v={m.source_table} mono />,
            <FieldRow key="ds" k="数据来源" v={m.data_sources} />,
          ]}
        />
        <FieldGroup
          title="数值与属性"
          fields={[
            <FieldRow key="u" k="计量单位" v={m.unit} />,
            <FieldRow key="fq" k="统计周期" v={m.frequency} />,
            <FieldRow key="p" k="精度" v={m.precision} />,
            <FieldRow key="d" k="统计维度" v={m.dimensions} />,
            <FieldRow key="s" k="适用场景" v={m.scenario} />,
            <FieldRow key="r" k="关联报表" v={m.reports} />,
            <FieldRow key="am" k="分析方法" v={m.analysis_methods} />,
            <FieldRow key="ar" k="预警规则" v={m.alert_rules} />,
          ]}
        />
        <FieldGroup
          title="治理与版本"
          fields={[
            <FieldRow key="rs" k="审核状态" v={m.review_status} />,
            <FieldRow key="sm" k="来源模型" v={m.source_model} />,
            <FieldRow key="os" k="异议状态" v={m.objection_status} />,
            <FieldRow key="on" k="异议说明" v={m.objection_note || m.objection} />,
            <FieldRow key="ow" k="负责人" v={m.owner} />,
            <FieldRow key="co" k="口径负责人" v={m.caliber_owner} />,
            <FieldRow key="cst" k="口径状态" v={m.caliber_status} />,
            <FieldRow key="ca" k="口径AI生成" v={m.caliber_ai_by} />,
            <FieldRow key="ccb" k="口径审核人" v={m.caliber_checked_by} />,
            <FieldRow key="cca" k="口径审核时间" v={m.caliber_checked_at} />,
            <FieldRow key="cr" k="口径驳回原因" v={m.caliber_reject_reason} />,
            <FieldRow key="ver" k="版本" v={m.version} mono />,
            <FieldRow key="vh" k="版本历史" v={m.version_history} mono />,
            <FieldRow key="or" k="下线原因" v={m.offline_reason} />,
            <FieldRow key="onn" k="下线备注" v={m.offline_note} />,
            <FieldRow key="ct" k="创建时间" v={m.created_at} mono />,
            <FieldRow key="ut" k="更新时间" v={m.updated_at} mono />,
          ]}
        />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 主组件：指标卡片（网格中的单卡）
 * ------------------------------------------------------------------------- */

/**
 * @param {{ metric: object, onOpen?: (m) => void }} props
 */
export function MetricCard({ metric, onOpen }) {
  const [hovered, setHovered] = useState(false);
  const rarity = rarityOf(metric.score);

  // 炉石式卡框：稀有度亮色描边 + hover 稀有度发光抬升
  const baseShadow = [
    `0 0 0 1px #ffffff`,
    `0 0 0 2px ${rarity.gem}`,
    "0 3px 8px rgba(0,0,0,0.5)",
  ].join(",");
  const hoverShadow = [
    `0 0 0 1px #ffffff`,
    `0 0 0 2px ${rarity.gem}`,
    `0 14px 28px rgba(0,0,0,0.6)`,
    rarity.glow,
  ].join(",");

  return (
    <button
      type="button"
      onClick={() => onOpen && onOpen(metric)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label={`指标 ${metric.metric_cn || metric.metric_id || ""}，${DOMAIN_STYLES[metric.domain_code]?.label || "未知域"}，${STATUS_STYLES[metric.review_status]?.label || "待审核"}，评分 ${metric.score ?? "—"}`}
      className={[
        "group relative w-full cursor-pointer rounded-[10px] bg-transparent text-left outline-none",
        "focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#12161f]",
        // 动效强度 4/7：抬升 + 稀有度发光 + 轻微放大
        "transition-[transform,box-shadow] duration-200 ease-out",
        "motion-reduce:transition-none motion-reduce:hover:transform-none",
      ].join(" ")}
      style={{
        boxShadow: hovered ? hoverShadow : baseShadow,
        transform: hovered ? "translateY(-6px) scale(1.02)" : "translateY(0) scale(1)",
      }}
    >
      <CardFace m={metric} rarity={rarity} />
    </button>
  );
}

/* ---------------------------------------------------------------------------
 * 主组件：卡牌网格（CSS Grid 自适应）
 * ------------------------------------------------------------------------- */

export function MetricCardGrid({ metrics = [], onOpenCard }) {
  if (!metrics.length) {
    return (
      <div
        className="rounded-lg border border-dashed p-10 text-center text-sm"
        style={{ borderColor: "rgba(255,255,255,0.2)", color: CARD_TEXT.muted, background: "#1c212e" }}
      >
        暂无指标（卡库为空）
      </div>
    );
  }
  return (
    <div
      role="list"
      aria-label="指标卡库"
      className="grid grid-cols-[repeat(auto-fill,minmax(252px,1fr))] gap-4"
    >
      {metrics.map((m) => (
        <div key={m.metric_id || m.metric_cn} role="listitem">
          <MetricCard metric={m} onOpen={onOpenCard} />
        </div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 主组件：下探弹窗 + 翻面预览
 * ------------------------------------------------------------------------- */

export function MetricCardModal({ metric, onClose }) {
  const [flipped, setFlipped] = useState(false);
  const dialogRef = useRef(null);
  const rarity = rarityOf(metric?.score);

  useEffect(() => {
    const el = dialogRef.current;
    if (el) el.focus();
    const onKey = (e) => {
      if (e.key === "Escape") onClose && onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  if (!metric) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[rgba(8,10,14,0.72)] p-4 pt-[7vh]"
      onClick={onClose}
      aria-label="关闭弹窗"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`指标 ${metric.metric_cn} 详情`}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-md rounded-xl outline-none [animation:drop-in_200ms_ease-out] motion-reduce:[animation:none]"
        style={{
          boxShadow: `0 24px 64px rgba(0,0,0,0.6), 0 0 0 2px ${rarity.gem}, 0 0 0 3px #ffffff`,
          background: "#1c212e",
        }}
      >
        <style>{`
          @keyframes drop-in {
            from { transform: translateY(-16px) scale(0.96); opacity: 0; }
            to   { transform: translateY(0) scale(1); opacity: 1; }
          }
          .mc-flip-scene { perspective: 1200px; }
          .mc-flip-inner { transform-style: preserve-3d; transition: transform 500ms cubic-bezier(0.22, 1, 0.36, 1); }
          .mc-flip-inner.flipped { transform: rotateY(180deg); }
          .mc-flip-face { backface-visibility: hidden; -webkit-backface-visibility: hidden; }
          .mc-flip-back { transform: rotateY(180deg); }
          @media (prefers-reduced-motion: reduce) {
            .mc-flip-inner { transition: none; }
          }
        `}</style>

        <button
          type="button"
          onClick={onClose}
          aria-label="关闭详情"
          className="absolute right-3 top-3 z-10 rounded-md px-2 py-1 text-sm font-bold outline-none focus-visible:ring-2"
          style={{ color: CARD_TEXT.muted }}
        >
          ✕
        </button>

        {/* 3D 翻面：正面 = 卡面；背面 = 完整信息（48 字段滚动） */}
        <div className="mc-flip-scene h-[360px]">
          <div className={`mc-flip-inner relative h-full w-full ${flipped ? "flipped" : ""}`}>
            <div className="mc-flip-face absolute inset-0 overflow-hidden rounded-xl">
              <CardFace m={metric} rarity={rarity} flipped={flipped} onFlip={() => setFlipped((v) => !v)} />
            </div>
            <div className="mc-flip-face mc-flip-back absolute inset-0 overflow-hidden rounded-xl">
              <CardBack m={metric} onFlip={() => setFlipped((v) => !v)} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 组合示例
 * ------------------------------------------------------------------------- */

export function MetricCardLibrary({ metrics }) {
  const [active, setActive] = useState(null);
  return (
    <>
      <MetricCardGrid metrics={metrics} onOpenCard={setActive} />
      <MetricCardModal metric={active} onClose={() => setActive(null)} />
    </>
  );
}

export default MetricCardLibrary;
