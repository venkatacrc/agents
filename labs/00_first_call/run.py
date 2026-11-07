"""Check Lab 00 and look at what a model really reads.  Usage: python labs/00_first_call/run.py [--solution] [--model ...]"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm, tokens  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, todo_hint  # noqa: E402
from agentlab.mock import results_of, say  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
mine = load_impl(__file__, args.solution)
ref = load_impl(__file__, True)

TOOLS = [lookup, calculator]
CHAT = [
    {"role": "system", "content": "You are a helpful agent."},
    {"role": "user", "content": "How much HBM do 8 H100s have in total?"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": '{"topic": "H100"}'}}]},
    {"role": "tool", "tool_call_id": "call_1", "name": "lookup", "content": lookup(topic="H100")},
]

try:
    for case in (CHAT[:2], CHAT, CHAT + [CHAT[3]]):
        for tools in (None, TOOLS):
            got, want = mine.render_chat(case, tools), ref.render_chat(case, tools)
            if got != want:
                print("your render differs from the reference. First difference:")
                i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
                print(f"  yours:     {got[max(0, i - 40):i + 40]!r}\n  reference: {want[max(0, i - 40):i + 40]!r}")
                raise SystemExit(1)
except NotImplementedError as e:
    todo_hint(e, __file__)
print("correctness: matches the ChatML reference for 6 conversations, with and without tools\n")

prompt = mine.render_chat(CHAT, TOOLS)
print(prompt)
no_tools = tokens.count(mine.render_chat(CHAT, None))
total = tokens.count(prompt)
tool_tok = total - no_tools
special = prompt.count("<|im_start|>") + prompt.count("<|im_end|>")
print(f"prompt tokens (approx): {total}   from tool definitions: {tool_tok} ({100 * tool_tok / total:.0f}%)   "
      f"chat-template special tokens: {special}")


def policy(messages, tools):
    fact = results_of(messages, "lookup")
    return say("Each H100 has 80 GB of HBM3, so 8 of them have 640 GB." if fact else "Let me look that up.")


llm = get_llm(args.model, policy)
reply = llm.chat(CHAT, TOOLS)
print(f"\nmodel ({args.model}) continues the prompt with:\n  {reply.text.strip() or reply.tool_calls}")
print(f"  prompt tokens: {reply.prompt_tokens} ({'reported by the server' if args.model != 'mock' else 'our estimate'})")

record(prompt_tokens=total, tool_tokens=tool_tok, special_tokens=special)
report(
    "a model only ever sees one flat string: messages and tool schemas are rendered into it by the chat "
    "template, and tool calls are just text the model was trained to write between special tags",
    f"{total} prompt tokens for a 4-message chat, {tool_tok} of them ({100 * tool_tok / total:.0f}%) are the two tool "
    f"definitions, re-sent on every call; {special} special tokens",
    "PASS",
    "run with --model ollama:gpt-oss:20b (or vllm:/sglang: with your own server) and compare the server's "
    "prompt token count with our estimate; then read the model's real template (tokenizer_config.json, chat_template)",
)
