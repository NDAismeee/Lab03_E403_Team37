import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.chatbot.chatbot import PhoneChatbot
from src.tools.phone_tools import build_phone_tools
from src.telemetry.logger import logger


class ChatRequest(BaseModel):
    message: str


def _provider_name_from_env() -> str:
    return (os.getenv("DEFAULT_PROVIDER") or "openai").strip().lower()


def _model_name_from_env() -> str:
    return (os.getenv("DEFAULT_MODEL") or "").strip()


def _how_to_fix_for(error_detail: Optional[str]) -> List[str]:
    d = (error_detail or "").lower()
    out: List[str] = []
    if "no module named 'openai'" in d or "missing dependency 'openai'" in d:
        out.append("Install OpenAI SDK in this venv: python -m pip install openai")
    if "google-generativeai" in d or "google.generativeai" in d or "missing dependency 'google-generativeai'" in d:
        out.append("Install Gemini SDK: python -m pip install google-generativeai")
    if "fastapi" in d:
        out.append("Install web server deps: python -m pip install fastapi uvicorn")
    if "model file not found" in d or "localmodel" in d.replace(" ", ""):
        out.append("Local: set LOCAL_MODEL_PATH to an existing .gguf under models/ or download Phi-3 per README.")
    if "llama" in d and "llama_cpp" in d:
        out.append("Local: python -m pip install -r requirements-local.txt (needs C++ build tools on Windows).")
    if not out:
        out.append("Install all deps: python -m pip install -r requirements.txt")
        out.append("Or use local GGUF: DEFAULT_PROVIDER=local + valid LOCAL_MODEL_PATH.")
    return out


def _build_provider():
    provider = _provider_name_from_env()
    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider

        model = os.getenv("OPENAI_MODEL") or _model_name_from_env() or "gpt-4o"
        return OpenAIProvider(model_name=model, api_key=os.getenv("OPENAI_API_KEY"))
    if provider in {"gemini", "google"}:
        from src.core.gemini_provider import GeminiProvider

        model = os.getenv("GEMINI_MODEL") or _model_name_from_env() or "gemini-1.5-flash"
        return GeminiProvider(model_name=model, api_key=os.getenv("GEMINI_API_KEY"))
    if provider == "local":
        from src.core.local_provider import LocalProvider

        return LocalProvider(model_path=os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf"))
    raise ValueError(f"Unknown DEFAULT_PROVIDER: {provider}")


load_dotenv()
llm = None
init_error = None
try:
    llm = _build_provider()
except Exception as e:
    init_error = str(e)
    logger.log_event(
        "WEB_INIT_ERROR",
        {
            "provider": _provider_name_from_env(),
            "model": _model_name_from_env() or None,
            "error": init_error,
            "traceback": traceback.format_exc(),
        },
    )

tools = build_phone_tools()
agent = ReActAgent(llm=llm, tools=tools, max_steps=int(os.getenv("AGENT_MAX_STEPS", "6"))) if llm else None
chatbot = PhoneChatbot(llm=llm) if llm else None

app = FastAPI(title="Chatbot vs Agent Demo")

frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    path = os.path.join(frontend_dir, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/chatbot")
def api_chatbot(req: ChatRequest):
    if not chatbot:
        detail = {
            "error": "LLM_NOT_READY",
            "detail": init_error,
            "how_to_fix": _how_to_fix_for(init_error),
        }
        logger.log_event("WEB_REQUEST_ERROR", {"endpoint": "/api/chatbot", "detail": detail})
        raise HTTPException(status_code=500, detail=detail)
    t0 = time.time()
    try:
        answer = chatbot.run(req.message)
    except Exception as e:
        logger.log_event(
            "WEB_RUNTIME_ERROR",
            {"endpoint": "/api/chatbot", "error": str(e), "traceback": traceback.format_exc()},
        )
        raise HTTPException(status_code=500, detail={"error": "CHATBOT_FAILED", "detail": str(e)}) from e
    t1 = time.time()
    return {
        "answer": answer,
        "provider": _provider_name_from_env(),
        "model": getattr(llm, "model_name", None) if llm else None,
        "latency_ms": int((t1 - t0) * 1000),
    }


@app.post("/api/agent")
def api_agent(req: ChatRequest):
    if not agent:
        detail = {
            "error": "LLM_NOT_READY",
            "detail": init_error,
            "how_to_fix": _how_to_fix_for(init_error),
        }
        logger.log_event("WEB_REQUEST_ERROR", {"endpoint": "/api/agent", "detail": detail})
        raise HTTPException(status_code=500, detail=detail)
    t0 = time.time()
    try:
        answer = agent.run(req.message)
    except Exception as e:
        logger.log_event(
            "WEB_RUNTIME_ERROR",
            {"endpoint": "/api/agent", "error": str(e), "traceback": traceback.format_exc()},
        )
        raise HTTPException(status_code=500, detail={"error": "AGENT_FAILED", "detail": str(e)}) from e
    t1 = time.time()
    return {
        "answer": answer,
        "provider": _provider_name_from_env(),
        "model": getattr(llm, "model_name", None) if llm else None,
        "latency_ms": int((t1 - t0) * 1000),
        "steps": getattr(agent, "last_steps", None),
    }

