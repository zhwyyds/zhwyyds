"""前端端到端验证（整合版）：同进程起 HTTP 服务 + Playwright headless 跑页面，捕获所有 console.error / pageerror / DOM 状态。"""

import asyncio
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.async_api import async_playwright

UI_DIR = Path("ui-prototype").resolve()
PORT = 8090  # 用 8090 避开沙箱里 8080 的残留


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, *args, **kwargs):  # 静默
        pass


def start_server() -> socketserver.TCPServer:
    server = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


async def run(url: str) -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await (await browser.new_context()).new_page()
        page.on("console", lambda m: console_errors.append(f"{m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("response", lambda r: failed_requests.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        # mock /api/* 路由（e2e 同源端口无后端服务，模拟真实数据）
        async def mock_ai_task(_route):
            # 模拟多 AI 进度：第一次 1/2，第二次 done
            count = getattr(mock_ai_task, "count", 0)
            mock_ai_task.count = count + 1
            if count == 0:
                await _route.fulfill(status=200, content_type="application/json",
                    body='{"status":"running","completed":1,"total":2,"result":null}')
            else:
                await _route.fulfill(status=200, content_type="application/json",
                    body='{"status":"done","completed":2,"total":2,'
                         '"result":{"metric_en":"monthly_rent_revenue",'
                         '"caliber_desc":"自然月内生效租赁合同的租金收入","formula_cn":"汇总当月租金",'
                         '"formula":"SUM(amount)","unit":"元","frequency":"月","value_type":"金额",'
                         '"dimensions":"租赁项目,客户,区域","scenario":"月度经营分析","owner":"财务部",'
                         '"reports":"月度租赁收入报表","analysis_methods":"同比,环比","alert_rules":"",'
                         '"precision":"2位小数","data_sources":"dwd_fact_rent","source_table":"dws_rent_monthly",'
                         '"tech_caliber":"按月汇总","category_l1":"收入类","category_l2":"租赁收入",'
                         '"suggestions":[],"suggested_roots":[],"source":"llm_multi","metric_cn":"月度租赁收入"}}')
        async def mock_suggest(_route):
            await _route.fulfill(
                status=200, content_type="application/json",
                body='{"task_id":"task_mock_001"}'
            )

        async def mock_metrics(_route):
            row = (
                '{"metric_id":"M_SALE_001","metric_cn":"月销售额","metric_en":"monthly_sales_amt",'
                '"domain_code":"sale","metric_type":"atomic",'
                '"review_status":"pending","version":"1","formula":"SUM(amt)","unit":"元","frequency":"月"},'
            )
            await _route.fulfill(
                status=200, content_type="application/json",
                body="[" + row * 15 + "]",
            )

        async def mock_pass(_route):
            await _route.fulfill(status=200, content_type="application/json", body="[]")

        await page.route("**/api/metrics/suggest/async*", lambda r: asyncio.create_task(mock_suggest(r)))
        await page.route("**/api/ai-tasks/**", lambda r: asyncio.create_task(mock_ai_task(r)))
        await page.route("**/api/metrics*", lambda r: asyncio.create_task(mock_metrics(r)))
        await page.route("**/api/roots*", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/domains*", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/metric-tree*", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/acceptance*", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/scores/**", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/caliber/**", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/metric-reviews/**", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/modifier-rules*", lambda r: asyncio.create_task(mock_pass(r)))
        await page.route("**/api/lineage*", lambda r: asyncio.create_task(mock_pass(r)))

        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)  # 等 init + renderTable 完成

        # 1. console errors
        print("=" * 60)
        print(f"console.error 数量：{len(console_errors)}")
        for e in console_errors:
            print(f"  - {e[:200]}")

        # 2. uncaught page errors（最关键）
        print("=" * 60)
        print(f"uncaught pageerror 数量：{len(page_errors)}")
        for e in page_errors:
            print(f"  - {e[:300]}")

        # 3. 切到指标管理页 + 点击「+ 新增指标」按钮（应打开抽屉）
        await page.evaluate("if (typeof switchToPage === 'function') switchToPage('metric-mgmt')")
        await page.wait_for_timeout(800)

        btn_info = await page.evaluate("""
            (() => {
              var b = document.querySelector('.new-metric-btn');
              return b ? { text: b.textContent.trim(), onclick: b.getAttribute('onclick') } : null;
            })()
        """)
        print("=" * 60)
        print(f"「+ 新增指标」按钮信息：{btn_info}")

        await page.click(".new-metric-btn", timeout=5000)
        await page.wait_for_timeout(500)
        drawer_state = await page.evaluate("""
            (() => {
              var d = document.getElementById('metricNewDrawer');
              return d ? (d.classList.contains('show') ? '抽屉已显示' : '抽屉未显示') : '抽屉不存在';
            })()
        """)
        print(f"点击后抽屉状态：{drawer_state}")

        # 填指标名称 → 点 AI 辅助 → 检查字段被填充
        await page.fill("#metricNewDrawer #newMetricCn", "月度租赁收入")
        await page.evaluate("suggestMetricDrawer()")
        await page.wait_for_timeout(3000)
        fill_state = await page.evaluate("""
            (() => {
              var g = function(id){ var e = document.getElementById(id); return e ? e.value : 'NO_FIELD'; };
              return '英文名=' + g('newMetricEn').slice(0,30) + ' | 单位=' + g('newMetricUnit') +
                     ' | 周期=' + g('newMetricFrequency') + ' | 负责人=' + g('newMetricOwner');
            })()
        """)
        print(f"AI 填充后：{fill_state}")

        inline_visible = await page.evaluate("""
            (() => {
              var row = document.getElementById('newMetricInlineRow');
              return row ? row.style.display : 'NOT_FOUND';
            })()
        """)
        print(f"点击前内联行 display：{inline_visible}")

        try:
            await page.click(".new-metric-btn", timeout=3000)
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"点击异常：{e}")

        inline_after = await page.evaluate("""
            (() => {
              var row = document.getElementById('newMetricInlineRow');
              return row ? row.style.display : 'NOT_FOUND';
            })()
        """)
        print(f"点击后内联行 display：{inline_after}")

        # 4. 分页栏文本
        pagination = await page.evaluate("""
            (() => {
              var bar = document.querySelector('#page-metric-mgmt .pagination-bar');
              return bar ? bar.innerText.replace(/\\s+/g, ' ').slice(0, 250) : 'NO_PAGINATION_BAR';
            })()
        """)
        print(f"指标管理分页栏：{pagination}")

        # 5. 状态流程图数字
        flow = await page.evaluate("""
            (() => {
              return Array.from(document.querySelectorAll('#page-metric-mgmt .batch-status-count'))
                .map(function(e){ return e.id + '=' + e.textContent; }).join(' | ');
            })()
        """)
        print(f"状态流程图：{flow}")

        # 5b. 失败的网络请求
        print("=" * 60)
        print(f"404/失败请求：{len(failed_requests)}")
        for r in failed_requests[:5]:
            print(f"  - {r}")

        # 6. 拿所有「共 N 条」类硬编码文本
        hardcodes = await page.evaluate("""
            (() => {
              var out = [];
              document.querySelectorAll('span.text-sm.text-muted, .pagination-info').forEach(function(e){
                var t = e.innerText.replace(/\\s+/g, ' ').trim();
                if (/共\\s*\\d+/.test(t)) out.push(t.slice(0, 120));
              });
              return out.join(' || ');
            })()
        """)
        print(f"页面「共 N 条」类文本：{hardcodes}")

        await browser.close()


async def main() -> None:
    server = start_server()
    try:
        await run(f"http://127.0.0.1:{PORT}/")
    finally:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)