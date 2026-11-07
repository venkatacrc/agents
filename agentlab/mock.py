"""Helpers for mock policies: functions that play the model's part offline.

A policy gets exactly what a real model gets, the messages and the tool
definitions, and returns what a model would: text, or tool calls. Keeping that
contract honest is what makes the labs meaningful: if your harness forgets to
pass a tool result back, the mock can't see it either and gets stuck, just as a
real model would.
"""
from __future__ import annotations

import json

from .llm import Reply, ToolCall


def call(tool_name: str, /, **args) -> ToolCall:
    return ToolCall(name=tool_name, args=args)


def say(text: str) -> Reply:
    return Reply(text=text)


def system_text(messages) -> str:
    return "\n".join(m.get("content") or "" for m in messages if m["role"] == "system")


def first_user(messages) -> str:
    return next((m.get("content") or "" for m in messages if m["role"] == "user"), "")


def last_user(messages) -> str:
    return next((m.get("content") or "" for m in reversed(messages) if m["role"] == "user"), "")


def tool_results(messages) -> list:
    """[(tool name, content)] in order, for every tool message in the conversation."""
    return [(m.get("name", ""), m.get("content") or "") for m in messages if m["role"] == "tool"]


def results_of(messages, name: str) -> list:
    return [c for n, c in tool_results(messages) if n == name]


def calls_made(messages) -> list:
    out = []
    for m in messages:
        for c in m.get("tool_calls") or []:
            f = c["function"]
            args = json.loads(f["arguments"]) if isinstance(f["arguments"], str) else f["arguments"]
            out.append(ToolCall(name=f["name"], args=args, id=c.get("id", "")))
    return out


def tool_names(tools) -> list:
    return [t.name if hasattr(t, "name") else t["function"]["name"] for t in tools or []]


def all_text(messages) -> str:
    """Everything the model can currently see, as one string."""
    return "\n".join((m.get("content") or "") for m in messages)
