"""Check Lab 01: schemas, parsing a corpus of real-world tool-call outputs, validation.

Usage: python labs/01_tool_calling/run.py [--solution] [--model ollama:NAME]
"""
import json
import pathlib
import sys
from typing import List, Literal, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.tools import function_schema as reference_schema  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)


def book_gpu(gpu: Literal["H100", "A100", "B200"], hours: int, region: str = "us-east",
             notify: Optional[List[str]] = None) -> str:
    """Reserve GPUs on the cluster.

    Args:
        gpu: which GPU type to reserve
        hours: how many hours, a whole number
        region: the data center region
        notify: email addresses to tell when the job starts
    """
    return f"booked {gpu} for {hours} h in {region}"


def kv_bytes(layers: int, kv_heads: int, head_dim: int, tokens: int, bytes_per_value: float = 2.0) -> float:
    """KV cache size in bytes.

    Args:
        layers: transformer layers
        kv_heads: key/value heads per layer
        head_dim: dimension of each head
        tokens: tokens in the cache
        bytes_per_value: 2 for BF16, 1 for FP8
    """
    return 2 * layers * kv_heads * head_dim * tokens * bytes_per_value


# Outputs collected from different model families and failure modes. Expected: list of calls, or "error".
CORPUS = [
    ("Hermes / Qwen tags", '<tool_call>\n{"name": "lookup", "arguments": {"topic": "H100"}}\n</tool_call>',
     [("lookup", {"topic": "H100"})]),
    ("two parallel calls", '<tool_call>\n{"name": "lookup", "arguments": {"topic": "H100"}}\n</tool_call>\n'
                           '<tool_call>\n{"name": "lookup", "arguments": {"topic": "A100"}}\n</tool_call>',
     [("lookup", {"topic": "H100"}), ("lookup", {"topic": "A100"})]),
    ("markdown fence", 'Sure! Let me compute that.\n```json\n{"name": "calculator", "arguments": {"expression": "2+2"}}\n```',
     [("calculator", {"expression": "2+2"})]),
    ("prose before JSON", "I'll look it up for you. {\"name\": \"lookup\", \"arguments\": {\"topic\": \"B200\"}}",
     [("lookup", {"topic": "B200"})]),
    ("bare JSON, Llama 'parameters'", '{"name": "lookup", "parameters": {"topic": "L4"}}',
     [("lookup", {"topic": "L4"})]),
    ("arguments as a JSON string", '{"name": "calculator", "arguments": "{\\"expression\\": \\"3*4\\"}"}',
     [("calculator", {"expression": "3*4"})]),
    ("trailing comma", '<tool_call>{"name": "lookup", "arguments": {"topic": "A100",}}</tool_call>',
     [("lookup", {"topic": "A100"})]),
    ("Python-style quotes", "{'name': 'lookup', 'arguments': {'topic': 'H100'}}",
     [("lookup", {"topic": "H100"})]),
    ("plain final answer", "The H100 has 80 GB of HBM3.", []),
    ("cut off by max_tokens", '<tool_call>{"name": "lookup", "arguments": {"topic": "H1', "error"),
    ("Llama 3 python_tag", '<|python_tag|>{"name": "calculator", "parameters": {"expression": "7*6"}}',
     [("calculator", {"expression": "7*6"})]),
    ("braces inside a string", 'Checking. {"name": "lookup", "arguments": {"topic": "kv cache {per token}"}}',
     [("lookup", {"topic": "kv cache {per token}"})]),
]


def naive_parse(text):
    try:
        obj = json.loads(text)
        return [{"name": obj["name"], "arguments": obj.get("arguments", {})}], None
    except (json.JSONDecodeError, KeyError, TypeError):
        return [], None


def score(parse):
    rows, ok = [], 0
    for name, text, want in CORPUS:
        try:
            calls, err = parse(text)
        except Exception as e:  # noqa: BLE001
            calls, err, crashed = [], str(e), True
        else:
            crashed = False
        if want == "error":
            good = err is not None and not crashed
        else:
            good = not crashed and err is None and [(c["name"], c["arguments"]) for c in calls] == want
        ok += good
        rows.append((name, "ok" if good else ("CRASH" if crashed else "wrong"), err or json.dumps(calls)[:60]))
    return ok, rows


try:
    for fn in (book_gpu, kv_bytes, lookup.fn):
        got, want = m.function_schema(fn), reference_schema(fn)
        if got != want:
            print(f"function_schema({fn.__name__}) differs:\n  yours:     {json.dumps(got)}\n  reference: {json.dumps(want)}")
            raise SystemExit(1)
    print("function_schema: matches the reference for book_gpu (Literal, Optional[List]), kv_bytes and lookup\n")
    naive_ok, _ = score(naive_parse)
    mine_ok, rows = score(m.parse_tool_calls)
    print("your parser on", len(CORPUS), "real-world outputs:")
    table(rows, ["output style", "result", "parsed"])

    schema = reference_schema(book_gpu)
    bad = [{"gpu": "H100"}, {"gpu": "H100", "hours": "four"}, {"gpu": "TPU", "hours": 4},
           {"gpu": "A100", "hours": 2, "zone": "eu"}, {"gpu": "B200", "hours": True}]
    good = [{"gpu": "B200", "hours": 8}, {"gpu": "A100", "hours": 1, "region": "eu-west", "notify": ["me@x.com"]}]
    caught = sum(bool(m.validate(a, schema)) for a in bad)
    false_alarms = sum(bool(m.validate(a, schema)) for a in good)
    print(f"\nvalidate: caught {caught} of {len(bad)} bad argument sets, {false_alarms} false alarms on {len(good)} good ones")
    for a in bad:
        print(f"  {json.dumps(a):48} -> {m.validate(a, schema)}")
except NotImplementedError as e:
    todo_hint(e, __file__)

if args.model != "mock":
    llm = get_llm(args.model)
    q = [{"role": "user", "content": "What is 17 * 23? Then look up the B200."}]
    r = llm.chat(q, [calculator, lookup])
    print(f"\n{args.model}, native tool calling (the server parses the calls):", [(c.name, c.args) for c in r.tool_calls] or r.text)
    sys_prompt = ("You can call tools by writing <tool_call>{\"name\": ..., \"arguments\": {...}}</tool_call>. Tools:\n"
                  + "\n".join(json.dumps(t.schema()["function"]) for t in (calculator, lookup)))
    r = llm.chat([{"role": "system", "content": sys_prompt}] + q)
    print("text protocol (your parser):", m.parse_tool_calls(r.text), "\n  raw:", r.text[:200])

record(naive_ok=naive_ok, parsed_ok=mine_ok, caught=caught, false_alarms=false_alarms)
report(
    "a forgiving parser plus schema validation turns most malformed model output into usable calls or clear "
    "errors, where json.loads alone silently drops them",
    f"json.loads: {naive_ok}/{len(CORPUS)} outputs handled; your parser: {mine_ok}/{len(CORPUS)}; "
    f"validation caught {caught}/{len(bad)} bad calls with {false_alarms} false alarms",
    "PASS" if mine_ok == len(CORPUS) and caught == len(bad) and not false_alarms else "CHECK: see the table above",
    "constrained decoding (vLLM/SGLang guided JSON, xgrammar, Outlines) makes invalid JSON impossible at the "
    "sampler; read how it masks logits per token, then compare its cost with parsing and retrying",
)
