from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import requests


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "VinUniPhoneAgent/1.0 (lab demo; +https://example.invalid)",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        }
    )
    return s


def tool_web_duckduckgo(query: str) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"error": "EMPTY_QUERY"}
    url = "https://api.duckduckgo.com/"
    r = _session().get(
        url,
        params={"q": q, "format": "json", "no_html": "1", "skip_disambig": "1"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    out: Dict[str, Any] = {
        "source": "duckduckgo_instant_answer",
        "query": q,
        "heading": data.get("Heading"),
        "abstract": (data.get("AbstractText") or "").strip(),
        "abstract_url": data.get("AbstractURL"),
        "answer": (data.get("Answer") or "").strip(),
    }
    related = data.get("RelatedTopics") or []
    snippets: List[str] = []
    for item in related[:8]:
        if isinstance(item, dict) and item.get("Text"):
            snippets.append(str(item["Text"])[:500])
        elif isinstance(item, str):
            snippets.append(item[:500])
    out["related_snippets"] = snippets
    if not out["abstract"] and not out["answer"] and not snippets:
        out["note"] = "No instant answer from DuckDuckGo for this query; try wikipedia_search or fetch_url on a product page."
    return out


def tool_wikipedia_search_summary(query: str, limit: int = 3) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"error": "EMPTY_QUERY"}
    lim = max(1, min(int(limit), 5))
    api = "https://en.wikipedia.org/w/api.php"
    r = _session().get(
        api,
        params={
            "action": "opensearch",
            "search": q,
            "limit": lim,
            "namespace": "0",
            "format": "json",
        },
        timeout=15,
    )
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list) or len(payload) < 2:
        return {"query": q, "results": [], "note": "Wikipedia opensearch returned empty."}
    titles = payload[1] if len(payload) > 1 else []
    descs = payload[2] if len(payload) > 2 else []
    if not titles:
        return {"query": q, "results": [], "note": "No Wikipedia titles matched."}
    results: List[Dict[str, Any]] = []
    base = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    for i, title in enumerate(titles):
        if not title:
            continue
        enc = quote(title.replace(" ", "_"), safe="")
        try:
            sr = _session().get(base + enc, timeout=15)
            if sr.status_code != 200:
                results.append({"title": title, "short": (descs[i] if i < len(descs) else "")[:800], "url": None, "extract": None})
                continue
            sj = sr.json()
            results.append(
                {
                    "title": sj.get("title") or title,
                    "short": (descs[i] if i < len(descs) else "")[:800],
                    "url": sj.get("content_urls", {}).get("desktop", {}).get("page"),
                    "extract": (sj.get("extract") or "")[:4000],
                }
            )
        except Exception:
            results.append({"title": title, "short": (descs[i] if i < len(descs) else "")[:800], "url": None, "extract": None})
    return {"query": q, "source": "wikipedia", "results": results}


def tool_fetch_url_text(url: str, max_chars: int = 6000) -> Dict[str, Any]:
    raw = (url or "").strip()
    if not raw:
        return {"error": "EMPTY_URL"}
    p = urlparse(raw)
    if p.scheme not in ("http", "https"):
        return {"error": "ONLY_HTTP_HTTPS"}
    cap = max(500, min(int(max_chars), 50000))
    r = _session().get(raw, timeout=20, allow_redirects=True)
    r.raise_for_status()
    ct = (r.headers.get("content-type") or "").lower()
    text = r.text
    if "json" in ct:
        body = text[:cap]
    else:
        text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        body = text[:cap]
    return {"url": raw, "content_type": ct, "text_excerpt": body, "truncated": len(body) >= cap}


def build_web_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "web_duckduckgo",
            "description": "External lookup via DuckDuckGo instant answer (not the store catalog). Args: {query: string}. Use for general facts, newsy queries, or when catalog has no match.",
            "fn": tool_web_duckduckgo,
        },
        {
            "name": "wikipedia_search_summary",
            "description": "Search English Wikipedia and return short extracts (not the store catalog). Args: {query: string, limit?: int 1-5}. Good for background on a phone model.",
            "fn": tool_wikipedia_search_summary,
        },
        {
            "name": "fetch_url_text",
            "description": "Fetch a public https page and return plain-text excerpt. Args: {url: string, max_chars?: int}. Use for official specs pages when user gives a URL or you need primary-source text.",
            "fn": tool_fetch_url_text,
        },
    ]
