# Agent Lab: build AI agents from scratch

Build an AI agent the way Claude Code, Codex or Deep Research are built: start from the flat string a chat model actually reads, add tool calls, wrap them in a loop, and keep going through planning, reflection, humans in the loop, multi-agent orchestration, evals, safety, MCP, and how agentic models are trained and served. It ends with a small coding agent that reads a repo, edits files, runs the tests and asks you before it writes.

In every lab you write the code (`agent.py` has TODO stubs), run it, record what it printed, and only then read why it behaved that way. The labs are plain Python 3.9+ with no dependencies. By default they run against a scripted mock model, so they work offline, cost nothing and give the same numbers every time. Add `--model` to run the same code against a real model.

The lessons live in a small offline web app (`web/`, published at [venkatacrc.github.io/agents](https://venkatacrc.github.io/agents/) once Pages is enabled) that installs on a phone, and in a native Mac app (`app/`). Both have Lessons, flash Cards (Learn and Test modes) and Progress. Progress is stored on your device and can be exported from one app and imported into the other. Lessons include step-by-step *Watch* replays of real agent runs: step through each model turn, tool call and result, watch the context meter grow, and choose Approve or Deny where the agent asks a human.

## Syllabus

| # | Lesson | Lab | You measure |
|---|---|---|---|
| 00 | What a model sees | `labs/00_first_call` | the 458-token prompt behind one message, 364 of them tool schemas |
| 01 | Tool calling from scratch | `labs/01_tool_calling` | naive vs robust parsing of model output, validation catching bad calls |
| 02 | The agent loop | `labs/02_agent_loop` | steps, prompt growth per step, a runaway loop and its recovery |
| 03 | Designing tools for models | `labs/03_tool_design` | vague vs well-designed tools, helpful errors the model recovers from |
| 04 | Context engineering and memory | `labs/04_context_memory` | peak context 15,210 → 1,640 tokens with clipping and compaction |
| 05 | Workflows before agents | `labs/05_workflows` | routing, parallel fan-out (2.04 s → 0.25 s), evaluator-optimizer |
| 06 | Plan, execute, replan | `labs/06_planning` | a plan that fails mid-way and is repaired |
| 07 | Reflection with a real verifier | `labs/07_reflection` | Reflexion with tests vs "blind" self-critique |
| 08 | Humans in the loop | `labs/08_human_in_the_loop` | interrupts, an approval policy, resuming after a crash without repeating work |
| 09 | Multi-agent systems | `labs/09_multi_agent` | orchestrator-workers: smaller contexts per agent, fewer tokens overall |
| 10 | Evaluating agents | `labs/10_evals` | pass@k vs pass^k, outcome vs trajectory grading |
| 11 | Safety and prompt injection | `labs/11_safety` | 5 injection attacks succeed, then 0 with taint tracking and the Rule of Two |
| 12 | The Model Context Protocol | `labs/12_mcp` | an MCP server and client over stdio JSON-RPC |
| 13 | How agentic models are trained and served | `labs/13_train_and_serve` | SFT loss masks, verifiable rewards, GRPO advantages, prefix-cache hit rates |
| 14 | Capstone: a coding agent | `labs/14_capstone_coding_agent` | an agent that fixes a repo (3 → 5 tests passing) with your approval |
| 15 | The frontier, mapped to what you built | — | how today's frontier agents use each piece |

## Run the labs

```bash
python3 tools/check_env.py                              # Python version, mock smoke test, which model servers are up
python3 labs/00_first_call/run.py                       # your agent.py (TODO stubs)
python3 labs/00_first_call/run.py --solution            # the reference solution
python3 labs/02_agent_loop/run.py --solution --trace    # print every model step and tool call
python3 labs/08_human_in_the_loop/run.py --interactive  # you are the human: approve or deny
python3 labs/14_capstone_coding_agent/run.py --interactive

python3 tools/run_all.py                                # every lab's solution vs the lesson's reference numbers
python3 tools/test_backend.py                           # the HTTP backend against a local fake server
```

Each lab prints `RECORD` lines with the numbers to enter in the lesson; the explanation unlocks once you have entered them.

## Real models

Pick a backend with `--model` (or `AGENTLAB_MODEL`). Every backend speaks the OpenAI chat-completions format with tool calls.

| `--model` | Server |
|---|---|
| `mock` (default) | the lab's scripted policy: offline, deterministic, free |
| `ollama:qwen2.5:7b` | Ollama on `localhost:11434` (`OLLAMA_HOST` to change) |
| `vllm:Qwen/Qwen3-8B` | vLLM, default `http://localhost:8000/v1` |
| `sglang:Qwen/Qwen3-8B` | SGLang, default `http://localhost:30000/v1` |
| `openai:gpt-4.1-mini` | OpenAI (`OPENAI_API_KEY`; `OPENAI_BASE_URL` for any compatible API) |

`AGENTLAB_BASE_URL` overrides the server address for every non-mock backend. The model must support tool calling: with Ollama, use a model such as `qwen2.5`, `qwen3`, `llama3.1` or `gpt-oss`.

```bash
vllm serve Qwen/Qwen3-8B --enable-auto-tool-choice --tool-call-parser hermes
python3 labs/14_capstone_coding_agent/run.py --solution --model vllm:Qwen/Qwen3-8B
```

With a real model your numbers will differ from the references, and explaining the difference is part of the exercise.

## The web app (and your phone)

```bash
python3 tools/build_course.py                   # course/*.md -> web/course.json
python3 -m http.server -d web 8080              # open http://localhost:8080
node tools/smoke_web.js                         # headless render check
```

Lessons are Markdown in `course/` with `::: write`, `::: run`, `::: measure`, `::: explain`, `::: trace`, `::: cards` and `::: note` blocks. The format is documented at the top of `tools/build_course.py`.

The layout is a single phone-width column. The ☰ menu opens a drawer with the lesson list (tick lessons to choose which cards you practise and what prints), card options and Export / Import / Print / Reset. Keyboard: `1`/`2`/`3` switch views; `←`/`→` previous/next lesson or card; `N` advances a replay; in Cards, `Space` reveals, `G`/`M` got it / missed it, `K`/`R` mark known / review. Cards swipe on phones. The app works offline.

**Publish it:** `.github/workflows/pages.yml` rebuilds `course.json`, runs the smoke test and publishes `web/` on every push to `main`. Enable it once under Settings → Pages → Source: GitHub Actions.

**Install on a Pixel:** open the Pages URL in Chrome, then ⋮ → *Add to home screen* → *Install*. It opens full screen like a native app and keeps working offline.

## The Mac app

```bash
./scripts/build_app.sh                          # needs Xcode or the Command Line Tools (macOS 14+)
open build/AgentLab.app
```

The same course in a native window: the sidebar lists the lessons with progress rings and checkboxes for selection, the toolbar switches Lessons / Cards / Progress, and lessons render with the same highlighting, replays and measurement checks as the web app. Shortcuts: `⌘1`–`⌘3` views, `⌘[` / `⌘]` previous / next lesson, `⌘L` practise this lesson's cards, `⌘P` print or save the lesson as PDF, `⌘⇧P` print the selected lessons, `⌘⇧E` / `⌘⇧I` export / import progress. Progress is saved to `~/Library/Application Support/AgentLab/progress.json`, in the same format as the web app's export.
