from __future__ import annotations

from typing import Optional

from src.core.llm_provider import LLMProvider


class PhoneChatbot:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def system_prompt(self) -> str:
        return (
            "You are VinUni Phone Store Chatbot.\n"
            "You answer questions about phones.\n"
            "If you are not sure about a price/stock/spec, say you are not sure.\n"
            "Be concise.\n"
        )

    def run(self, user_input: str) -> str:
        res = self.llm.generate(user_input, system_prompt=self.system_prompt())
        return (res.get("content") or "").strip()

