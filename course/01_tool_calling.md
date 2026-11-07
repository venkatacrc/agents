---
id: 01
title: Tool calling from scratch
lab: labs/01_tool_calling
minutes: 50
track: foundations
summary: JSON schemas from Python functions, parsing the messy calls real models write, validating arguments
---
Three pieces of code sit between a model and your functions. Servers like vLLM and Ollama run some of them for you (their "tool parsers"), but they fail in production often enough that you should know exactly what they do.

## 1. Describe the function: JSON schema

The model can only call what it has read about. A tool definition is a name, a description, and a JSON schema for the arguments:

```python
def book_gpu(gpu: Literal["H100", "A100", "B200"], hours: int, tags: Optional[List[str]] = None):
    """Reserve GPUs.

    Args:
        gpu: which GPU type
        hours: how long, in whole hours
    """
```

```json
{"type": "object",
 "properties": {"gpu":   {"type": "string", "enum": ["H100", "A100", "B200"], "description": "which GPU type"},
                "hours": {"type": "integer", "description": "how long, in whole hours"},
                "tags":  {"type": "array", "items": {"type": "string"}, "default": null}},
 "required": ["gpu", "hours"]}
```

Every framework (OpenAI Agents SDK, LangChain, Pydantic AI, smolagents, MCP servers) generates this from type hints and docstrings, as `agentlab/tools.py` does. The `enum` matters more than it looks: it is the difference between the model writing `"h100"`, `"H-100"` or `"H100 SXM"` and writing a value your code accepts.

## 2. Parse what the model wrote

When a server has no tool parser for your model, or the model drifts from its format, you get the raw text. Real outputs include:

- the trained format: `<tool_call>{"name": ..., "arguments": {...}}</tool_call>`, possibly several in a row (parallel calls);
- a markdown fence around the JSON, or a sentence of prose before it;
- Llama 3's `<|python_tag|>` and its `"parameters"` key instead of `"arguments"`;
- `arguments` as a JSON-encoded *string* (OpenAI's wire format, which models sometimes imitate);
- trailing commas, Python-style single quotes;
- output cut off by `max_tokens` in the middle of the JSON;
- braces inside string values (`"topic": "kv cache {per token}"`) that break naive brace matching.

`json.loads(text)` handles exactly one of those. A robust parser scans for top-level `{...}` objects while tracking whether it is inside a string, tries strict JSON, then a lenient repair, and reports *why* it failed (an unterminated object usually means truncation, which is worth telling the model or raising `max_tokens`).

## 3. Validate before you run

A parsed call can still be wrong: a missing required argument, `"hours": "four"`, a GPU that isn't in the enum, an argument that doesn't exist, or `true` for an integer (in Python `bool` is a subclass of `int`, a classic bug). Validation turns these into specific messages the model can act on, instead of a stack trace or, worse, a wrong action.

> The alternative to parsing and validating is **constrained decoding**: vLLM, SGLang, llama.cpp and OpenAI's strict mode can compile the JSON schema into a grammar and mask the logits at every step so invalid output is impossible. It is the right default for production, but it doesn't remove the need for semantic validation (the job id must exist), and grammars can slightly hurt quality when they force tokens the model would not have chosen.

::: trace
title: the same call, five ways
call | <tool_call>{"name": "lookup", "arguments": {"topic": "H100"}}</tool_call>
call | Sure! I'll check that. {"name": "lookup", "arguments": {"topic": "B200"}}
call | <|python_tag|>{"name": "calculator", "parameters": {"expression": "7*6"}}
call | {'name': 'lookup', 'arguments': {'topic': 'H100'},}
call | <tool_call>{"name": "lookup", "arguments": {"topic": "kv cache
note | all but the last parse; the last is reported as "unterminated JSON object (was the output truncated?)"
:::

::: write
In `labs/01_tool_calling/agent.py`:

1. `function_schema(fn)`: walk `inspect.signature(fn).parameters` with `typing.get_type_hints(fn)`. Map `str/int/float/bool` to JSON types, `List[X]` to an array with `items`, `Literal[...]` to an `enum`, `Optional[X]` to the schema of `X`. Take descriptions from the docstring's `Args:` section. Parameters without defaults are `required`.
2. `parse_tool_calls(text)`: find top-level JSON objects by counting braces (quotes only count inside an object, so an apostrophe in prose doesn't start a "string"); parse with `json.loads`, then without trailing commas, then `ast.literal_eval`; accept `arguments` or `parameters`, decode string arguments; return `(calls, error)`.
3. `validate(args, schema)`: required, unknown, type (bool is not an integer) and enum checks, as human-readable strings.
:::

::: run
```bash
python labs/01_tool_calling/run.py
python labs/01_tool_calling/run.py --solution
python labs/01_tool_calling/run.py --solution --model ollama:qwen2.5:7b   # native vs text-protocol calling
```
:::

::: measure
- naive_ok | outputs handled by json.loads alone | 1 | of 12
- parsed_ok | outputs handled by your parser | 12 | of 12
- caught | bad argument sets caught by validate | 5 | of 5
- false_alarms | good argument sets rejected | 0 |
:::

::: explain
**Only 1 of 12 real-world outputs is pure JSON.** Everything else has tags, prose, fences, a different key, or small syntax slips. Servers' built-in parsers handle the format the model was *trained* on (Hermes tags for Qwen, `<|python_tag|>` for Llama), and fail when the model deviates. When they fail, the call is usually silently dropped and the text is returned as if it were a final answer, and the agent "finishes" without doing anything. Knowing this failure mode saves hours of debugging.

**The truncation case must be an error, not an empty list.** If the parser returned `[]` for a cut-off call, the loop would treat the half-written call as the model's final answer. Returning a reason ("unterminated JSON object, was the output truncated?") lets the harness retry with a larger `max_tokens`.

**Validation's messages are written for the model.** "hours should be integer, got str 'four'" is enough for any decent model to fix its next call. Lesson 03 takes this further: error messages are part of the tool's interface.
:::

::: cards
Q: What three things make up a tool definition the model sees?
A: A name, a natural-language description, and a JSON schema of the parameters (types, descriptions, enums, required list).
Q: Why put an `enum` in a tool schema?
A: It tells the model the exact accepted values (and lets constrained decoding enforce them), eliminating near-miss strings like "h100" or "H100 SXM".
Q: What is the most common silent failure when a server can't parse a tool call?
A: The call text is returned as ordinary content, so the harness sees no tool calls and treats it as the final answer: the agent stops without acting.
Q: Why must a truncated tool call be reported as an error rather than "no calls"?
A: Otherwise the loop ends on a half-written call; an explicit error lets the harness retry, e.g. with a larger max_tokens.
Q: Why is `isinstance(True, int)` a validation trap?
A: In Python bool is a subclass of int, so a naive check accepts `true` for an integer parameter. Check bool explicitly first.
Q: What is constrained (guided) decoding?
A: The server compiles a JSON schema or grammar into a state machine and masks logits each step so only valid continuations can be sampled; invalid JSON becomes impossible.
Q: What does constrained decoding not fix?
A: Semantic errors: a well-formed call with a job id that doesn't exist, or the wrong tool for the task. You still validate and return helpful errors.
:::
