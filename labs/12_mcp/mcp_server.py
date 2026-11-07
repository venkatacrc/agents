"""The lab's MCP server: reads JSON-RPC requests on stdin, one per line, and answers on stdout.

    python labs/12_mcp/mcp_server.py              # uses your handle() from agent.py
    python labs/12_mcp/mcp_server.py --solution   # uses solution.py

stdout carries protocol messages only; anything else must go to stderr.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

from agentlab.labs import load_impl  # noqa: E402
from gpu_tools import TOOLS  # noqa: E402

impl = load_impl(__file__, "--solution" in sys.argv)
print("gpu-cluster MCP server ready", file=sys.stderr)
for line in sys.stdin:
    if not line.strip():
        continue
    try:
        req = json.loads(line)
    except json.JSONDecodeError:
        print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}), flush=True)
        continue
    try:
        resp = impl.handle(req, TOOLS)
    except Exception as e:  # a bug in handle() must not kill the server
        print(f"handle() raised {type(e).__name__}: {e}", file=sys.stderr)
        resp = {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32603, "message": f"Internal error: {e}"}}
    if resp is not None:
        print(json.dumps(resp), flush=True)
