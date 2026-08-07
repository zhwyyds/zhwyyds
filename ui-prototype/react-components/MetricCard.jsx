/**
 * ============================================================================
 * MetricCard · 数据治理指标卡片组件（成品卡）
 * ============================================================================
 * 风格：TCG 集换式卡牌质感 × 企业级可读性
 *   卡牌质感：细装饰边框 + 双层描边 + 四角饰点 + 多层阴影 hover 抬升
 *   企业约束：无粒子特效 / 无炫丽渐变 / 业务信息优先 / WCAG AA 对比度
 *
 * 设计参数（产品确认）：
 *   DESIGN_VARIANCE = 5  —— 适度辨识度（TCG 元素克制存在，不喧宾夺主）
 *   MOTION_INTENSITY = 4 —— 中等动效（hover 抬升 / 下探弹窗 / 翻面，全部可降级）
 *   VISUAL_DENSITY   = 7  —— 高信息密度（卡面紧凑承载名称/中英文/口径/时间/角标/徽章）
 *
 * 产品隐喻（PRD 1.5）：指标 = 成品卡，主题域 = 卡库，评分 = 稀有度，口径 = 效果文字
 *
 * 技术栈：React 18 + Tailwind CSS（无第三方 UI 依赖）
 * 无障碍：语义 <button> / aria / focus-visible / Esc 关闭 / prefers-reduced-motion 降级
 * ============================================================================
 */

import { useEffect, useRef, useState } from "react";

/* ---------------------------------------------------------------------------
 * 常量与工具
 * ------------------------------------------------------------------------- */

/** 14 主题域角标配色 —— 深色底 + 白字，均为对比度 ≥ 4.5:1 的深色系 */
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
  approved: { label: "已审核", bg: "#1a7f37" }, // 白字对比 ≈ 4.9:1
  pending:  { label: "待审核", bg: "#8a5a00" }, // 白字对比 ≈ 5.1:1
  rejected: { label: "已打回", bg: "#a40e26" }, // 白字对比 ≈ 7.0:1
};

/** 异议标记（争议中）—— 深红描边 + 淡红底文字（非实色，避免与"已打回"撞视觉） */
const OBJECTION_STYLE = {
  border: "#a40e26",
  text: "#7a0c1c", // 对比 ≈ 9.5:1 on #fff
  bg: "#fff1f0",
};

/** 稀有度（评分 → 星级，PRD 3.6：≥90 优秀 / ≥75 良好 / ≥60 合格 / <60 待改进） */
function rarityOf(score) {
  if (score >= 90) return { stars: 4, label: "优秀" };
  if (score >= 75) return { stars: 3, label: "良好" };
  if (score >= 60) return { stars: 2, label: "合格" };
  return { stars: 1, label: "待改进" };
}

/** 展示时间（企业级：显式日期，不做"3 天前"模糊化） */
function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const CARD_TEXT = {
  title: "#1f2328", // 主文字，on #fff ≈ 16:1
  body: "#3d444d",  // 口径文字，≈ 11:1
  muted: "#57606a", // 英文名/时间，≈ 7.4:1
  faint: "#6e7781", // 辅助标注，≈ 5.4:1
};
const CARD_BORDER = "#d0d7de";

/* ---------------------------------------------------------------------------
 * 子组件
 * ------------------------------------------------------------------------- */

/** 卡面内容（网格/弹窗正面共用） */
function CardFace({ m, rarity, onFlip, flipped }) {
  const domain = DOMAIN_STYLES[m.domain_code] || DOMAIN_FALLBACK;
  const status = STATUS_STYLES[m.review_status] || STATUS_STYLES.pending;
  const hasObjection = Boolean(m.objection);

  return (
    <div className="relative flex h-full flex-col p-4">
      {/* 左上：业务域角标 */}
      <div
        className="absolute left-4 top-4 rounded-sm px-1.5 py-0.5 text-[11px] font-semibold tracking-wide"
        style={{ backgroundColor: domain.bg, color: "#ffffff" }}
      >
        {domain.label}
      </div>

      {/* 右上：状态徽章 + 异议标记 */}
      <div className="absolute right-4 top-4 flex items-center gap-1.5">
        {hasObjection && (
          <span
            className="rounded-sm border px-1.5 py-0.5 text-[10px] font-bold tracking-wide"
            style={{ borderColor: OBJECTION_STYLE.border, color: OBJECTION_STYLE.text, backgroundColor: OBJECTION_STYLE.bg }}
            title="存在异议，口径待复核"
          >
            异议
          </span>
        )}
        <span
          className="rounded-sm px-1.5 py-0.5 text-[10px] font-bold tracking-wide"
          style={{ backgroundColor: status.bg, color: "#ffffff" }}
        >
          {status.label}
        </span>
      </div>

      {/* 中部：稀有度（评分星级，克制的金色文字，不用发光效果） */}
      <div className="mt-6 flex items-center gap-1" aria-label={`质量等级：${rarity.label}`}>
        <span className="text-[11px] font-semibold" style={{ color: "#9a6700" }}>
          {"★".repeat(rarity.stars)}
          <span style={{ color: "#d4d9e0" }}>{"★".repeat(4 - rarity.stars)}</span>
        </span>
        <span className="text-[10px]" style={{ color: CARD_TEXT.faint }}>
          {rarity.label}
        </span>
      </div>

      {/* 指标名称 + 中英文 */}
      <h3
        className="mt-2 text-lg font-bold leading-snug"
        style={{ color: CARD_TEXT.title }}
      >
        {m.metric_cn || "—"}
      </h3>
      <p
        className="mt-0.5 font-mono text-[11px] tracking-wide"
        style={{ color: CARD_TEXT.muted }}
      >
        {m.metric_en || "pending_naming"} · {m.metric_id || ""}
      </p>

      {/* 口径摘要（3 行截断） */}
      <p
        className="mt-3 line-clamp-3 text-[12.5px] leading-relaxed"
        style={{ color: CARD_TEXT.body }}
        title={m.caliber_desc}
      >
        {m.caliber_desc || "暂无口径描述"}
      </p>

      {/* 底部：更新时间 + 翻面入口 */}
      <div className="mt-auto flex items-center justify-between border-t pt-2.5" style={{ borderColor: CARD_BORDER }}>
        <span className="text-[10.5px]" style={{ color: CARD_TEXT.faint }}>
          更新 {formatTime(m.updated_at)}
        </span>
        {onFlip && (
          <button
            type="button"
            onClick={onFlip}
            className="rounded-sm px-1.5 py-0.5 text-[10.5px] font-semibold outline-none transition-colors focus-visible:ring-2"
            style={{ color: "#0b4f6c", "--tw-ring-color": "#0969da" }}
          >
            {flipped ? "返回正面" : "查看完整口径 ↻"}
          </button>
        )}
      </div>
    </div>
  );
}

/** 卡背：完整口径（公式/粒度/边界/来源） */
function CardBack({ m, rarity, onFlip }) {
  const rows = [
    ["计算公式", m.formula_cn || m.formula || "—"],
    ["统计周期", m.frequency || "—"],
    ["计量单位", m.unit || "—"],
    ["统计维度", m.dimensions || "—"],
    ["数据来源", m.data_sources || m.source_table || "—"],
    ["负责人", m.owner || "—"],
  ];
  return (
    <div className="flex h-full flex-col p-4">
      <h4 className="text-sm font-bold" style={{ color: CARD_TEXT.title }}>
        {m.metric_cn} · 完整口径
      </h4>
      <dl className="mt-3 space-y-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex gap-2 text-[11.5px] leading-relaxed">
            <dt className="w-16 shrink-0 font-semibold" style={{ color: CARD_TEXT.faint }}>
              {k}
            </dt>
            <dd style={{ color: CARD_TEXT.body }}>{v}</dd>
          </div>
        ))}
        <div className="flex gap-2 text-[11.5px] leading-relaxed">
          <dt className="w-16 shrink-0 font-semibold" style={{ color: CARD_TEXT.faint }}>
            业务口径
          </dt>
          <dd style={{ color: CARD_TEXT.body }}>{m.caliber_desc || "—"}</dd>
        </div>
      </dl>
      <div className="mt-auto flex justify-end pt-3">
        <button
          type="button"
          onClick={onFlip}
          className="rounded-sm px-1.5 py-0.5 text-[10.5px] font-semibold outline-none focus-visible:ring-2"
          style={{ color: "#0b4f6c" }}
        >
          ↻ 返回正面
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 主组件：指标卡片（网格中的单卡）
 * ------------------------------------------------------------------------- */

/**
 * @param {{ metric: object }} props
 * metric: { metric_id, metric_cn, metric_en, domain_code, caliber_desc,
 *           formula, formula_cn, frequency, unit, dimensions, data_sources,
 *           source_table, owner, updated_at, review_status, objection, score }
 */
export function MetricCard({ metric, onOpen }) {
  const [hovered, setHovered] = useState(false);
  const rarity = rarityOf(metric.score);

  // TCG 质感：双层描边（白内圈 + 灰外圈）由多层 box-shadow 模拟，hover 时增强抬升
  const baseShadow = [
    "0 0 0 1px #ffffff",   // 内白描边（模拟卡牌白边）
    "0 0 0 2px " + CARD_BORDER, // 外灰描边
    "0 1px 2px rgba(31,35,40,0.10)",
  ].join(",");
  const hoverShadow = [
    "0 0 0 1px #ffffff",
    "0 0 0 2px #8c959f",
    "0 8px 16px rgba(31,35,40,0.16)",
    "0 16px 32px rgba(31,35,40,0.12)",
  ].join(",");

  return (
    <button
      type="button"
      onClick={() => onOpen && onOpen(metric)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label={`指标 ${metric.metric_cn || metric.metric_id || ""}，${DOMAIN_STYLES[metric.domain_code]?.label || "未知域"}，${STATUS_STYLES[metric.review_status]?.label || "待审核"}`}
      className={[
        "group relative w-full cursor-pointer rounded-lg bg-white text-left outline-none",
        "focus-visible:ring-2 focus-visible:ring-offset-2",
        // 动效强度 4/7：轻抬升 + 阴影增强，180ms 指数缓出（无粒子/无炫光）
        "transition-[transform,box-shadow] duration-180 ease-out",
        "motion-reduce:transition-none motion-reduce:hover:transform-none",
      ].join(" ")}
      style={{
        boxShadow: hovered ? hoverShadow : baseShadow,
        transform: hovered ? "translateY(-4px)" : "translateY(0)",
        // 四角饰点（TCG 质感：细装饰，纯色小方块）
        backgroundImage: "radial-gradient(circle at 8px 8px, " + CARD_BORDER + " 1.5px, transparent 1.5px), radial-gradient(circle at calc(100% - 8px) 8px, " + CARD_BORDER + " 1.5px, transparent 1.5px), radial-gradient(circle at 8px calc(100% - 8px), " + CARD_BORDER + " 1.5px, transparent 1.5px), radial-gradient(circle at calc(100% - 8px) calc(100% - 8px), " + CARD_BORDER + " 1.5px, transparent 1.5px)",
        backgroundPosition: "0 0, 100% 0, 0 100%, 100% 100%",
        backgroundRepeat: "no-repeat",
      }}
    >
      <CardFace m={metric} rarity={rarity} />
    </button>
  );
}

/* ---------------------------------------------------------------------------
 * 主组件：卡牌网格（CSS Grid 自适应）
 * ------------------------------------------------------------------------- */

/**
 * 布局：grid auto-fill + minmax(280px, 1fr)，窄屏自动降列，无需媒体查询断点
 */
export function MetricCardGrid({ metrics = [], onOpenCard }) {
  if (!metrics.length) {
    return (
      <div
        className="rounded-lg border border-dashed p-10 text-center text-sm"
        style={{ borderColor: CARD_BORDER, color: CARD_TEXT.muted }}
      >
        暂无指标（卡库为空）
      </div>
    );
  }
  return (
    <div
      role="list"
      aria-label="指标卡库"
      className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4"
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

/**
 * 交互：点击卡片 → 弹窗从卡片处"下探"落下（scale .96 → 1 + 下滑），
 *       弹窗内可 3D 翻面查看完整口径。
 * 无障碍：role=dialog / aria-modal / Esc 关闭 / 点击遮罩关闭 / 初始聚焦弹窗。
 */
export function MetricCardModal({ metric, onClose }) {
  const [flipped, setFlipped] = useState(false);
  const dialogRef = useRef(null);
  const rarity = rarityOf(metric?.score);

  // 焦点管理：打开时聚焦弹窗；Esc 关闭；prefers-reduced-motion 时关闭翻面动画
  useEffect(() => {
    const el = dialogRef.current;
    if (el) el.focus();
    const onKey = (e) => {
      if (e.key === "Escape") onClose && onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden"; // 锁定背景滚动
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  if (!metric) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[rgba(20,24,28,0.45)] p-4 pt-[8vh]"
      onClick={onClose}
      aria-label="关闭弹窗"
    >
      {/* 下探动画：drop-in（scale .96 + translateY -16px → 0，200ms ease-out） */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`指标 ${metric.metric_cn} 详情`}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-md rounded-xl bg-white outline-none [animation:drop-in_200ms_ease-out] motion-reduce:[animation:none]"
        style={{ boxShadow: "0 24px 64px rgba(20,24,28,0.35), 0 0 0 1px rgba(20,24,28,0.08)" }}
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

        {/* 关闭按钮（弹窗右上） */}
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭详情"
          className="absolute right-3 top-3 z-10 rounded-md px-2 py-1 text-sm font-bold outline-none focus-visible:ring-2"
          style={{ color: CARD_TEXT.muted }}
        >
          ✕
        </button>

        {/* 3D 翻面容器：正面 = 卡面信息；背面 = 完整口径 */}
        <div className="mc-flip-scene h-[320px]">
          <div className={`mc-flip-inner relative h-full w-full ${flipped ? "flipped" : ""}`}>
            <div className="mc-flip-face absolute inset-0">
              <CardFace m={metric} rarity={rarity} flipped={flipped} onFlip={() => setFlipped((v) => !v)} />
            </div>
            <div className="mc-flip-face mc-flip-back absolute inset-0">
              <CardBack m={metric} rarity={rarity} onFlip={() => setFlipped((v) => !v)} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 组合示例：网格 + 弹窗状态管理
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
