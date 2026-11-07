---
id: 02
title: The agent loop
lab: labs/02_agent_loop
minutes: 45
track: foundations
summary: ReAct in fifteen lines; parallel calls, bounded steps, errors as observations, and why cost grows with every step
---
Here is the whole idea. Every agent you have heard of is a variant of this:

```python
messages = [system, user_task]
for step in range(max_steps):
    reply = llm.chat(messages, tools)          # think, maybe ask for tools
    messages.append(reply.message())
    if not reply.tool_calls:
        return reply.text                      # the model decided it is done
    for call in reply.tool_calls:              # act
        result = execute(call)                 # never raises
        messages.append(tool_message(call, result))   # observe
return "stopped: out of steps"
```

This is **ReAct** (Yao et al., 2022, "Reason + Act"): the model interleaves reasoning, actions and observations, and each observation shapes the next step. The original paper used text like `Thought: … Action: … Observation: …`. Today the model's reasoning goes in its content (or a hidden reasoning channel for o-series, gpt-oss, Claude's extended thinking), and actions are structured tool calls, but the loop is the same.

## Four rules the harness must enforce

1. **The model decides when to stop**, by replying without tool calls. The harness never guesses.
2. **Bound the loop.** Models get stuck: they repeat a call, or keep "checking" forever. `max_steps` is the minimum; production agents also cap tokens, wall time and cost.
3. **Errors are observations, not exceptions.** A tool that raises must not crash the agent. Return `"Error: ValueError: cannot parse '8 x 80': use numbers and + - * /…"` as the tool result, and the model, which can read, fixes its call. Most "the agent is dumb" bugs are harnesses that swallow or hide errors.
4. **Every call gets a result**, in order, matched by `tool_call_id`. APIs reject an assistant message with tool calls that are not all answered, and models trained on well-formed histories get confused by gaps.

## Parallel calls

Models can ask for several independent calls in one reply. Here it looks up the H100 and the A100 at once. It saves a model round trip (one prefill and decode) per call, and a harness can run them concurrently. Models were trained to do this, and the system prompt can encourage it ("call several at once when they are independent").

::: trace
title: 8 H100s and 4 A100s: how much HBM?
user | How much HBM do 8 H100s and 4 A100s (80 GB version) have together, in GB?
think 334 | I need both memory sizes; the two lookups are independent, so ask for both.
call | lookup(topic="H100")  ·  lookup(topic="A100")
tool | NVIDIA H100 SXM: 80 GB HBM3, 3.35 TB/s …   ·   NVIDIA A100 SXM: 80 GB HBM2e (a 40 GB version also exists) …
think 426 | Use the calculator rather than mental arithmetic.
call | calculator(expression="8 * 80 + 4 * 80")
tool | 960
answer 451 | 8 H100s (80 GB each) and 4 A100s (80 GB each) have 960 GB of HBM together.
:::

## Why agents are expensive

Look at the prompt sizes on that trace: 334, 426, 451 tokens. **Every step re-sends the entire history.** The prompt grows by each step's output plus each tool's result, so total prompt tokens grow roughly *quadratically* with the number of steps. A 50-step coding session where tools return file contents can easily send millions of prompt tokens. Two things keep this affordable: prefix caching on the server (lesson 13) and context management in the harness (lesson 04).

::: write
In `labs/02_agent_loop/agent.py`:

1. `execute(box, call)`: unknown tool → an error string that lists the available tools; otherwise `tool.fn(**call.args)`; any exception → `"Error: <Type>: <message>"`.
2. `run_agent(...)`: the loop above. Count `steps` (model calls) and `tool_calls`, call `on_event` after each reply and each tool result (that's how `--trace` prints), and return a `Run` with `stopped="answer"` or `"max_steps"`.
:::

::: run
```bash
python labs/02_agent_loop/run.py --trace
python labs/02_agent_loop/run.py --solution --trace
```
Three scenarios: a competent model, a runaway model that repeats itself, and a sloppy one that writes `8 x 80` to the calculator.
:::

::: measure
- steps | model calls to answer | 3 |
- tool_calls | tool calls | 3 |
- total_prompt | total prompt tokens over the run | 1211 | tokens
- runaway_steps | runaway model stopped after | 6 | calls
- recovery_steps | model calls to recover from a tool error | 3 |
:::

::: explain
**Three model calls, three tool calls, 1,211 prompt tokens for a 30-token answer.** The answer is tiny; the cost is the history re-sent three times, and most of each prompt is the two tool schemas (lesson 00). That ratio only gets worse as tasks get longer.

**The runaway is stopped by the harness, not the model.** The runaway policy repeats `lookup("H100")` forever; `max_steps=6` ends it with `stopped="max_steps"`. Real models loop like this when a tool keeps returning something they don't expect. Production harnesses also detect repeated identical calls and inject a nudge ("you have called this 3 times with the same arguments").

**The error message did the recovering.** The calculator raised `ValueError` with a hint ("use * for multiplication"), the harness returned it as the tool result, and the next call was `8 * 80`. If `execute` had raised instead, the run would have crashed; if it had returned only `"error"`, the model would have had to guess.
:::

::: cards
Q: Write the agent loop in four lines of pseudocode.
A: reply = model(messages, tools); append reply; if no tool calls: return reply.text; else run each call and append its result; repeat (bounded).
Q: What does ReAct stand for and what is its key idea?
A: Reason + Act: interleave reasoning, tool actions and observations so each observation informs the next step.
Q: Who decides that an agent is finished?
A: The model, by replying without tool calls. The harness only enforces limits (steps, tokens, time, cost).
Q: Why must tool errors be returned as results instead of raised?
A: The model can read the error and fix its call; raising crashes the run, and hiding the error leaves the model guessing.
Q: Why does an agent's total prompt-token cost grow roughly quadratically with steps?
A: Each step re-sends the full history, which grows linearly with steps; summing over steps gives a quadratic total.
Q: What are parallel tool calls, and what do they save?
A: Several independent calls in one model reply; they save a model round trip per call and can execute concurrently.
Q: What must be true of tool results in the message history?
A: Every tool call in an assistant message gets exactly one result, matched by tool_call_id, before the next assistant turn.
:::
