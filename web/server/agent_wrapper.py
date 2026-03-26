import re
import sys
from pathlib import Path
from typing import Any

import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langfuse.langchain import CallbackHandler

ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from model import build_openrouter_model  # noqa: E402
from subagent.cypher_subagent import get_cypher_middleware  # noqa: E402
from system_prompt import system_prompt, todo_middleware_system_prompt  # noqa: E402

MARKDOWN_YAML_PATTERN = re.compile(r"```yaml\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

langfuse_callback = CallbackHandler()

agent = create_agent(
    model=build_openrouter_model(),
    middleware=[
        get_cypher_middleware(),
        TodoListMiddleware(system_prompt=todo_middleware_system_prompt),
    ],
    system_prompt=system_prompt,
)


def _extract_yaml_payload(content: str) -> dict[str, Any]:
    match = MARKDOWN_YAML_PATTERN.search(content)
    source = match.group(1) if match else content
    try:
        parsed = yaml.safe_load(source) or {}
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"message": content, "todos": [], "cypher_queries": [], "confidence": 0.0}


def _to_langchain_messages(history: list[dict[str, str]]) -> list[dict[str, str]]:
    trimmed = history[-14:]
    messages: list[dict[str, str]] = []
    for item in trimmed:
        role = item.get("role", "user")
        if role not in {"user", "assistant"}:
            continue
        messages.append({"role": role, "content": item.get("content", "")})
    return messages


async def invoke_agent(message: str, history: list[dict[str, str]]) -> dict[str, Any]:
    messages = _to_langchain_messages(history)
    messages.append({"role": "user", "content": message})
    result = agent.invoke({"messages": messages}, config={"callbacks": [langfuse_callback]})
    raw_content = result["messages"][-1].content
    parsed = _extract_yaml_payload(raw_content)
    parsed.setdefault("message", raw_content)
    parsed.setdefault("todos", [])
    parsed.setdefault("cypher_queries", [])
    parsed.setdefault("confidence", 0.0)
    parsed.setdefault("confidence_rationale", "No rationale provided.")
    return {"raw": raw_content, "parsed": parsed}
