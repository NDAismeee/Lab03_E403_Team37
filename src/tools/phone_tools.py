from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.tools.phone_catalog import find_items, get_by_id, list_brands, summarize_item, vnd
from src.tools.web_tools import build_web_tools


def tool_search_phones(query: str, limit: int = 5) -> Dict[str, Any]:
    items = find_items(query=query, limit=limit)
    return {
        "query": query,
        "count": len(items),
        "results": [summarize_item(it) for it in items],
    }


def tool_get_phone_details(phone_id: str) -> Dict[str, Any]:
    item = get_by_id(phone_id)
    if not item:
        return {"error": "NOT_FOUND", "phone_id": phone_id}
    return summarize_item(item)


def tool_check_stock(phone_id: str) -> Dict[str, Any]:
    item = get_by_id(phone_id)
    if not item:
        return {"error": "NOT_FOUND", "phone_id": phone_id}
    return {"phone_id": item.get("id"), "stock": item.get("stock")}


def tool_quote_order(phone_id: str, quantity: int, coupon_percent: Optional[float] = None) -> Dict[str, Any]:
    item = get_by_id(phone_id)
    if not item:
        return {"error": "NOT_FOUND", "phone_id": phone_id}
    q = int(quantity)
    if q <= 0:
        return {"error": "INVALID_QUANTITY", "quantity": quantity}
    price = int(item.get("price_vnd") or 0)
    subtotal = price * q
    discount_pct = float(coupon_percent) if coupon_percent is not None else 0.0
    if discount_pct < 0:
        discount_pct = 0.0
    if discount_pct > 80:
        discount_pct = 80.0
    discount_amount = int(round(subtotal * (discount_pct / 100.0)))
    total = subtotal - discount_amount
    return {
        "phone_id": item.get("id"),
        "unit_price_vnd": price,
        "quantity": q,
        "subtotal_vnd": subtotal,
        "discount_percent": discount_pct,
        "discount_vnd": discount_amount,
        "total_vnd": total,
        "formatted": {"unit": vnd(price), "subtotal": vnd(subtotal), "discount": vnd(discount_amount), "total": vnd(total)},
    }


def tool_compare_phones(phone_id_a: str, phone_id_b: str) -> Dict[str, Any]:
    a = get_by_id(phone_id_a)
    b = get_by_id(phone_id_b)
    if not a or not b:
        return {
            "error": "NOT_FOUND",
            "missing": [pid for pid, it in [(phone_id_a, a), (phone_id_b, b)] if not it],
        }
    sa = summarize_item(a)
    sb = summarize_item(b)
    return {"a": sa, "b": sb}


def tool_list_brands() -> Dict[str, Any]:
    return {"brands": list_brands()}


def build_phone_tools() -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = [
        {
            "name": "search_phones",
            "description": "Search phones in catalog by text query (brand/model/variant). Args: {query: string, limit?: int}. Returns matching phones with ids.",
            "fn": tool_search_phones,
        },
        {
            "name": "get_phone_details",
            "description": "Get phone details by phone_id. Args: {phone_id: string}. Returns price, stock, and key specs.",
            "fn": tool_get_phone_details,
        },
        {
            "name": "check_stock",
            "description": "Check current stock for a phone_id. Args: {phone_id: string}. Returns stock count.",
            "fn": tool_check_stock,
        },
        {
            "name": "quote_order",
            "description": "Quote total price for buying phones. Args: {phone_id: string, quantity: int, coupon_percent?: number}. Returns subtotal/discount/total.",
            "fn": tool_quote_order,
        },
        {
            "name": "compare_phones",
            "description": "Compare two phones by id. Args: {phone_id_a: string, phone_id_b: string}. Returns both summaries for side-by-side reasoning.",
            "fn": tool_compare_phones,
        },
        {
            "name": "list_brands",
            "description": "List available brands in the phone catalog. Args: {}. Returns brand names.",
            "fn": tool_list_brands,
        },
    ]
    return catalog + build_web_tools()

