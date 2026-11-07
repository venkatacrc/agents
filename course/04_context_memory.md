---
id: 04
title: Context engineering and memory
lab: labs/04_context_memory
minutes: 50
track: foundations
summary: the context window is working memory; clip tool output, compact old turns, and never drop facts blindly
---
A model's context window is its only working memory during a run. Everything it knows about the task, its progress and the world is in the prompt, and every tool result makes the prompt bigger. Long agent runs fail in three ways:

- **Cost and latency.** Prefill scales with prompt length, and every step re-reads it all (lesson 02).
- **Overflow.** The run hits the context limit and the API rejects the request.
- **Context rot.** Well before the limit, quality drops: models attend less reliably to facts buried in the middle of a long context ("lost in the middle", Liu et al. 2023; Chroma's 2025 "context rot" study measured the same across frontier models). A 200K-token context is not 200K tokens of reliable memory.

*Context engineering* is the harness deciding, at every step, what goes into that window. Three techniques cover most of it.

## 1. Clip tool output at the source

A 700-token log file where one line matters should not cost 700 tokens for the rest of the run. Clip each result: keep the head and tail (structure and the latest state) plus every line matching what matters (`ERROR|Traceback|FAILED`), and mark the gaps: `[... 14 lines elided ...]`. Claude Code and Cursor truncate long command output the same way, and good tools take `max_results` / line-range arguments so the model can ask for more.

## 2. Compact the middle

When the history passes a budget, replace the old middle with a summary written by the model itself, and keep the system prompt, the task, and the most recent turns verbatim:

```text
[system] [task] [Summary of earlier work: files read so far, every ERROR line, what's next] [last 6 messages]
```

This is what Claude Code's `/compact` and auto-compaction do, and what Codex does when its context fills. Two details decide whether it works:

- **The summary prompt must say what to keep.** "Summarize the conversation" loses exactly the facts you need. Say "keep the full file list, which files were read, and every ERROR line verbatim".
- **Never split a tool call from its result.** The kept tail can't start with a `tool` message whose assistant call was summarized away. APIs reject that history, and models misread it.

## 3. Don't just drop the oldest turns

The obvious fix, deleting the oldest messages until it fits, is what many chat apps do. For an agent it is a disaster: the oldest turns hold the plan and the list of work, so the agent forgets what it has done and starts over.

## Memory beyond one run

The same ideas extend across runs. **Scratchpads and notes**: the agent writes progress to a file (`NOTES.md`, a todo list) and reads it back, so state survives compaction. **Long-term memory**: facts stored outside the model (Cursor's memories, ChatGPT memory, a vector store) and retrieved into the prompt when relevant. **Just-in-time context**: rather than pre-loading everything, give the agent tools (`grep`, `read_file` with line ranges) to pull in what it needs. Coding agents moved from embedding-based retrieval to agentic search with grep for exactly this reason.

::: trace
title: reading 20 log files under a 1,500-token budget
user | Read every log file of last night's training run and list every ERROR line, with the file it was in.
call | list_logs()
tool | train_00.log, train_01.log, …, train_19.log
call | read_log(name="train_00.log")
tool | [clipped] 3 head lines · [... 30 lines elided ...] · 3 tail lines
note | …the history passes 1,500 tokens: compaction runs
plan | [Summary of earlier work] All files: train_00.log … train_19.log · Files read: train_00 … train_07 · Errors found: 02:03:17 ERROR rank 12: NCCL timeout …; 02:07:17 ERROR rank 3: CUDA out of memory …
call 1640 | read_log(name="train_08.log")
note | …and so on to train_19.log; the context never passes 1,640 tokens
answer | Found 5 errors: train_03.log: NCCL timeout … train_18.log: loss is NaN at step 48210 …
:::

::: write
In `labs/04_context_memory/agent.py`:

1. `clip(text, max_tokens, keep, head=3, tail=3)`: unchanged if it fits; otherwise first `head` lines, last `tail` lines, and every line matching the `keep` regex, with `[... N lines elided ...]` for each gap.
2. `split_point(messages, keep_last)`: where the kept tail starts: `len - keep_last`, never before index 2, and moved back while it points at a `tool` message.
3. `compact(messages, budget, summarize, keep_last=6)`: over budget → `messages[:2] + [summary message] + tail`.
:::

::: run
```bash
python labs/04_context_memory/run.py --solution
python labs/04_context_memory/run.py --solution --trace     # watch the context size per step
```
Four strategies on the same task: keep everything, drop the oldest turns, clip tool output, clip plus compact.
:::

::: measure
- peak_full | peak context, keep everything | 15210 | tokens
- total_full | total prompt tokens, keep everything | 163298 | tokens
- errors_drop | errors reported, drop oldest | 0 | of 5
- peak_managed | peak context, clip + compact | 1640 | tokens
- total_managed | total prompt tokens, clip + compact | 27173 | tokens
- errors_managed | errors reported, clip + compact | 5 | of 5
:::

::: explain
**Keeping everything works here, at 6x the cost.** 163K prompt tokens for one task, a 15K peak, and the peak grows with every file. With 200 files it would overflow any context, and long before that the errors in the middle of files would start being missed by a real model.

**Dropping the oldest turns found 0 of 5 errors and never finished.** It deleted the file list and the early reads, so the agent re-listed the files and started over, again and again, until it hit 40 steps. Forgetting is not neutral: it destroys the plan.

**Clip + compact: 9x smaller peak, 6x fewer tokens, all 5 errors.** Clipping alone cut the peak to 3.5K because the ERROR lines survive and the INFO noise doesn't. Compaction bounded it at 1.6K: the summary keeps the file list, the progress and every error verbatim, and costs three extra model calls (25 versus 22). That trade, a few summarizer calls for a bounded context, is how every long-running agent works.

**What the summary prompt keeps is the whole game.** Try weakening it (drop "every ERROR line verbatim" from `summarize` in `run.py`) and the agent finishes confidently with errors missing. Compaction failures are silent.
:::

::: cards
Q: What is context rot?
A: The degradation of a model's recall and reasoning as its context grows, well before the hard limit; facts in the middle of long contexts are used less reliably.
Q: What are the three main context-management techniques for agents?
A: Clip tool outputs at the source, compact (summarize) old history when over a budget, and fetch context just in time with tools instead of pre-loading it.
Q: How should a tool's long output be clipped?
A: Keep head and tail lines plus every line matching what matters (errors, failures), with explicit markers for elided gaps.
Q: What does compaction keep verbatim?
A: The system prompt, the task, and the most recent turns; the middle is replaced by a model-written summary that preserves progress and key facts.
Q: Why must compaction never split a tool call from its result?
A: A tool message without its calling assistant message is an invalid history: APIs reject it and models misread it.
Q: Why is "drop the oldest messages" bad for agents?
A: The oldest turns hold the task's plan and progress; dropping them makes the agent forget what it did and repeat work or loop.
Q: Name two forms of memory that persist beyond one context window.
A: Notes or scratchpad files the agent writes and re-reads (e.g. a todo list or NOTES.md), and long-term memory stores retrieved into the prompt when relevant.
:::
