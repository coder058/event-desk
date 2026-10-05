"""One feature boundary shared by archive training and production prediction."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

FACTS = "earnings-call-facts"
PREVIEW = "earnings-preview"
OPTIONS = "option-implied-stats"
# SOURCE: official option-implied-stats schema used by the starter.
OPTION_NAMES = ("implied_earnings_volatility", "implied_absolute_earnings_move", "skew_25_delta")


def select_items(bundle: dict[str, Any]) -> dict[str, Any]:
    """Only official disclosure items; outcome/metrics/baseline blocks never enter features."""
    disclosure = bundle.get("disclosure", bundle)
    if not isinstance(disclosure, dict):
        raise ValueError("Expected disclosure object")
    raw_items = disclosure.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("Expected disclosure items list")
    selected: dict[str, Any] = {}
    for item in raw_items:
        if not isinstance(item, dict) or item.get("id") not in (FACTS, PREVIEW, OPTIONS):
            continue
        item_id = str(item["id"])
        if item_id in selected:
            raise ValueError("Duplicate known material item")
        selected[item_id] = item.get("content")
    return selected


def facts_text(items: dict[str, Any]) -> str:
    facts = items.get(FACTS)
    if facts is None:
        return ""
    if not isinstance(facts, list) or not all(isinstance(fact, str) for fact in facts):
        raise ValueError("Facts must be a list of strings")
    return " ".join(facts)


def feature_row(items: dict[str, Any], *, enriched: bool) -> dict[str, Any]:
    facts = facts_text(items)
    preview = items.get(PREVIEW)
    if preview is not None and not isinstance(preview, str):
        raise ValueError("Preview must be a string")
    row: dict[str, Any] = {"text": facts}
    if not enriched:
        return row
    row["text"] = facts + "\nPREVIEW\n" + (preview or "")
    row["facts_missing"] = float(not facts)
    row["preview_missing"] = float(not preview)
    stats = items.get(OPTIONS)
    for name in OPTION_NAMES:
        block = stats.get(name) if isinstance(stats, dict) else None
        value = block.get("value") if isinstance(block, dict) and block.get("status") == "ok" else None
        present = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        # SOURCE: missing-value sentinel, paired with an explicit missingness indicator.
        row[name] = float(value) if present and isinstance(value, (int, float)) else 0.0
        row[name + "_missing"] = float(not present)
    return row


def input_hash(items: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()
