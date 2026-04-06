from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "phones.json"


def load_catalog() -> List[Dict[str, Any]]:
    path = _catalog_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("catalog_not_list")
    return data


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _matches_query(item: Dict[str, Any], query: str) -> bool:
    q = _norm(query)
    if not q:
        return False
    hay = " ".join(
        [
            _norm(str(item.get("brand", ""))),
            _norm(str(item.get("model", ""))),
            _norm(str(item.get("variant", ""))),
            _norm(str(item.get("id", ""))),
        ]
    )
    return q in hay


def find_items(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    items = load_catalog()
    out: List[Dict[str, Any]] = []
    for it in items:
        if _matches_query(it, query):
            out.append(it)
        if len(out) >= max(1, int(limit)):
            break
    return out


def get_by_id(phone_id: str) -> Optional[Dict[str, Any]]:
    pid = _norm(phone_id)
    for it in load_catalog():
        if _norm(str(it.get("id", ""))) == pid:
            return it
    return None


def summarize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    specs = item.get("specs") or {}
    return {
        "id": item.get("id"),
        "name": f"{item.get('brand')} {item.get('model')} {item.get('variant')}".strip(),
        "price_vnd": item.get("price_vnd"),
        "stock": item.get("stock"),
        "specs": {
            "ram_gb": specs.get("ram_gb"),
            "storage_gb": specs.get("storage_gb"),
            "battery_mah": specs.get("battery_mah"),
            "chipset": specs.get("chipset"),
            "screen_inch": specs.get("screen_inch"),
            "refresh_hz": specs.get("refresh_hz"),
        },
    }


def list_brands() -> List[str]:
    brands = sorted({str(it.get("brand", "")).strip() for it in load_catalog() if it.get("brand")})
    return [b for b in brands if b]


def vnd(amount: Any) -> str:
    try:
        n = int(amount)
    except Exception:
        return str(amount)
    return f"{n:,}".replace(",", ".") + " VND"

