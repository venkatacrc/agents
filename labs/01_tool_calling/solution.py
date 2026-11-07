"""Lab 01 reference: JSON schemas from Python functions, a forgiving tool-call parser, argument validation."""
import ast
import inspect
import json
import re
import typing

from agentlab.tools import parse_docstring

JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


def type_schema(annotation):
    origin = typing.get_origin(annotation)
    if origin is typing.Union:  # Optional[X] is Union[X, None]
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return type_schema(args[0])
    if origin is typing.Literal:
        values = list(typing.get_args(annotation))
        return {"type": JSON_TYPES.get(type(values[0]), "string"), "enum": values}
    if origin is list:
        (item,) = typing.get_args(annotation) or (str,)
        return {"type": "array", "items": type_schema(item)}
    if origin is dict:
        return {"type": "object"}
    return {"type": JSON_TYPES.get(annotation, "string")}


def function_schema(fn):
    hints = typing.get_type_hints(fn)
    _, docs = parse_docstring(fn.__doc__)
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        s = type_schema(hints.get(name, str))
        if name in docs:
            s["description"] = docs[name]
        if p.default is inspect.Parameter.empty:
            required.append(name)
        else:
            s["default"] = p.default
        props[name] = s
    return {"type": "object", "properties": props, "required": required}


def json_objects(text):
    """Yield every top-level {...} span, matching braces outside of strings."""
    depth, start, in_str, quote, esc = 0, None, False, "", False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        elif ch in "\"'" and depth:  # quotes in the prose around the JSON ("I'll ...") don't count
            in_str, quote = True, ch
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                yield text[start:i + 1]
    if depth:
        yield None  # an object that never closed: the output was cut off


def loads_lenient(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", s))  # trailing commas
    except json.JSONDecodeError:
        pass
    return ast.literal_eval(s)  # Python-style quotes and True/False/None


def parse_tool_calls(text):
    calls = []
    for span in json_objects(text):
        if span is None:
            return calls, "unterminated JSON object (was the output truncated?)"
        try:
            obj = loads_lenient(span)
        except (ValueError, SyntaxError) as e:
            return calls, f"could not parse {span[:40]!r}: {e}"
        if not isinstance(obj, dict) or "name" not in obj:
            continue
        args = obj.get("arguments", obj.get("parameters", {}))
        if isinstance(args, str):
            args = loads_lenient(args)
        calls.append({"name": obj["name"], "arguments": args})
    return calls, None


CHECK = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


def validate(args, schema):
    errors = []
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in args:
            errors.append(f"missing required argument {name!r}")
    for name, value in args.items():
        if name not in props:
            errors.append(f"unknown argument {name!r}")
            continue
        s = props[name]
        want = CHECK.get(s.get("type"))
        bad_bool = isinstance(value, bool) and s.get("type") in ("integer", "number")
        if want and (not isinstance(value, want) or bad_bool):
            errors.append(f"{name} should be {s['type']}, got {type(value).__name__} {value!r}")
        elif "enum" in s and value not in s["enum"]:
            errors.append(f"{name} must be one of {s['enum']}, got {value!r}")
    return errors
