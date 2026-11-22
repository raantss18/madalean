"""Stand-in for `lean` in the warm-Lean unit tests (D37): `--server` speaks the subset of Lean's LSP used by
madalean.runtime.leanwarm, `--json FILE` prints the same messages as a fresh `lean --json` would.

Messages are derived from the text, line by line:
- a line containing `bad` -> error « unknown identifier 'bad' » on that word (UTF-16 columns in LSP mode);
- `sorry` -> warning « declaration uses 'sorry' »;
- `#print axioms NAME` -> information « 'NAME' depends on axioms: [propext] »;
- `DISAGREE` -> an error in `--json` mode only (warm and fresh disagree);
- `SLEEP=<s>` -> elaboration takes <s> seconds; `CRASH` -> the server exits while checking;
- `LATEPUB` -> diagnostics are published only after « done » (Lean's « never blocked » order);
- `import Mathlib.Broken` in the header -> error on that line.
Every process start is appended to $LEAN_FAKE_LOG (one line: mode)."""
import json
import os
import sys
import time


def messages(text: str, mode: str) -> list[dict]:
    out = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("import") and "Broken" in line:
            out.append(("error", i, 0, i, len(line), "unknown module prefix 'Broken'"))
        k = line.find("bad")
        if k >= 0:
            out.append(("error", i, k, i, k + 3, "unknown identifier 'bad'"))
        if "sorry" in line and not line.startswith("#print"):
            out.append(("warning", i, 0, i, 7, "declaration uses 'sorry'"))
        if line.startswith("#print axioms "):
            out.append(("information", i, 0, i, 6, f"'{line.split()[-1]}' depends on axioms: [propext]"))
        if "DISAGREE" in line and mode == "json":
            out.append(("error", i, 0, None, None, "fresh-only error"))
    return out


def utf16(line: str, cp: int) -> int:
    return sum(2 if ord(c) > 0xFFFF else 1 for c in line[:cp])


def log(mode: str) -> None:
    p = os.environ.get("LEAN_FAKE_LOG")
    if p:
        with open(p, "a") as f:
            f.write(mode + "\n")


def json_mode(path: str) -> int:
    log("json")
    text = open(path, encoding="utf-8").read()
    if "SLEEP=" in text:
        time.sleep(float(text.split("SLEEP=")[1].split()[0]))
    msgs = messages(text, "json")
    for sev, l, c, el, ec, data in msgs:
        print(json.dumps({"severity": sev, "pos": {"line": l + 1, "column": c},
                          "endPos": None if el is None else {"line": el + 1, "column": ec}, "data": data}))
    return 1 if any(m[0] == "error" for m in msgs) else 0


def send(obj: dict) -> None:
    b = json.dumps(obj).encode()
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(b) + b)
    sys.stdout.buffer.flush()


def read() -> dict | None:
    n = -1
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        k, _, v = line.partition(b":")
        if k.lower() == b"content-length":
            n = int(v)
    return json.loads(sys.stdin.buffer.read(n))


def elaborate(uri: str, version: int, text: str) -> None:
    lines = text.split("\n")
    late = "LATEPUB" in text
    if not late:
        send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
              "params": {"uri": uri, "version": version, "diagnostics": []}})
    send({"jsonrpc": "2.0", "method": "$/lean/fileProgress",
          "params": {"textDocument": {"uri": uri, "version": version},
                     "processing": [{"range": {"start": {"line": 0, "character": 0},
                                               "end": {"line": 1, "character": 0}}, "kind": 1}]}})
    if "CRASH" in text:
        sys.exit(3)
    if "SLEEP=" in text:
        time.sleep(float(text.split("SLEEP=")[1].split()[0]))
    diags = []
    for sev, l, c, el, ec, data in messages(text, "lsp"):
        end = {"line": l if el is None else el,
               "character": utf16(lines[l], c) if el is None else utf16(lines[el], ec)}
        rng = {"start": {"line": l, "character": utf16(lines[l], c)}, "end": end}
        diags.append({"range": rng, "fullRange": rng, "severity": {"error": 1, "warning": 2, "information": 3}[sev],
                      "message": data, "source": "Lean 4"})
    pub = {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
           "params": {"uri": uri, "version": version, "diagnostics": diags}}
    if not late:
        send(pub)
    send({"jsonrpc": "2.0", "method": "$/lean/fileProgress",
          "params": {"textDocument": {"uri": uri, "version": version}, "processing": []}})
    if late:
        send(pub)


def server_mode() -> int:
    log("server")
    init = read()
    send({"jsonrpc": "2.0", "id": "register_lean_watcher", "method": "client/registerCapability",
          "params": {"registrations": []}})
    send({"jsonrpc": "2.0", "id": init["id"], "result": {"capabilities": {}}})
    m = read()
    if not m or m.get("method") != "initialized":      # like Lean v4.9: anything else first is fatal
        print("expected initialized, got " + json.dumps(m), file=sys.stderr)
        return 1
    text = ""
    while True:
        m = read()
        if m is None:
            return 0
        meth = m.get("method")
        p = m.get("params") or {}
        if meth == "textDocument/didOpen":
            td = p["textDocument"]
            text = td["text"]
            elaborate(td["uri"], td["version"], text)
        elif meth == "textDocument/didChange":
            text = p["contentChanges"][-1]["text"]
            elaborate(p["textDocument"]["uri"], p["textDocument"]["version"], text)
        elif "id" in m and meth:
            send({"jsonrpc": "2.0", "id": m["id"], "result": None})


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--server" in args:
        sys.exit(server_mode())
    sys.exit(json_mode(args[args.index("--json") + 1]))
