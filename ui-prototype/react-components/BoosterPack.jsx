/**
 * ============================================================================
 * BoosterPack · 炉石式卡包开包 + 手牌堆叠（评审包 / 卡库开包）
 * ============================================================================
 * 参考炉石开包体验：
 *   1. 卡包（蓝紫包裹 + 封印）→ hover 浮动 → 点击进入晃动（shake）
 *   2. 卡包爆开（光爆）→ 卡牌背面朝上逐张飞入手牌位（重叠堆叠）
 *   3. 逐张翻面揭示：稀有度越高光效越强（紫/橙金有光晕扫过）
 *   4. 揭示完成后形成"手牌"扇形堆叠：hover 单卡上浮放大抽出，点击查看详情
 *
 * 大气原则（用户："不要这么小气"）：卡片 280×392（炉石卡牌比例），舞台居中宽敞
 * 业务隐喻（PRD 1.5）：卡包 = 批量导入评审包 / 卡库；指标 = 成品卡；评分 = 稀有度
 * 无障碍：卡片为 <button> + aria；Esc 关闭弹窗；prefers-reduced-motion 降级动画
 * ============================================================================
 */

import { useEffect, useRef, useState } from "react";
import { MetricCardModal, CardFace, Gem, rarityOf, DOMAIN_STYLES, STATUS_STYLES, formatTime } from "./MetricCard.jsx";

// 炉石实体卡比例 ≈ 1:1.4，放大到 320×448（大气）
const CARD_W = 320;
const CARD_H = 448;

/** 卡包配色（按主题域） */
const PACK_COLORS = {
  default: { from: "#4b3b8c", to: "#241c4d", seal: "#c9b458" },
  sale:    { from: "#0f5e8c", to: "#0a2e4a", seal: "#58a6c9" },
  fin:     { from: "#8c3b3b", to: "#4a1515", seal: "#c9a058" },
  cust:    { from: "#5c3b8c", to: "#2a1a4a", seal: "#b458c9" },
  hr:      { from: "#8c6b3b", to: "#4a2e15", seal: "#c9c958" },
};

function pickPackColor(domain) {
  return PACK_COLORS[domain] || PACK_COLORS.default;
}

/* ---------------------------------------------------------------------------
 * 卡背（未揭示状态）：深色 + 稀有度宝石（炉石翻牌感）
 * ------------------------------------------------------------------------- */
function CardBackCover({ rarity, gem }) {
  return (
    <div
      className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-lg"
      style={{
        background: "radial-gradient(circle at 50% 40%, #2a3040, #12161f 75%)",
        boxShadow: `inset 0 0 0 2px ${gem}, inset 0 0 0 3px #ffffff`,
      }}
    >
      <Gem size={34} />
      <span
        className="absolute bottom-3 text-[9px] font-bold tracking-[0.3em]"
        style={{ color: "#8f98a8" }}
      >
        数据治理 · 指标卡
      </span>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 卡包组件
 * ------------------------------------------------------------------------- */
export function BoosterPack({ title, sub, domain, packSize = 5, onOpen, disabled }) {
  const [state, setState] = useState("idle"); // idle | shaking | burst | gone
  const colors = pickPackColor(domain);

  const handleClick = () => {
    if (disabled || state !== "idle") return;
    setState("shaking");
    setTimeout(() => {
      setState("burst");
      setTimeout(() => {
        setState("gone");
        onOpen && onOpen();
      }, 380);
    }, 850);
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        role="button"
        tabIndex={0}
        aria-label={`开 ${title} 卡包`}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleClick();
          }
        }}
        className={[
          "relative cursor-pointer select-none outline-none focus-visible:ring-2",
          "transition-transform duration-300 motion-reduce:transition-none",
          state === "gone" ? "pointer-events-none opacity-0 scale-0" : "",
        ].join(" ")}
        style={{
          width: 208,
          height: 288,
          transform: state === "idle" ? "translateY(0)" : undefined,
        }}
      >
        {/* 包体：蓝紫渐变 + 系带 + 中央封印 */}
        <div
          className="absolute inset-0 rounded-xl"
          style={{
            background: `linear-gradient(160deg, ${colors.from}, ${colors.to})`,
            boxShadow:
              "0 18px 40px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.14), inset 0 2px 0 rgba(255,255,255,0.22)",
            animation: state === "shaking" ? "pack-shake 0.14s linear infinite" : "pack-float 3.2s ease-in-out infinite",
          }}
        >
          {/* 顶部系带 */}
          <div
            className="absolute inset-x-0 top-3 h-4"
            style={{ background: "rgba(0,0,0,0.28)", boxShadow: "inset 0 1px 3px rgba(0,0,0,0.6)" }}
          />
          {/* 中央封印（菱形） */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              style={{
                width: 78,
                height: 78,
                transform: "rotate(45deg)",
                background: `radial-gradient(circle at 35% 30%, ${colors.seal}, #7a5c1e)`,
                border: "3px solid #f0e6c8",
                boxShadow: `0 0 30px ${colors.seal}`,
              }}
            />
            <span
              className="absolute text-[15px] font-black tracking-widest"
              style={{ color: "#f7efd6", textShadow: "0 1px 2px rgba(0,0,0,0.7)" }}
            >
              DG
            </span>
          </div>
          {/* 爆开光效 */}
          {state === "burst" && (
            <div
              className="absolute inset-0 rounded-xl"
              style={{
                animation: "pack-burst 0.4s ease-out forwards",
                background: "radial-gradient(circle, rgba(255,255,255,0.95), rgba(255,255,255,0) 65%)",
              }}
            />
          )}
        </div>
      </div>

      <div className="text-center">
        <div className="text-[15px] font-extrabold" style={{ color: "#ffffff" }}>
          {title}
        </div>
        <div className="text-[11px]" style={{ color: "#8f98a8" }}>
          {sub || "点击开包"}
        </div>
      </div>

      <style>{`
        @keyframes pack-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes pack-shake {
          0%, 100% { transform: rotate(0); }
          25% { transform: rotate(-4deg); }
          75% { transform: rotate(4deg); }
        }
        @keyframes pack-burst {
          0% { transform: scale(0.6); opacity: 0; }
          40% { transform: scale(1.6); opacity: 1; }
          100% { transform: scale(2.4); opacity: 0; }
        }
        @media (prefers-reduced-motion: reduce) {
          @keyframes pack-float { 0%, 100% { transform: none; } }
          @keyframes pack-shake { 0%, 100% { transform: none; } }
        }
      `}</style>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 手牌：扇形堆叠（炉石手牌）—— 重叠排开，hover 上浮放大抽出
 * ------------------------------------------------------------------------- */
export function HandFan({ cards, onSelect }) {
  const [spread, setSpread] = useState(false);
  const n = cards.length;
  if (!n) return null;

  return (
    <div
      role="list"
      aria-label="开出的指标卡手牌"
      onMouseEnter={() => setSpread(true)}
      onMouseLeave={() => setSpread(false)}
      className="flex items-end justify-center overflow-x-auto pt-20 pb-4"
      style={{ minHeight: CARD_H + 90 }}
    >
      {cards.map((c, i) => {
        const r = rarityOf(c.score);
        return (
          <div
            key={c.metric_id || c.metric_cn}
            role="listitem"
            className="card-slot shrink-0"
            style={{
              marginLeft: i === 0 ? 0 : spread ? -24 : -240,
              zIndex: i,
              transition: "margin 0.32s cubic-bezier(0.22,1,0.36,1)",
            }}
          >
            <button
              type="button"
              onClick={() => onSelect && onSelect(c)}
              aria-label={`指标 ${c.metric_cn}，稀有度 ${r.label}，评分 ${c.score ?? "—"}`}
              className="card-item relative cursor-pointer rounded-[10px] bg-transparent p-0 outline-none focus-visible:ring-2"
              style={{ width: CARD_W, height: CARD_H, transition: "transform 0.25s cubic-bezier(0.22,1,0.36,1)" }}
            >
              {c.__revealed ? (
                <div className="h-full w-full overflow-hidden rounded-lg" style={{ boxShadow: `0 0 0 2px ${r.gem}, 0 0 0 3px #fff, 0 16px 32px rgba(0,0,0,0.5), ${r.glow}` }}>
                  <CardFace m={c} rarity={r} />
                </div>
              ) : (
                <div className="h-full w-full" style={{ boxShadow: `0 16px 32px rgba(0,0,0,0.5)` }}>
                  <CardBackCover rarity={r} gem={r.gem} />
                </div>
              )}
            </button>
          </div>
        );
      })}

      <style>{`
        /* peek：平时叠紧（露 80px），hover 原位弹出放大，内容清晰可读 */
        .card-item:hover {
          transform: translateY(-46px) scale(1.28) !important;
          z-index: 99;
        }
        .card-slot:hover { z-index: 50; position: relative; }
        @media (prefers-reduced-motion: reduce) {
          .card-item, .card-slot { transition: none; }
          .card-item:hover { transform: translateY(-14px) scale(1.12) !important; }
        }
      `}</style>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 卡册网格卡（一包 30 张的展示形态）—— 每张完全可见，hover 浮起放大
 * ------------------------------------------------------------------------- */
export function CardGridCard({ m, revealed, onSelect }) {
  const [hovered, setHovered] = useState(false);
  const r = rarityOf(m.score);
  const domain = DOMAIN_STYLES[m.domain_code] || { label: "未知域" };
  const status = STATUS_STYLES[m.review_status] || { label: "待审核", bg: "oklch(52% 0.11 75)" };
  const hasObjection = Boolean(m.objection_status && m.objection_status !== "none") || Boolean(m.objection);

  return (
    <button
      type="button"
      onClick={() => onSelect && onSelect(m)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label={`指标 ${m.metric_cn}，稀有度 ${r.label}，评分 ${m.score ?? "—"}`}
      className="relative w-full cursor-pointer rounded-[10px] p-0 text-left outline-none focus-visible:ring-2"
      style={{
        aspectRatio: "320 / 448",
        boxShadow: hovered
          ? `0 0 0 1px ${r.edge}, 0 0 0 2px oklch(12% 0.015 265), 0 16px 36px oklch(0% 0 0 / 0.55), ${r.glow}`
          : `0 0 0 1px ${r.edge}, 0 0 0 2px oklch(12% 0.015 265), 0 5px 14px oklch(0% 0 0 / 0.45)`,
        transform: hovered ? "translateY(-8px) scale(1.14)" : "translateY(0) scale(1)",
        transition: "transform 0.28s cubic-bezier(0.16,1,0.3,1), box-shadow 0.28s cubic-bezier(0.16,1,0.3,1)",
      }}
    >
      {!revealed ? (
        // 未揭示：卡背（深色 + 稀有度宝石）
        <div
          className="flex h-full w-full items-center justify-center overflow-hidden rounded-[10px]"
          style={{ background: "radial-gradient(circle at 50% 40%, oklch(28% 0.03 265), oklch(16% 0.02 265) 75%)" }}
        >
          <Gem color={r.gem} size={22} />
        </div>
      ) : (
        // 已揭示：精简卡面
        <div
          className="flex h-full w-full flex-col overflow-hidden rounded-[10px] p-2.5"
          style={{
            background: `linear-gradient(168deg, oklch(28% 0.03 265) 0%, oklch(23% 0.026 265) 46%, oklch(19% 0.022 265) 100%)`,
            boxShadow: `inset 0 0 0 1px oklch(95% 0.02 265 / 0.08)`,
          }}
        >
          {/* 顶部：宝石 + 名称 + 状态 */}
          <div className="flex items-center gap-1.5">
            <Gem color={r.gem} size={12} />
            <span className="min-w-0 flex-1 truncate" style={{ fontSize: "12.5px", fontWeight: 900, color: "oklch(97% 0.012 265)" }}>
              {m.metric_cn || "—"}
            </span>
            {hasObjection && (
              <span className="rounded-[3px] border px-0.5 text-[8px] font-bold" style={{ borderColor: "oklch(70% 0.13 25)", color: "oklch(86% 0.06 25)" }}>
                异议
              </span>
            )}
            <span className="rounded-[3px] px-1 text-[8px] font-bold" style={{ backgroundColor: status.bg, color: "oklch(98% 0.01 265)" }}>
              {status.label}
            </span>
          </div>

          {/* 英文 + 域 */}
          <p className="mt-1 truncate" style={{ fontSize: "9px", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", letterSpacing: "0.04em", color: "oklch(77% 0.02 265)" }}>
            {m.metric_en || "pending_naming"}
          </p>
          <p className="text-[8.5px]" style={{ color: "oklch(66% 0.02 265)" }}>
            {domain.label} · {m.metric_type === "derived" ? "衍生" : m.metric_type === "composite" ? "复合" : "原子"}
          </p>

          {/* 口径摘要 2 行 */}
          <p className="mt-1.5 line-clamp-2" style={{ fontSize: "10px", lineHeight: 1.5, color: "oklch(88% 0.016 265)" }}>
            {m.caliber_desc || "暂无口径"}
          </p>

          {/* 底部：评分角标 + 更新时间 */}
          <div className="mt-auto flex items-end justify-between pt-1">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-full"
              style={{ background: r.gem, border: "1.5px solid oklch(94% 0.015 265)", boxShadow: `0 2px 6px oklch(0% 0 0 / 0.5), ${r.glow}` }}
              aria-label={`评分 ${m.score ?? "—"}，${r.label}`}
            >
              <span style={{ fontSize: "11px", fontWeight: 900, color: "oklch(16% 0.02 265)" }}>
                {m.score ?? "—"}
              </span>
            </div>
            <span style={{ fontSize: "8px", color: "oklch(66% 0.02 265)" }}>
              {formatTime(m.updated_at || m.created_at)}
            </span>
          </div>
        </div>
      )}
    </button>
  );
}

/** 卡册网格：30 张紧凑排列，hover 浮起放大，点击弹窗 */
export function CardGrid({ cards, revealedAll, onSelect }) {
  if (!cards.length) return null;
  return (
    <div role="list" aria-label="指标卡册" className="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-3">
      {cards.map((c, i) => (
        <div key={c.metric_id || c.metric_cn} role="listitem">
          <CardGridCard m={c} revealed={revealedAll ? true : c.__revealed} onSelect={onSelect} />
        </div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 开包流程编排：卡包 → 卡飞出（背面）→ 逐张翻面揭示 → 手牌
 * ------------------------------------------------------------------------- */
export function BoosterPackOpener({ pack, cards }) {
  const [phase, setPhase] = useState("fly"); // fly(卡片入场) | reveal(逐张翻面) | done
  const [deck, setDeck] = useState([]);      // 网格状态（含 __revealed 标记）
  const [selected, setSelected] = useState(null);
  const timers = useRef([]);

  // 挂载即开包：按稀有度排序（高的最后揭示，像炉石）→ 逐张翻面揭示
  // 30 张节奏：入场 400ms 后每 110ms 揭示 1 张（约 3.7s 完成）
  useEffect(() => {
    const sorted = [...cards].sort((a, b) => (b.score || 0) - (a.score || 0));
    setDeck(sorted.map((c) => ({ ...c, __revealed: false })));

    const revealAt = 400 + sorted.length * 60;
    sorted.forEach((_, i) => {
      timers.current.push(
        setTimeout(() => {
          setDeck((prev) => prev.map((c, ci) => (ci === i ? { ...c, __revealed: true } : c)));
          if (i === sorted.length - 1) setPhase("done");
        }, revealAt + i * 110)
      );
    });
    return () => timers.current.forEach(clearTimeout);
  }, [cards]);

  return (
    <div className="w-full">
      <div className="mb-3 text-center text-[12px]" style={{ color: "#8f98a8" }}>
        {phase === "fly"
          ? `开包中 · ${pack.title}…`
          : phase === "reveal"
          ? "揭示中…"
          : `开包完成 · ${deck.length} 张指标卡（hover 浮起放大，点击查看完整信息）`}
      </div>
      <CardGrid cards={deck} revealedAll={phase === "done"} onSelect={setSelected} />
      <MetricCardModal metric={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Demo 编排：卡库选择 → 开包 → 手牌
 * ------------------------------------------------------------------------- */
export function BoosterPackDemo({ metrics, packs }) {
  const [activePack, setActivePack] = useState(null);
  const packsList = packs && packs.length ? packs : [{ id: "all", title: "指标卡库", sub: "全部指标", domain: "default", filter: () => true }];

  const handlePick = (p) => {
    const list = metrics.filter(p.filter).sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, p.max || 5);
    setActivePack({ ...p, cards: list });
  };

  if (activePack) {
    return <BoosterPackOpener pack={activePack} cards={activePack.cards} />;
  }

  return (
    <div>
      <h2 className="mb-1 text-[18px] font-black" style={{ color: "#ffffff" }}>
        选择卡包开包
      </h2>
      <p className="mb-6 text-[12.5px]" style={{ color: "#8f98a8" }}>
        参考炉石 · 一包 5 张 · 稀有度越高越晚揭示（评分 = 稀有度）
      </p>
      <div className="flex flex-wrap justify-center gap-10 py-6">
        {packsList.map((p) => (
          <BoosterPack key={p.id} title={p.title} sub={p.sub} domain={p.domain} onOpen={() => handlePick(p)} />
        ))}
      </div>
    </div>
  );
}

export default BoosterPackDemo;
