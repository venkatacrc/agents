"""The agent loop (the reference answer to Lab 02).

    while not done:
        reply = model(messages, tools)            # think, maybe ask for tools
        messages.append(reply)
        if no tool calls: return reply.text        # the model decided it is finished
        for call in reply.tool_calls:              # act
            messages.append(tool result)           # observe

Everything later in the course (planning, approvals, sub-agents, compaction)
is a change to one of these few lines.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .llm import LLM, tool_message
from .tools import Toolbox

DEFAULT_SYSTEM = (
    "You are a helpful agent. Use the tools when they help; call several at once when they are independent. "
    "When you have the answer, reply with it directly and call no tools."
)


@dataclass
class Run:
    answer: str
    messages: list
    steps: int = 0
    tool_calls: int = 0
    stopped: str = "answer"  # "answer", "max_steps", or why a later lab paused the run
    extra: dict = field(default_factory=dict)


def run_agent(llm: LLM, tools, task: str, system: str = DEFAULT_SYSTEM, max_steps: int = 10,
              messages: Optional[list] = None, execute: Optional[Callable] = None,
              on_event: Optional[Callable] = None, compact: Optional[Callable] = None) -> Run:
    """execute(call) -> str runs a tool (default: the Toolbox); compact(messages) -> messages
    rewrites the history before each model call (Lab 04)."""
    box = tools if isinstance(tools, Toolbox) else Toolbox(tools)
    execute = execute or box.run
    if messages is None:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    run = Run(answer="", messages=messages)
    for _ in range(max_steps):
        if compact:
            messages[:] = compact(messages)
        reply = llm.chat(messages, list(box))
        run.steps += 1
        messages.append(reply.message())
        if on_event:
            on_event("assistant", reply, messages)
        if not reply.tool_calls:
            run.answer = reply.text
            return run
        for call in reply.tool_calls:
            result = execute(call)
            run.tool_calls += 1
            messages.append(tool_message(call, result))
            if on_event:
                on_event("tool", (call, result), messages)
    run.stopped = "max_steps"
    run.answer = f"(stopped after {max_steps} steps without a final answer)"
    return run
