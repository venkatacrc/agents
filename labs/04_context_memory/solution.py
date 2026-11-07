"""Lab 04 reference: shape tool output, and compact the history when it outgrows a budget."""
import re

from agentlab import tokens


def clip(text, max_tokens, keep=r"ERROR|WARN|Traceback", head=3, tail=3):
    if tokens.count(text) <= max_tokens:
        return text
    lines = text.splitlines()
    pattern = re.compile(keep)
    out, skipped = [], 0
    for i, line in enumerate(lines):
        if i < head or i >= len(lines) - tail or pattern.search(line):
            if skipped:
                out.append(f"[... {skipped} lines elided ...]")
                skipped = 0
            out.append(line)
        else:
            skipped += 1
    return "\n".join(out)


def split_point(messages, keep_last):
    """Index where the kept tail starts, moved back so no tool result loses the call that asked for it."""
    i = max(2, len(messages) - keep_last)
    while i > 2 and messages[i]["role"] == "tool":
        i -= 1
    return i


def compact(messages, budget, summarize, keep_last=6):
    if tokens.count_messages(messages) <= budget:
        return messages
    i = split_point(messages, keep_last)
    middle = messages[2:i]
    if not middle:
        return messages
    note = {"role": "user", "content": "[Summary of earlier work]\n" + summarize(middle)}
    return messages[:2] + [note] + messages[i:]
