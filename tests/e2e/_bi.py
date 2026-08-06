import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        pg = await (await b.new_context(viewport={"width":1440,"height":900})).new_page()
        errs, dlg = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: dlg.append(d.message) or d.dismiss())
        await pg.goto("http://127.0.0.1:8080/", wait_until="domcontentloaded")
        await pg.wait_for_timeout(4000)
        # 1. 切到批量导入页
        await pg.evaluate("(x) => typeof switchToPage === 'function' && switchToPage(x)", "batch-import")
        await pg.wait_for_timeout(1500)
        page_ok = await pg.evaluate("!!document.getElementById('page-batch-import') && document.getElementById('page-batch-import').style.display !== 'none'")
        print("① 批量导入页打开:", page_ok, flush=True)
        # 2. 构造 CSV 并通过 API 上传（Playwright 文件上传用 set_input_files）
        csv_text = "metric_cn,caliber_desc\n" + "\n".join([f"批量测试指标{i},批量测试定义{i}" for i in range(12)])
        with open("/tmp/import_test.csv", "w", encoding="utf-8") as f:
            f.write(csv_text)
        await pg.set_input_files("#importTaskFile", "/tmp/import_test.csv")
        await pg.click("button[onclick*='uploadImportTaskFile']")
        await pg.wait_for_timeout(1500)
        tasks = await pg.evaluate("document.querySelectorAll('#importTaskBody tr').length")
        print("② 任务列表行数:", tasks, flush=True)
        # 3. 打开第一个任务 + 处理（去重+AI生成，mock 模式快）
        await pg.evaluate("openImportTask(document.querySelector('#importTaskBody tr .btn').getAttribute('onclick').match(/'([^']+)'/)[1])")
        await pg.wait_for_timeout(800)
        await pg.evaluate("processImportTask()")
        await pg.wait_for_timeout(3000)
        cards = await pg.evaluate("document.querySelectorAll('#importTaskCards .card').length")
        statuses = await pg.evaluate("Array.from(document.querySelectorAll('#importTaskCards .badge')).map(function(b){return b.textContent;})")
        print("③ 指标卡片数:", cards, "| 状态标签:", statuses[:5], flush=True)
        # 4. 评审第一张卡（通过）
        await pg.evaluate("reviewImportRow(0,'approve')")
        await pg.wait_for_timeout(1200)
        prog = await pg.evaluate("document.getElementById('importTaskDetailMeta').textContent")
        print("④ 评审后 meta:", prog, flush=True)
        await pg.screenshot(path="/Users/heyuan/DEVELOPMENT/data_go/tests/e2e/screenshots/h31-batch-import.png", full_page=True)
        print("pageerror:", errs or "无", flush=True)
        print("alert:", dlg or "无", flush=True)
        await b.close()

asyncio.run(main())
