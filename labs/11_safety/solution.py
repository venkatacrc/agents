"""Lab 11 reference: guardrails in the harness, not in the prompt."""
import json


class Guard:
    def __init__(self, allowed_domains, secrets, ask_human):
        self.allowed_domains = set(allowed_domains)
        self.secrets = list(secrets)
        self.ask_human = ask_human
        self.tainted = False
        self.log = []

    def observe(self, tool):
        if tool.meta.get("untrusted"):
            self.tainted = True

    def check(self, call, tool):
        blob = json.dumps(call.args)
        if any(s in blob for s in self.secrets):
            return False, "the arguments contain a secret"
        if call.name == "send_email":
            domain = str(call.args.get("to", "")).rpartition("@")[2].lower()
            if domain not in self.allowed_domains:
                return False, f"{domain or 'that address'} is not an allowed recipient domain"
        if tool.risk != "read" and self.tainted:
            if not self.ask_human(call):
                return False, "the user did not approve this action"
        return True, ""

    def execute(self, box):
        def run(call):
            tool = box.get(call.name)
            if tool is None:
                return f"Error: no tool {call.name!r}"
            ok, why = self.check(call, tool)
            self.log.append((call.name, ok, why))
            if not ok:
                return f"Blocked by guardrail: {why}."
            result = box.run(call)
            self.observe(tool)
            return result
        return run
