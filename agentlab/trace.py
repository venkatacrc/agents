"""Print a run as it happens: each model step, each tool call and result.

    run_agent(..., on_event=Printer())
"""
from __future__ import annotations

import json
import os
import sys

from . import tokens

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def short(s, n=160) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def fmt_call(call) -> str:
    args = ", ".join(f"{k}={json.dumps(v)}" for k, v in call.args.items())
    return f"{call.name}({args})"


class Printer:
    def __init__(self, width: int = 160, show_context: bool = True):
        self.step = 0
        self.width = width
        self.show_context = show_context

    def __call__(self, kind, payload, messages):
        if kind == "assistant":
            self.step += 1
            head = f"[{self.step}] model"
            lines = []
            if payload.text and payload.tool_calls:
                lines.append(_c(36, short(payload.text, self.width)))
            lines += [f"→ {_c(33, fmt_call(c))}" for c in payload.tool_calls]
            if not payload.tool_calls:
                lines.append(_c(32, "answer: " + short(payload.text, self.width)))
            ctx = f"  {_c(90, f'[context {tokens.count_messages(messages):,} tok]')}" if self.show_context else ""
            for i, line in enumerate(lines):
                print(f"{_c(1, head) if i == 0 else ' ' * len(head)}  {line}{ctx if i == 0 else ''}")
        elif kind == "tool":
            call, result = payload
            print(f"    {_c(90, 'tool')}   ← {short(result, self.width)}")
        else:
            print(f"    {_c(35, kind)}  {short(payload, self.width)}")
