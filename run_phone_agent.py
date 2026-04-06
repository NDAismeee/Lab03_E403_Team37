import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.tools.phone_tools import build_phone_tools


def _build_provider():
    provider = (os.getenv("DEFAULT_PROVIDER") or "openai").strip().lower()
    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider
        return OpenAIProvider(model_name=os.getenv("OPENAI_MODEL", "gpt-4o"), api_key=os.getenv("OPENAI_API_KEY"))
    if provider in {"gemini", "google"}:
        from src.core.gemini_provider import GeminiProvider
        return GeminiProvider(model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"), api_key=os.getenv("GEMINI_API_KEY"))
    if provider == "local":
        from src.core.local_provider import LocalProvider
        return LocalProvider(model_path=os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf"))
    raise ValueError(f"Unknown DEFAULT_PROVIDER: {provider}")


def main():
    load_dotenv()
    agent = ReActAgent(llm=_build_provider(), tools=build_phone_tools(), max_steps=int(os.getenv("AGENT_MAX_STEPS", "6")))
    print("VinUni Phone Store Agent. Type 'exit' to quit.")
    while True:
        user = input("\nYou: ").strip()
        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            break
        out = agent.run(user)
        print(f"Agent: {out}")


if __name__ == "__main__":
    main()

