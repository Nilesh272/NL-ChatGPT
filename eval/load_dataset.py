"""Load evaluation dataset from JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from eval.schemas import EvalItem

DEFAULT_DATASET = Path(__file__).parent / "dataset.jsonl"


def load_dataset(path: Path = DEFAULT_DATASET, limit: int = 0) -> List[EvalItem]:
    items: List[EvalItem] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            items.append(
                EvalItem(
                    id=row["id"],
                    query=row["query"],
                    expects_sources=row.get("expects_sources", True),
                    expected_behavior=row.get("expected_behavior", "answer"),
                    stakes=row.get("stakes", "medium"),
                    ground_truth=row.get("ground_truth", ""),
                    reference_urls=row.get("reference_urls", []),
                    notes=row.get("notes", ""),
                )
            )
    if limit > 0:
        return items[:limit]
    return items
