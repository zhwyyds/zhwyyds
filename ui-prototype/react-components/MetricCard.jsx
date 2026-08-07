/**
 * ============================================================================
 * MetricCard · 数据治理指标卡片（成品卡）—— Impeccable 方法论 × 炉石收藏风
 * ============================================================================
 * 设计语言（impeccable）：
 *   - 色彩：OKLCH 色板（冷调品牌色），中性色全部带色相倾向，避免死黑死白
 *   - 排版：模块化比例（major third 1.25），5 级字号大对比，深底行高 +0.1
 *   - 边框："铸造边框"系统 —— 内高光细线 + 稀有度主框 + 外缘暗影，角部饰点
 *   - 动效：ease-out-expo 缓动，状态变化动画，非交互态无光污染
 *
 * 炉石收藏风（用户）：
 *   - 稀有度宝石 ◆ + 名称栏 + 底部攻/血式角标（评分/版本）
 *   - 稀有度色阶：≥90 橙金（传说）/ ≥75 紫（史诗）/ ≥60 蓝（稀有）/ <60 银（普通）
 *
 * 对比度（WCAG AA，白字 on 深色卡面 12:1~4.6:1；稀有度角标深字 on 亮色 ≥4.5:1）
 * 产品隐喻（PRD 1.5）：指标=成品卡，主题域=卡库，评分=稀有度，口径=效果文字
 * 技术栈：React 18 + Tailwind CSS；无障碍：语义 button / aria / Esc / reduced-motion
 * ============================================================================
 */

import { useEffect, useRef, useState } from "react";

/* ---------------------------------------------------------------------------
 * 设计 Token —— OKLCH 色板（冷调品牌色：hue 265）
 * ------------------------------------------------------------------------- */

/** 卡面层级（深蓝调，非死黑） */
const SURFACE = {
  deep: "oklch(19% 0.022 265)", // 最深层（卡面底部）
  base: "oklch(23% 0.026 265)",  // 卡面主体
  rise: "oklch(28% 0.03 265)",   // 名称栏
  raise2: "oklch(33% 0.034 265)",// 角标/交互层
};

/** 文字（冷调中性，非纯白纯灰） */
const TEXT = {
  title: "oklch(97% 0.012 265)", // ≈12:1
  body: "oklch(88% 0.016 265)",  // ≈8.5:1
  muted: "oklch(77% 0.02 265)",  // ≈6:1
  faint: "oklch(66% 0.02 265)",  // ≈4.6:1
  onGem: "oklch(16% 0.02 265)",  // 稀有度角标上的深色数字
};

/** 稀有度色阶（OKLCH，深色变体保白字/深字对比） */
export function rarityOf(score) {
  if (score >= 90)
    return {
      stars: 4, label: "传说",
      gem: "oklch(72% 0.14 65)",     // 橙金
      gemDeep: "oklch(16% 0.02 265)",// 数字色
      edge: "oklch(78% 0.12 65)",    // 边框高光
      glow: "0 0 26px oklch(72% 0.14 65 / 0.40)",
    };
  if (score >= 75)
    return {
      stars: 3, label: "史诗",
      gem: "oklch(60% 0.19 305)",     // 紫
      gemDeep: "oklch(16% 0.02 265)",
      edge: "oklch(70% 0.15 305)",
      glow: "0 0 24px oklch(60% 0.19 305 / 0.38)",
    };
  if (score >= 60)
    return {
      stars: 2, label: "稀有",
      gem: "oklch(62% 0.16 255)",     // 蓝
      gemDeep: "oklch(16% 0.02 265)",
      edge: "oklch(72% 0.12 255)",
      glow: "0 0 22px oklch(62% 0.16 255 / 0.34)",
    };
  return {
    stars: 1, label: "普通",
    gem: "oklch(74% 0.012 265)",     // 冷调银
    gemDeep: "oklch(16% 0.02 265)",
    edge: "oklch(82% 0.014 265)",
    glow: "0 0 16px oklch(74% 0.012 265 / 0.22)",
  };
}

/** 14 主题域角标（OKLCH 深色 + 白字 ≥4.5:1） */
export const DOMAIN_STYLES = {
  sale:  { label: "交易",   bg: "oklch(40% 0.09 245)" },
  mall:  { label: "商场",   bg: "oklch(42% 0.09 150)" },
  base:  { label: "基础",   bg: "oklch(42% 0.02 265)" },
  cont:  { label: "合同",   bg: "oklch(38% 0.07 55)" },
  cust:  { label: "消费者", bg: "oklch(40% 0.11 300)" },
  fin:   { label: "财务",   bg: "oklch(38% 0.11 25)" },
  fund:  { label: "资金",   bg: "oklch(40% 0.08 195)" },
  hr:    { label: "人资",   bg: "oklch(40% 0.08 70)" },
  mkt:   { label: "营销",   bg: "oklch(40% 0.11 330)" },
  prod:  { label: "商品",   bg: "oklch(40% 0.08 220)" },
  ptnr:  { label: "商户",   bg: "oklch(40% 0.1 280)" },
  shop:  { label: "店铺",   bg: "oklch(40% 0.08 260)" },
  traf:  { label: "流量",   bg: "oklch(40% 0.08 205)" },
  wk:    { label: "流程",   bg: "oklch(40% 0.07 95)" },
};
const DOMAIN_FALLBACK = { label: "未知域", bg: "oklch(42% 0.02 265)" };

/** 主题域图标（插画区中央徽章，炉石式卡面插画替代图） */
export const DOMAIN_ICONS = {
  sale: "📊", mall: "🏬", base: "📁", cont: "📄", cust: "👥",
  fin: "💰", fund: "💵", hr: "👤", mkt: "📢", prod: "📦",
  ptnr: "🤝", shop: "🏪", traf: "📈", wk: "⚙️",
};
const DOMAIN_ICON_FALLBACK = "📊";

/** 状态徽章（白字 ≥4.5:1） */
export const STATUS_STYLES = {
  approved: { label: "已审核", bg: "oklch(50% 0.13 150)" },
  pending:  { label: "待审核", bg: "oklch(52% 0.11 75)" },
  rejected: { label: "已打回", bg: "oklch(48% 0.19 25)" },
  draft:    { label: "草稿",   bg: "oklch(48% 0.03 265)" },
};

/** 异议标记（深色卡面上可读的淡红） */
const OBJECTION_STYLE = {
  border: "oklch(70% 0.13 25)",
  text: "oklch(86% 0.06 25)",
  bg: "oklch(30% 0.09 25 / 0.5)",
};

/** 模块化字号（major third 1.25 取整） */
const FS = {
  xs: "10.5px",   // 角标/标签
  sm: "12px",     // 辅助
  base: "13px",   // 正文（口径）
  lg: "16.5px",   // 卡名
  xl: "21px",     // 名称栏主字（弹窗）
};

export function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const typeLabels = { atomic: "原子", derived: "衍生", composite: "复合" };
const dataTypeLabels = { amt: "金额", cnt: "数量", pct: "比率", rate: "比率", ratio: "比率", avg: "均值", idx: "指数" };

/* ---------------------------------------------------------------------------
 * 子组件
 * ------------------------------------------------------------------------- */

/** 将稀有度 glow（box-shadow 格式）转为 drop-shadow filter 片段 */
function glowToDrop(rarity) {
  // rarity.glow 形如 "0 0 26px oklch(72% 0.14 65 / 0.40)" → drop-shadow(0 0 26px oklch(72% 0.14 65 / 0.40))
  return "drop-shadow(" + rarity.glow + ")";
}

/** 稀有度宝石（菱形 ◆） */
export function Gem({ color, size = 15 }) {  return (
    <span
      aria-hidden="true"
      className="inline-block shrink-0"
      style={{
        width: size,
        height: size,
        transform: "rotate(45deg)",
        background: `linear-gradient(135deg, ${color}, oklch(55% 0.08 265))`,
        border: "1px solid oklch(93% 0.015 265)",
        borderRadius: 3,
        boxShadow: `0 0 8px ${color}66`,
      }}
    />
  );
}

/** 卡面（正面 · 收藏展示态） */
export function CardFace({ m, rarity, onFlip, flipped }) {
  const domain = DOMAIN_STYLES[m.domain_code] || DOMAIN_FALLBACK;
  const status = STATUS_STYLES[m.review_status] || STATUS_STYLES.pending;
  const hasObjection = Boolean(m.objection_status && m.objection_status !== "none" && m.objection_status !== "") || Boolean(m.objection);

  const roots = String(m.root_ids || "")
    .split(/[;,]/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div
      className="relative flex h-full flex-col overflow-hidden"
      style={{
        // 实心卡面（不透明，纯 SURFACE 渐变，无半透明叠加）
        background: `linear-gradient(168deg, ${SURFACE.rise} 0%, ${SURFACE.base} 46%, ${SURFACE.deep} 100%)`,
      }}
    >
      {/* ── 金属雕花边框（内层 inset 装饰线 + 角部雕花）── */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          boxShadow: `inset 0 0 0 1px ${rarity.edge}66, inset 0 0 0 2px oklch(95% 0.01 265 / 0.06)`,
          background: [
            // 上边缘稀有度饰带
            `linear-gradient(90deg, transparent 6%, ${rarity.gem}55 22%, ${rarity.edge}88 50%, ${rarity.gem}55 78%, transparent 94%)`,
            // 下边缘稀有度饰带
            `linear-gradient(180deg, transparent 97%, ${rarity.gem}33 100%)`,
          ].join(", "),
          backgroundSize: "100% 3px, 100% 3px",
          backgroundPosition: "0 0, 0 calc(100% - 3px)",
          backgroundRepeat: "no-repeat",
        }}
      />
      {/* ── 四角铆钉（稀有度色，金属卡角细节）── */}
      {[
        "left-1.5 top-1.5",
        "right-1.5 top-1.5",
        "left-1.5 bottom-1.5",
        "right-1.5 bottom-1.5",
      ].map((pos) => (
        <span
          key={pos}
          aria-hidden="true"
          className={`absolute ${pos} h-[9px] w-[9px] rounded-full`}
          style={{
            background: `radial-gradient(circle at 35% 30%, ${rarity.edge}, ${rarity.gem})`,
            boxShadow: `0 0 6px ${rarity.gem}88, inset 0 0 0 1px oklch(95% 0.01 265 / 0.7)`,
          }}
        />
      ))}
      {/* ── 顶部名称栏（铸造顶栏 + 稀有度渐变底条）── */}
      <div
        className="relative flex items-center gap-2.5 px-3.5 pb-3 pt-3"
        style={{
          background: `linear-gradient(180deg, ${SURFACE.raise2}, ${SURFACE.rise})`,
          boxShadow: `inset 0 1px 0 oklch(95% 0.02 265 / 0.12), inset 0 -14px 20px -14px ${rarity.gem}`,
        }}
      >
        {/* 稀有度渐变底条（名称栏下缘，炉石顶栏装饰） */}
        <div
          className="absolute inset-x-0 bottom-0 h-[3px]"
          style={{
            background: `linear-gradient(90deg, transparent 0%, ${rarity.gem} 22%, ${rarity.edge} 50%, ${rarity.gem} 78%, transparent 100%)`,
            boxShadow: `0 1px 4px ${rarity.gem}88`,
          }}
        />
        <Gem color={rarity.gem} />
        <h3
          className="min-w-0 flex-1 truncate"
          style={{
            fontSize: FS.lg,
            fontWeight: 900,
            letterSpacing: "0.015em",
            lineHeight: 1.25,
            color: TEXT.title,
            textShadow: `0 1px 2px oklch(0% 0 0 / 0.55), 0 0 14px ${rarity.gem}66`,
          }}
        >
          {m.metric_cn || "—"}
        </h3>
        {/* 右上：异议 + 状态徽章 */}
        <div className="flex shrink-0 items-center gap-1">
          {hasObjection && (
            <span
              className="rounded-sm border px-1 py-0.5"
              style={{ fontSize: FS.xs, fontWeight: 700, borderColor: OBJECTION_STYLE.border, color: OBJECTION_STYLE.text, backgroundColor: OBJECTION_STYLE.bg }}
              title={m.objection_note || m.objection || "存在异议"}
            >
              异议
            </span>
          )}
          <span
            className="rounded-sm px-1.5 py-0.5"
            style={{ fontSize: FS.xs, fontWeight: 700, backgroundColor: status.bg, color: "oklch(98% 0.01 265)" }}
          >
            {status.label}
          </span>
        </div>
      </div>

      {/* ── 插画区（炉石式卡面插画窗口）── */}
      <div
        className="relative mx-3.5 mt-3 h-[118px] shrink-0 overflow-hidden rounded-[8px]"
        style={{
          background: `radial-gradient(120% 130% at 50% 0%, ${domain.bg} 0%, oklch(24% 0.03 265) 72%)`,
          boxShadow: `inset 0 0 0 1px oklch(95% 0.02 265 / 0.14), inset 0 0 26px ${rarity.gem}40`,
        }}
      >
        {/* 中央大图标（主题域徽章） */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ fontSize: 46, filter: "drop-shadow(0 6px 12px oklch(0% 0 0 / 0.55))", transform: "translateY(-4px)" }}
          aria-hidden="true"
        >
          {DOMAIN_ICONS[m.domain_code] || DOMAIN_ICON_FALLBACK}
        </div>
        {/* 稀有度光晕（中心柔光） */}
        <div className="absolute inset-0" style={{ background: `radial-gradient(55% 55% at 50% 62%, ${rarity.gem}40, transparent 72%)` }} />
        {/* 顶部高光 */}
        <div className="absolute inset-x-0 top-0 h-6" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.16), transparent)" }} />
        {/* 底部过渡到卡面 */}
        <div className="absolute inset-x-0 bottom-0 h-7" style={{ background: "linear-gradient(180deg, transparent, oklch(23% 0.026 265))" }} />
        {/* 左上：域角标（移到插画区） */}
        <div
          className="absolute left-1.5 top-1.5 rounded-[3px] px-1.5 py-0.5"
          style={{ fontSize: FS.xs, fontWeight: 700, letterSpacing: "0.08em", backgroundColor: "oklch(12% 0.02 265 / 0.6)", color: "oklch(97% 0.012 265)" }}
        >
          {domain.label}
        </div>
      </div>

      {/* ── 中部：英文名 + 构件 + 口径 ── */}
      <div className="relative flex flex-1 flex-col px-3.5 pt-3">
        <p className="" style={{ fontSize: FS.sm, fontWeight: 500, letterSpacing: "0.03em", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", color: TEXT.muted }}>
          {m.metric_en || "pending_naming"}
        </p>
        <p className="mt-0.5" style={{ fontSize: FS.xs, letterSpacing: "0.14em", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", color: TEXT.faint }}>
          {m.metric_id || ""} · {typeLabels[m.metric_type] || m.metric_type || "原子"}
          {dataTypeLabels[m.data_type] ? " · " + dataTypeLabels[m.data_type] : ""}
        </p>

        {/* 构件（词根）标签 */}
        <div className="mt-2.5 flex flex-wrap gap-1">
          {roots.length > 0 ? (
            roots.map((r) => (
              <span
                key={r}
                className="rounded-[3px] border px-1 py-px"
                style={{
                  fontSize: "9.5px",
                  fontWeight: 600,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  borderColor: "oklch(80% 0.02 265 / 0.28)",
                  color: TEXT.muted,
                  backgroundColor: "oklch(90% 0.02 265 / 0.06)",
                }}
                title="构成该指标的词根构件"
              >
                {r}
              </span>
            ))
          ) : (
            <span style={{ fontSize: FS.xs, color: TEXT.faint }}>无构件映射</span>
          )}
        </div>

        {/* 口径摘要（3 行截断，深底行高 +0.1） */}
        <p
          className="mt-2.5 line-clamp-3"
          style={{ fontSize: FS.base, lineHeight: 1.62, color: TEXT.body }}
          title={m.caliber_desc}
        >
          {m.caliber_desc || "暂无口径描述"}
        </p>
      </div>

      {/* ── 底部：攻/血式大数字角标 + 信息条 ── */}
      <div className="relative px-3.5 pb-3 pt-1.5">
        {/* 左下：质量评分（炉石式大数字角标 · 稀有度宝石底） */}
        <div
          className="absolute bottom-3 left-3.5 flex h-[52px] w-[52px] flex-col items-center justify-center"
          style={{
            background: `radial-gradient(circle at 34% 28%, color-mix(in oklch, ${rarity.gem} 85%, white 15%), ${rarity.gem})`,
            clipPath: "polygon(50% 0%, 96% 25%, 96% 75%, 50% 100%, 4% 75%, 4% 25%)",
            filter: `drop-shadow(0 2px 5px oklch(0% 0 0 / 0.45)) ${glowToDrop(rarity)}`,
          }}
          aria-label={`质量评分 ${m.score ?? "—"}，${rarity.label}`}
        >
          <span style={{ fontSize: "19px", fontWeight: 900, lineHeight: 1, color: rarity.gemDeep, textShadow: "0 1px 0 oklch(100% 0 0 / 0.35)" }}>
            {m.score ?? "—"}
          </span>
          <span className="mt-0.5" style={{ fontSize: "7.5px", fontWeight: 800, letterSpacing: "0.06em", color: rarity.gemDeep }}>
            {rarity.label}
          </span>
        </div>

        {/* 右下：版本号（六边形宝石底 · 大数字） */}
        <div
          className="absolute bottom-3 right-3.5 flex h-[52px] w-[52px] flex-col items-center justify-center"
          style={{
            background: `radial-gradient(circle at 34% 28%, ${SURFACE.raise2}, ${SURFACE.rise})`,
            clipPath: "polygon(50% 0%, 96% 25%, 96% 75%, 50% 100%, 4% 75%, 4% 25%)",
            filter: "drop-shadow(0 2px 5px oklch(0% 0 0 / 0.45))",
          }}
          aria-label={`版本 ${m.version || "—"}，${typeLabels[m.metric_type] || m.metric_type || "原子"}指标`}
        >
          <span style={{ fontSize: "17px", fontWeight: 900, lineHeight: 1, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", color: TEXT.title, textShadow: "0 1px 0 oklch(100% 0 0 / 0.2)" }}>
            {m.version || "—"}
          </span>
          <span className="mt-0.5" style={{ fontSize: "7.5px", fontWeight: 700, letterSpacing: "0.06em", color: TEXT.faint }}>
            {typeLabels[m.metric_type] || "原子"}
          </span>
        </div>

        {/* 信息条：星级 + 更新时间 + 翻面（右侧留角标空间） */}
        <div
          className="flex items-center gap-2 rounded-[4px] px-2 py-1.5"
          style={{ backgroundColor: "oklch(90% 0.02 265 / 0.05)", borderTop: `1px solid oklch(90% 0.02 265 / 0.08)`, paddingRight: 60 }}
        >
          <span style={{ fontSize: FS.xs, fontWeight: 700, color: rarity.edge }}>
            {"★".repeat(rarity.stars)}
            <span style={{ color: "oklch(90% 0.02 265 / 0.22)" }}>{"★".repeat(4 - rarity.stars)}</span>
          </span>
          <span className="ml-auto" style={{ fontSize: "10px", color: TEXT.faint }}>
            更新 {formatTime(m.updated_at || m.created_at)}
          </span>
          {onFlip && (
            <button
              type="button"
              onClick={onFlip}
              className="shrink-0 rounded-[3px] px-1 py-0.5 outline-none focus-visible:ring-2"
              style={{ fontSize: "10px", fontWeight: 600, color: "oklch(80% 0.09 250)", "--tw-ring-color": "oklch(70% 0.12 250)" }}
            >
              {flipped ? "返回正面" : "完整口径 ↻"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 卡背（阅读态）—— 全字段分组，编辑式排版
 * ------------------------------------------------------------------------- */

function FieldRow({ k, v, mono }) {
  return (
    <div className="flex gap-2.5" style={{ lineHeight: 1.55 }}>
      <dt className="w-20 shrink-0" style={{ fontSize: "10.5px", fontWeight: 700, letterSpacing: "0.04em", color: TEXT.faint }}>
        {k}
      </dt>
      <dd
        className={mono ? "break-all font-mono" : "break-words"}
        style={{ fontSize: FS.sm, color: TEXT.body }}
      >
        {v === undefined || v === null || v === "" ? "—" : v}
      </dd>
    </div>
  );
}

function FieldGroup({ index, title, icon, fields, open, onToggle }) {
  return (
    <section
      className="overflow-hidden rounded-[6px]"
      style={{ border: "1px solid oklch(90% 0.02 265 / 0.12)", background: "oklch(90% 0.02 265 / 0.03)" }}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-2 px-2.5 py-1.5 text-left outline-none focus-visible:ring-2"
      >
        <span
          className="flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px]"
          style={{ background: "oklch(90% 0.02 265 / 0.1)", color: "oklch(70% 0.12 250)", fontSize: "9px" }}
        >
          {icon}
        </span>
        <span style={{ fontSize: "10.5px", fontWeight: 800, letterSpacing: "0.1em", color: TEXT.muted }}>{title}</span>
        <span className="ml-auto" style={{ fontSize: "9px", color: TEXT.faint, transform: open ? "rotate(90deg)" : "none", transition: "transform 0.2s" }}>
          ▶
        </span>
      </button>
      {open && (
        <div className="border-t px-2.5 py-2" style={{ borderColor: "oklch(90% 0.02 265 / 0.1)" }}>
          <dl className="space-y-1.5">{fields}</dl>
        </div>
      )}
    </section>
  );
}

export function CardBack({ m, onFlip }) {
  const [open, setOpen] = useState(null); // 展开的分区（null=全收起，'01'=第一个）
  const groups = [
    {
      key: "01", title: "标识与归属", icon: "ID",
      fields: [
        <FieldRow key="id" k="指标ID" v={m.metric_id} mono />,
        <FieldRow key="en" k="英文名" v={m.metric_en} mono />,
        <FieldRow key="dom" k="主题域" v={`${m.domain_code}${m.category_l1 ? " · " + m.category_l1 : ""}`} />,
        <FieldRow key="type" k="类型" v={typeLabels[m.metric_type] || m.metric_type} />,
        <FieldRow key="dtype" k="数据类型" v={m.data_type} />,
        <FieldRow key="roots" k="构件" v={m.root_ids} mono />,
        <FieldRow key="tree" k="树节点" v={m.tree_node_id} mono />,
        <FieldRow key="c2" k="二级分类" v={m.category_l2} />,
      ],
    },
    {
      key: "02", title: "口径（完整）", icon: "口",
      fields: [
        <FieldRow key="cd" k="口径描述" v={m.caliber_desc} />,
        <FieldRow key="cb" k="业务口径" v={m.caliber_business} />,
        <FieldRow key="cf" k="口径公式" v={m.caliber_formula} />,
        <FieldRow key="cp" k="口径周期" v={m.caliber_period} />,
        <FieldRow key="cg" k="口径粒度" v={m.caliber_granularity} />,
        <FieldRow key="cbd" k="口径边界" v={m.caliber_boundary} />,
        <FieldRow key="cs" k="口径来源" v={m.caliber_source} />,
      ],
    },
    {
      key: "03", title: "公式与实现", icon: "Σ",
      fields: [
        <FieldRow key="fc" k="公式(中文)" v={m.formula_cn} />,
        <FieldRow key="f" k="公式(SQL)" v={m.formula} mono />,
        <FieldRow key="tc" k="技术口径" v={m.tech_caliber} mono />,
        <FieldRow key="st" k="物理表" v={m.source_table} mono />,
        <FieldRow key="ds" k="数据来源" v={m.data_sources} />,
      ],
    },
    {
      key: "04", title: "数值与属性", icon: "数",
      fields: [
        <FieldRow key="u" k="计量单位" v={m.unit} />,
        <FieldRow key="fq" k="统计周期" v={m.frequency} />,
        <FieldRow key="p" k="精度" v={m.precision} />,
        <FieldRow key="d" k="统计维度" v={m.dimensions} />,
        <FieldRow key="s" k="适用场景" v={m.scenario} />,
        <FieldRow key="r" k="关联报表" v={m.reports} />,
        <FieldRow key="am" k="分析方法" v={m.analysis_methods} />,
        <FieldRow key="ar" k="预警规则" v={m.alert_rules} />,
      ],
    },
    {
      key: "05", title: "治理与版本", icon: "管",
      fields: [
        <FieldRow key="rs" k="审核状态" v={m.review_status} />,
        <FieldRow key="sm" k="来源模型" v={m.source_model} />,
        <FieldRow key="os" k="异议状态" v={m.objection_status} />,
        <FieldRow key="on" k="异议说明" v={m.objection_note || m.objection} />,
        <FieldRow key="ow" k="负责人" v={m.owner} />,
        <FieldRow key="co" k="口径负责人" v={m.caliber_owner} />,
        <FieldRow key="cst" k="口径状态" v={m.caliber_status} />,
        <FieldRow key="ca" k="AI生成" v={m.caliber_ai_by} />,
        <FieldRow key="ccb" k="口径审核人" v={m.caliber_checked_by} />,
        <FieldRow key="cca" k="口径审核时间" v={m.caliber_checked_at} />,
        <FieldRow key="cr" k="口径驳回" v={m.caliber_reject_reason} />,
        <FieldRow key="ver" k="版本" v={m.version} mono />,
        <FieldRow key="vh" k="版本历史" v={m.version_history} mono />,
        <FieldRow key="or" k="下线原因" v={m.offline_reason} />,
        <FieldRow key="onn" k="下线备注" v={m.offline_note} />,
        <FieldRow key="ct" k="创建时间" v={m.created_at} mono />,
        <FieldRow key="ut" k="更新时间" v={m.updated_at} mono />,
      ],
    },
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden" style={{ background: `linear-gradient(168deg, ${SURFACE.rise}, ${SURFACE.base} 45%, ${SURFACE.deep})` }}>
      {/* 头部摘要：ID + 名称 + 英文 + 返回 */}
      <div className="flex items-center justify-between px-4 pb-2 pt-3.5">
        <div className="min-w-0">
          <h4 style={{ fontSize: FS.lg, fontWeight: 900, color: TEXT.title }}>{m.metric_cn} · 完整信息</h4>
          <p className="truncate" style={{ fontSize: "10px", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", letterSpacing: "0.04em", color: TEXT.faint }}>
            {m.metric_id || ""}{m.metric_en ? " · " + m.metric_en : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={onFlip}
          className="shrink-0 rounded-[3px] px-1.5 py-0.5 outline-none focus-visible:ring-2"
          style={{ fontSize: "10.5px", fontWeight: 600, color: "oklch(80% 0.09 250)" }}
        >
          ↻ 返回正面
        </button>
      </div>

      {/* 分区折叠面板（参考指标库详情排版，适配卡背） */}
      <div className="flex flex-1 flex-col gap-1.5 overflow-y-auto px-2.5 pb-3">
        {groups.map((g) => (
          <FieldGroup
            key={g.key}
            index={g.key}
            title={g.title}
            icon={g.icon}
            fields={g.fields}
            open={open === g.key}
            onToggle={() => setOpen((k) => (k === g.key ? null : g.key))}
          />
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 主组件
 * ------------------------------------------------------------------------- */

/** 铸造边框系统（炉石多层嵌套框）：暗线 → 稀有度主框 → 白高光 → 稀有度内圈 → 外缘暗影 */
function frameShadow(rarity, hovered) {
  const layers = [
    `0 0 0 1px oklch(12% 0.015 265)`,                   // 最外暗线（托底）
    `0 0 0 2px ${hovered ? rarity.gem : rarity.edge}`,   // 稀有度主框（hover 亮起）
    `0 0 0 3px oklch(96% 0.01 265 / 0.9)`,               // 白高光细线（铸造感）
    `0 0 0 4px ${hovered ? rarity.gem : "oklch(40% 0.02 265)"}`, // 稀有度内圈
    hovered ? `0 16px 38px oklch(0% 0 0 / 0.55), ${rarity.glow}` : "0 6px 16px oklch(0% 0 0 / 0.45)",
  ];
  return layers.join(", ");
}

export function MetricCard({ metric, onOpen }) {
  const [hovered, setHovered] = useState(false);
  const rarity = rarityOf(metric.score);

  return (
    <button
      type="button"
      onClick={() => onOpen && onOpen(metric)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label={`指标 ${metric.metric_cn || metric.metric_id || ""}，${DOMAIN_STYLES[metric.domain_code]?.label || "未知域"}，${STATUS_STYLES[metric.review_status]?.label || "待审核"}，评分 ${metric.score ?? "—"}`}
      className={[
        "group relative w-full cursor-pointer rounded-[12px] text-left outline-none",
        "focus-visible:ring-2 focus-visible:ring-offset-2",
        // ease-out-expo 缓动，状态变化动画
        "transition-[transform,box-shadow,filter] duration-300",
        "motion-reduce:transition-none motion-reduce:hover:transform-none",
      ].join(" ")}
      style={{
        boxShadow: frameShadow(rarity, hovered),
        transform: hovered ? "translateY(-6px) scale(1.015)" : "translateY(0)",
        filter: hovered ? "brightness(1.08)" : "brightness(1)",
        transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <CardFace m={metric} rarity={rarity} />
    </button>
  );
}

export function MetricCardGrid({ metrics = [], onOpenCard }) {
  if (!metrics.length) {
    return (
      <div
        className="rounded-xl border border-dashed p-10 text-center"
        style={{ borderColor: "oklch(60% 0.03 265 / 0.3)", color: TEXT.muted, backgroundColor: SURFACE.deep }}
      >
        暂无指标（卡库为空）
      </div>
    );
  }
  return (
    <div role="list" aria-label="指标卡库" className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
      {metrics.map((m) => (
        <div key={m.metric_id || m.metric_cn} role="listitem">
          <MetricCard metric={m} onOpen={onOpenCard} />
        </div>
      ))}
    </div>
  );
}

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
      className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto p-4 pt-[7vh]"
      onClick={onClose}
      aria-label="关闭弹窗"
      style={{ backgroundColor: "oklch(8% 0.02 265 / 0.72)" }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`指标 ${metric.metric_cn} 详情`}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg rounded-2xl outline-none [animation:drop-in_220ms_cubic-bezier(0.16,1,0.3,1)] motion-reduce:[animation:none]"
        style={{ boxShadow: `0 30px 80px oklch(0% 0 0 / 0.6), 0 0 0 2px ${rarity.edge}, 0 0 0 3px oklch(12% 0.015 265)`, background: SURFACE.base }}
      >
        <style>{`
          @keyframes drop-in {
            from { transform: translateY(-18px) scale(0.96); opacity: 0; }
            to   { transform: translateY(0) scale(1); opacity: 1; }
          }
          .mc-flip-scene { perspective: 1200px; }
          .mc-flip-inner { transform-style: preserve-3d; transition: transform 550ms cubic-bezier(0.16, 1, 0.3, 1); }
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
          style={{ color: TEXT.muted }}
        >
          ✕
        </button>

        <div className="mc-flip-scene h-[480px]">
          <div className={`mc-flip-inner relative h-full w-full ${flipped ? "flipped" : ""}`}>
            <div className="mc-flip-face absolute inset-0 overflow-hidden rounded-2xl">
              <CardFace m={metric} rarity={rarity} flipped={flipped} onFlip={() => setFlipped((v) => !v)} />
            </div>
            <div className="mc-flip-face mc-flip-back absolute inset-0 overflow-hidden rounded-2xl">
              <CardBack m={metric} onFlip={() => setFlipped((v) => !v)} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

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
