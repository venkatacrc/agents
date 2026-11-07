"""Lab 00 reference: render a conversation with a ChatML chat template (Qwen 2.5 / Hermes style)."""
import json

TOOLS_HEADER = (
    "# Tools\n\n"
    "You may call one or more functions to assist with the user query.\n\n"
    "You are provided with function signatures within <tools></tools> XML tags:\n<tools>"
)
TOOLS_FOOTER = (
    "</tools>\n\n"
    "For each function call, return a json object with function name and arguments within "
    "<tool_call></tool_call> XML tags:\n<tool_call>\n"
    '{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call>'
)


def render_chat(messages, tools=None):
    out = []
    for i, m in enumerate(messages):
        role, content = m["role"], m.get("content") or ""
        if role == "system":
            if tools:
                lines = "\n".join(json.dumps(t.schema()) for t in tools)
                content = f"{content}\n\n{TOOLS_HEADER}\n{lines}\n{TOOLS_FOOTER}"
            out.append(f"<|im_start|>system\n{content}<|im_end|>\n")
        elif role == "user":
            out.append(f"<|im_start|>user\n{content}<|im_end|>\n")
        elif role == "assistant":
            parts = [content] if content else []
            for c in m.get("tool_calls") or []:
                f = c["function"]
                call = {"name": f["name"], "arguments": json.loads(f["arguments"])}
                parts.append(f"<tool_call>\n{json.dumps(call)}\n</tool_call>")
            out.append("<|im_start|>assistant\n" + "\n".join(parts) + "<|im_end|>\n")
        elif role == "tool":
            # Consecutive tool results share one user turn.
            first = i == 0 or messages[i - 1]["role"] != "tool"
            last = i == len(messages) - 1 or messages[i + 1]["role"] != "tool"
            out.append(("<|im_start|>user" if first else "") +
                       f"\n<tool_response>\n{content}\n</tool_response>" +
                       ("<|im_end|>\n" if last else ""))
    out.append("<|im_start|>assistant\n")
    return "".join(out)
