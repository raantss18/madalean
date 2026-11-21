"""Real-network tests (skipped unless MADALEAN_ONLINE_TESTS=1): public Lean search services, the free keyless
providers, the catalogue refresh. Marker `online` (register it in pytest.ini: `online: needs the Internet`)."""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.online,
              pytest.mark.skipif(os.environ.get("MADALEAN_ONLINE_TESTS") != "1", reason="set MADALEAN_ONLINE_TESTS=1")]


def test_lean_search_services():
    from madalean.brain.lean_search import search_online
    from madalean.brain.net import Http

    async def main():
        h = Http({})
        try:
            return await search_online(h, "Even a → Even b → Even (a + b)", 6)
        finally:
            await h.close()
    res, failed = asyncio.run(main())
    assert any(r["name"] == "Even.add" for r in res), (res, failed)


def test_free_provider_completion_and_refresh():
    from madalean.brain import create_brain

    async def main():
        b = create_brain(Path(tempfile.mkdtemp()), None, lambda p: None, {"mode": "online"})
        try:
            await b.refresh()
            n = len(b.store.cat.models)
            c = await b.complete("route", [{"role": "user", "content": "Reply with exactly the word: OK"}], mode="online")
            return n, c
        finally:
            await b.close()
    n, c = asyncio.run(main())
    assert n > 20 and "OK" in c.text.upper() and not c.model.paid
