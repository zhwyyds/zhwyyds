#!/usr/bin/env python3
"""黄金演示数据生成器（IT3-3）。

生成覆盖 S / A / B / C 四级的演示指标，用于验收演示与口径助手试用：
- S 级：英文规范、口径完整（含公式+周期）、关联词根
- A 级：口径略简
- B 级：metric_en 拼音残留（评分封顶 B）
- C 级：口径为空（评分封顶 C）

用法：
  python scripts/demo_data.py            # 写入当前项目 metrics/
  python scripts/demo_data.py --base-dir /path/to/project
幂等：已存在的 metric_id 自动跳过。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_governance.io.metrics_csv import create_metric

DEMO_METRICS: list[dict] = [
    # S 级：字段完整、英文规范、口径含业务定义+公式+统计周期
    {
        "metric_id": "M_SALE_D01",
        "metric_cn": "订单金额",
        "metric_en": "order_amount",
        "metric_abbr": "ord_amt",
        "domain_code": "sale",
        "root_ids": "R_SALE_001",
        "metric_type": "atomic",
        "caliber_desc": "统计周期内已完成订单的销售总金额，不含退款，按支付完成时间归属",
        "formula": "SUM(sale_amt) WHERE order_status='completed' AND stat_month=当前自然月",
        "frequency": "月",
        "owner": "交易分析部",
        "review_status": "approved",
        "source_model": "manual",
    },
    # A 级：口径偏简（缺边界条件）
    {
        "metric_id": "M_SALE_D02",
        "metric_cn": "订单笔数",
        "metric_en": "order_count",
        "metric_abbr": "ord_cnt",
        "domain_code": "sale",
        "root_ids": "R_SALE_001",
        "metric_type": "atomic",
        "caliber_desc": "已完成订单数量",
        "frequency": "月",
        "owner": "交易分析部",
        "review_status": "approved",
        "source_model": "manual",
    },
    # B 级：metric_en 拼音残留（触发「拼音残留」特殊规则，封顶 B）
    {
        "metric_id": "M_SALE_D03",
        "metric_cn": "销售额",
        "metric_en": "xiaoshou_jine",
        "metric_abbr": "xsje",
        "domain_code": "sale",
        "root_ids": "R_SALE_001",
        "metric_type": "atomic",
        "caliber_desc": "统计周期内销售总额",
        "frequency": "月",
        "owner": "交易分析部",
        "review_status": "approved",
        "source_model": "manual",
    },
    # C 级：口径为空（触发「口径为空」特殊规则，封顶 C）
    {
        "metric_id": "M_SALE_D04",
        "metric_cn": "退款率",
        "metric_en": "refund_rate",
        "metric_abbr": "ref_rt",
        "domain_code": "sale",
        "root_ids": "R_SALE_001",
        "metric_type": "atomic",
        "caliber_desc": "",
        "frequency": "月",
        "owner": "交易分析部",
        "review_status": "approved",
        "source_model": "manual",
    },
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo_data", description="生成 S/A/B/C 四级黄金演示指标")
    parser.add_argument("--base-dir", type=Path, default=None, help="项目根目录（默认当前目录）")
    args = parser.parse_args(argv)
    base = (args.base_dir or Path.cwd()).resolve()

    created, skipped = 0, 0
    for payload in DEMO_METRICS:
        try:
            create_metric(base, payload)
            created += 1
            print(f"  created {payload['metric_id']}  {payload['metric_cn']}")
        except ValueError as exc:
            if "already exists" in str(exc):
                skipped += 1
                print(f"  skipped {payload['metric_id']}（已存在）")
            else:
                print(f"  FAILED {payload['metric_id']}: {exc}")
    print(f"demo_data: created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
