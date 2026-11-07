"""Check Lab 12: start your MCP server, discover its tools, and let an agent use them.

Usage: python labs/12_mcp/run.py [--solution] [--trace] [--model ollama:NAME]
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

from agentlab import get_llm  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, results_of, say, tool_names  # noqa: E402
from agentlab.trace import Printer  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)
server_cmd = [sys.executable, str(HERE / "mcp_server.py")] + (["--solution"] if args.solution else [])
TASK = "Is there room in us-east for an 8-GPU H100 job right now, and what happened to job-121?"


def policy(messages, tools):
    names = tool_names(tools)  # only what the server advertised
    inv = next((n for n in names if "inventory" in n), None)
    status = next((n for n in names if "status" in n), None)
    if inv and not results_of(messages, inv):
        return [call(inv, region="us-east"), call(status, job_id="job-121")]
    nodes = results_of(messages, inv)[-1]
    full = [n for n, f in re.findall(r"(gpu-\w+): H100, (\d+)/8 free", nodes) if f == "8"]
    job = results_of(messages, status)[-1]
    return say(f"Yes: {full[0]} has all 8 H100s free. {job}" if full else f"No node has 8 free H100s. {job}")


try:
    m.handle({"jsonrpc": "2.0", "id": 0, "method": "ping"}, [])  # your server code, in-process first
    client = m.MCPClient(server_cmd)
    info = client.initialize()
    print(f"connected to {info['serverInfo']['name']} {info['serverInfo']['version']}, protocol {info['protocolVersion']}")
    tools = m.as_tools(client)
    print(f"discovered {len(tools)} tools: {', '.join(t.name for t in tools)}")
    unknown = client.request("resources/subscribe")
    bad_tool = client.call_tool("format_disk", {})
    bad_args = client.call_tool("gpu_inventory", {"region": "mars"})
    print(f"unknown method -> JSON-RPC error {unknown.get('error', {}).get('code')}; unknown tool -> {bad_tool!r}\n"
          f"tool exception -> {bad_args!r}\n")
    before = client.sent
    r = run_agent(get_llm(args.model, policy), tools, TASK, on_event=Printer() if args.trace else None)
    during = client.sent - before
    client.close()
except NotImplementedError as e:
    todo_hint(e, __file__)

print(f"answer: {r.answer}\n")
cfg = {"mcpServers": {"gpu-cluster": {"command": "python3", "args": [str(HERE / "mcp_server.py"), "--solution"]}}}
print("use this server from Cursor: add to ~/.cursor/mcp.json (or .cursor/mcp.json in a project):")
print(json.dumps(cfg, indent=2))
record(tools_found=len(tools), unknown_method_code=unknown.get("error", {}).get("code"), calls_during_run=during)
report(
    "MCP separates tools from agents: a server describes its tools in JSON schema, any client discovers and calls "
    "them at runtime over JSON-RPC, so one server works in every agent that speaks the protocol",
    f"{len(tools)} tools discovered at runtime; the agent answered with {during} tools/call messages; unknown method "
    f"returned error {unknown.get('error', {}).get('code')} and tool failures came back as isError results",
    "PASS" if len(tools) == 3 and unknown.get("error", {}).get("code") == -32601 and "gpu-a2" in r.answer
    else "CHECK: expected 3 tools, error -32601 and an answer naming gpu-a2",
    "add the server to Cursor with the config above and ask Cursor's agent about job-121; then read the spec's "
    "sections on resources, prompts and authorization",
)
