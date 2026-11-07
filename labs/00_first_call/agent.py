"""Lab 00: turn a chat (messages + tools) into the one string the model actually reads.

Run:  python labs/00_first_call/run.py             (your code)
      python labs/00_first_call/run.py --solution

A model never sees "messages" or "tools". The server's chat template flattens
them into text with special tokens, the model continues that text, and the
server parses tool calls back out of what it wrote. This is the ChatML template
used by Qwen 2.5 and Hermes models.
"""
import json  # noqa: F401  (you will need it)

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
    """Return the prompt string for `messages`, ending with the assistant generation prompt.

    Each message becomes  <|im_start|>ROLE\\nCONTENT<|im_end|>\\n
    """
    # TODO 1: system message. If tools are given, append to its content:
    #         "\n\n" + TOOLS_HEADER + "\n" + one json.dumps(t.schema()) per line + "\n" + TOOLS_FOOTER
    # TODO 2: user messages, as-is.
    # TODO 3: assistant messages. Content (if any), then one block per tool call, joined with "\n":
    #         <tool_call>\n{"name": ..., "arguments": {...}}\n</tool_call>
    #         (arguments are stored as a JSON string in m["tool_calls"][i]["function"]["arguments"])
    # TODO 4: tool messages go back to the model in a *user* turn, each wrapped as
    #         \n<tool_response>\nCONTENT\n</tool_response>
    #         and consecutive tool messages share one <|im_start|>user ... <|im_end|>\n turn.
    # TODO 5: finish with the generation prompt "<|im_start|>assistant\n" so the model writes next.
    raise NotImplementedError("render_chat")
