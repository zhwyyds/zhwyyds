/**
 * MetricCard Demo 入口 —— 炉石式开包 + 手牌（数据来自指标库）
 * 加载策略：优先 /api/metrics，失败回退内联快照。
 */
import { createRoot } from "react-dom/client";
import { useEffect, useState } from "react";
import BoosterPackDemo from "../BoosterPack.jsx";
import snapshot from "./metrics-data.json";

const DOMAIN_NAMES = {
  sale: "交易", mall: "商场", base: "基础", cont: "合同", cust: "消费者",
  fin: "财务", fund: "资金", hr: "人资", mkt: "营销", prod: "商品",
  ptnr: "商户", shop: "店铺", traf: "流量", wk: "流程",
};

function loadMetrics() {
  return fetch("/api/metrics", { headers: { Accept: "application/json" } })
    .then((r) => {
      if (!r.ok) throw new Error("api unavailable");
      return r.json();
    })
    .then((data) => {
      const list = Array.isArray(data) ? data : data.metrics || data.items || [];
      if (!list.length) throw new Error("empty api data");
      return { list, fromApi: true };
    })
    .catch(() => ({ list: snapshot, fromApi: false }));
}

/** 单卡包：一包 30 张（对应批量导入"每组 30 条"切分），全部指标按稀有度排序 */
function buildPacks(metrics) {
  return [
    {
      id: "all",
      title: "指标卡库",
      sub: "一包 30 张 · 全部指标",
      domain: "default",
      filter: () => true,
      max: 30,
    },
  ];
}

function App() {
  const [metrics, setMetrics] = useState(null);
  const [source, setSource] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadMetrics()
      .then(({ list, fromApi }) => {
        setMetrics(list);
        setSource(fromApi ? "api" : "snapshot");
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  if (error) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24, color: "#e5534b" }}>
        加载指标库数据失败：{error}
      </div>
    );
  }
  if (!metrics) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24, color: "#8f98a8" }}>
        正在从指标库加载数据…
      </div>
    );
  }

  const packs = buildPacks(metrics);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, margin: 0, color: "#ffffff" }}>
          ⚔ 指标卡包 · 炉石开包
        </h1>
        <p style={{ fontSize: 12.5, color: "#8f98a8", margin: "6px 0 0" }}>
          数据源：{source === "api" ? "指标库 API" : "指标库快照"} · {metrics.length} 条指标 ·{" "}
          一包 30 张（对应批量导入每组切分）· 开包逐张揭示（评分 = 稀有度）→ 按稀有度分摞 → 点摞展开 → 点击看全部 48 字段
        </p>
      </header>
      <BoosterPackDemo metrics={metrics} packs={packs} />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
