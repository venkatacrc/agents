"""Lab 03 reference: error messages a model can act on, and arguments coerced to the schema."""
import difflib


class NotFound(Exception):
    """Raised by tools when an id doesn't exist; carries the ids that do."""

    def __init__(self, kind, value, choices):
        super().__init__(f"no {kind} {value!r}")
        self.kind, self.value, self.choices = kind, value, list(choices)


def helpful_error(exc, tool):
    if isinstance(exc, NotFound):
        near = difflib.get_close_matches(str(exc.value), exc.choices, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        return f"Error: no {exc.kind} {exc.value!r}.{hint} Valid {exc.kind} ids: {', '.join(exc.choices)}."
    if isinstance(exc, TypeError):
        params = ", ".join(f"{k} ({v.get('type')})" for k, v in tool.parameters["properties"].items())
        return f"Error: {exc}. {tool.name} takes: {params}."
    return f"Error: {type(exc).__name__}: {exc}"


def coerce_args(args, schema):
    out = dict(args)
    for name, value in args.items():
        kind = schema["properties"].get(name, {}).get("type")
        if not isinstance(value, str):
            continue
        try:
            if kind == "integer":
                out[name] = int(value.strip())
            elif kind == "number":
                out[name] = float(value.strip())
            elif kind == "boolean" and value.strip().lower() in ("true", "false", "yes", "no"):
                out[name] = value.strip().lower() in ("true", "yes")
        except ValueError:
            pass  # leave it; validation or the tool will report it
    return out


def call_tool(tool, args):
    try:
        return str(tool.fn(**coerce_args(args, tool.parameters)))
    except Exception as e:  # noqa: BLE001
        return helpful_error(e, tool)
