---
id: 12
title: The Model Context Protocol
lab: labs/12_mcp
minutes: 45
track: systems
summary: tools in another process, discovered at runtime over JSON-RPC; build a server that works in Cursor
---
Until now every tool has been a Python function in the agent's own process. That doesn't scale: every agent (Cursor, Claude Code, ChatGPT, your own) would need its own integration with every system (GitHub, Jira, Postgres, your cluster). The **Model Context Protocol** (MCP, Anthropic, late 2024, now supported across the industry) turns N×M integrations into N+M. A system exposes its tools once as an MCP **server**, and any MCP **client** can discover and call them.

## The protocol

MCP is JSON-RPC 2.0 over a transport: **stdio** for local servers (the client starts the server as a subprocess and they exchange one JSON object per line) or **Streamable HTTP** for remote ones. A session:

```text
client → {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{...}}}
server ← {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"gpu-cluster",...}}}
client → {"jsonrpc":"2.0","method":"notifications/initialized"}            (a notification: no id, no reply)
client → {"jsonrpc":"2.0","id":2,"method":"tools/list"}
server ← {"result":{"tools":[{"name":"gpu_inventory","description":"...","inputSchema":{...}}]}}
client → {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"job_status","arguments":{"job_id":"job-121"}}}
server ← {"result":{"content":[{"type":"text","text":"job-121: failed: CUDA out of memory at step 300"}],"isError":false}}
```

Three details trip people up:

- **Tool failures are results, not protocol errors.** An unknown tool or an exception inside a tool returns a normal result with `isError: true`, so the model sees the message (lesson 02's rule again). JSON-RPC errors such as `-32601 Method not found` are for protocol problems.
- **stdout is the protocol.** A stray `print()` in a stdio server corrupts the stream. Log to stderr.
- **The tool list is discovered at runtime.** The client asks the server what it has, and the server can announce changes (`notifications/tools/list_changed`). The schemas go into the model's prompt like any other tool.

Besides tools, MCP servers can offer **resources** (data the client can read into context), **prompts** (templates), and ask the client for **sampling** (a model call) or **elicitation** (a question for the user). Most servers you'll meet only do tools.

::: trace
title: an agent using tools it discovered at runtime
note | client starts `python3 mcp_server.py` and sends initialize, notifications/initialized, tools/list
tool | discovered 3 tools: gpu_inventory, job_status, kv_cache_gb
user | Is there room in us-east for an 8-GPU H100 job right now, and what happened to job-121?
call | gpu_inventory(region="us-east")  ·  job_status(job_id="job-121")
note | each call is a tools/call request on the server's stdin
tool | gpu-a1: H100, 3/8 free · gpu-a2: H100, 8/8 free · gpu-a3: A100, 0/8 free  ·  job-121: failed: CUDA out of memory at step 300
answer | Yes: gpu-a2 has all 8 H100s free. job-121: failed: CUDA out of memory at step 300
:::

::: write
In `labs/12_mcp/agent.py`:

1. `handle(req, tools)`, the server side: `initialize` (protocol version, `capabilities: {"tools": {}}`, serverInfo), `ping`, `tools/list` (name, description, `inputSchema`), `tools/call` (text content; `isError` for unknown tools and exceptions), `-32601` for unknown methods, and `None` for notifications.
2. `MCPClient`: start the server with `subprocess.Popen(..., stdin=PIPE, stdout=PIPE, text=True)`; `request` writes one JSON line and reads lines until the matching `id`; `notify`; `initialize`; `list_tools`; `call_tool` (join the text content, prefix `Error: ` when `isError`); `close`.
3. `as_tools(client)`: wrap each server tool as an agentlab `Tool` whose function calls `client.call_tool`. Bind the name per tool: a closure in a loop captures the variable, not its value.

`mcp_server.py` is the stdio loop around your `handle`.
:::

::: run
```bash
python labs/12_mcp/run.py --solution
```
It prints a config block. Paste it into `~/.cursor/mcp.json` and Cursor's agent can use your server's tools.
:::

::: measure
- tools_found | tools discovered over MCP | 3 |
- unknown_method_code | JSON-RPC code for an unknown method | -32601 |
- calls_during_run | tools/call requests during the agent run | 2 |
:::

::: explain
**The agent code didn't change.** `as_tools` turned three remote tools into ordinary `Tool` objects, and `run_agent` from lesson 02 used them without knowing they lived in another process. That's the point of a protocol: the loop, the context management and the approvals stay the same; only where tools come from changes.

**Two parallel calls became two `tools/call` requests.** The model asked for the inventory and the job status at once. Over stdio they go one after another on one pipe; a server over HTTP could handle them concurrently.

**Errors stayed observations.** `format_disk` (unknown) and `gpu_inventory(region="mars")` (raises) came back as `isError` results the model can read, while a protocol-level mistake (`tools/destroy`) got `-32601`. Mixing these up is the most common MCP server bug.

**Treat MCP servers like dependencies.** A server runs with your permissions, and its tool descriptions are text in your model's prompt (lesson 11's tool poisoning). Install servers you trust, pin versions, and prefer servers that ask for approval on writes.
:::

::: cards
Q: What problem does MCP solve?
A: It standardizes how agents discover and call external tools, so each system exposes an MCP server once and every MCP client can use it (N+M integrations instead of N×M).
Q: What wire format and transports does MCP use?
A: JSON-RPC 2.0, over stdio for local servers (newline-delimited JSON) or Streamable HTTP for remote ones.
Q: List the messages of an MCP session that calls one tool.
A: initialize → result; notifications/initialized; tools/list → tools; tools/call → content and isError.
Q: How should an MCP server report that a tool raised an exception?
A: As a normal tools/call result with isError: true and the message as text, not as a JSON-RPC error.
Q: What does JSON-RPC error -32601 mean?
A: Method not found: the request named a method the server doesn't implement.
Q: Why must a stdio MCP server never print to stdout?
A: stdout carries the protocol; any extra output corrupts the JSON stream. Logs go to stderr.
Q: Besides tools, what can an MCP server offer?
A: Resources (readable data), prompts (templates), and requests to the client for sampling (a model call) or elicitation (asking the user).
:::
