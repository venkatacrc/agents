"""Lab 12: the Model Context Protocol. Tools that live in another process, discovered at runtime.

Run:  python labs/12_mcp/run.py             (your code)
      python labs/12_mcp/run.py --solution

MCP over stdio: the client starts the server as a subprocess and they exchange JSON-RPC 2.0 messages,
one JSON object per line. Your server will work in Cursor and other MCP clients (run.py prints the config).

  client -> {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": ..., ...}}
  server <- {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion", "capabilities": {"tools": {}}, "serverInfo"}}
  client -> {"jsonrpc": "2.0", "method": "notifications/initialized"}          (no id: never answered)
  client -> tools/list                      <- {"tools": [{"name", "description", "inputSchema"}]}
  client -> tools/call {"name", "arguments"} <- {"content": [{"type": "text", "text": ...}], "isError": bool}
"""
import json  # noqa: F401
import subprocess  # noqa: F401

from agentlab.tools import Tool  # noqa: F401

PROTOCOL = "2025-06-18"


# ---- server -----------------------------------------------------------------------------------

def handle(req, tools):
    """Return the response dict for one request, or None for a notification (a message without "id").

    initialize -> protocolVersion, capabilities {"tools": {}}, serverInfo {"name": "gpu-cluster", "version"}
    ping       -> {}
    tools/list -> each Tool as {"name", "description", "inputSchema": tool.parameters}
    tools/call -> run tool.fn(**arguments); text result in content. Unknown tool or an exception is still a
                  *result*, with "isError": True (the model should see it), not a JSON-RPC error.
    anything else -> {"jsonrpc": "2.0", "id": ..., "error": {"code": -32601, "message": "Method not found: ..."}}
    """
    # TODO 1
    raise NotImplementedError("handle")


# ---- client -----------------------------------------------------------------------------------

class MCPClient:
    def __init__(self, command):
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.next_id = 0
        self.sent = 0  # messages sent, requests and notifications

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        self.sent += 1

    def request(self, method, params=None):
        """Send a request with a new id and return the response with that id (skip any other lines)."""
        # TODO 2
        raise NotImplementedError("MCPClient.request")

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self):
        """initialize (with protocolVersion, capabilities {}, clientInfo), then the initialized notification.
        Return the server's result."""
        # TODO 3
        raise NotImplementedError("MCPClient.initialize")

    def list_tools(self):
        return self.request("tools/list")["result"]["tools"]

    def call_tool(self, name, arguments):
        """tools/call; join the text content. Prefix "Error: " when isError is true."""
        # TODO 4
        raise NotImplementedError("MCPClient.call_tool")

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def as_tools(client):
    """Wrap every server tool as an agentlab Tool whose fn calls client.call_tool(name, kwargs).
    Careful with closures in a loop: bind the name per tool (a default argument does it)."""
    # TODO 5
    raise NotImplementedError("as_tools")
