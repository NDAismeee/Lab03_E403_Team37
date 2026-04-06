import os
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []
        self.last_steps = 0

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return (
            "You are VinUni Phone Store Assistant.\n"
            "You help users choose and buy smartphones using the available tools.\n"
            "Be concise and practical.\n\n"
            "Available tools:\n"
            f"{tool_descriptions}\n\n"
            "You must output exactly one JSON object per turn, with one of two shapes:\n"
            '1) {"type":"action","tool":"<tool_name>","args":{...},"thought":"<short reasoning>"}\n'
            '2) {"type":"final","answer":"<final answer for user>","thought":"<short reasoning>"}\n\n'
            "Rules:\n"
            "- For this store's price, stock, and checkout math, use catalog tools (search_phones, get_phone_details, check_stock, quote_order) first.\n"
            "- If the user asks for information not in the catalog, or needs the outside world, use web tools: web_duckduckgo, wikipedia_search_summary, or fetch_url_text.\n"
            "- When reporting web or Wikipedia results, say they are external and may differ from the store; catalog prices are authoritative for this shop.\n"
            "- Do not invent catalog prices; web tools may still omit prices or be incomplete.\n"
            "- If catalog search returns nothing, try web tools before giving up.\n"
        )

    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        scratchpad = ""
        current_prompt = self._build_prompt(user_input=user_input, scratchpad=scratchpad)
        steps = 0
        self.last_steps = 0

        while steps < self.max_steps:
            result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )
            content = (result.get("content") or "").strip()
            logger.log_event("AGENT_LLM_OUTPUT", {"step": steps, "content": content})

            parsed, parse_error = self._parse_agent_json(content)
            if parse_error:
                logger.log_event("AGENT_PARSE_ERROR", {"step": steps, "error": parse_error, "raw": content})
                scratchpad = self._append_step(
                    scratchpad,
                    thought="Parser error",
                    action={"tool": None, "args": None},
                    observation={"error": "PARSE_ERROR", "detail": parse_error},
                )
                current_prompt = self._build_prompt(user_input=user_input, scratchpad=scratchpad)
                steps += 1
                continue

            if parsed.get("type") == "final":
                answer = (parsed.get("answer") or "").strip()
                logger.log_event("AGENT_FINAL", {"step": steps, "answer": answer})
                logger.log_event("AGENT_END", {"steps": steps + 1})
                self.last_steps = steps + 1
                return answer or "I couldn't produce a final answer."

            if parsed.get("type") != "action":
                scratchpad = self._append_step(
                    scratchpad,
                    thought=parsed.get("thought") or "",
                    action={"tool": None, "args": None},
                    observation={"error": "INVALID_TYPE"},
                )
                current_prompt = self._build_prompt(user_input=user_input, scratchpad=scratchpad)
                steps += 1
                continue

            tool_name = parsed.get("tool")
            tool_args = parsed.get("args") or {}
            thought = parsed.get("thought") or ""
            observation = self._execute_tool(tool_name=tool_name, args=tool_args)
            logger.log_event(
                "AGENT_TOOL_CALL",
                {"step": steps, "tool": tool_name, "args": tool_args, "observation": observation},
            )
            scratchpad = self._append_step(
                scratchpad,
                thought=thought,
                action={"tool": tool_name, "args": tool_args},
                observation=observation,
            )
            current_prompt = self._build_prompt(user_input=user_input, scratchpad=scratchpad)
            steps += 1
            
        logger.log_event("AGENT_END", {"steps": steps})
        self.last_steps = steps
        return "I couldn't finish within the step limit. Please rephrase or ask a narrower phone question."

    def _execute_tool(self, tool_name: Optional[str], args: Dict[str, Any]) -> Any:
        if not tool_name:
            return {"error": "NO_TOOL_SPECIFIED"}
        for tool in self.tools:
            if tool['name'] == tool_name:
                fn = tool.get("fn")
                if not callable(fn):
                    return {"error": "TOOL_NOT_CALLABLE", "tool": tool_name}
                try:
                    return fn(**args)
                except TypeError as e:
                    return {"error": "INVALID_TOOL_ARGS", "tool": tool_name, "detail": str(e)}
                except Exception as e:
                    return {"error": "TOOL_EXECUTION_ERROR", "tool": tool_name, "detail": str(e)}
        return {"error": "TOOL_NOT_FOUND", "tool": tool_name}

    def _build_prompt(self, user_input: str, scratchpad: str) -> str:
        if scratchpad.strip():
            return f"User request:\n{user_input}\n\nSteps so far:\n{scratchpad}\n"
        return f"User request:\n{user_input}\n"

    def _append_step(self, scratchpad: str, thought: str, action: Dict[str, Any], observation: Any) -> str:
        step = {
            "thought": (thought or "").strip(),
            "action": action,
            "observation": observation,
        }
        return (scratchpad + "\n" if scratchpad else "") + json.dumps(step, ensure_ascii=False)

    def _parse_agent_json(self, text: str) -> Tuple[Dict[str, Any], Optional[str]]:
        cleaned = text.strip()
        cleaned = re.sub(r"^\s*```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        obj_str, extract_err = self._extract_first_json_object(cleaned)
        if extract_err:
            return {}, extract_err
        try:
            data = json.loads(obj_str)
        except Exception as e:
            return {}, f"json_loads_failed: {e}"

        if not isinstance(data, dict):
            return {}, "json_not_object"

        t = data.get("type")
        if t == "action":
            if not isinstance(data.get("tool"), str):
                return {}, "action_missing_tool"
            if "args" in data and not isinstance(data.get("args"), dict):
                return {}, "action_args_not_object"
            return data, None
        if t == "final":
            if not isinstance(data.get("answer"), str):
                return {}, "final_missing_answer"
            return data, None
        return {}, "unknown_type"

    def _extract_first_json_object(self, text: str) -> Tuple[str, Optional[str]]:
        start = text.find("{")
        if start == -1:
            return "", "no_json_object_start"
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1], None
        return "", "unterminated_json_object"
