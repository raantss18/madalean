"""Record the literature search's fixtures: ONE real, polite search per source (zbMATH Open, OpenAlex, arXiv, plus
the Crossref confirmations of the DOIs found), stored in tests/data/literature/http for the offline tests and the
demo. Run by hand only (network):

    PYTHONPATH=. .venv/bin/python scripts/dev/literature_record.py

Nothing is sent but the search words built from the statement below (and DOIs to confirm)."""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

STATEMENT = ("theorem bertrand_postulate (n : ℕ) (hn : 1 ≤ n) : ∃ p, Nat.Prime p ∧ n < p ∧ p ≤ 2 * n := by sorry")
WORDS = "Bertrand : pour tout entier n ≥ 1, il existe un nombre premier p tel que n < p ≤ 2n."


async def main() -> None:
    from helpers import make_ctx
    from madalean.brain.fake import FakeBrain
    from madalean.literature import Budget, search
    from madalean.research.fetch import AiohttpTransport, Fetcher, RecordingTransport, ReplayTransport
    out = ROOT / "tests" / "data" / "literature" / "http"
    tmp = Path(tempfile.mkdtemp(prefix="lit-record-"))
    ctx = make_ctx(tmp, brain=FakeBrain(online=False))
    replay = "--replay" in sys.argv
    f = Fetcher(ReplayTransport(out, strict=True) if replay else RecordingTransport(AiohttpTransport(), out))
    try:
        res = await search(STATEMENT, ctx, Budget(seconds=120, requests=20, model_calls=0, lean_checks=0, items=6),
                           text=WORDS, mode="online", fetcher=f, formalize=False, use_cache=False)
    finally:
        await f.close()
    print(json.dumps({"providers": res.providers, "rejected": res.rejected, "queries": res.query.queries,
                      "items": [{"id": it.reference.id, "title": it.reference.title, "kind": it.reference.kind,
                                 "quotes": [q.text for q in it.quotes]} for it in res.items]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
