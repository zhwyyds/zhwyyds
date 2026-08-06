"""AI 生成服务（R2 重构）。

把 app.py 中的大逻辑（指标 suggest / 词根 suggest / 词根 generate / 词根 commit）
下沉到服务层，路由只留薄壳。职责：

- suggest_metric：AI 辅助生成指标定义（mock 相似复用 + live LLM，含词根归并过滤）
- suggest_root：词根字段建议（命中已有词根确定性复用，不调 LLM）
- generate_roots：词根批量生成（reuse 预检查 + 多模型 pipeline）
- commit_roots：词根评审结果确认入库（跳过 reuse/未通过/未勾选项）
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from data_governance.caliber.draft import parse_response
from data_governance.config_loader import load_models
from data_governance.io.catalog import RootRecord, load_catalog
from data_governance.llm import factory as llm_factory
from data_governance.llm.env import resolve_use_mock
from data_governance.llm.parallel import run_models_parallel_prompt
from data_governance.pipeline.root_generation import RootGenerationPipeline
from data_governance.roots.dictionary import (
    build_root_dictionary,
    dictionary_to_prompt_text,
    find_root_for_term,
)
from data_governance.schemas.roots import (
    ReviewStatus,
    RootGenerationRequest,
    SourceModel,
    TermInput,
)

# metric_en 收集的字段清单（与 suggest prompt 输出对齐）
_METRIC_FIELDS = (
    "metric_en",
    "caliber_desc",
    "unit",
    "frequency",
    "value_type",
    "dimensions",
    "scenario",
    "formula",
    "formula_cn",
    "reports",
    "analysis_methods",
    "alert_rules",
    "precision",
    "owner",
    "category_l1",
    "category_l2",
    "data_sources",
    "source_table",
    "tech_caliber",
    "suggestions",
    "suggested_roots",
)


class AsyncTaskManager:
    """进程内异步任务管理器（I1：多 AI 进度条）。

    - 内存 dict 存任务状态：{status, completed, total, result, error}
    - 后台线程池执行任务，run_fn 通过 on_progress(completed, total) 上报进度
    - 秒级任务，进程重启即清空（可接受）；并发访问用锁保护
    """

    def __init__(self, max_workers: int = 2) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai-task")

    def create(self, task_type: str, run_fn: Callable[[Callable[[int, int], None]], Any]) -> str:
        """创建任务并立即返回 task_id；run_fn(on_progress) 在后台线程执行。"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "type": task_type,
                "status": "running",
                "completed": 0,
                "total": 0,
                "result": None,
                "error": None,
            }
        self._pool.submit(self._execute, task_id, run_fn)
        return task_id

    def _execute(self, task_id: str, run_fn: Callable[[Callable[[int, int], None]], Any]) -> None:
        def on_progress(completed: int, total: int) -> None:
            with self._lock:
                task = self._tasks.get(task_id)
                if task is not None:
                    task["completed"] = completed
                    task["total"] = total

        try:
            result = run_fn(on_progress)
            with self._lock:
                task = self._tasks.get(task_id)
                if task is not None:
                    task["status"] = "done"
                    task["result"] = result
                    task["completed"] = task["total"] or task["completed"]
        except Exception as exc:
            with self._lock:
                task = self._tasks.get(task_id)
                if task is not None:
                    task["status"] = "error"
                    task["error"] = str(exc)

    def get(self, task_id: str) -> dict[str, Any] | None:
        """查询任务快照；不存在返回 None。"""
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task is not None else None


class AiService:
    """指标/词根 AI 生成服务，聚合 LLM 调用与词根归并规则。"""

    def __init__(self, base_dir: Path) -> None:
        self.base = base_dir
        # 异步任务管理器（多 AI 进度：进程内内存存储，秒级任务可接受）
        self.tasks = AsyncTaskManager()

    # ── 指标 AI 生成 ─────────────────────────────────────────────

    def suggest_metric(self, body: dict) -> dict:
        """AI 辅助生成指标定义：mock（相似指标复用+词根提示）/ live（LLM 生成）。"""
        metric_cn = str((body or {}).get("metric_cn") or "").strip()
        domain = str((body or {}).get("domain_code") or "").strip().lower()
        desc = str((body or {}).get("caliber_desc") or "").strip()
        formula = str((body or {}).get("formula") or "").strip()
        unit = str((body or {}).get("unit") or "").strip()
        frequency = str((body or {}).get("frequency") or "").strip()
        if not metric_cn:
            raise HTTPException(400, "metric_cn 必填")
        catalog = load_catalog(self.base)

        if resolve_use_mock(None):
            return self._suggest_metric_mock(catalog, metric_cn, domain, desc)

        # live：单模型生成指标定义
        merged = self._suggest_metric_live(catalog, metric_cn, domain, desc, formula, unit, frequency)
        merged.setdefault("metric_cn", metric_cn)
        merged.setdefault("frequency", "月")
        merged.setdefault("suggestions", [])
        merged["suggested_roots"] = self._filter_missing_roots(catalog, merged.get("suggested_roots") or [])
        return merged

    def suggest_metric_async(self, body: dict) -> str:
        """异步版 suggest（多 AI 进度）：创建任务并立即返回 task_id，进度由 get_task 轮询。

        mock 模式：任务直接完成（无 LLM 进度）；live 模式：逐模型完成时更新 completed/total。
        """
        metric_cn = str((body or {}).get("metric_cn") or "").strip()
        if not metric_cn:
            raise HTTPException(400, "metric_cn 必填")

        def _run(on_progress: Callable[[int, int], None]) -> dict:
            domain = str((body or {}).get("domain_code") or "").strip().lower()
            desc = str((body or {}).get("caliber_desc") or "").strip()
            formula = str((body or {}).get("formula") or "").strip()
            unit = str((body or {}).get("unit") or "").strip()
            frequency = str((body or {}).get("frequency") or "").strip()
            catalog = load_catalog(self.base)
            if resolve_use_mock(None):
                on_progress(1, 1)
                result = self._suggest_metric_mock(catalog, metric_cn, domain, desc)
            else:
                merged = self._suggest_metric_live(
                    catalog,
                    metric_cn,
                    domain,
                    desc,
                    formula,
                    unit,
                    frequency,
                    on_progress=on_progress,
                )
                result = merged
            result.setdefault("metric_cn", metric_cn)
            result.setdefault("frequency", "月")
            result.setdefault("suggestions", [])
            result["suggested_roots"] = self._filter_missing_roots(catalog, result.get("suggested_roots") or [])
            return result

        return self.tasks.create("metric_suggest", _run)

    def get_task(self, task_id: str) -> dict | None:
        """查询异步任务状态：{status, completed, total, result?, error?}。"""
        return self.tasks.get(task_id)

    def _suggest_metric_mock(self, catalog, metric_cn: str, domain: str, desc: str) -> dict:
        """mock 模式：同名指标复用 / 词根组合提示。"""
        same = next((m for m in catalog.metrics if m.metric_cn == metric_cn), None)
        if same is not None:
            return {
                "source": "similar_metric",
                "metric_cn": metric_cn,
                "metric_en": same.metric_en,
                "caliber_desc": same.caliber_desc,
                "unit": same.unit,
                "frequency": same.frequency,
                "value_type": same.value_type,
                "dimensions": same.dimensions,
                "scenario": same.scenario,
                "formula": same.formula,
                "formula_cn": same.formula_cn,
                "reports": same.reports,
                "analysis_methods": same.analysis_methods,
                "alert_rules": same.alert_rules,
                "precision": same.precision,
                "owner": same.owner,
                "category_l1": same.category_l1,
                "category_l2": same.category_l2,
                "data_sources": same.data_sources,
                "source_table": same.source_table,
                "tech_caliber": same.tech_caliber,
                "suggestions": ["已复用同名指标的既有定义，请核查后确认"],
                "suggested_roots": [],
            }
        hits = [r.root_en for r in catalog.roots if r.domain_code == domain and r.root_cn and r.root_cn in metric_cn]
        metric_en = "_".join(hits) if hits else "pending_naming"
        return {
            "source": "rule_hint",
            "metric_cn": metric_cn,
            "metric_en": metric_en,
            "caliber_desc": desc,
            "unit": "",
            "frequency": "月",
            "value_type": "数量",
            "dimensions": "",
            "scenario": "",
            "formula": "",
            "formula_cn": "",
            "reports": "",
            "analysis_methods": "",
            "alert_rules": "",
            "precision": "",
            "owner": "待定",
            "category_l1": "待定",
            "category_l2": "待定",
            "data_sources": "",
            "source_table": "",
            "tech_caliber": "",
            "suggestions": ["mock 模式给出词根组合提示；配置 ≥2 个 LLM Key 后可生成完整定义"],
            "suggested_roots": [],
        }

    def _suggest_metric_live(
        self,
        catalog,
        metric_cn: str,
        domain: str,
        desc: str,
        formula: str,
        unit: str,
        frequency: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict:
        """live 模式：LLM 生成指标定义，多模型取首个非空字段（合并）。

        on_progress(completed, total)：每完成一个模型回调一次（多 AI 进度条）。
        """
        models = load_models("metric_review", config_path=self.base / "config" / "models.csv")
        clients = llm_factory.build_live_clients(models)
        entries = build_root_dictionary(catalog.roots, domain=domain)
        root_text = dictionary_to_prompt_text(entries)
        context_lines = [f"中文名：{metric_cn}", f"主题域：{domain}"]
        if desc:
            context_lines.append(f"业务定义/描述：{desc}")
        if formula:
            context_lines.append(f"计算公式：{formula}")
        if unit:
            context_lines.append(f"计量单位：{unit}")
        if frequency:
            context_lines.append(f"统计频率：{frequency}")
        context_block = "\n".join(context_lines)
        prompt = _build_metric_prompt(metric_cn, domain, root_text, context_block)
        raws = run_models_parallel_prompt(clients, prompt, cache_base_dir=self.base, on_progress=on_progress)

        merged: dict = {}
        for _mname, raw in raws:
            try:
                data = parse_response(raw)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for key in _METRIC_FIELDS:
                v = data.get(key)
                if v not in (None, "") and key not in merged:
                    merged[key] = v
        if not merged.get("metric_en"):
            # 降级容错（G6）：偶发格式漂移 → 200 + 警告，不让用户卡死
            merged["metric_en"] = ""
            merged["metric_en_warning"] = "AI 未能生成有效英文名，请手动填写"
        merged["source"] = "llm_multi" if len(raws) > 1 else "llm"
        return merged

    @staticmethod
    def _filter_missing_roots(catalog, suggested: list) -> list[dict]:
        """过滤 suggested_roots：词根库已有的（跨域查公共词根）不重复建议。"""
        missing: list[dict] = []
        for sr in suggested:
            if not isinstance(sr, dict):
                continue
            en = str(sr.get("root_en") or "").strip().lower()
            cn = str(sr.get("root_cn") or "").strip()
            if not en or not cn:
                continue
            if find_root_for_term(catalog.roots, en) is not None:
                continue
            if find_root_for_term(catalog.roots, cn) is not None:
                continue
            missing.append(
                {
                    "root_cn": cn,
                    "root_en": en,
                    "root_abbr": str(sr.get("root_abbr") or "").strip() or en,
                    "root_type": str(sr.get("root_type") or "noun").strip() or "noun",
                    "description": str(sr.get("description") or "").strip(),
                }
            )
        return missing

    # ── 词根 AI 字段建议 ─────────────────────────────────────────

    def suggest_root(self, body: dict) -> dict:
        """词根字段建议：命中已有词根（含同义词）→ 确定性复用；否则 live LLM 生成。"""
        root_cn = str((body or {}).get("root_cn") or "").strip()
        if not root_cn:
            raise HTTPException(400, "root_cn 必填")
        domain = str((body or {}).get("domain") or (body or {}).get("domain_code") or "sale").strip().lower()
        context = str((body or {}).get("context") or "").strip()
        catalog = load_catalog(self.base)

        hit = find_root_for_term(catalog.roots, root_cn, domain=domain) or find_root_for_term(catalog.roots, root_cn)
        if hit is not None:
            return {
                "root_cn": root_cn,
                "root_en": hit.root_en,
                "root_abbr": hit.root_abbr,
                "root_type": hit.root_type,
                "description": f"已复用已有词根 {hit.root_id}（{hit.root_cn}），语义一致",
                "reused_root_id": hit.root_id,
            }

        root_text = dictionary_to_prompt_text(build_root_dictionary(catalog.roots, domain=domain))
        if resolve_use_mock(None):
            return {
                "root_cn": root_cn,
                "root_en": "",
                "root_abbr": "",
                "root_type": "noun",
                "description": "",
                "warning": "mock 模式无法生成英文词根，请配置 LLM Key 或手动填写",
            }

        models = load_models("root_generation", config_path=self.base / "config" / "models.csv")
        clients = llm_factory.build_live_clients(models)
        prompt = _build_root_suggest_prompt(root_cn, context, root_text)
        data = parse_response(clients[0].complete(prompt))
        if not data.get("root_en"):
            return {
                "root_cn": root_cn,
                "root_en": "",
                "root_abbr": "",
                "root_type": "noun",
                "description": "",
                "warning": "AI 未能生成英文词根，请重试或手动填写",
            }
        return {
            "root_cn": root_cn,
            "root_en": str(data.get("root_en") or "").strip(),
            "root_abbr": str(data.get("root_abbr") or "").strip() or str(data.get("root_en") or "").strip(),
            "root_type": str(data.get("root_type") or "noun").strip(),
            "description": str(data.get("description") or "").strip(),
        }

    # ── 词根批量生成 ─────────────────────────────────────────────

    def generate_roots(self, body: dict) -> dict:
        """词根批量生成：术语命中已有词根（含同义词）→ reuse 标记跳过 LLM；其余走多模型 pipeline。"""
        domain = str((body or {}).get("domain") or "sale").strip().lower()
        terms_raw = (body or {}).get("terms") or []
        if not terms_raw:
            raise HTTPException(400, "terms 必填（至少一个中文词根）")
        terms: list[TermInput] = []
        for t in terms_raw:
            cn = str((t or {}).get("cn_term") or "").strip()
            if not cn:
                raise HTTPException(400, "cn_term 不能为空")
            terms.append(TermInput(cn_term=cn, context=str((t or {}).get("context") or "").strip()))

        catalog = load_catalog(self.base)
        reuse_items: list[dict] = []
        pending_terms: list[TermInput] = []
        for t in terms:
            hit = find_root_for_term(catalog.roots, t.cn_term, domain=domain)
            if hit is not None:
                reuse_items.append(_build_reuse_item(t, hit))
            else:
                pending_terms.append(t)

        root_text = dictionary_to_prompt_text(build_root_dictionary(catalog.roots, domain=domain))
        if pending_terms:
            req = RootGenerationRequest(domain=domain, terms=pending_terms)
            doc = RootGenerationPipeline(base_dir=self.base, use_mock=None, root_dictionary_text=root_text).run(
                req, write_roots=False
            )
            payload = doc.model_dump(mode="json")
            payload["items"] = payload["items"] + reuse_items
            return payload
        if reuse_items:
            return {
                "review_id": f"RR_{domain.upper()}_001",
                "domain": domain,
                "review_type": "root_generation",
                "created_at": _now_iso(),
                "models_used": [],
                "items": reuse_items,
            }
        return {"review_id": f"RR_{domain.upper()}_001", "domain": domain, "items": []}

    def commit_roots(self, body: dict) -> dict:
        """词根评审结果确认入库（勾选 cn_terms；空=全部 auto_approved）。"""
        import json as _json

        from data_governance.io.roots_csv import append_root_row, make_root_csv_row

        review_id = str((body or {}).get("review_id") or "").strip()
        if not review_id:
            raise HTTPException(400, "review_id 必填")
        cn_terms = [t for t in [(t or "").strip() for t in (body or {}).get("cn_terms") or []] if t]

        reviews_dir = self.base / "reviews" / "root_reviews"
        doc: dict | None = None
        for path in sorted(reviews_dir.glob("*_root_review_*.json"), reverse=True):
            try:
                candidate = _json.loads(path.read_text(encoding="utf-8"))
            except (_json.JSONDecodeError, OSError):
                continue
            if isinstance(candidate, dict) and candidate.get("review_id") == review_id:
                doc = candidate
                break
        if doc is None:
            raise HTTPException(404, f"review not found: {review_id}")

        domain = str(doc.get("domain") or "sale").lower()
        created: list[str] = []
        skipped: list[str] = []
        for item in doc.get("items") or []:
            cn = str(item.get("cn_term") or "").strip()
            if item.get("reused_root_id"):
                skipped.append(f"{cn}(已复用 {item['reused_root_id']}，无需入库)")
                continue
            if not item.get("auto_approved"):
                skipped.append(f"{cn}(未自动通过)")
                continue
            if cn_terms and cn not in cn_terms:
                skipped.append(f"{cn}(未勾选)")
                continue
            fd = item.get("final_decision") or {}
            if not (fd.get("root_en") or "").strip():
                skipped.append(f"{cn}(无英文名)")
                continue
            try:
                row = make_root_csv_row(
                    domain=domain,
                    root_cn=cn,
                    root_en=str(fd["root_en"]).strip(),
                    root_abbr=str(fd.get("root_abbr") or "").strip() or str(fd["root_en"]).strip(),
                    root_type=str(fd.get("root_type") or "noun").strip() or "noun",
                    description=str(fd.get("description") or "").strip(),
                    source_model=SourceModel("model_consensus"),
                    review_status=ReviewStatus.approved,
                    roots_dir=self.base / "roots",
                )
                append_root_row(self.base / "roots" / f"{domain}_roots.csv", row)
                created.append(cn)
            except ValueError as exc:
                skipped.append(f"{cn}({exc})")
        return {"review_id": review_id, "domain": domain, "created": created, "skipped": skipped}


# ── 提示词构建（与路由层解耦，便于单测） ──────────────────────────


def _build_metric_prompt(metric_cn: str, domain: str, root_text: str, context_block: str) -> str:
    """构造指标定义生成 prompt：词根字典注入 + 强制复用规则。"""
    return (
        "你是数据治理平台的指标定义专家。根据指标名称【并结合业务定义/计算公式】生成标准化的指标定义，只输出 JSON：\n"
        f'{{"metric_cn":"{metric_cn}","metric_en":"snake_case 英文名",'
        f'"caliber_desc":"业务定义(含统计周期与边界)","unit":"单位","frequency":"月/日/周",'
        f'"value_type":"值类型(如 金额/数量/比率/百分数)","dimensions":"常用维度(逗号分隔)",'
        f'"scenario":"适用场景","formula":"计算公式","formula_cn":"公式中文说明",'
        f'"reports":"应用报表","analysis_methods":"分析方法",'
        f'"alert_rules":"预警标准(可为空)","precision":"精度(如 2位小数)",'
        f'"owner":"指标负责单位(根据指标语义判断归属部门，如 财务部/运营部/营销部，不确定填 待定)",'
        f'"category_l1":"一级分类(如 收入类/成本类/客户类/经营类/财务类，按语义判断)",'
        f'"category_l2":"二级分类(更细的业务分类，如 租赁收入/租金类)",'
        f'"data_sources":"来源表/数仓层","source_table":"所属物理表(dwd/dws表名)","tech_caliber":"技术口径",'
        f'"suggestions":["需人工确认的点"],'
        f'"suggested_roots":[{{"root_cn":"中文词根","root_en":"词根英文","root_abbr":"缩写",'
        f'"root_type":"noun/verb/adj/unit/time","description":"说明"}}]}}\n\n'
        "强制要求（必须遵守，缺失将视为生成失败）：\n"
        "- 输出 JSON 必须包含上面列出的【全部字段键】（metric_cn / metric_en / caliber_desc / unit / frequency /\n"
        "  value_type / dimensions / scenario / formula / formula_cn / reports / analysis_methods / alert_rules /\n"
        "  precision / owner / category_l1 / category_l2 / data_sources / source_table / tech_caliber / suggestions /\n"
        "  suggested_roots），一个键都不能少；无法确定的值填 待定 或空字符串，但键必须存在\n"
        "- metric_en 必须是非空 snake_case 英文名（如 monthly_rent_amount），绝不能为空、不能含中文、不能是单字母占位\n"
        "- 如确实难以命名（中文名极含糊），可用 <英文占位>_pending_<序号> 并在 suggestions 中说明\n"
        "- suggested_roots 只列出 metric_en 用到的词根中【词根库缺失】的部分，词根库已有的绝不要列\n\n"
        f"参考词根库（该域的既有标准词根，含同义词）：\n{root_text}\n\n"
        "语义判定规则（必须遵守）：\n"
        "0. 【名称可能不规范】中文名可能口语化/含糊/不符合命名规范，请以【业务定义/计算公式】为准理解指标真实语义，"
        "再生成规范英文名与口径；有定义/公式时，metric_en 与 caliber_desc 必须与其语义一致，不得照抄口语化名称\n"
        "1. metric_en 必须由词根库中的词根组合而成（使用 root_en 原词）\n"
        "2. 术语语义若已被词根库覆盖（包括其同义词），必须复用对应词根，禁止自创新词根\n"
        "3. 例如词根库已有 rent（同义词：租金/租赁/出租），则「租赁收入」必须用 rent，不能写 lease\n"
        "4. suggested_roots 只列出 metric_en 用到的词根中【词根库缺失】的部分（供同步新建），"
        "词根库已有的绝不要列；无缺失则为空数组 []\n"
        f"\n{context_block}"
    )


def _build_root_suggest_prompt(root_cn: str, context: str, root_text: str) -> str:
    """构造词根字段建议 prompt。"""
    return (
        "你是数据治理平台的词根专家。根据中文词根生成标准英文词根，只输出 JSON：\n"
        '{"root_en":"标准英文单词（不用拼音）","root_abbr":"缩写不超过6字符",'
        '"root_type":"noun/verb/adj/unit/time","description":"一句话说明"}\n'
        "规则：\n"
        "- root_en 使用标准英文单词，不用拼音\n"
        "- root_abbr 不超过 6 字符（单词取前3-4字母，短词用全称）\n"
        "- 语义若与参考词根库中已有词根相同（含同义词），必须复用其 root_en，不得自创\n"
        f"参考词根库：\n{root_text}\n"
        f"中文词根：{root_cn}\n上下文：{context or '（无）'}"
    )


def _build_reuse_item(t: TermInput, hit: RootRecord) -> dict:
    """构造「已复用已有词根」的评审条目（跳过 LLM）。"""
    return {
        "cn_term": t.cn_term,
        "context": t.context,
        "model_results": [],
        "comparison": {
            "root_en_consistent": True,
            "root_abbr_consistent": True,
            "root_type_consistent": True,
            "conflict_fields": [],
        },
        "final_decision": {
            "root_en": hit.root_en,
            "root_abbr": hit.root_abbr,
            "root_type": hit.root_type,
            "description": f"已复用已有词根 {hit.root_id}（{hit.root_cn}），未新建",
            "decision_reason": f"语义命中已有词根 {hit.root_id}（含同义词），强制复用",
            "decision_type": "model_consensus",
            "review_status": "approved",
        },
        "auto_approved": True,
        "reused_root_id": hit.root_id,
    }


def _now_iso() -> str:
    """当前时间 ISO（与 reviews 模块对齐）。"""
    from data_governance.io.reviews import now_iso_cn

    return now_iso_cn()
