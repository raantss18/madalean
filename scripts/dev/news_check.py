#!/usr/bin/env python3
"""Real fetch check of the « Actualités » sources (docs/NEWS.md §2): ONE polite GET per source through the very
code the server uses (NewsService._get: host allow-list, public-address resolver, generic client name), parsed by
the source's parser. Prints one line per source. Needs the Internet; touches nothing of the user's profile (a
temporary directory holds the store).

    .venv/bin/python scripts/dev/news_check.py                 # every source
    .venv/bin/python scripts/dev/news_check.py arxiv-math ams  # some sources
    .venv/bin/python scripts/dev/news_check.py --record        # also rewrite madalean/news/demo_data (trimmed)

    .venv/bin/python scripts/dev/news_check.py --retrim        # re-cut the recorded answers, no network

The recorded answers are trimmed to a few entries and, for feeds, to excerpts (see `shorten`)."""
from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from madalean.news import parsers, registry  # noqa: E402
from madalean.news.service import DATA, NewsService  # noqa: E402
from madalean.research.fetch import FetchError  # noqa: E402

KEEP = {"arxiv-math": 14, "arxiv-ai": 8, "erdos": 14, "mathlib-feat": 8}
DEFAULT_KEEP = 5


def trim(src, body: bytes) -> bytes:
    n = KEEP.get(src.id, DEFAULT_KEEP)
    if src.parser in ("feed", "arxiv"):
        tag = b"entry" if re.search(rb"<entry[\s>]", body) else b"item"
        seen = 0

        def keep(m):
            nonlocal seen
            seen += 1
            return m.group(0) if seen <= n else b""
        return re.sub(rb"<" + tag + rb"[\s>].*?</" + tag + rb">\s*", keep, body, flags=re.S)
    if src.parser == "github_releases":
        keep = ("tag_name", "name", "html_url", "published_at", "created_at", "prerelease", "draft", "body")
        return json.dumps([{k: r.get(k) for k in keep} for r in json.loads(body)[:n]], ensure_ascii=False,
                          indent=1).encode()
    if src.parser == "github_commits":
        rows = [r for r in json.loads(body) if src.require is None or src.require.search(r["commit"]["message"])]
        rows = (rows + [r for r in json.loads(body) if r not in rows])[:n]      # the additions first, then others
        return json.dumps([{"sha": r["sha"], "html_url": r["html_url"], "commit": {
            "message": r["commit"]["message"][:1200],
            "author": {"name": r["commit"]["author"]["name"], "date": r["commit"]["author"]["date"]}}}
            for r in rows], ensure_ascii=False, indent=1).encode()
    if src.parser == "stackexchange":
        v = json.loads(body)
        v["items"] = v.get("items", [])[:n]
        for q in v["items"]:                       # the owner's avatar and profile links are not needed
            if isinstance(q.get("owner"), dict):
                q["owner"] = {"display_name": q["owner"].get("display_name", "")}
        return json.dumps(v, ensure_ascii=False, indent=1).encode()
    if src.parser == "erdos":
        text = body.decode("utf-8", "replace")
        blocks = [b for b in re.split(r"(?m)^(?=- number:)", text) if b.startswith("- number:")]

        def when(b: str) -> str:
            m = re.search(r'(?m)^  status:\n(?:    .*\n)*?    last_update: "([^"]+)"', b)
            return m.group(1) if m else ""
        blocks.sort(key=when, reverse=True)
        return "".join(blocks[:n]).encode()
    return body


EXCERPT = 600
_MAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def shorten(src, body: bytes) -> bytes:
    """What is committed is an excerpt, as in the app: full article bodies are dropped, descriptions cut to
    EXCERPT characters, e-mail addresses replaced, and a CDN's appended script reduced to a marker."""
    if src.parser != "feed":
        return _MAIL.sub(b"user@example.org", body) if src.parser != "arxiv" else body

    def cut(m):
        head, inner, tail = m.group(1), m.group(2), m.group(3)
        if inner.startswith(b"<![CDATA["):
            text = inner[9:-3].decode("utf-8", "replace")
            if len(text) > EXCERPT:
                text = re.sub(r"<[^>]*$", "", text[:EXCERPT]) + "…"
            return head + b"<![CDATA[" + text.encode() + b"]]>" + tail
        text = inner.decode("utf-8", "replace")
        if len(text) > EXCERPT:
            text = re.sub(r"&[^;\s]{0,12}$", "", text[:EXCERPT]) + "…"
        return head + text.encode() + tail
    body = re.sub(rb"<content:encoded>.*?</content:encoded>\s*", b"", body, flags=re.S)
    body = re.sub(rb"(<(?:description|summary|content)(?:\s[^>]*)?>)(.*?)(</(?:description|summary|content)>)", cut,
                  body, flags=re.S)
    body = re.sub(rb"(</rss>)\s*<script>.*\Z", rb"\1\n<script>/* appended by the CDN in front of the feed */</script>\n",
                  body, flags=re.S)
    return _MAIL.sub(b"user@example.org", body)


async def main(argv: list[str]) -> int:
    if "--retrim" in argv:                          # re-apply `shorten` to the recorded answers, without network
        for src in registry.SOURCES:
            f = DATA / src.fixture
            if src.fixture and f.exists():
                f.write_bytes(shorten(src, f.read_bytes()))
        return 0
    record = "--record" in argv
    only = [a for a in argv if not a.startswith("--")]
    tmp = Path(tempfile.mkdtemp(prefix="madalean-news-check-"))
    ctx = SimpleNamespace(paths=SimpleNamespace(config=tmp), settings=SimpleNamespace(mode="auto"), demo=False,
                          publish=lambda *_a, **_k: None, spawn=lambda c: c.close())
    svc = NewsService(ctx)
    bad = 0
    for src in registry.SOURCES:
        if only and src.id not in only:
            continue
        t0 = time.monotonic()
        try:
            r = await svc._get(src.url, hosts=src.hosts, max_bytes=src.max_bytes)
            fn = parsers.PARSERS[src.parser]
            items = fn(r.body)
            kept = [it for it in items if src.require is None or src.require.search(f"{it['title']}\n{it['summary']}")]
            validators = ", ".join(k for k in ("etag", "last-modified") if r.headers.get(k)) or "none"
            print(f"OK    {src.id:17s} {len(r.body):7d} bytes  {len(items):3d} items ({len(kept)} kept)  "
                  f"{time.monotonic() - t0:4.1f} s  validators: {validators}  host: {sorted(src.hosts)[0]}")
            if record and src.fixture:
                DATA.mkdir(exist_ok=True)
                (DATA / src.fixture).write_bytes(shorten(src, trim(src, r.body)))
        except (FetchError, parsers.ParseError, ValueError) as e:
            bad += 1
            print(f"FAIL  {src.id:17s} {type(e).__name__}: {e}")
    await svc.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
