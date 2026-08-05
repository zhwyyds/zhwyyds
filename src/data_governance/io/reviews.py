from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data_governance.schemas.roots import RootReviewDocument

_REVIEW_SEQ = re.compile(r"_root_review_(\d+)\.json$")


def next_review_path(reviews_dir: Path, domain: str) -> Path:
    reviews_dir.mkdir(parents=True, exist_ok=True)
    max_seq = 0
    for p in reviews_dir.glob(f"{domain}_root_review_*.json"):
        m = _REVIEW_SEQ.search(p.name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return reviews_dir / f"{domain}_root_review_{max_seq + 1:03d}.json"


def write_root_review(doc: RootReviewDocument, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def now_iso_cn() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).replace(microsecond=0).isoformat()
