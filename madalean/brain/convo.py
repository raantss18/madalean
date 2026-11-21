"""Provider-neutral conversation used by the agent loop, and its conversion to each wire format.

Neutral messages:
  {"role": "system"|"user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": [{"id", "name", "input", "arguments"}],
   "anthropic_blocks": [...] (exact content blocks of an Anthropic answer, replayed unchanged), "text_protocol": bool}
  {"role": "tool_results", "results": [{"id", "name", "content", "is_error"}]}

The text protocol (models without native tool calling) writes calls as
  <tool_call>{"name": "...", "arguments": {...}}</tool_call>
and receives results as <tool_result name="..." id="...">…</tool_result> in a user message."""
from __future__ import annotations

import json
import re
import uuid

_ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def safe_id(i: str) -> str:
    return i if _ID_OK.match(i or "") else "call_" + re.sub(r"[^A-Za-z0-9_-]", "", i or "")[:40] + uuid.uuid4().hex[:8]


def render_call(c: dict) -> str:
    return "<tool_call>\n" + json.dumps({"name": c["name"], "arguments": c.get("input") or {}}, ensure_ascii=False) \
        + "\n</tool_call>"


def render_results(results: list[dict]) -> str:
    out = []
    for r in results:
        err = ' error="true"' if r.get("is_error") else ""
        out.append(f'<tool_result name="{r["name"]}" id="{r["id"]}"{err}>\n{r["content"]}\n</tool_result>')
    return "\n\n".join(out)


def to_openai(history: list[dict], native_tools: bool) -> list[dict]:
    out: list[dict] = []
    for m in history:
        r = m["role"]
        if r in ("system", "user"):
            out.append({"role": r, "content": m["content"]})
        elif r == "assistant":
            calls = m.get("tool_calls") or []
            if native_tools and calls and not m.get("text_protocol"):
                out.append({"role": "assistant", "content": m.get("content") or None,
                            "tool_calls": [{"id": c["id"], "type": "function",
                                            "function": {"name": c["name"],
                                                         "arguments": json.dumps(c.get("input") or {}, ensure_ascii=False)
                                                         if c.get("input") is not None else (c.get("arguments") or "{}")}}
                                           for c in calls]})
            elif native_tools and calls:
                # text-protocol turn replayed to a native model: keep the prose, give the calls structurally
                out.append({"role": "assistant", "content": strip_calls(m.get("content") or "") or None,
                            "tool_calls": [{"id": c["id"], "type": "function", "function": {
                                "name": c["name"], "arguments": json.dumps(c.get("input") or {}, ensure_ascii=False)}}
                                for c in calls]})
            else:
                text = m.get("content") or ""
                if calls and not m.get("text_protocol"):
                    text = (text + "\n\n" if text else "") + "\n".join(render_call(c) for c in calls)
                out.append({"role": "assistant", "content": text})
        elif r == "tool_results":
            if native_tools:
                for x in m["results"]:
                    out.append({"role": "tool", "tool_call_id": x["id"], "content": x["content"]})
            else:
                out.append({"role": "user", "content": render_results(m["results"])})
    return out


def to_anthropic(history: list[dict]) -> tuple[str, list[dict]]:
    system = "\n\n".join(m["content"] for m in history if m["role"] == "system")
    out: list[dict] = []

    def add(role: str, blocks: list[dict]) -> None:
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})
    for m in history:
        r = m["role"]
        if r == "user":
            add("user", [{"type": "text", "text": m["content"] or "."}])
        elif r == "assistant":
            if m.get("anthropic_blocks"):
                add("assistant", [dict(b) for b in m["anthropic_blocks"]])
                continue
            blocks: list[dict] = []
            text = strip_calls(m.get("content") or "") if m.get("text_protocol") else (m.get("content") or "")
            if text.strip():
                blocks.append({"type": "text", "text": text})
            for c in m.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": safe_id(c["id"]), "name": c["name"], "input": c.get("input") or {}})
            add("assistant", blocks or [{"type": "text", "text": "…"}])
        elif r == "tool_results":
            add("user", [{"type": "tool_result", "tool_use_id": safe_id(x["id"]) if not _ID_OK.match(x["id"]) else x["id"],
                          "content": x["content"] or "(empty)", **({"is_error": True} if x.get("is_error") else {})}
                         for x in m["results"]])
    return system, out


def fix_ids(history: list[dict]) -> None:
    """Make every tool call id valid for every provider (done once when the call is recorded)."""
    for m in history:
        if m["role"] == "assistant":
            for c in m.get("tool_calls") or []:
                c["id"] = safe_id(c["id"])


# ------------------------------------------------------------------ text protocol
_CALL_RE = re.compile(r"<tool_call(?P<attrs>[^>]*)>(?P<body>.*?)(?:</tool_call>|(?=<tool_call)|\Z)", re.S)
_FENCE_RE = re.compile(r"```[A-Za-z0-9_+-]*\n(.*?)(?:```|\Z)", re.S)


def strip_calls(text: str) -> str:
    return _CALL_RE.sub("", text).strip()


def text_protocol_prompt(tools: list[dict]) -> str:
    lines = ["# Tools", "", "You can call the following tools.", ""]
    for t in tools:
        lines.append(f"## {t['name']}\n{t['description']}\nArguments (JSON schema): "
                     f"{json.dumps(t['parameters'], ensure_ascii=False)}\n")
    lines += [
        "## How to call a tool",
        "Write a block exactly like this (the JSON object must be valid; escape newlines in strings as \\n):",
        '<tool_call>\n{"name": "TOOL_NAME", "arguments": {"ARG": "VALUE"}}\n</tool_call>',
        "When the only required argument is code, you may instead write the code in a fenced block:",
        '<tool_call name="TOOL_NAME">\n```lean\n…code…\n```\n</tool_call>',
        "You may call several tools in one answer. Then STOP and wait: the results arrive in the next message inside "
        "<tool_result> tags. Never write a <tool_result> yourself.",
    ]
    return "\n".join(lines)


def _lenient_json(s: str):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[A-Za-z]*\n?", "", s)
        s = re.sub(r"```\s*$", "", s)
    i = s.find("{")
    if i < 0:
        return None
    s = s[i:]
    for cand in (s, s[: s.rfind("}") + 1]):
        try:
            return json.loads(cand)
        except ValueError:
            pass
        try:   # raw newlines / tabs inside strings (very common with code)
            return json.loads(_escape_ctrl_in_strings(cand))
        except ValueError:
            pass
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", _escape_ctrl_in_strings(cand)))
        except ValueError:
            pass
    return None


def _escape_ctrl_in_strings(s: str) -> str:
    out, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            elif ch == "\n":
                out.append("\\n")
                continue
            elif ch == "\t":
                out.append("\\t")
                continue
            elif ch == "\r":
                continue
        elif ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


def parse_text_calls(text: str, tools: list[dict]) -> list[dict]:
    """Tool calls written with the text protocol; robust to missing closing tags, code fences, raw newlines in
    JSON strings, `{"tool": …, "args": …}` variants. Unknown tool names are kept (the loop answers with an error)."""
    by_name = {t["name"]: t for t in tools}
    visible = re.sub(r"<think>.*?(?:</think>|\Z)", "", text, flags=re.S)
    calls: list[dict] = []
    for k, m in enumerate(_CALL_RE.finditer(visible)):
        attrs, body = m.group("attrs"), m.group("body")
        named = re.search(r'name\s*=\s*"([^"]+)"', attrs)
        name, args, err = None, None, ""
        v = _lenient_json(body) if "{" in body else None
        if isinstance(v, dict) and (v.get("name") or v.get("tool")) and not named:
            name = v.get("name") or v.get("tool")
            args = v.get("arguments", v.get("args", v.get("parameters", v.get("input", {}))))
            if isinstance(args, str):
                args = _lenient_json(args) or {"_raw": args}
        elif named:
            name = named.group(1)
            t = by_name.get(name)
            fence = _FENCE_RE.search(body)
            req = [r for r in (t or {}).get("parameters", {}).get("required", [])]
            if isinstance(v, dict) and not fence:
                args = v.get("arguments", v)
            elif fence and len(req) == 1:
                args = {req[0]: fence.group(1).strip("\n")}
                extra = _lenient_json(body[: fence.start()]) if "{" in body[: fence.start()] else None
                if isinstance(extra, dict):
                    args = {**extra, **args}
            elif fence and t:
                props = list(t.get("parameters", {}).get("properties", {}))
                args = {props[0]: fence.group(1).strip("\n")} if props else {}
            else:
                args = {}
        if not name:
            err = "could not read this tool call (invalid JSON)"
            name = "?"
        if not isinstance(args, dict):
            args, err = None, err or "arguments must be a JSON object"
        calls.append({"id": f"tc{k}_{uuid.uuid4().hex[:8]}", "name": str(name), "input": args,
                      "arguments": body.strip()[:4000], "error": err})
    return calls
