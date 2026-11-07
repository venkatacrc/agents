"""Tools: a Python function plus the JSON schema the model sees.

    @tool
    def lookup(topic: str) -> str:
        '''Look up a fact in the knowledge base.

        Args:
            topic: what to look up, e.g. "H100"
        '''

The decorator reads the signature and the docstring (Lab 01 builds this from
scratch). `risk` tags a tool for approval policies (Lab 08): "read" tools only
look, "write" tools change things, "destructive" ones can't be undone.
"""
from __future__ import annotations

import inspect
import json
import re
import typing
from dataclasses import dataclass, field
from typing import Callable, Optional

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


def _type_schema(annotation) -> dict:
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _type_schema(args[0]) if args else {}
    if origin is typing.Literal:
        values = list(typing.get_args(annotation))
        return {"type": _JSON_TYPES.get(type(values[0]), "string"), "enum": values}
    if origin in (list, typing.List):
        (item,) = typing.get_args(annotation) or (str,)
        return {"type": "array", "items": _type_schema(item)}
    if origin in (dict, typing.Dict):
        return {"type": "object"}
    return {"type": _JSON_TYPES.get(annotation, "string")}


def parse_docstring(doc: str):
    """Split a Google-style docstring into (description, {arg: description})."""
    doc = inspect.cleandoc(doc or "")
    head, _, rest = doc.partition("\nArgs:")
    params, current = {}, None
    for line in rest.splitlines():
        m = re.match(r"^\s{2,}(\w+)\s*(?:\([^)]*\))?:\s*(.*)$", line)
        if m:
            current = m.group(1)
            params[current] = m.group(2).strip()
        elif current and line.strip() and not re.match(r"^\S", line):
            params[current] += " " + line.strip()
        elif re.match(r"^\S", line):
            current = None
    return " ".join(head.split()), params


def function_schema(fn: Callable) -> dict:
    """The JSON schema for fn's parameters, from its type hints and docstring."""
    hints = typing.get_type_hints(fn)
    _, docs = parse_docstring(fn.__doc__)
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        s = _type_schema(hints.get(name, str))
        if name in docs:
            s["description"] = docs[name]
        if p.default is inspect.Parameter.empty:
            required.append(name)
        else:
            s["default"] = p.default
        props[name] = s
    return {"type": "object", "properties": props, "required": required}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable
    risk: str = "read"
    meta: dict = field(default_factory=dict)

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

    def __call__(self, **kwargs):
        return self.fn(**kwargs)


def tool(fn: Optional[Callable] = None, *, name: Optional[str] = None, risk: str = "read",
         description: Optional[str] = None):
    def wrap(f):
        desc, _ = parse_docstring(f.__doc__)
        return Tool(name=name or f.__name__, description=description or desc, parameters=function_schema(f),
                    fn=f, risk=risk)
    return wrap(fn) if fn else wrap


class Toolbox:
    """Tools by name. run() never raises: errors go back to the model as text."""

    def __init__(self, tools=()):
        self.tools = {t.name: t for t in tools}

    def __iter__(self):
        return iter(self.tools.values())

    def __len__(self):
        return len(self.tools)

    def __contains__(self, name):
        return name in self.tools

    def get(self, name):
        return self.tools.get(name)

    def add(self, t: Tool):
        self.tools[t.name] = t

    def run(self, call) -> str:
        t = self.tools.get(call.name)
        if t is None:
            return f"Error: no tool named {call.name!r}. Available tools: {', '.join(self.tools)}."
        try:
            out = t.fn(**call.args)
        except TypeError as e:
            return f"Error: bad arguments for {call.name}: {e}. Expected parameters: {json.dumps(t.parameters['properties'])}"
        except Exception as e:  # noqa: BLE001 - every failure becomes an observation
            return f"Error: {type(e).__name__}: {e}"
        return out if isinstance(out, str) else json.dumps(out)
