"""Lab 04: context engineering. The context window is the agent's working memory, and it fills up.

Run:  python labs/04_context_memory/run.py             (your code)
      python labs/04_context_memory/run.py --solution

Two tools against a growing history:
  clip     keep a tool's output small, but keep the lines that matter
  compact  when the history passes a budget, replace the middle with a summary
"""
import re  # noqa: F401

from agentlab import tokens  # noqa: F401  tokens.count(text), tokens.count_messages(messages)


def clip(text, max_tokens, keep=r"ERROR|WARN|Traceback", head=3, tail=3):
    """Return text unchanged if it fits in max_tokens; otherwise keep the first `head` lines, the last
    `tail` lines and every line matching `keep`, with "[... N lines elided ...]" for each gap."""
    # TODO 1
    raise NotImplementedError("clip")


def split_point(messages, keep_last):
    """Where the kept recent tail starts: len(messages) - keep_last, but never before index 2
    (system + task), and moved *back* while it points at a "tool" message. A tool result without the
    assistant message that called it is an invalid conversation; real APIs reject it."""
    # TODO 2
    raise NotImplementedError("split_point")


def compact(messages, budget, summarize, keep_last=6):
    """If tokens.count_messages(messages) > budget, return
        messages[:2] + [{"role": "user", "content": "[Summary of earlier work]\\n" + summarize(middle)}] + tail
    where tail = messages[split_point(...):] and middle is everything between. Otherwise return messages.
    summarize(list_of_messages) -> str is an LLM call that run.py provides."""
    # TODO 3
    raise NotImplementedError("compact")
