"""Lab 12 reference: both halves of the Model Context Protocol (stdio transport, JSON-RPC 2.0)."""
import json
import subprocess

from agentlab.tools import Tool

PROTOCOL = "2025-06-18"


# ---- server -----------------------------------------------------------------------------------

def handle(req, tools):
    if "id" not in req:
        return None  # a notification, such as notifications/initialized: never answered
    by_name = {t.name: t for t in tools}
    method, params = req.get("method"), req.get("params") or {}

    def ok(result):
        return {"jsonrpc": "2.0", "id": req["id"], "result": result}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                   "serverInfo": {"name": "gpu-cluster", "version": "0.1.0"}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{"name": t.name, "description": t.description, "inputSchema": t.parameters}
                             for t in tools]})
    if method == "tools/call":
        t = by_name.get(params.get("name"))
        if t is None:
            return ok({"content": [{"type": "text", "text": f"unknown tool {params.get('name')!r}"}], "isError": True})
        try:
            text = str(t.fn(**(params.get("arguments") or {})))
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:  # tool errors are results the model can read, not protocol errors
            return ok({"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": req["id"], "error": {"code": -32601, "message": f"Method not found: {method}"}}


# ---- client -----------------------------------------------------------------------------------

class MCPClient:
    def __init__(self, command):
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.next_id = 0
        self.sent = 0

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        self.sent += 1

    def request(self, method, params=None):
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        while True:
            msg = json.loads(self.proc.stdout.readline())
            if msg.get("id") == self.next_id:
                return msg

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self):
        r = self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                        "clientInfo": {"name": "agentlab", "version": "0.1.0"}})
        self.notify("notifications/initialized")
        return r["result"]

    def list_tools(self):
        return self.request("tools/list")["result"]["tools"]

    def call_tool(self, name, arguments):
        r = self.request("tools/call", {"name": name, "arguments": arguments})["result"]
        text = "\n".join(c.get("text", "") for c in r["content"] if c.get("type") == "text")
        return ("Error: " + text) if r.get("isError") else text

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def as_tools(client):
    out = []
    for spec in client.list_tools():
        def fn(_name=spec["name"], **kwargs):
            return client.call_tool(_name, kwargs)
        out.append(Tool(name=spec["name"], description=spec.get("description", ""),
                        parameters=spec.get("inputSchema", {"type": "object", "properties": {}}), fn=fn))
    return out
