"""Check `runtime/ollama_share.activity` against the real local Ollama (S-AS, D51): idle, while generating, after.

    .venv/bin/python scripts/dev/check_ollama_busy.py [model]      # default phi4-mini; unloads it at the end

The generation is requested from this process, so it is excluded from the connection count: `busy` must come from
the runner's CPU alone. Never stops Ollama."""
import asyncio
import json
import subprocess
import sys
import threading
import urllib.request

from madalean.runtime import ollama_share

BASE = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "phi4-mini"


def util() -> float:
    out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def generate() -> None:
    body = {"model": MODEL, "prompt": "Count from 1 to 300, one number per line.", "stream": False,
            "keep_alive": 0, "options": {"num_predict": 500}}
    urllib.request.urlopen(urllib.request.Request(BASE + "/api/generate", data=json.dumps(body).encode()),
                           timeout=300).read()


async def main() -> None:
    print("idle:      ", await ollama_share.activity(BASE, util()))
    t = threading.Thread(target=generate)
    t.start()
    while t.is_alive():
        await asyncio.sleep(1)
        print("during:    ", await ollama_share.activity(BASE, util()))
    t.join()
    await asyncio.sleep(1)
    print("after:     ", await ollama_share.activity(BASE, util()))


asyncio.run(main())
