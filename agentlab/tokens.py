"""An approximate token counter.

Real tokenizers (BPE, SentencePiece) need model files; the labs only need a
stable, offline measure of how big a context is. One token per word piece or
punctuation mark lands within about 20% of tiktoken on English and code, and it
is deterministic, so the reference numbers in the lessons match yours exactly.
"""
from __future__ import annotations

import json
import re

_PIECE = re.compile(r"<\|[^|<>\s]+\|>|\w+|[^\w\s]")  # special tokens like <|im_start|> count as one

# Chat templates wrap every message in a few special tokens
# (<|im_start|>role ... <|im_end|>), which is what this overhead stands for.
MESSAGE_OVERHEAD = 4


def count(text: str) -> int:
    return len(_PIECE.findall(text or ""))


def count_message(m: dict) -> int:
    n = MESSAGE_OVERHEAD + count(m.get("content") or "")
    for c in m.get("tool_calls") or []:
        f = c.get("function", c)
        n += count(f.get("name", "")) + count(f.get("arguments", "") if isinstance(f.get("arguments"), str)
                                              else json.dumps(f.get("arguments", {})))
    return n


def count_messages(messages: list) -> int:
    return sum(count_message(m) for m in messages)


def count_tools(tools: list) -> int:
    """Tokens the tool definitions add to every request (they are rendered into the prompt)."""
    return sum(count(json.dumps(t.schema() if hasattr(t, "schema") else t)) for t in tools or [])
