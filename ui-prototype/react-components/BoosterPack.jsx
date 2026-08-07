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
import { MetricCardModal, CardFace, Gem, rarityOf } from "./MetricCard.jsx";

const CARD_W = 280;
const CARD_H = 392;

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
          width: 168,
          height: 232,
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
                width: 64,
                height: 64,
                transform: "rotate(45deg)",
                background: `radial-gradient(circle at 35% 30%, ${colors.seal}, #7a5c1e)`,
                border: "3px solid #f0e6c8",
                boxShadow: `0 0 24px ${colors.seal}`,
              }}
            />
            <span
              className="absolute text-[13px] font-black tracking-widest"
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
      className="flex items-end justify-center overflow-x-auto pb-4 pt-8"
      style={{ minHeight: CARD_H + 70 }}
    >
      {cards.map((c, i) => {
        const r = rarityOf(c.score);
        return (
          <div
            key={c.metric_id || c.metric_cn}
            role="listitem"
            className="card-slot shrink-0"
            style={{
              marginLeft: i === 0 ? 0 : spread ? -56 : -168,
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
        .card-item:hover {
          transform: translateY(-56px) scale(1.1) !important;
          z-index: 99;
        }
        @media (prefers-reduced-motion: reduce) {
          .card-item, .card-slot { transition: none; }
          .card-item:hover { transform: translateY(-20px) !important; }
        }
      `}</style>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * 开包流程编排：卡包 → 卡飞出（背面）→ 逐张翻面揭示 → 手牌
 * ------------------------------------------------------------------------- */
export function BoosterPackOpener({ pack, cards }) {
  const [phase, setPhase] = useState("fly"); // fly(卡片入场) | reveal(逐张翻面) | done
  const [deck, setDeck] = useState([]);      // 手牌状态（含 __revealed 标记）
  const [selected, setSelected] = useState(null);
  const timers = useRef([]);

  // 挂载即开包：按稀有度排序（高的最后揭示，像炉石）→ 卡片入场 → 逐张翻面
  useEffect(() => {
    const sorted = [...cards].sort((a, b) => (b.score || 0) - (a.score || 0));
    setDeck(sorted.map((c) => ({ ...c, __revealed: false })));

    const revealAt = 600 + sorted.length * 130;
    sorted.forEach((_, i) => {
      timers.current.push(
        setTimeout(() => {
          setDeck((prev) => prev.map((c, ci) => (ci === i ? { ...c, __revealed: true } : c)));
          if (i === sorted.length - 1) setPhase("done");
        }, revealAt + i * 420)
      );
    });
    return () => timers.current.forEach(clearTimeout);
  }, [cards]);

  return (
    <div className="w-full">
      <div className="mb-2 text-center text-[12px]" style={{ color: "#8f98a8" }}>
        {phase === "fly"
          ? `开包中 · ${pack.title}…`
          : phase === "reveal"
          ? "揭示中…"
          : `开包完成 · ${deck.length} 张指标卡（hover 抽出，点击查看完整信息）`}
      </div>
      <HandFan cards={deck} onSelect={setSelected} />
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
