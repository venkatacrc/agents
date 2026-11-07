"""Lab 03: design tools for a model, not for a programmer (the agent-computer interface).

Run:  python labs/03_tool_design/run.py             (your code)
      python labs/03_tool_design/run.py --solution

Part A of run.py shows how names and descriptions decide which tool a model picks.
You write parts B and C: errors the model can recover from, and arguments that can't be wrong.
"""
import difflib  # noqa: F401  difflib.get_close_matches(word, choices, n=3, cutoff=0.5)


class NotFound(Exception):
    """Raised by tools when an id doesn't exist; carries the ids that do."""

    def __init__(self, kind, value, choices):
        super().__init__(f"no {kind} {value!r}")
        self.kind, self.value, self.choices = kind, value, list(choices)


def helpful_error(exc, tool):
    """Turn an exception into a message that tells the model how to fix its call.

    NotFound  -> "Error: no job 'job-12'. Did you mean: job-121, job-123? Valid job ids: ..."
                 The mock model retries with the first id after "Did you mean: ", so keep that wording.
    TypeError -> the error plus the tool's parameters and their types (tool.parameters["properties"]).
    other     -> "Error: <type>: <message>"
    """
    # TODO 1
    raise NotImplementedError("helpful_error")


def coerce_args(args, schema):
    """Return a copy of args with string values converted to the schema's type.

    Models often send {"replicas": "3"} for an integer. "3" -> 3 for "integer", "2.5" -> 2.5 for
    "number", "true"/"false" -> bool for "boolean". Leave anything that doesn't convert unchanged.
    """
    # TODO 2
    raise NotImplementedError("coerce_args")


def call_tool(tool, args):
    """Coerce, run, and turn any exception into helpful_error(...). Returns text, never raises."""
    # TODO 3
    raise NotImplementedError("call_tool")
