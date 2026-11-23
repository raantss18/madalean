"""A strict subset of JSON Schema for the inputs of Madalean's MCP tools (session S-AZ, DECISIONS D58).

Every tool declares its input with: `type` (object, string, integer, number, boolean, array), `properties`,
`required`, `additionalProperties: false` (always, for objects: an unknown key is an error, never ignored), `enum`,
`minLength` / `maxLength`, `pattern`, `minimum` / `maximum`, `items`, `maxItems`. `validate` answers the list of
problems ([] = valid); nothing is coerced (a number given as a string is refused) and booleans are never integers.

The same module cleans the input schemas that EXTERNAL servers declare before a model sees them (`sanitize`): only
these keywords survive, descriptions are capped, depth and size are bounded."""
from __future__ import annotations

import re
from typing import Any

MAX_DEPTH = 6
_TYPES = {"object": dict, "string": str, "array": list, "boolean": bool}


def _type_ok(value: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "null":
        return value is None
    py = _TYPES.get(t)
    return py is not None and isinstance(value, py)


def validate(value: Any, schema: dict, path: str = "") -> list[str]:
    """Problems of `value` against `schema` (strict subset above), as short English phrases with the JSON path."""
    where = path or "arguments"
    t = schema.get("type")
    if isinstance(t, str) and not _type_ok(value, t):
        return [f"{where}: expected {t}"]
    out: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{where}: must be one of {', '.join(map(str, schema['enum']))}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(f"{where}: at least {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{where}: at most {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{where}: invalid format")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{where}: at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{where}: at most {schema['maximum']}")
    if isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{where}: at most {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, v in enumerate(value[:1000]):
                out += validate(v, schema["items"], f"{where}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for k in schema.get("required") or []:
            if k not in value:
                out.append(f"{where}: missing required '{k}'")
        for k, v in value.items():
            if k not in props:
                if schema.get("additionalProperties", False) is False:
                    out.append(f"{where}: unknown property '{str(k)[:40]}'")
                continue
            out += validate(v, props[k], f"{where}.{k}" if path else k)
    return out


# ---------------------------------------------------------------- external schemas (MCP client side)
_KEEP = {"type", "properties", "required", "enum", "items", "description", "minLength", "maxLength", "minimum",
         "maximum", "maxItems", "default", "additionalProperties"}
_SIMPLE_TYPES = {"object", "string", "integer", "number", "boolean", "array", "null"}


def sanitize(schema: Any, depth: int = 0, desc_max: int = 200) -> dict:
    """An external tool's input schema reduced to the keywords above (anything else is dropped: `$ref`, `oneOf`,
    vendor extensions…), with capped descriptions. Never raises; a malformed schema becomes {"type": "object"}."""
    if not isinstance(schema, dict) or depth > MAX_DEPTH:
        return {"type": "object", "properties": {}, "additionalProperties": True} if depth == 0 else {}
    out: dict = {}
    for k, v in schema.items():
        if k not in _KEEP:
            continue
        if k == "type":
            if isinstance(v, str) and v in _SIMPLE_TYPES:
                out[k] = v
            elif isinstance(v, list):
                ts = [x for x in v if isinstance(x, str) and x in _SIMPLE_TYPES][:4]
                if ts:
                    out[k] = ts
        elif k == "properties" and isinstance(v, dict):
            out[k] = {str(name)[:64]: sanitize(sub, depth + 1, desc_max) for name, sub in list(v.items())[:40]
                      if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.-]{1,64}$", name)}
        elif k == "required" and isinstance(v, list):
            out[k] = [str(x)[:64] for x in v if isinstance(x, str)][:40]
        elif k == "items":
            out[k] = sanitize(v, depth + 1, desc_max)
        elif k == "description" and isinstance(v, str):
            out[k] = clean_text(v, desc_max)
        elif k == "enum" and isinstance(v, list):
            out[k] = [x for x in v if isinstance(x, (str, int, float, bool)) and len(str(x)) <= 100][:50]
        elif k in ("minLength", "maxLength", "minimum", "maximum", "maxItems") and isinstance(v, (int, float)) \
                and not isinstance(v, bool):
            out[k] = v
        elif k == "additionalProperties" and isinstance(v, bool):
            out[k] = v
        elif k == "default" and isinstance(v, (str, int, float, bool)) and len(str(v)) <= 200:
            out[k] = v
    if out.get("type") == "object" or "properties" in out:
        out.setdefault("additionalProperties", True)    # external schemas: unknown keys are the server's business
    if depth == 0:
        out["type"] = "object"
        out.setdefault("properties", {})
        if "required" in out:
            out["required"] = [r for r in out["required"] if r in out["properties"]]
    return out


# control, zero-width and bidirectional-override characters (as news/parsers.py): never shown to a model or a user
_CTRL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁠-⁩﻿]")


def clean_text(text: Any, limit: int) -> str:
    s = _CTRL.sub("", text if isinstance(text, str) else "")
    return s if len(s) <= limit else s[: max(0, limit - 1)] + "…"
