"""Agent loop: native OpenAI tools, native Anthropic tool use (thinking blocks replayed, parallel results in one
message), text-protocol fallback, model switch mid-run, budgets, tool errors, StopAgent, nudges."""
import asyncio
import json

from madalean.brain import convo
from madalean.brain.agent import StopAgent, validate
from madalean.brain.api import ToolSpec
from test_brain_fakes import FakeServer, an_stream, free_provider, make_brain, model, oa_stream, run, write_catalogue

ADD_SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}


def tools(log):
    async def add(a):
        log.append(("add", a))
        return str(a["a"] + a["b"])

    async def boom(a):
        log.append(("boom", a))
        raise RuntimeError("disk on fire")

    async def finish(a):
        raise StopAgent(a["answer"], "done")
    return [ToolSpec("add", "Add two integers.", ADD_SCHEMA, add),
            ToolSpec("boom", "Always fails.", {"type": "object", "properties": {}}, boom),
            ToolSpec("finish", "Finish with the answer.", {"type": "object", "properties": {"answer": {"type": "string"}},
                                                         "required": ["answer"]}, finish)]


def test_openai_native_tools_parallel_errors_and_final(tmp_path):
    async def main():
        srv = await FakeServer([
            oa_stream("Plan: add.", tool_calls=[("c1", "add", {"a": 2}), ("c2", "boom", {})]),
            oa_stream("", tool_calls=[("c3", "add", {"a": 2, "b": 3})]),
            oa_stream("The answer is 5."),
        ]).start()
        write_catalogue(tmp_path, [free_provider("f", srv.url)], [model("f", "m", 0.8)])
        b = make_brain(tmp_path)
        log, chunks = [], []
        try:
            r = await b.run_agent("assistant", "You are helpful.", "2+3?", tools(log), on_chunk=chunks.append)
        finally:
            await b.close(); await srv.stop()
        assert r.finish == "done" and r.final_text == "The answer is 5." and r.steps == 3
        assert log == [("boom", {}), ("add", {"a": 2, "b": 3})]          # invalid args never reach the tool
        msgs = srv.requests[1].body["messages"]
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]
        assert "missing required argument(s): b" in tool_msgs[0]["content"]
        assert "disk on fire" in tool_msgs[1]["content"]
        assert msgs[2]["tool_calls"][0]["function"]["name"] == "add"
        kinds = [c.kind for c in chunks]
        assert "tool_call" in kinds and "tool_result" in kinds
        assert any(t["type"] == "tool_result" and t["is_error"] for t in r.transcript)
    run(main())


def test_anthropic_tool_use_replays_thinking_and_groups_results(tmp_path):
    async def main():
        srv = await FakeServer([
            an_stream([("thinking", "I should add.", "SIG-1"), ("text", "Adding."),
                       ("tool_use", "toolu_01", "add", {"a": 1, "b": 2}), ("tool_use", "toolu_02", "add", {"a": 3, "b": 4})]),
            an_stream([("thinking", "done", "SIG-2"), ("tool_use", "toolu_03", "finish", {"answer": "3 and 7"})]),
        ]).start()
        write_catalogue(tmp_path, [free_provider("dead", "http://127.0.0.1:9/v1")], [model("dead", "dead", 0.01)])
        b = make_brain(tmp_path, keys={"anthropic": "sk-ant-x"}, endpoints={"anthropic": srv.url})
        log = []
        try:
            r = await b.run_agent("prove", "System prompt.", "Task.", tools(log), prefer="anthropic:claude-opus-5-5")
        finally:
            await b.close(); await srv.stop()
        assert r.finish == "done" and r.final_text == "3 and 7" and r.model.key == "anthropic:claude-opus-5-5"
        first, second = srv.requests[0].body, srv.requests[1].body
        assert first["system"][0]["text"] == "System prompt." and first["tool_choice"] == {"type": "auto"}
        assert all(t["eager_input_streaming"] for t in first["tools"]) and first["tools"][0]["input_schema"] == ADD_SCHEMA
        assistant = second["messages"][1]
        assert assistant["role"] == "assistant"
        assert assistant["content"][0] == {"type": "thinking", "thinking": "I should add.", "signature": "SIG-1"}
        assert [b_["type"] for b_ in assistant["content"]] == ["thinking", "text", "tool_use", "tool_use"]
        results = second["messages"][2]
        assert results["role"] == "user" and [x["tool_use_id"] for x in results["content"]] == ["toolu_01", "toolu_02"]
        assert [x["content"] for x in results["content"]] == ["3", "7"]
        assert second["messages"][:2] == [first["messages"][0], assistant]            # append-only history
    run(main())


def test_text_protocol_fallback_when_tools_unsupported(tmp_path):
    def answer(body):
        if "tools" in body:
            return {"status": 400, "body": {"error": {"message": "This model does not support tools"}}}
        last = body["messages"][-1]["content"]
        if "<tool_result" in last:
            return oa_stream("Result received: 5. Done.")
        return oa_stream('I will compute.\n<tool_call>\n{"name": "add", "arguments": {"a": 2, "b": 3}}\n</tool_call>')
    async def main():
        srv = await FakeServer([answer]).start()
        write_catalogue(tmp_path, [free_provider("f", srv.url)], [model("f", "m", 0.8)])
        b = make_brain(tmp_path)
        log = []
        try:
            r = await b.run_agent("assistant", "Sys.", "2+3?", tools(log))
        finally:
            await b.close(); await srv.stop()
        assert r.finish == "done" and "5" in r.final_text and log == [("add", {"a": 2, "b": 3})]
        last = srv.requests[-1].body["messages"]
        assert "# Tools" in last[0]["content"] and "<tool_call>" in last[0]["content"]
        assert last[-1]["role"] == "user" and '<tool_result name="add"' in last[-1]["content"]
    run(main())


def test_model_switch_mid_run_keeps_transcript(tmp_path):
    async def main():
        s1 = await FakeServer([oa_stream("", tool_calls=[("c1", "add", {"a": 1, "b": 1})]),
                               {"status": 500, "body": {"error": {"message": "internal"}}}]).start()
        s2 = await FakeServer([oa_stream("Two.")]).start()
        write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                        [model("f1", "a", 0.9), model("f2", "b", 0.5)])
        b = make_brain(tmp_path)
        log = []
        try:
            r = await b.run_agent("assistant", "Sys.", "1+1?", tools(log))
        finally:
            await b.close(); await s1.stop(); await s2.stop()
        assert r.final_text == "Two." and r.model.key == "f2:b"
        msgs = s2.requests[0].body["messages"]
        assert any(m["role"] == "tool" and m["content"] == "2" for m in msgs)
        assert any(t["type"] == "model_error" for t in r.transcript)
    run(main())


def test_budgets_and_nudge(tmp_path):
    async def main():
        srv = await FakeServer([oa_stream("", tool_calls=[("c", "add", {"a": 1, "b": 1})])]).start()
        write_catalogue(tmp_path, [free_provider("f", srv.url)], [model("f", "m", 0.8)])
        b = make_brain(tmp_path)
        try:
            r = await b.run_agent("assistant", "Sys.", "loop", tools([]), max_steps=3)
            assert r.finish == "max_steps" and r.steps == 3
            srv.script[:] = [{"events": [0.5, "data: [DONE]\n\n"]}]
            r = await b.run_agent("assistant", "Sys.", "slow", tools([]), max_seconds=0.3)
            assert r.finish == "budget"
            srv.script[:] = [oa_stream("I think I am done."), oa_stream("", tool_calls=[("c9", "finish", {"answer": "ok"})])]
            r = await b.run_agent("assistant", "Sys.", "do it", tools([]), require_tool="finish")
            assert r.finish == "done" and r.final_text == "ok"
            assert any(t["type"] == "nudge" for t in r.transcript)
        finally:
            await b.close(); await srv.stop()
    run(main())


def test_text_protocol_parser_is_robust():
    defs = [{"name": "lean_check", "description": "", "parameters": {"type": "object", "properties": {"proof": {"type": "string"}},
                                                                     "required": ["proof"]}},
            {"name": "search", "description": "", "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}]
    text = ('<think>maybe <tool_call>{"name":"x"}</tool_call></think>Plan.\n'
            '<tool_call>\n{"name": "lean_check", "arguments": {"proof": "intro x\n  simp"}}\n</tool_call>\n'
            '<tool_call name="lean_check">\n```lean\nexact Even.add ha hb\n```\n</tool_call>\n'
            '<tool_call>{"tool": "search", "args": {"q": "even add",}}\n'
            '<tool_call>{not json</tool_call>')
    calls = convo.parse_text_calls(text, defs)
    assert [c["name"] for c in calls] == ["lean_check", "lean_check", "search", "?"]
    assert calls[0]["input"] == {"proof": "intro x\n  simp"}
    assert calls[1]["input"] == {"proof": "exact Even.add ha hb"}
    assert calls[2]["input"] == {"q": "even add"}
    assert calls[3]["input"] is None and calls[3]["error"]
    assert convo.strip_calls(text).startswith("<think>")
    assert validate({"a": "3", "b": 4}, ADD_SCHEMA) == "" and validate({"a": [1], "b": 1}, ADD_SCHEMA)


def test_history_conversion_between_providers():
    hist = [{"role": "system", "content": "S"}, {"role": "user", "content": "T"},
            {"role": "assistant", "content": "x", "tool_calls": [{"id": "call.1/bad", "name": "add", "input": {"a": 1}}]},
            {"role": "tool_results", "results": [{"id": "call.1/bad", "name": "add", "content": "1", "is_error": False}]}]
    convo.fix_ids(hist[2:3])
    hist[3]["results"][0]["id"] = hist[2]["tool_calls"][0]["id"]
    system, msgs = convo.to_anthropic(hist)
    assert system == "S" and msgs[1]["content"][1]["type"] == "tool_use"
    assert msgs[1]["content"][1]["id"] == msgs[2]["content"][0]["tool_use_id"]
    assert all(c.isalnum() or c in "_-" for c in msgs[1]["content"][1]["id"])
    oa = convo.to_openai(hist, native_tools=False)
    assert "<tool_call>" in oa[2]["content"] and "<tool_result" in oa[3]["content"]
