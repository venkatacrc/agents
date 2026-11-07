"""Exercise the real HTTP path (OpenAICompatLLM) against a fake OpenAI-compatible server.

    python tools/test_backend.py

The server plays a model with a scripted policy, but everything between the agent and it is the same
JSON that vLLM, SGLang, Ollama or OpenAI would see: tool schemas, assistant tool_calls with string
arguments, tool messages with tool_call_id, and usage counts in the response.
"""
import json
import os
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agentlab import get_llm  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402

SEEN = []


def reply_for(body):
    msgs = body["messages"]
    tools = {t["function"]["name"] for t in body.get("tools", [])}
    results = [m for m in msgs if m["role"] == "tool"]
    ids = {c["id"] for m in msgs if m["role"] == "assistant" for c in m.get("tool_calls") or []}
    assert all(r["tool_call_id"] in ids for r in results), "every tool result must answer a tool call id"
    if not results:
        assert tools == {"lookup", "calculator"}, tools
        calls = [("call_a", "lookup", {"topic": "H100"}), ("call_b", "lookup", {"topic": "A100"})]
    elif len(results) == 2:
        calls = [("call_c", "calculator", {"expression": "8 * 80 + 4 * 80"})]
    else:
        return {"role": "assistant", "content": f"Together they have {results[-1]['content']} GB."}
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": i, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, n, a in calls]}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        if self.path != "/v1/chat/completions" or body.get("model") != "fake-7b":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "model not found"}')
            return
        out = {"choices": [{"message": reply_for(body), "finish_reason": "stop"}],
               "usage": {"prompt_tokens": 100 * len(body["messages"]), "completion_tokens": 20}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["AGENTLAB_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1"
    try:
        llm = get_llm("vllm:fake-7b")
        run = run_agent(llm, [lookup, calculator], "How much HBM do 8 H100s and 4 A100s have, in GB?")
        assert "960" in run.answer, run.answer
        assert run.steps == 3 and run.tool_calls == 3, (run.steps, run.tool_calls)
        assert llm.prompt_tokens == 100 * (2 + 5 + 7), llm.prompt_tokens  # the server's counts, not our estimate
        assert all(isinstance(c["function"]["arguments"], str) for b in SEEN for m in b["messages"]
                   if m["role"] == "assistant" for c in m.get("tool_calls") or [])
        print(f"ok  agent over HTTP: {run.answer!r} in {run.steps} requests; {llm.usage()}")
        try:
            get_llm("vllm:missing").chat([{"role": "user", "content": "hi"}])
            raise AssertionError("expected an HTTP error")
        except RuntimeError as e:
            assert "HTTP 404" in str(e), e
            print(f"ok  errors are readable: {e}")
    finally:
        server.shutdown()
    os.environ["AGENTLAB_BASE_URL"] = "http://127.0.0.1:9/v1"
    try:
        get_llm("vllm:x").chat([{"role": "user", "content": "hi"}])
    except RuntimeError as e:
        assert "Is the server running" in str(e), e
        print(f"ok  a server that is down: {e}")


if __name__ == "__main__":
    main()
