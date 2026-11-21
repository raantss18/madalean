"""Live calls to the scholarly APIs (arXiv, Crossref/doi.org, OpenAlex, OpenLibrary, zbMATH Open, Semantic Scholar).

Skipped unless MADALEAN_ONLINE_TESTS=1. With MADALEAN_RECORD=1 the answers are (re)recorded into
tests/data/research/http/ — the fixtures replayed by the offline tests (tests/test_sources_api.py)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from madalean.research import litsearch
from madalean.research.fetch import AiohttpTransport, Fetcher, FetchError, RecordingTransport

pytestmark = [pytest.mark.online,
              pytest.mark.skipif(os.environ.get("MADALEAN_ONLINE_TESTS") != "1", reason="online tests disabled")]
FIX = Path(__file__).parent / "data" / "research" / "http"


def fetcher() -> Fetcher:
    t = AiohttpTransport()
    if os.environ.get("MADALEAN_RECORD") == "1":
        return Fetcher(RecordingTransport(t, FIX))
    return Fetcher(t)


async def test_live_identifiers():
    f = fetcher()
    try:
        doi = await litsearch.resolve(f, "10.2307/2118559", "auto")
        assert doi.item["title"].startswith("Modular Elliptic Curves") and doi.item["author"][0]["family"] == "Wiles"
        assert doi.oa.get("status") in ("closed", "bronze", "green", "gold", "hybrid", "diamond")
        ax = await litsearch.resolve(f, "arXiv:2603.29335", "auto")
        assert "spectral radius" in ax.item["title"].lower() and ax.eprint
        isbn = await litsearch.resolve(f, "978-0-19-853171-5", "auto")
        assert "theory of numbers" in isbn.item["title"].lower()
        zb = await litsearch.resolve(f, "Zbl 0965.11001", "auto")
        assert zb.item["title"] == "Twenty years of number theory" and zb.item["msc"]
    finally:
        await f.close()


async def test_live_search_and_related():
    f = fetcher()
    try:
        res = await litsearch.search(f, "Hilton-Milner theorem short proof", "auto", n=6)
        provs = res["providers"]
        assert provs["arxiv"]["ok"] and provs["crossref"]["ok"] and provs["openalex"]["ok"]
        assert any("hilton" in r["title"].lower() for r in res["results"][:5])
        assert any(len(r["providers"]) > 1 for r in res["results"])            # merged across providers
        rel = await litsearch.related(f, "10.2307/2118559", "references", "auto", n=5)
        assert rel and all(r["title"] for r in rel)
    finally:
        await f.close()


async def test_live_eprint_and_ssrf_resolver():
    f = Fetcher(AiohttpTransport())
    try:
        data, ctype = await litsearch.arxiv_source(f, "2603.29335", "auto")
        assert data[:2] == b"\x1f\x8b" and ctype == "application/gzip"
        # a public name that resolves to loopback is refused by the resolver (resolve-then-connect)
        with pytest.raises(FetchError) as e:
            await f.get("https://localtest.me/", mode="auto", policy="public")
        assert e.value.kind in ("blocked", "network")
    finally:
        await f.close()
