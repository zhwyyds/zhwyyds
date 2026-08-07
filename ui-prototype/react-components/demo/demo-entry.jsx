/**
 * MetricCard Demo 入口 —— 数据来自指标库（真实 CSV 快照）
 * 加载策略：优先 fetch /api/metrics（本地联 API 时用实时数据），
 *           失败则回退 ./metrics-data.json（静态快照，部署可用）。
 * 构建：esbuild --bundle
 */
import { createRoot } from "react-dom/client";
import { useEffect, useState } from "react";
import MetricCardLibrary from "../MetricCard.jsx";

const STATUS_LABELS = {
  approved: "已审核",
  pending: "待审核",
  rejected: "已打回",
  draft: "草稿",
};

/** 加载真实指标库数据 */
function loadMetrics() {
  return fetch("/api/metrics", { headers: { Accept: "application/json" } })
    .then((r) => {
      if (!r.ok) throw new Error("api unavailable");
      return r.json();
    })
    .then((data) => {
      const list = Array.isArray(data) ? data : data.metrics || data.items || [];
      if (!list.length) throw new Error("empty api data");
      return list;
    })
    .catch(() =>
      fetch("./metrics-data.json")
        .then((r) => r.json())
        .then((list) => {
          if (!list || !list.length) throw new Error("snapshot empty");
          return list;
        })
    );
}

function App() {
  const [metrics, setMetrics] = useState(null);
  const [source, setSource] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadMetrics()
      .then((list) => {
        setMetrics(list);
        setSource("api");
      })
      .catch((e) => {
        setError(String(e.message || e));
        setSource("error");
      });
  }, []);

  if (error) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24, color: "#a40e26" }}>
        加载指标库数据失败：{error}（请确认本地服务已启动，或检查 metrics-data.json）
      </div>
    );
  }
  if (!metrics) {
    return (
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24, color: "#57606a" }}>
        正在从指标库加载数据…
      </div>
    );
  }

  const counts = {
    已审核: metrics.filter((m) => m.review_status === "approved").length,
    待审核: metrics.filter((m) => m.review_status === "pending" || m.review_status === "draft").length,
    异议: metrics.filter(
      (m) => m.objection_status && m.objection_status !== "none" && m.objection_status !== ""
    ).length,
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 4px" }}>
          指标卡 · TCG 质感 × 企业可读性（指标库真实数据）
        </h1>
        <p style={{ fontSize: 12.5, color: "#57606a", margin: 0 }}>
          数据源：{source === "api" ? "指标库 API（/api/metrics）" : "指标库快照（metrics-data.json）"} ·
          {metrics.length} 条指标 · 已审核 {counts.已审核} / 待审核 {counts.待审核} / 异议 {counts.异议}
          {"  "}· 点击卡片查看全部 48 字段（可翻面）
        </p>
      </header>
      <MetricCardLibrary metrics={metrics} />
      <footer style={{ marginTop: 20, fontSize: 11.5, color: "#6e7781" }}>
        组件：MetricCard.jsx（React + Tailwind）· 无障碍：WCAG AA · 无粒子特效 / 无炫丽渐变 · 完整字段见翻面详情
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
