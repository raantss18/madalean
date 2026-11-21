"""Tool-using agent loop: native Anthropic tool use, OpenAI-style tools, or the JSON-in-text protocol for models
without tool support (convo.py). Bounded by steps, wall time and a token budget; tool errors go back to the model;
parallel tool calls run concurrently; switches to the next model on provider failure, keeping the transcript."""
from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from .. import leancheck
from . import convo
from .api import AgentResult, OnChunk, ToolSpec
from .providers.base import ProviderError, StreamResult, emit

if TYPE_CHECKING:
    from .engine import MadaleanBrain

MAX_RESULT_CHARS = 12000
MAX_NUDGES = 2


class StopAgent(Exception):
    """Raised by a tool to end the run successfully (e.g. `submit` accepted). `text` becomes final_text."""

    def __init__(self, text: str, result_for_model: str = "Accepted."):
        super().__init__(text)
        self.text, self.result_for_model = text, result_for_model


def validate(args: dict, schema: dict) -> str:
    """Minimal JSON-schema check (required keys and basic types): returns an error message or ''."""
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    props = schema.get("properties") or {}
    missing = [r for r in schema.get("required") or [] if r not in args]
    if missing:
        return f"missing required argument(s): {', '.join(missing)}"
    types = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
    for k, v in args.items():
        t = (props.get(k) or {}).get("type")
        if isinstance(t, str) and t in types and not isinstance(v, types[t]):
            if t == "integer" and isinstance(v, str) and v.strip().lstrip("-").isdigit():
                args[k] = int(v)
                continue
            return f"argument {k!r} must be of type {t}"
    return ""


async def _run_one(call: dict, tools: dict[str, ToolSpec]) -> tuple[str, bool, StopAgent | None]:
    if call.get("error") or call.get("input") is None:
        raw = call.get("arguments") or ""
        return json.dumps({"INVALID_JSON": raw[:2000], "error": call.get("error") or "invalid arguments"}), True, None
    spec = tools.get(call["name"])
    if spec is None:
        return f"Error: unknown tool {call['name']!r}. Available tools: {', '.join(tools)}.", True, None
    err = validate(call["input"], spec.parameters)
    if err:
        return f"Error: {err}.", True, None
    try:
        out = await spec.run(call["input"])
        return str(out), False, None
    except StopAgent as s:
        return s.result_for_model, False, s
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 (tool failures are information for the model)
        return f"Error while running {call['name']}: {type(e).__name__}: {e}", True, None


def _clip(s: str) -> str:
    if len(s) <= MAX_RESULT_CHARS:
        return s
    return s[: MAX_RESULT_CHARS - 200] + f"\n… [{len(s) - MAX_RESULT_CHARS + 200} more characters cut]"


async def run_agent_loop(brain: "MadaleanBrain", role: str, system: str, task: str, tools: list[ToolSpec], *,
                         mode: str, max_steps: int, max_seconds: float, on_chunk: OnChunk | None,
                         prefer: str | None, require_tool: str | None, max_tokens_budget: int) -> AgentResult:
    t0 = time.monotonic()
    deadline = t0 + max_seconds
    specs = {t.name: t for t in tools}
    tool_defs = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]
    chain = brain.ranking(role, mode, prefer=prefer, need_tools=False)
    # models with native tools first, then the others (text protocol) — order kept within each group
    chain = [c for c in chain if c.model.tools] + [c for c in chain if not c.model.tools]
    if not chain:
        from .api import BrainError
        raise BrainError("no_model", f"no model available for an agent ({mode} mode)")
    idx = 0
    native = chain[0].model.tools
    history: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    transcript: list[dict] = [{"type": "task", "text": task}]
    steps, tokens, nudges = 0, 0, 0
    final_text, finish = "", "error"
    tried: list[str] = []
    model = chain[0].model
    emit(on_chunk, "info", f"agent: {model.name}", event="model", model=model.key)

    def sys_for(native_: bool) -> list[dict]:
        if native_:
            return history
        h = [dict(m) for m in history]
        h[0] = {"role": "system", "content": system + "\n\n" + convo.text_protocol_prompt(tool_defs)}
        return h

    while True:
        if steps >= max_steps:
            finish = "max_steps"
            break
        if tokens >= max_tokens_budget:
            finish = "budget"
            break
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            finish = "budget"
            break
        model = chain[idx].model
        try:
            res: StreamResult = await asyncio.wait_for(
                brain._generate(model, role, mode=mode, history=sys_for(native), tools=tool_defs if native else None,
                                on_chunk=on_chunk), remaining)
        except asyncio.TimeoutError:
            finish = "budget"
            break
        except ProviderError as e:
            if e.kind == "tools_unsupported" and native:
                native = False
                emit(on_chunk, "info", "tools not supported: text protocol", event="protocol", model=model.key)
                continue
            if e.kind == "context" and not model.paid and _elide(history):
                continue
            why = await brain._on_failure(model, e, mode)
            tried.append(f"{model.key}: {why}")
            transcript.append({"type": "model_error", "model": model.key, "reason": why})
            idx += 1
            while idx < len(chain) and not chain[idx].model.local and brain.http.known_offline():
                idx += 1
            if idx >= len(chain):
                final_text = "no model could continue:\n" + "\n".join(tried)
                finish = "error"
                break
            native = chain[idx].model.tools
            emit(on_chunk, "info", f"→ {chain[idx].model.name}", event="switch", model=chain[idx].model.key, reason=why)
            continue
        steps += 1
        tokens += res.tokens_out + max(0, res.tokens_in - res.cache_read)
        brain.states.record(model.key, True)
        if native:
            calls = [{"id": c.id, "name": c.name, "input": c.input, "arguments": c.arguments, "error": c.error}
                     for c in res.tool_calls]
        else:
            calls = convo.parse_text_calls(res.text, tool_defs)
        msg: dict = {"role": "assistant", "content": res.text, "tool_calls": [dict(c) for c in calls],
                     "text_protocol": not native}
        if res.raw_blocks and model.provider == "anthropic":
            msg["anthropic_blocks"] = res.raw_blocks
        convo.fix_ids([msg])
        for c, mc in zip(calls, msg["tool_calls"]):
            c["id"] = mc["id"]
        history.append(msg)
        transcript.append({"type": "assistant", "step": steps, "model": model.key, "text": res.text,
                           "thinking": res.thinking[:4000], "finish": res.finish,
                           "tool_calls": [{"id": c["id"], "name": c["name"], "input": c.get("input")} for c in calls]})
        if res.finish == "loop":
            emit(on_chunk, "info", "loop detected", event="loop", model=model.key)
        if not calls:
            text = leancheck.clean_model_text(res.text)
            if require_tool and nudges < MAX_NUDGES and res.finish != "refusal":
                nudges += 1
                note = (f"You have not called `{require_tool}`. Continue working with the tools, and finish by calling "
                        f"`{require_tool}`.")
                if res.finish == "length":
                    note = "Your answer was cut (output limit). Be shorter. " + note
                history.append({"role": "user", "content": note})
                transcript.append({"type": "nudge", "text": note})
                continue
            final_text, finish = text, ("done" if not require_tool else "error")
            break
        for c in calls:
            emit(on_chunk, "tool_call", c["name"], id=c["id"], name=c["name"], input=c.get("input"))
        outs = await asyncio.gather(*(_run_one(c, specs) for c in calls))
        results, stop = [], None
        for c, (out, is_err, st) in zip(calls, outs):
            out = _clip(out)
            results.append({"id": c["id"], "name": c["name"], "content": out, "is_error": is_err})
            emit(on_chunk, "tool_result", out[:2000], id=c["id"], name=c["name"], is_error=is_err)
            transcript.append({"type": "tool_result", "id": c["id"], "name": c["name"], "content": out,
                               "is_error": is_err})
            stop = stop or st
        history.append({"role": "tool_results", "results": results})
        if stop is not None:
            final_text, finish = stop.text, "done"
            break
    return AgentResult(final_text, _ref(chain[min(idx, len(chain) - 1)].model), steps, finish, transcript)


def _ref(m):
    from .engine import ref_of
    return ref_of(m)


def _elide(history: list[dict]) -> bool:
    """Free models with small contexts: shorten old tool results (never done for paid / Anthropic models, whose
    history must stay append-only). Returns False when nothing more can be removed."""
    idxs = [i for i, m in enumerate(history) if m["role"] == "tool_results"]
    changed = False
    for i in idxs[:-2]:
        for r in history[i]["results"]:
            if len(r["content"]) > 300:
                r["content"] = r["content"][:300] + "\n… [old result shortened]"
                changed = True
    return changed
