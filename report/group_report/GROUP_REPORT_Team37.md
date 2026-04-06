# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: Team 37
- **Team Members**: [Nguyen Duc Anh - 2A202600146]
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

We built a **phone-store assistant** with a **baseline chatbot** (single LLM call, no tools) and a **ReAct agent** that uses **catalog tools** (`data/phones.json`) plus **optional web tools** (DuckDuckGo instant answer, Wikipedia summary, URL fetch) when the question goes beyond the catalog.

**Telemetry note (this report):** Metrics below count **only successful remote LLM API calls**, identified by log events of type **`LLM_METRIC`** in `logs/2026-04-06.log` (OpenAI Chat Completions that returned usage). Failed requests (e.g. `WEB_INIT_ERROR`, `LLM_NOT_READY`, `WEB_RUNTIME_ERROR`) are **excluded**. The chatbot path in the current codebase does **not** emit `LLM_METRIC`; therefore **token/latency aggregates are for the agent’s LLM calls** during the logged sessions.

- **Successful LLM API calls (OpenAI)**: **23** (`LLM_METRIC` events)
- **Agent conversation sessions logged (`AGENT_START` with `gpt-4o-mini`)**: **6** (excluding the early local-model `AGENT_START` that has no `LLM_METRIC` in this file)
- **Key outcome**: On **in-catalog** queries (e.g. iPhone 15 / 17 price, multi-step quote), the agent **grounded answers in tool output** (prices in VND, stock, `quote_order`). On **out-of-catalog / news** queries, results depended on **web tool coverage**; we observed **invalid JSON shapes** from the model (`AGENT_PARSE_ERROR`, e.g. `type: "web_duckduckgo"` instead of `type: "action"`), which increased steps and tokens until the model emitted a valid `action`.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

The agent runs a **Thought → Action (JSON) → Observation** loop in `src/agent/agent.py`:

1. The LLM must return **one JSON object per step**: either `{"type":"action",...}` or `{"type":"final",...}`.
2. On `action`, the named tool runs; the **observation** (JSON) is appended to the scratchpad.
3. On `final`, the user-facing answer is returned.
4. Each successful LLM round trip is logged as **`LLM_METRIC`** (tokens, latency, mock cost).

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `search_phones` | `{ query, limit? }` | Find models in the **store catalog** (`data/phones.json`). |
| `get_phone_details` | `{ phone_id }` | Price, stock, key specs for a catalog `phone_id`. |
| `check_stock` | `{ phone_id }` | Stock count. |
| `quote_order` | `{ phone_id, quantity, coupon_percent? }` | Subtotal / discount / total for purchases. |
| `compare_phones` | `{ phone_id_a, phone_id_b }` | Side-by-side catalog comparison. |
| `list_brands` | `{}` | Brands present in the catalog. |
| `web_duckduckgo` | `{ query }` | External **instant-answer** style lookup (not the catalog). |
| `wikipedia_search_summary` | `{ query, limit? }` | English Wikipedia search + short extracts. |
| `fetch_url_text` | `{ url, max_chars? }` | HTTPS page text excerpt (user-supplied or trusted URLs). |

### 2.3 LLM Providers Used

- **Primary (logged runs)**: **OpenAI** `gpt-4o-mini` (see `LLM_METRIC` → `provider: openai`, `model: gpt-4o-mini`).
- **Secondary / local (lab)**: **Local GGUF** via `llama-cpp-python` when `DEFAULT_PROVIDER=local` (not represented by `LLM_METRIC` in this log file for the early `AGENT_START` line).

---

## 3. Telemetry & Performance Dashboard

*Computed from **`LLM_METRIC` only** (successful OpenAI completions with usage) in `logs/2026-04-06.log`.*

| Metric | Value |
| :--- | :--- |
| **Successful LLM API calls** | **23** |
| **Total prompt tokens** | **15,382** |
| **Total completion tokens** | **1,054** |
| **Total tokens** | **16,436** |
| **Average tokens per LLM call** | **≈ 714.6** |
| **Average latency (per LLM call)** | **≈ 2,147 ms** |
| **Median latency (P50)** | **1,865 ms** |
| **Min / Max latency** | **1,040 ms / 6,438 ms** |
| **Sum of mock `cost_estimate` (lab formula)** | **≈ $0.164** *(dummy: \(total\_tokens / 1000 \times 0.01\) in code)* |

**Interpretation:** Multi-step agent tasks (e.g. search → quote, or parse-error recovery loops) **multiply** LLM calls, so **total latency** for a user question is the **sum** of per-step latencies, not a single P50.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study A: Environment / dependency (`WEB_INIT_ERROR`)

- **Observation**: `No module named 'openai'` / missing OpenAI SDK during `web_app` startup.
- **Root cause**: The Python environment running `uvicorn` did not have the **`openai`** package installed while `DEFAULT_PROVIDER=openai`.
- **Fix**: `python -m pip install openai` (or `pip install -r requirements.txt`) in the **same** venv as the server.

### Case Study B: Chatbot runtime (`WEB_RUNTIME_ERROR`)

- **Input**: Long user message about iPhone 17 discount (multiple newlines).
- **Observation**: OpenAI **400** “could not parse the JSON body” from the client library.
- **Root cause**: Transient client/API payload issue during that request (needs reproduction); **agent** path in the same window still produced **`LLM_METRIC`** immediately after, so the failure was isolated to the **chatbot** request path for that attempt.

### Case Study C: Schema violation → `AGENT_PARSE_ERROR` (`unknown_type`)

- **Input**: “Iran and America war recently”, “COVID-19”.
- **Observation**: Model emitted JSON like `{"type":"web_duckduckgo",...}` instead of **`type: "action"`** + **`tool: "web_duckduckgo"`**.
- **Root cause**: Output contract drift; only `action` / `final` are accepted.
- **Impact**: Extra LLM calls until valid `action` (see **11** `AGENT_PARSE_ERROR` lines in this log), increasing tokens and latency.

### Case Study D: Web tools empty results

- **Observation**: `web_duckduckgo` returned **no instant answer** for geopolitical news queries; `wikipedia_search_summary` returned **no title match** for a vague query string.
- **Root cause**: **DuckDuckGo instant answer** is often empty for news-like queries; **Wikipedia** needs a matchable title/query.
- **Mitigation (product)**: Add a **paid search API** or stricter **query rewriting** + fallback to `fetch_url_text` with curated URLs.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Catalog-only vs catalog + web

- **Diff**: Adding `web_duckduckgo`, `wikipedia_search_summary`, `fetch_url_text` beyond the catalog.
- **Result**: Agent can **attempt** external grounding; **quality** depends on tool/API coverage. **Format errors** (`unknown_type`) showed up when the model ignored the JSON schema.

### Experiment 2: Chatbot vs Agent (qualitative, from same UI)

| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| In-catalog price (iPhone 15 / 17) | General knowledge / “not sure” | Tool-grounded VND price + stock | **Agent** |
| Multi-step (price × quantity + discount) | Weak without tools | `quote_order` totals | **Agent** |
| Breaking news / politics | Prose / caveats | Limited by DDG/Wikipedia; parse loops possible | **Depends** (infra) |

---

## 6. Production Readiness Review

- **Security**: Restrict `fetch_url_text` to **HTTPS**, block internal IPs in production, cap response size (already bounded in tool).
- **Guardrails**: `max_steps` on the agent; monitor **`AGENT_PARSE_ERROR`** rate; add **JSON repair** or **stricter** system prompt / few-shot for `action` shape.
- **Scaling**: Externalize catalog to a **database**; add **caching** for web tool results; consider **LangGraph**-style state machine if branching grows.
- **Observability**: Ensure **both** chatbot and agent paths emit **`LLM_METRIC`** if you need apples-to-apples cost comparisons (currently agent-centric in logs).

---