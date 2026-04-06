# Lab 3: Chatbot vs ReAct Agent — Phone Store Demo

Course lab: compare a **baseline chatbot** (single LLM call, no tools) with a **ReAct-style agent** that uses **catalog tools** and optional **web tools**, with **JSON logs** under `logs/`.

**Domain:** VinUni Phone Store — mock inventory in `data/phones.json`, tools in `src/tools/`.

## Features

- **ReAct loop** (`src/agent/agent.py`): JSON `action` / `final` steps, tool execution, scratchpad observations.
- **Catalog tools:** search, details, stock, quote, compare, list brands.
- **Web tools (beyond catalog):** DuckDuckGo instant answer, Wikipedia summary, HTTPS URL text fetch (`src/tools/web_tools.py`).
- **Providers:** OpenAI, Gemini (`DEFAULT_PROVIDER=gemini` or `google`), local GGUF via `llama-cpp-python` (`DEFAULT_PROVIDER=local`).
- **Web UI:** two-column chatbot vs agent — `web_app.py` + `frontend/index.html`.
- **Telemetry:** `IndustryLogger` + `LLM_METRIC` events in daily log files.

## Requirements

- Python **3.10+** (3.12 recommended)
- For **OpenAI** or **Gemini:** API keys in `.env` (never commit `.env`)
- For **local:** a `.gguf` model file and a working `llama-cpp-python` install (Windows may need MSVC build tools)

## Quick start

### 1. Clone and virtual environment

```bash
cd Day-3-Lab-Chatbot-vs-react-agent
python -m venv .venv
```

Activate:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

### 2. Environment variables

Copy the example file and edit **only on your machine**:

```bash
copy .env.example .env
```

On macOS/Linux use `cp .env.example .env`.

| Variable | Purpose |
| :--- | :--- |
| `DEFAULT_PROVIDER` | `openai` \| `gemini` or `google` \| `local` |
| `OPENAI_API_KEY` | Required if `openai` |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini` |
| `GEMINI_API_KEY` | Required if `gemini` / `google` |
| `GEMINI_MODEL` | e.g. `gemini-1.5-flash` |
| `LOCAL_MODEL_PATH` | Path to `.gguf` if `local` |
| `AGENT_MAX_STEPS` | Optional; default `6` |

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

If `llama-cpp-python` fails to build on Windows, use **OpenAI/Gemini** for the demo, or install build tools and retry. For a split install without local wheels, you can keep only API providers and skip local.

### 4. Run the web demo (recommended)

```bash
python -m uvicorn web_app:app --reload
```

Open **http://127.0.0.1:8000/** — left: chatbot, right: agent.

### 5. Run the agent in the terminal

```bash
python run_phone_agent.py
```

## Project layout

| Path | Role |
| :--- | :--- |
| `data/phones.json` | Mock phone catalog (lab data) |
| `src/agent/agent.py` | ReAct agent |
| `src/chatbot/chatbot.py` | Baseline chatbot |
| `src/core/` | `LLMProvider` + OpenAI / Gemini / local |
| `src/tools/` | Phone + web tools |
| `src/telemetry/` | Structured logging and metrics |
| `web_app.py` | FastAPI backend |
| `frontend/index.html` | Static UI |
| `logs/` | Daily `.log` files (gitignored) |
| `report/` | Group / individual report templates and submissions |
| `SCORING.md`, `EVALUATION.md` | Rubric and metrics guidance |

## Telemetry

Logs are JSON lines, e.g. `AGENT_START`, `AGENT_TOOL_CALL`, `AGENT_PARSE_ERROR`, `LLM_METRIC`, `WEB_INIT_ERROR`. Use them for the lab write-up and failure analysis.

