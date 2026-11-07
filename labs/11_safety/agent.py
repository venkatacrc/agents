"""Lab 11: safety. Anything a tool returns can contain instructions, and models follow instructions.

Run:  python labs/11_safety/run.py             (your code)
      python labs/11_safety/run.py --solution

Defend in the harness, where the rules are code, not in the prompt, where they are suggestions:
  1. never let a secret leave in tool arguments
  2. least privilege: email only goes to allowed domains
  3. taint tracking: once untrusted content (emails, web pages) is in the context, every action with side
     effects needs a human's approval
"""
import json  # noqa: F401


class Guard:
    def __init__(self, allowed_domains, secrets, ask_human):
        """ask_human(call) -> bool is the approval prompt (run.py scripts the human)."""
        self.allowed_domains = set(allowed_domains)
        self.secrets = list(secrets)
        self.ask_human = ask_human
        self.tainted = False
        self.log = []

    def observe(self, tool):
        """Called after a tool runs. tool.meta.get("untrusted") marks tools whose output comes from outside
        (emails, web pages): from then on the context is tainted."""
        # TODO 1
        raise NotImplementedError("Guard.observe")

    def check(self, call, tool):
        """Return (allowed, reason). In order:
        - any secret string appears in json.dumps(call.args)          -> block
        - send_email to a domain not in allowed_domains                -> block
        - tool.risk != "read" while tainted and the human says no      -> block
        """
        # TODO 2
        raise NotImplementedError("Guard.check")

    def execute(self, box):
        """Return an execute(call) -> str function for run_agent: check, then either return
        "Blocked by guardrail: <reason>." or run box.run(call), observe(tool), and return the result.
        Append (call.name, allowed, reason) to self.log."""
        # TODO 3
        raise NotImplementedError("Guard.execute")
