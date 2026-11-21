"""JupyterLab child + reverse proxy, for real: status, lab page, contents API, kernel over WebSocket, cleanup."""
import asyncio
import json
import os
import shutil
import uuid

import aiohttp
import pytest
from aiohttp import web

from madalean.jupyter import JupyterManager, safe_path

pytestmark = pytest.mark.skipif(not shutil.which("jupyter-lab"), reason="jupyter-lab not installed")


def test_safe_path():
    assert safe_path("") == "" and safe_path("a/b.ipynb") == "a/b.ipynb"
    for bad in ("../x.ipynb", "/etc/passwd", "a/../../b", "a\x00b", ".hidden/x.ipynb", "~/x", "a\\..\\b"):
        with pytest.raises(ValueError):
            safe_path(bad)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False


async def _main(tmp_path):
    events = []
    m = JupyterManager(tmp_path / "notebooks", tmp_path / "runtime", lambda t, p: events.append((t, p)))
    app = web.Application()
    app.router.add_route("*", "/jupyter/{tail:.*}", m.proxy)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    base = f"http://127.0.0.1:{port}"
    pid = None
    try:
        st = await m.start()
        assert st["state"] == "ready", st
        assert st["port"] not in (8888, 8890) and "python3" in st["kernels"]
        assert st["lean_kernel"]["available"] is False and "Lean" in st["lean_kernel"]["note"]
        pid = m.proc.pid
        async with aiohttp.ClientSession() as s:
            # a Madalean cookie / bearer from the client must not reach jupyter, nor break it
            hdr = {"Cookie": "madalean_token=SECRET", "Authorization": "Bearer SECRET", "Origin": "https://evil.example"}
            async with s.get(base + "/jupyter/api/status", headers=hdr) as r:
                assert r.status == 200, await r.text()
                assert "started" in await r.json()
            async with s.get(base + "/jupyter/lab") as r:
                assert r.status == 200 and "html" in r.headers["Content-Type"]
                assert m._token not in await r.text()          # the child token never reaches clients
            await m.create_notebook("work/t.ipynb")
            assert (await m.append_cell("work/t.ipynb", "print(6*7)")) == {"path": "work/t.ipynb", "index": 0}
            await m.append_cell("work/t.ipynb", "# note", "markdown")
            nb = await m.read_notebook("work/t.ipynb")
            assert [c["source"] for c in nb["cells"]] == ["print(6*7)", "# note"] and nb["kernel"] == "python3"
            names = [n["path"] for n in await m.list_notebooks()]
            assert "work/t.ipynb" in names
            for bad in ("../x.ipynb", "/etc/passwd"):
                with pytest.raises(ValueError):
                    await m.read_notebook(bad)
            # kernel through the proxy (HTTP + WebSocket)
            async with s.post(base + "/jupyter/api/kernels", json={"name": "python3"}) as r:
                assert r.status == 201, await r.text()
                kid = (await r.json())["id"]
            async with s.ws_connect(base + f"/jupyter/api/kernels/{kid}/channels") as ws:
                msg_id = uuid.uuid4().hex
                await ws.send_str(json.dumps({
                    "header": {"msg_id": msg_id, "username": "t", "session": uuid.uuid4().hex, "msg_type": "execute_request",
                               "version": "5.3", "date": ""},
                    "parent_header": {}, "metadata": {}, "channel": "shell", "buffers": [],
                    "content": {"code": "print(6*7)", "silent": False, "store_history": False,
                                "user_expressions": {}, "allow_stdin": False, "stop_on_error": True}}))
                got = ""
                deadline = asyncio.get_running_loop().time() + 60
                while "42" not in got and asyncio.get_running_loop().time() < deadline:
                    m_ = await ws.receive(timeout=60)
                    if m_.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m_.data)
                    if d.get("msg_type") == "stream" and d.get("parent_header", {}).get("msg_id") == msg_id:
                        got += d["content"]["text"]
                assert "42" in got
            async with s.delete(base + f"/jupyter/api/kernels/{kid}") as r:
                assert r.status == 204
    finally:
        await m.stop()
        await runner.cleanup()
    assert m.status()["state"] == "stopped"
    if pid:
        for _ in range(50):
            if not _alive(pid):
                break
            await asyncio.sleep(0.1)
        assert not _alive(pid)
    assert any(t == "jupyter.status" for t, _p in events)


def test_jupyter_proxy_end_to_end(tmp_path):
    asyncio.run(_main(tmp_path))


def test_proxy_503_when_jupyter_missing(tmp_path):
    async def main():
        m = JupyterManager(tmp_path / "nb", tmp_path / "rt", lambda t, p: None, exe=str(tmp_path / "no-such-exe"))
        m.exe = None
        app = web.Application()
        app.router.add_route("*", "/jupyter/{tail:.*}", m.proxy)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        try:
            async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/jupyter/api/status") as r:
                assert r.status == 503 and (await r.json())["error"] == "jupyter_unavailable"
        finally:
            await runner.cleanup()
            await m.stop()
    asyncio.run(main())
