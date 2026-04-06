# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyen Duc Anh
- **Student ID**: 2A202600146
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

I contributed to the **VinUni Phone Store** baseline: a **single-turn chatbot** for comparison, a **ReAct agent** with **strict JSON** actions, **catalog-backed tools**, **optional web tools** for queries outside the mock inventory, **structured logging**, and a **small FastAPI web UI** to demo chatbot vs agent side by side.

- **Modules implemented / extended**:
  - `src/agent/agent.py` — ReAct loop: LLM returns `{"type":"action"}` or `{"type":"final"}`; parses JSON (including fenced blocks); executes `tool["fn"](**args)`; appends observations; logs `AGENT_*` and drives `LLM_METRIC` via the shared tracker.
  - `src/tools/phone_catalog.py`, `src/tools/phone_tools.py` — Load `data/phones.json`, search/details/stock/quote/compare/list brands.
  - `src/tools/web_tools.py` — `web_duckduckgo`, `wikipedia_search_summary`, `fetch_url_text` (network-backed, not catalog).
  - `src/chatbot/chatbot.py` — Baseline `PhoneChatbot` with system prompt only (no tools).
  - `src/core/openai_provider.py`, `src/core/gemini_provider.py`, `src/core/local_provider.py` — Lazy imports for optional SDKs; clearer errors when a dependency is missing.
  - `web_app.py` — FastAPI routes `/api/chatbot` and `/api/agent`; init/request/runtime errors logged as `WEB_INIT_ERROR` / `WEB_REQUEST_ERROR` / `WEB_RUNTIME_ERROR`; `how_to_fix` hints from the actual failure.
  - `frontend/index.html` — Two-column UI for live demo.
  - `data/phones.json` — Mock inventory (editable for lab scenarios).

- **Code highlights**: The agent does not hallucinate catalog prices by design when tools succeed: `search_phones` / `quote_order` return structured JSON that is fed back as **Observation** before the next LLM step.

- **Documentation (interaction with ReAct)**: Tool descriptions are injected into the system prompt; each step’s observation is serialized into the scratchpad so the model can branch (e.g. search → quote → final).

---

## II. Debugging Case Study (10 Points)

- **Problem description**: During runs logged in `logs/2026-04-06.log`, the agent sometimes logged **`AGENT_PARSE_ERROR`** with **`error": "unknown_type"`**. The raw model output looked like a JSON object with **`"type":"web_duckduckgo"`** (and a `query` field) instead of the required shape **`{"type":"action","tool":"web_duckduckgo","args":{"query":"..."}}`**.

- **Log source**: `logs/2026-04-06.log` — events `AGENT_PARSE_ERROR` alongside `AGENT_LLM_OUTPUT` for steps where the user asked for **non-catalog** topics (e.g. geopolitics or general COVID-19 info). Example pattern: model invents a new top-level `type` name instead of nesting the tool under `action`.

- **Diagnosis**: The failure is **not** the Python parser itself; it is **contract drift** in the LLM output. The system prompt allows only `action` and `final`. Smaller models (or rushed completions) “shortcut” by mimicking tool names as `type`. Web-style queries also **stress** the prompt because they pull the model toward free-form answers.

- **Solution**: (1) **Tighten the system prompt** with one-line few-shot: always use `"type":"action"` + `"tool":"web_duckduckgo"` + `"args":{"query":"..."}`. (2) Optionally add a **repair step**: on `unknown_type`, prepend a one-line system reminder in the next user message (already partially mitigated by feeding `PARSE_ERROR` into the scratchpad). (3) For production, use **JSON schema** / **tool-calling API** from the provider instead of free-text JSON.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: A plain chatbot answers in **one shot** from parametric memory; it may be right, vague, or outdated. The ReAct-style agent exposes **intermediate structure** (`thought` + tool choice). Even when the final answer is imperfect, the trace shows **what it tried**, which is essential for debugging and grading.

2. **Reliability — when the agent was worse**: (a) **Higher latency and cost**: each tool step is an extra LLM call (see multiple `LLM_METRIC` rows per user question). (b) **Parse loops**: invalid JSON wastes steps and can hit `max_steps`. (c) **Simple chit-chat**: a chatbot can answer faster without tool overhead; the agent may over-call tools if the prompt is not scoped.

3. **Observation**: Tool **observations** are the ground truth for our lab store: empty `search_phones` forces a different strategy (web tools or “not in catalog”). Wrong JSON triggers an explicit **PARSE_ERROR** observation, which nudges the model toward valid `action` shapes in later steps.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Move `phones.json` to a **database**; add **async** tool execution and streaming partial answers to the UI; queue long-running `fetch_url_text` jobs.

- **Safety**: Allow-list **domains** for `fetch_url_text`; rate-limit web tools; **PII redaction** in logs; optional **human approval** before executing high-risk tools.

- **Performance**: **Cache** Wikipedia/DDG results by query hash; reduce prompt size by **dynamic tool injection** (only relevant tools per turn); use provider-native **function calling** to cut parse errors; **RAG** over product docs for support answers without bloating the system prompt.

---
