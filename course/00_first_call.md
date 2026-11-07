---
id: 00
title: What a model sees
lab: labs/00_first_call
minutes: 40
track: foundations
summary: an agent is a model in a loop with tools; first, the one flat string a chat model actually reads
---
You know how a model is trained and how it generates tokens. An **agent** adds remarkably little on top: a program (the *harness*) that

1. sends the model a conversation plus a list of tools it may use,
2. reads the reply: either a final answer, or a request to call some tools,
3. runs those tools, appends the results to the conversation, and goes back to step 1.

Claude Code, Cursor's agent, OpenAI's Codex and Deep Research are all this loop, with better tools, better context management, planning, and humans in the right places. This course builds each of those pieces, one lab at a time, until lab 14 is a small coding agent.

## There are no messages, only text

A chat API takes a list of messages and a list of tools. The model never sees either. The server runs a **chat template** (a Jinja program shipped in the model's `tokenizer_config.json`) that flattens everything into one string with special tokens, and the model simply continues that string. This is the ChatML template used by Qwen 2.5 and Hermes models:

```text
<|im_start|>system
You are a helpful agent.

# Tools
...
<tools>
{"type": "function", "function": {"name": "lookup", "description": "...", "parameters": {...}}}
</tools>
For each function call, return a json object ... within <tool_call></tool_call> XML tags<|im_end|>
<|im_start|>user
How much HBM do 8 H100s have in total?<|im_end|>
<|im_start|>assistant
<tool_call>
{"name": "lookup", "arguments": {"topic": "H100"}}
</tool_call><|im_end|>
<|im_start|>user
<tool_response>
NVIDIA H100 SXM: 80 GB HBM3, ...
</tool_response><|im_end|>
<|im_start|>assistant
```

Four things to notice, because the rest of the course depends on them:

- **Tools are text in the system prompt.** Every tool's JSON schema is pasted in, on *every* request. Tool definitions cost prompt tokens and attention, which is why tool count and description quality matter (lessons 03 and 04).
- **A tool call is text the model was trained to write.** Post-training (SFT and RL on agent trajectories, lesson 13) teaches the model to emit `<tool_call>{json}</tool_call>` when a tool would help. The server *parses* it back out into `tool_calls`. If the model writes slightly broken JSON, parsing fails (lesson 01).
- **Tool results come back as a user turn.** In Qwen's template, results are wrapped in `<tool_response>` inside a `user` message. Other families differ (Llama 3 uses an `ipython` role, gpt-oss uses its "harmony" format with channels), but every one of them is a convention learned in training. Use the template the model was trained with, or it gets noticeably worse.
- **The prompt ends with `<|im_start|>assistant\n`**, the *generation prompt*. The model's next tokens are its turn, and it ends the turn by producing `<|im_end|>`, which the server treats as a stop token.

::: trace
title: one request, as the model reads it
system 373 | system prompt + 2 tool schemas rendered into <tools>…</tools>
user 386 | How much HBM do 8 H100s have in total?
call 419 | <tool_call>{"name": "lookup", "arguments": {"topic": "H100"}}</tool_call>
note | the harness runs lookup and appends the result
tool 456 | <tool_response>NVIDIA H100 SXM: 80 GB HBM3, 3.35 TB/s …</tool_response>
note | the prompt ends with "<|im_start|>assistant\n": the model writes next
answer 458 | Each H100 has 80 GB of HBM3, so 8 of them have 640 GB.
:::

The number on each step is the size of the prompt, in tokens, once that piece is in it. 373 of the 458 tokens are there before the user has said a word.

## The course's model

Every lab runs **offline** against a *mock model*: a small Python policy that receives exactly what a real model receives (messages and tool schemas) and returns what a real model would (text or tool calls). That makes every number in the course reproducible on a laptop, and the mock is honest: if your harness forgets to send a tool result back, the mock can't see it either and gets stuck, exactly like a real model.

Every lab also takes `--model` to run against a real server, so you can compare:

```bash
python tools/check_env.py                       # what can this machine reach?
python labs/02_agent_loop/run.py --model ollama:qwen2.5:7b
python labs/02_agent_loop/run.py --model vllm:Qwen/Qwen2.5-7B-Instruct    # vllm serve ... on :8000
AGENTLAB_BASE_URL=http://gpu-box:30000/v1 python labs/02_agent_loop/run.py --model sglang:Qwen/Qwen2.5-7B-Instruct
```

The library in `agentlab/` is small and readable: `llm.py` (mock and OpenAI-compatible clients), `tools.py` (schemas from Python functions), `loop.py` (the agent loop, which you will write yourself in lab 02), `tokens.py` (an approximate tokenizer).

::: write
Open `labs/00_first_call/agent.py` and fill in `render_chat(messages, tools)`, following its five TODOs:

1. The system message; if tools are given, append the `# Tools` block with one JSON schema per line inside `<tools></tools>`, and the instruction to answer in `<tool_call>` tags.
2. User messages as they are.
3. Assistant messages: the content (if any), then one `<tool_call>\n{"name": ..., "arguments": {...}}\n</tool_call>` block per call. Note that `arguments` arrives as a JSON *string* in OpenAI format; decode it, then re-encode with the template's spacing.
4. Tool messages: consecutive results go into *one* user turn, each as `<tool_response>\n...\n</tool_response>`.
5. End with the generation prompt.
:::

::: run
```bash
python labs/00_first_call/run.py             # your agent.py
python labs/00_first_call/run.py --solution  # the reference
```
It checks your rendering against the reference on 6 conversations, prints the full prompt, and counts tokens.
:::

::: measure
- prompt_tokens | prompt tokens, 4-message chat with 2 tools | 458 | tokens
- tool_tokens | of which tool definitions | 364 | tokens
- special_tokens | chat-template special tokens | 9 | tokens
:::

::: explain
**79% of the prompt is tool definitions.** Two short tools cost 364 tokens and a whole four-message conversation costs 458. Real agents ship 20 to 100 tools, and Claude Code's system prompt plus tools is well over 10,000 tokens. That cost is paid on every request, which is why prefix caching (lesson 13) matters so much for agents: the tools and system prompt are identical across steps, so a server can reuse their KV cache.

**Nine special tokens carry all the structure.** `<|im_start|>` and `<|im_end|>` are single tokens in the vocabulary, which plain text can't produce by accident. (Whether a user can inject them by typing the string depends on the tokenizer settings, a real security concern.) `<tool_call>` and `<tool_response>` are added tokens in Qwen 2.5 too, so the model learns sharp boundaries for calls and results.

**Our token counts are estimates.** `agentlab/tokens.py` approximates a BPE tokenizer with a regex. With `--model`, servers report the true `prompt_tokens`, which typically differs by 10 to 30%. The *ratios* are what to take away.
:::

::: cards
Q: What is an AI agent, mechanically?
A: A program (the harness) that calls a model in a loop: send messages plus tool schemas, run any tool calls the model asks for, append the results, repeat until the model answers without calling tools.
Q: What does a chat template do?
A: It renders messages, tool schemas and tool results into the single token sequence the model was trained on, with special tokens marking roles and turn boundaries, and ends with the generation prompt.
Q: Where do tool definitions live in the model's input?
A: In the system prompt, as text (JSON schemas inside `<tools>` for Qwen). They are re-sent and re-read on every request.
Q: How does a model "call a tool"?
A: It writes text in a format it was trained to use, e.g. `<tool_call>{"name": ..., "arguments": ...}</tool_call>`; the server parses that text into structured `tool_calls`.
Q: In ChatML (Qwen 2.5), how do tool results go back to the model?
A: As a user turn containing one `<tool_response>…</tool_response>` block per result.
Q: What is the generation prompt, and why does it matter?
A: The trailing `<|im_start|>assistant\n` that opens the model's turn. Without it the model may continue the user's text instead of answering.
Q: Why does using the model's own chat template matter?
A: The model learned its tool-call and turn conventions in post-training; a different format is out of distribution and degrades tool use noticeably.
:::
