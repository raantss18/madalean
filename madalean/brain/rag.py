"""RAG over a Lean workspace's declarations: SQLite FTS5 index (BM25 over name / name words / docstring /
signature) built from the sources compiled in the workspace (madalean.names.source_roots + lean_parse), query
expansion from natural language and from Lean statements (notation → names: ≤ → le, ∑ → sum…), optional semantic
re-ranking with an Ollama embedding model (loopback only, never required).

Index files: <cache_dir>/rag/<workspace>-<hash>.sqlite, hash = path, toolchain, lean_path, mtimes of
lake-manifest.json / lean-toolchain and the parser version (an update of Mathlib rebuilds it). Built in a
background thread at the lowest CPU and I/O priority."""
from __future__ import annotations

import asyncio
import ctypes
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from .lean_parse import PARSER_VERSION, Decl, additive_signature, parse_source  # noqa: F401

log = logging.getLogger("madalean.brain.rag")

# notation -> words (indexed with the signature, and used to expand Lean statements)
NOTATION = [("≤", "le"), ("≥", "le ge"), ("<", "lt"), (">", "lt gt"), ("≠", "ne"), ("∑", "sum finset"),
            ("∏", "prod finset"), ("∣", "dvd"), ("∈", "mem"), ("∉", "not mem"), ("⊆", "subset"),
            ("⊂", "ssubset"), ("∩", "inter"), ("∪", "union"), ("∅", "empty"), ("∫", "integral"),
            ("√", "sqrt"), ("^", "pow"), ("¬", "not"), ("↔", "iff"), ("∀", "forall"), ("∃!", "exists unique"),
            ("∃", "exists"), ("∘", "comp"), ("⁻¹", "inv"), ("‖", "norm"), ("•", "smul"), ("⊤", "top"),
            ("⊥", "bot"), ("∧", "and"), ("∨", "or"), ("→", "imp"), ("%", "mod"), ("/", "div"), ("*", "mul"),
            ("+", "add"), ("-", "sub"), ("|", "abs"), ("!", "factorial"), ("ℕ", "nat"), ("ℤ", "int"),
            ("ℚ", "rat"), ("ℝ", "real"), ("ℂ", "complex"), ("π", "pi"), ("⌊", "floor"), ("⌈", "ceil"),
            ("∞", "top infinite"), ("deriv", "deriv"), ("∂", "deriv"), ("⨆", "supr sup"), ("⨅", "infi inf"),
            ("⊔", "sup"), ("⊓", "inf"), ("ᶜ", "compl"), ("′", "deriv"), ("∘ₗ", "comp")]

STOP = set("""a an the of to in on for is are be by with and or as at it its that this these those any all some
every each no not if then than there their which such from into let show prove proof that's we our us you your
can must will would should given number numbers integer integers natural real two three one theorem lemma
statement result fact true holds hold has have also exist exists only when where""".split())
STOP -= {"not", "exists", "natural", "integer", "integers", "real"}
WEAK = {"function", "functions", "set", "sets", "map", "space", "value", "element", "elements", "nat", "int", "real",
        "type", "natural", "integer"}
NAME_FILLER = {"of", "or", "and", "iff", "eq", "the"}

# natural language -> Mathlib name words (each entry: alternatives searched together)
SYNONYMS: dict[str, list[str]] = {
    "sum": ["sum", "add"], "plus": ["add"], "addition": ["add"], "added": ["add"],
    "product": ["prod", "mul"], "times": ["mul"], "multiplication": ["mul"], "multiply": ["mul"],
    "difference": ["sub"], "minus": ["sub"], "quotient": ["div"], "divides": ["dvd"], "divisible": ["dvd"],
    "divisor": ["dvd", "divisors"], "divisors": ["divisors", "dvd"], "remainder": ["mod"], "modulo": ["mod"],
    "even": ["even"], "odd": ["odd"], "prime": ["prime"], "primes": ["prime"], "square": ["sq", "pow", "square"],
    "squares": ["sq", "pow"], "squared": ["sq", "pow"], "power": ["pow"], "powers": ["pow"], "cube": ["pow"],
    "root": ["root", "roots", "sqrt"], "roots": ["roots", "root"], "sqrt": ["sqrt"], "absolute": ["abs"],
    "less": ["lt", "le"], "smaller": ["lt", "le"], "greater": ["lt", "le"], "larger": ["lt", "le"],
    "inequality": ["le"], "bounded": ["bdd", "bounded"], "bound": ["bdd", "bound", "le"],
    "maximum": ["max", "exists_max"], "minimum": ["min", "exists_min"], "max": ["max"], "min": ["min"],
    "continuous": ["continuous"], "continuity": ["continuous"], "derivative": ["deriv", "hasderivat"],
    "differentiable": ["differentiable"], "integral": ["integral"], "limit": ["tendsto", "lim"],
    "converges": ["tendsto"], "convergent": ["tendsto", "cauchyseq"], "sequence": ["seq", "tendsto"],
    "series": ["summable", "tsum"], "intermediate": ["intermediate"], "value": ["value"], "mean": ["mean", "exists"],
    "polynomial": ["polynomial"], "polynomials": ["polynomial"], "degree": ["degree", "natdegree"],
    "coefficient": ["coeff"], "matrix": ["matrix"], "matrices": ["matrix"], "determinant": ["det"],
    "basis": ["basis"], "linearly": ["linear"], "independent": ["independent", "linearindependent"],
    "extend": ["extension", "extend", "exists"], "extension": ["extension", "extend"], "span": ["span"],
    "dimension": ["finrank", "rank", "dim"], "vector": ["module", "vector"], "space": ["space", "module"],
    "subspace": ["submodule"], "linear": ["linear"], "map": ["map", "linearmap"], "function": ["fun", "function"],
    "injective": ["injective"], "surjective": ["surjective"], "bijective": ["bijective"], "inverse": ["inv", "inverse"],
    "set": ["set"], "finite": ["finite", "finset", "fintype"], "infinite": ["infinite"], "countable": ["countable"],
    "cardinality": ["card"], "count": ["card", "count"], "subset": ["subset"], "union": ["union"],
    "intersection": ["inter"], "complement": ["compl"], "empty": ["empty"], "group": ["group"],
    "subgroup": ["subgroup"], "order": ["orderof", "card", "order"], "cyclic": ["cyclic"], "ring": ["ring"],
    "field": ["field"], "ideal": ["ideal"], "factorial": ["factorial"], "binomial": ["choose"], "choose": ["choose"],
    "gcd": ["gcd"], "lcm": ["lcm"], "coprime": ["coprime"], "triangle": ["triangle", "dist", "abs_add"],
    "distance": ["dist"], "metric": ["metric", "dist"], "compact": ["compact", "iscompact"], "open": ["isopen", "open"],
    "closed": ["isclosed", "closed"], "connected": ["connected", "preconnected"], "interval": ["icc", "ioo", "interval"],
    "zero": ["zero"], "positive": ["pos"], "negative": ["neg"], "nonnegative": ["nonneg"], "equal": ["eq"],
    "unique": ["unique"], "exponential": ["exp"], "logarithm": ["log"], "log": ["log"], "exp": ["exp"],
    "sine": ["sin"], "cosine": ["cos"], "fermat": ["fermat", "pow_card"], "little": ["little"], "pigeonhole": ["pigeonhole"],
    "irrational": ["irrational"], "rational": ["rat"], "infinitely": ["infinite"], "many": ["infinite"],
    "composition": ["comp"], "identity": ["id"], "permutation": ["perm"], "graph": ["graph", "simplegraph"],
    "tree": ["tree"], "probability": ["prob", "measure"], "measure": ["measure"], "expectation": ["integral"],
    "cauchy": ["cauchy"], "schwarz": ["schwarz", "inner_mul_le_norm_mul_norm"], "am": ["geom_mean", "inner_le"],
    "gm": ["geom_mean"], "arithmetic": ["arith"], "geometric": ["geom"], "induction": ["induction", "rec"],
    "real": ["real"], "complex": ["complex"], "conjugate": ["conj"], "norm": ["norm"], "eigenvalue": ["eigenvalue"],
    "dense": ["dense"], "tend": ["tendsto"], "tends": ["tendsto"], "goes": ["tendsto"], "approaches": ["tendsto"],
    "infinity": ["attop", "top"], "natural": ["nat"], "integer": ["int"], "real": ["real"], "nonnegative": ["nonneg"],
    "reverse": ["sub", "abs"], "constant": ["const"], "constants": ["const"], "uniformly": ["uniform"], "bezout": ["gcd_eq_gcd_ab", "bezout"],
}


def name_words(name: str) -> list[str]:
    """Words of a declaration name: dots, underscores and camelCase split, plus the joined camel words."""
    out: list[str] = []
    for comp in name.split("."):
        for part in comp.split("_"):
            if not part:
                continue
            pieces = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9']+", part)
            low = part.lower().replace("'", "")
            out.extend(p.lower().replace("'", "") for p in pieces if p)
            if len(pieces) > 1:
                out.append(low)
    return [w for w in out if w]


_PATTERNS = [(re.compile(r"(?<![\w.])0 ≤|≥ 0\b"), "nonneg"), (re.compile(r"(?<![\w.])0 <|> 0\b"), "pos"),
             (re.compile(r"≤ 0\b"), "nonpos"), (re.compile(r"< 0\b"), "neg"), (re.compile(r"\^ 2\b"), "sq"),
             (re.compile(r"≠ 0\b"), "ne zero"), (re.compile(r"= 0\b"), "eq zero"), (re.compile(r"= 1\b"), "eq one"),
             (re.compile(r"\b2 \*"), "two mul"), (re.compile(r"⁻¹|1 /"), "inv")]


def pattern_words(text: str) -> list[str]:
    return [w for rx, ws in _PATTERNS if rx.search(text) for w in ws.split()]


def notation_words(text: str) -> list[str]:
    out = pattern_words(text)
    for sym, words in NOTATION:
        if sym in text:
            out.extend(words.split())
    return out


def words_column(d: Decl) -> str:
    w = name_words(d.name)
    w += notation_words(d.signature)
    w += [x.lower() for x in d.module.split(".")[-2:]]
    if d.origin:
        w.append("toadditive")
    return " ".join(dict.fromkeys(w))


# ------------------------------------------------------------------ workspace -> index file
def default_resolve(key: str):
    from ..workspaces import Workspace, _read_toolchain, builtin_workspaces
    for w in builtin_workspaces():
        if w.key == key:
            return w
    if key.startswith("user:"):
        p = Path(key[5:])
        return Workspace(key, p.name, p, _read_toolchain(p), True)
    return None


def index_path(cache_dir: Path, ws) -> Path:
    stamps = []
    for f in ("lake-manifest.json", "lean-toolchain"):
        try:
            stamps.append((ws.path / f).stat().st_mtime_ns)
        except OSError:
            stamps.append(0)
    key = hashlib.sha1(f"{ws.path}|{ws.toolchain}|{ws.lean_path()}|{stamps}|v{PARSER_VERSION}".encode()).hexdigest()[:16]
    return cache_dir / "rag" / f"{ws.key.replace('/', '_').replace(':', '_')}-{key}.sqlite"


def _lower_priority() -> None:
    """This thread only: nice 19 and idle I/O class (Linux; ignored elsewhere)."""
    try:
        tid = threading.get_native_id()
        os.setpriority(os.PRIO_PROCESS, tid, 19)
    except (OSError, AttributeError):
        pass
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.syscall(251 if os.uname().machine == "x86_64" else 30, 1, threading.get_native_id(), 3 << 13)
    except (OSError, AttributeError):
        pass


SCHEMA = """
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE decls(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT, signature TEXT, doc TEXT, module TEXT,
                   context TEXT, origin TEXT, deprecated INTEGER, words TEXT, pop REAL DEFAULT 0);
CREATE VIRTUAL TABLE decls_fts USING fts5(name, words, doc, signature, content='decls', content_rowid='id',
                                          tokenize='unicode61 remove_diacritics 2');
"""


def build_index(ws, out: Path, roots: list[Path] | None = None) -> dict:
    """Parse the workspace sources and write the index (atomic). Returns stats."""
    from ..names import source_roots
    t0 = time.monotonic()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
    n_files = n = 0
    seen: set[str] = set()
    batch: list[tuple] = []
    uses: Counter = Counter()
    aligned: set[str] = set()
    for root in roots if roots is not None else source_roots(ws):
        base = root.parent
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in (".lake", "test", "tests"))
            for fn in sorted(filenames):
                if not fn.endswith(".lean"):
                    continue
                f = Path(dirpath) / fn
                module = ".".join(f.relative_to(base).with_suffix("").parts)
                try:
                    src = f.read_text(encoding="utf-8", errors="replace")
                    decls = parse_source(src, module)
                except (OSError, RecursionError):
                    continue
                aligned.update(_ALIGNED.findall(src))
                for tok in _USE.findall(src):
                    uses[tok] += 1
                    if "." in tok:
                        uses[tok.rsplit(".", 1)[-1]] += 1
                n_files += 1
                for d in decls:
                    if d.name in seen:
                        continue
                    seen.add(d.name)
                    batch.append((d.name, d.kind, d.signature, d.doc, d.module, d.context, d.origin,
                                  int(d.deprecated), words_column(d)))
                if len(batch) >= 5000:
                    con.executemany("INSERT INTO decls(name,kind,signature,doc,module,context,origin,deprecated,words)"
                                    " VALUES (?,?,?,?,?,?,?,?,?)", batch)
                    n += len(batch)
                    batch.clear()
    if batch:
        con.executemany("INSERT INTO decls(name,kind,signature,doc,module,context,origin,deprecated,words)"
                        " VALUES (?,?,?,?,?,?,?,?,?)", batch)
        n += len(batch)
    # generated names whose signature comes from another declaration (attribute [to_additive …] src), and names
    # only known from `#align` lines (Lean 4.9-era Mathlib): searchable by name, signature unknown
    for rid, origin in con.execute("SELECT id, origin FROM decls WHERE signature = '' AND origin != ''").fetchall():
        o = con.execute("SELECT signature, context FROM decls WHERE name = ?", (origin,)).fetchone()
        if o is None and "." in origin:
            o = con.execute("SELECT signature, context FROM decls WHERE name = ?", (origin.rsplit(".", 1)[-1],)).fetchone()
        if o is not None:
            con.execute("UPDATE decls SET signature = ?, context = ? WHERE id = ?",
                        (additive_signature(o[0]), additive_signature(o[1] or ""), rid))
    missing = [(t, "theorem", "", "", "", "", "#align", 0, " ".join(dict.fromkeys(name_words(t))))
               for t in aligned if t not in seen]
    con.executemany("INSERT INTO decls(name,kind,signature,doc,module,context,origin,deprecated,words)"
                    " VALUES (?,?,?,?,?,?,?,?,?)", missing)
    n += len(missing)
    # popularity: how often the name (or its last component, shared among the declarations that have it) is used
    same_last: Counter = Counter()
    for (nm,) in con.execute("SELECT name FROM decls"):
        same_last[nm.rsplit(".", 1)[-1]] += 1
    upd = []
    for rid, nm in con.execute("SELECT id, name FROM decls").fetchall():
        lastc = nm.rsplit(".", 1)[-1]
        c = max(0, uses.get(nm, 0) - (1 if "." not in nm else 0)) + max(0, uses.get(lastc, 0) - 1) / same_last[lastc]
        upd.append((math.log1p(c), rid))
    con.executemany("UPDATE decls SET pop = ? WHERE id = ?", upd)
    del uses
    con.execute("INSERT INTO decls_fts(decls_fts) VALUES('rebuild')")
    con.execute("CREATE INDEX decls_name ON decls(name)")
    con.execute("CREATE INDEX decls_lname ON decls(lower(name))")
    stats = {"declarations": n, "files": n_files, "seconds": round(time.monotonic() - t0, 1), "built": time.time(),
             "workspace": ws.key, "toolchain": ws.toolchain, "parser": PARSER_VERSION}
    con.executemany("INSERT INTO meta VALUES (?,?)", [(k, json.dumps(v)) for k, v in stats.items()])
    con.commit()
    con.execute("INSERT INTO decls_fts(decls_fts) VALUES('optimize')")
    con.commit()
    con.close()
    os.replace(tmp, out)
    for old in out.parent.glob(out.name.rsplit("-", 1)[0] + "-*.sqlite"):
        if old != out:
            old.unlink(missing_ok=True)
    stats["bytes"] = out.stat().st_size
    return stats


# ------------------------------------------------------------------ queries
_ALIGNED = re.compile(r"(?m)^#align\s+\S+\s+(\S+)")
_USE = re.compile(r"(?<![\w'.])[A-Za-z_][\w'.]*[\w']")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_'.]*[A-Za-z0-9_']|[A-Za-z]")


def _stem(w: str) -> str:
    w = w.replace("'s", "").replace("’s", "").strip("'")
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and w.endswith("ed"):
        return w[:-1] if w[-3] in "aeiouv" or w.endswith(("ated", "ized", "uced")) else w[:-2]
    if len(w) > 5 and w.endswith("ing"):
        return w[:-3]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


PHRASES: list[tuple[str, list[str]]] = [
    (r"\bnumber of\b|\bhow many\b|\bcardinality\b", ["card"]), (r"\bat most\b|\bno more than\b", ["le"]),
    (r"\bat least\b", ["le"]), (r"\bfirst n\b", ["range"]), (r"\bgreatest common divisor\b", ["gcd"]),
    (r"\bleast common multiple\b", ["lcm"]), (r"\bif and only if\b|\biff\b", ["iff"]),
]

# Well-known results -> Mathlib names (looked up exactly; only those present in the workspace are returned).
FAMOUS: list[tuple[str, list[str]]] = [
    (r"fermat'?s? little", ["ZMod.pow_card_sub_one_eq_one", "Int.ModEq.pow_card_sub_one_eq_one", "ZMod.pow_card"]),
    (r"cauchy.?schwarz", ["inner_mul_le_norm_mul_norm", "abs_real_inner_le_norm", "real_inner_mul_inner_self_le",
                          "inner_mul_inner_self_le", "Finset.inner_mul_le_norm_mul_norm"]),
    (r"b[ée]zout", ["Nat.gcd_eq_gcd_ab", "Int.gcd_eq_gcd_ab", "Nat.xgcd"]),
    (r"intermediate value", ["intermediate_value_Icc", "intermediate_value_Icc'", "intermediate_value_Ioo",
                             "intermediate_value_uIcc"]),
    (r"infinitely many primes|infinitude of primes", ["Nat.exists_infinite_primes", "Nat.infinite_setOf_prime"]),
    (r"geometric (series|sum)", ["geom_sum_eq", "hasSum_geometric_of_lt_one", "tsum_geometric_of_lt_one"]),
    (r"pigeon.?hole", ["Finset.exists_ne_map_eq_of_card_lt_of_maps_to", "Fintype.exists_ne_map_eq_of_card_lt"]),
    (r"binomial (theorem|formula|expansion)", ["add_pow", "Commute.add_pow"]),
    (r"mean value theorem", ["exists_deriv_eq_slope", "exists_hasDerivAt_eq_slope"]),
    (r"\brolle", ["exists_deriv_eq_zero", "exists_hasDerivAt_eq_zero"]),
    (r"squeeze|sandwich", ["tendsto_of_tendsto_of_tendsto_of_le_of_le"]),
    (r"fundamental theorem of calculus", ["intervalIntegral.integral_eq_sub_of_hasDerivAt",
                                          "intervalIntegral.integral_hasDerivAt_right"]),
    (r"fundamental theorem of arithmetic|unique factori[sz]ation", ["Nat.factors_unique", "Nat.primeFactorsList_unique"]),
    (r"chinese remainder", ["Nat.chineseRemainder", "ZMod.chineseRemainder"]),
    (r"wilson", ["ZMod.wilsons_lemma", "Nat.prime_iff_fac_equiv_neg_one"]),
    (r"euclid'?s? lemma", ["Nat.Prime.dvd_mul", "Prime.dvd_mul"]),
    (r"lagrange'?s? theorem", ["Subgroup.card_subgroup_dvd_card"]),
    (r"cayley.?hamilton", ["Matrix.aeval_self_charpoly"]),
    (r"bolzano.?weierstrass", ["tendsto_subseq_of_bounded", "IsCompact.tendsto_subseq"]),
    (r"extreme value theorem", ["IsCompact.exists_isMaxOn", "IsCompact.exists_isMinOn"]),
    (r"incomplete basis|extend(ed)? to a basis|basis extension", ["exists_linearIndependent_extension", "Basis.extend"]),
    (r"rank.?nullity", ["LinearMap.finrank_range_add_finrank_ker"]),
    (r"am.?gm|arithmetic.{0,8}geometric mean", ["Real.inner_le_nnorm_mul_nnorm", "Real.geom_mean_le_arith_mean2_weighted",
                                               "Real.geom_mean_le_arith_mean_weighted"]),
    (r"gauss sum|sum of (the )?first n", ["Finset.sum_range_id_mul_two", "Finset.sum_range_id", "Gauss_sum"]),
]


Group = tuple[list[str], float]          # alternatives, weight


def nl_groups(q: str) -> list[Group]:
    """Natural-language query -> weighted concept groups (alternatives)."""
    groups: list[Group] = []
    text = q
    for pat, alts in PHRASES:
        if re.search(pat, text, re.I):
            groups.append((alts, 1.0))
            text = re.sub(pat, " ", text, flags=re.I)
    for sym, words in NOTATION:
        if sym in text and sym not in "+-*/|!%<>^":
            groups.append((words.split(), 1.0))
            text = text.replace(sym, " ")
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_'.]*", text):
        lw = w.lower().rstrip(".")
        if lw in STOP or len(lw) < 2:
            continue
        if any(c.isupper() for c in w[1:]) or "_" in w or "." in w.strip("."):     # an identifier: use its words
            groups.extend(([x], 1.0) for x in name_words(w) if x not in STOP)
            continue
        st = _stem(lw)
        if st in STOP:
            continue
        alts = SYNONYMS.get(lw) or SYNONYMS.get(st) or ([lw] if lw == st else [st, lw])
        groups.append((list(dict.fromkeys(alts)), 0.15 if (lw in WEAK or st in WEAK) else 1.0))
    return _dedup(groups)


def famous(q: str) -> list[str]:
    out: list[str] = []
    for pat, names in FAMOUS:
        if re.search(pat, q, re.I):
            out += names
    return out


def _dedup(groups: list[Group]) -> list[Group]:
    out: dict[tuple, float] = {}
    for alts, w in groups:
        k = tuple(alts)
        out[k] = max(out.get(k, 0.0), w)
    return [(list(k), w) for k, w in out.items()]


_STRUCT = {"forall", "imp", "and", "or", "iff", "not", "exists"}


def _conclusion(sig: str) -> tuple[str, str]:
    """(hypotheses, conclusion) of a theorem signature: split at the last ':' outside brackets."""
    depth, cut = 0, -1
    for i, ch in enumerate(sig):
        if ch in "([{⦃⟨":
            depth += 1
        elif ch in ")]}⦄⟩":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0 and not sig.startswith(":=", i):
            cut = i
    return (sig[:cut], sig[cut + 1:]) if cut >= 0 else ("", sig)


def lean_groups(stmt: str) -> list[Group]:
    """Lean statement -> weighted concept groups: identifiers (not bound variables) and notation; the conclusion
    weighs more than the hypotheses, structural words (∀, →, ∧) are ignored."""
    s = re.sub(r"--[^\n]*|/-.*?-/", " ", stmt, flags=re.S)
    s = re.sub(r"(?m)^\s*(import|open|set_option)\b.*$", " ", s)
    m = re.search(r"\b(?:theorem|lemma|example)\b", s)
    if m:
        s = s[m.end():]
        s = re.sub(r"^\s*[^\s:({\[⦃]+", " ", s) if not stmt[m.start():].startswith("example") else s
    s = s.split(":= by")[0].split(":=")[0]
    bound = set(re.findall(r"[(\[{⦃]\s*([^:()\[\]{}]+?)\s*:", s))
    bound_names = {b for grp in bound for b in grp.split()}
    bound_names |= set(re.findall(r"[∀∃λ]\s*([A-Za-z_][\w']*)", s))
    bound_names |= set(re.findall(r"[∑∏]\s*([A-Za-z_][\w']*)", s))
    hyps, concl = _conclusion(s)
    parts = [(concl, 2.0), (hyps, 1.0)]
    eq = re.split(r"\s(?:=|↔)\s", concl, maxsplit=1)
    if len(eq) == 2 and "(" not in eq[0][:1] or len(eq) == 2:
        parts = [(eq[0], 2.0), (eq[1], 1.0), (hyps, 1.0)]       # rewrite lemmas are named after their left side
    groups: list[Group] = []
    for part, weight in parts:
        pw = pattern_words(part)
        for w in pw:
            groups.append(([w], weight))
        subsumed = ({"<"} if "pos" in pw or "neg" in pw else set()) | ({"≤"} if "nonneg" in pw or "nonpos" in pw else set()) \
            | ({"^"} if "sq" in pw else set())
        for sym, words in NOTATION:
            if sym in part and sym not in subsumed:
                ws = [w for w in words.split() if w not in _STRUCT]
                if ws and sym not in "ℕℤℚℝℂ":
                    groups.append((ws, weight))
                elif ws:
                    groups.append((ws, 0.3))
        for ident in _IDENT.findall(part):
            if ident in bound_names or len(ident) <= 1 or ident in ("Type", "Prop", "Sort", "fun", "by", "at", "with", "in"):
                continue
            for w in name_words(ident):
                if w not in STOP and w not in _STRUCT:
                    groups.append(([w], weight * (0.5 if w in ("nat", "int", "real", "rat", "complex") else 1.0)))
    return _dedup(groups)


def _term(w: str) -> str:
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    return (f'"{w}"' + ("*" if len(w) >= 5 else "")) if w else ""


def fts_query(groups: list[Group], all_: bool = False) -> str:
    parts = []
    for alts, _w in groups:
        terms = [t for t in dict.fromkeys(_term(x) for x in alts) if t]
        if terms:
            parts.append("(" + " OR ".join(terms) + ")" if len(terms) > 1 else terms[0])
    return (" AND " if all_ else " OR ").join(parts)


POP_W = {"last": 0.07, "ns": 0.03, "pop": 0.06}


def rerank(rows: list[sqlite3.Row], groups: list[Group], k: int, prefer_theorems: bool = True,
           phrase: str = "") -> list[tuple[float, sqlite3.Row]]:
    if not rows:
        return []
    bm = [r["bm"] for r in rows]
    lo, hi = min(bm), max(bm)
    total = sum(w for _, w in groups) or 1.0
    phrase = phrase.lower()
    out = []
    for r in rows:
        nw = name_words(r["name"])
        nws = set(nw)
        other = set((r["words"] or "").split()) | set(re.findall(r"[a-z0-9]+", ((r["doc"] or "") + " " + (r["signature"] or "")).lower()))
        cov_name = cov_other = 0.0
        matched: set[str] = set()
        for alts, w in groups:
            gs = {re.sub(r"[^a-z0-9]", "", x.lower()) for x in alts}
            exact_hit = nws & gs
            hit = exact_hit or {x for x in nws if any(len(g) >= 5 and x.startswith(g) for g in gs)}
            if hit:
                cov_name += w if exact_hit else 0.7 * w
                matched |= hit
            elif gs & other:
                cov_other += w
        lex = (hi - r["bm"]) / (hi - lo) if hi > lo else 1.0          # bm25: lower is better
        s = 2.0 * cov_name / total + 0.5 * cov_other / total + 0.4 * lex
        last = set(name_words(r["name"].rsplit(".", 1)[-1]))
        for x in dict.fromkeys(nw):                                 # words of the name that the query did not ask
            if x not in matched and x not in NAME_FILLER:
                s -= POP_W["last"] if x in last else POP_W["ns"]
        s += POP_W["pop"] * (r["pop"] or 0.0)
        if r["deprecated"]:
            s -= 0.6
        if r["kind"] in ("instance",):
            s -= 0.4
        elif prefer_theorems and r["kind"] in ("theorem", "lemma"):
            s += 0.05
        if phrase and r["doc"] and phrase in r["doc"].lower():
            s += 0.5
        out.append((s, r))
    out.sort(key=lambda x: x[0], reverse=True)
    return out[:k]


def row_dict(r: sqlite3.Row, score: float = 0.0) -> dict:
    d = {"name": r["name"], "kind": r["kind"], "signature": r["signature"], "doc": r["doc"] or "",
         "module": r["module"], "score": round(float(score), 4)}
    if r["origin"] == "#align":
        d["note"] = "exists (listed by Mathlib's #align) but its statement was not found in the sources: check it with lean_check (#check)"
    elif r["origin"]:
        d["generated_from"] = r["origin"]
        d["note"] = ("generated by @[to_additive] from " + r["origin"] +
                     "; the signature is a rough additive translation of the original one")
    if r["context"]:
        d["variables"] = r["context"]
    if r["deprecated"]:
        d["deprecated"] = True
    return d


class LeanRetriever:
    """Implements api.Retriever."""

    def __init__(self, cache_dir: Path, resolve: Callable[[str], object] | None = None, embeddings: bool = True,
                 ollama_url: str = "http://127.0.0.1:11434"):
        self.cache_dir = Path(cache_dir)
        self.resolve = resolve or default_resolve
        self.embeddings = embeddings
        self.ollama_url = ollama_url
        self._lock = threading.Lock()
        self._building: dict[str, threading.Thread] = {}
        self._paths: dict[str, Path] = {}
        self.errors: dict[str, str] = {}
        self.stats: dict[str, dict] = {}
        self._embed: "Embedder | None" = None

    # -------------------------------------------------------------- index lifecycle
    def _path(self, key: str) -> Path | None:
        if key in self._paths:
            return self._paths[key]
        ws = self.resolve(key)
        if ws is None:
            return None
        p = index_path(self.cache_dir, ws)
        self._paths[key] = p
        return p

    def ready(self, key: str) -> bool:
        p = self._path(key)
        return bool(p and p.exists())

    def start(self, key: str) -> None:
        """Build the index in the background if needed (never blocks)."""
        p = self._path(key)
        if p is None or p.exists():
            return
        with self._lock:
            t = self._building.get(key)
            if t and t.is_alive():
                return
            ws = self.resolve(key)

            def run():
                _lower_priority()
                try:
                    self.stats[key] = build_index(ws, p)
                    self.errors.pop(key, None)
                except Exception as e:  # noqa: BLE001
                    log.warning("RAG index of %s failed: %s", key, e)
                    self.errors[key] = str(e)
            t = threading.Thread(target=run, name=f"rag-{key}", daemon=True)
            self._building[key] = t
            t.start()

    async def ensure(self, key: str, timeout: float = 600) -> bool:
        """Build if needed and wait (up to timeout). True when the index is usable."""
        self.start(key)
        t0 = time.monotonic()
        while not self.ready(key):
            t = self._building.get(key)
            if (t is None or not t.is_alive()) and not self.ready(key):
                return False
            if time.monotonic() - t0 > timeout:
                return False
            await asyncio.sleep(0.25)
        return True

    def _connect(self, key: str) -> sqlite3.Connection | None:
        p = self._path(key)
        if p is None or not p.exists():
            self.start(key)
            return None
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    # -------------------------------------------------------------- queries (sync, run in a thread)
    def _search_groups(self, key: str, groups: list[Group], k: int, exact: list[str] | None = None,
                       phrase: str = "") -> list[dict]:
        con = self._connect(key)
        if con is None:
            return []
        try:
            out: list[dict] = []
            for name in exact or []:
                r = con.execute("SELECT *, 0.0 AS bm FROM decls WHERE name = ?", (name,)).fetchone()
                if r is not None and all(d["name"] != name for d in out):
                    out.append(row_dict(r, 99.0 - 0.01 * len(out)))
            rows: dict[str, sqlite3.Row] = {}
            sql = ("SELECT d.*, bm25(decls_fts, 10.0, 5.0, 1.5, 1.0) AS bm FROM decls_fts "
                   "JOIN decls d ON d.id = decls_fts.rowid WHERE decls_fts MATCH ? ORDER BY bm LIMIT ?")
            strong = [g for g in groups if g[1] >= 1.0]
            if len(strong) >= 2:
                q_and = fts_query(strong, all_=True)
                for r in con.execute(sql, (q_and, 400)).fetchall():
                    rows.setdefault(r["name"], r)
            if len(strong) >= 1:
                q_name = "{name words} : (" + fts_query(strong, all_=len(strong) >= 2) + ")"
                for r in con.execute(sql.replace("ORDER BY bm", "ORDER BY length(d.name)"), (q_name, 400)).fetchall():
                    rows.setdefault(r["name"], r)
            q_or = fts_query(groups)
            if q_or:
                for r in con.execute(sql, (q_or, 600)).fetchall():
                    rows.setdefault(r["name"], r)
            have = {d["name"] for d in out}
            out += [row_dict(r, s) for s, r in rerank(list(rows.values()), groups, k + len(out), phrase=phrase)
                    if r["name"] not in have]
            return out[:k]
        finally:
            con.close()

    def search_sync(self, key: str, query: str, k: int = 8) -> list[dict]:
        q = query.strip()
        exact = famous(q)
        phrase = ""
        if re.fullmatch(r"[A-Za-z_][\w'.]*", q) and ("." in q or "_" in q or any(c.isupper() for c in q[1:])):
            exact = [q] + exact
            groups = [([w], 1.0) for w in name_words(q)]
        elif any(ch in q for ch in "∀∃≤≥∑∏∣∈⊆→↔ℕℤℝ") or re.search(r"\b(theorem|lemma)\b", q):
            groups = _dedup(lean_groups(q) + [(a, 0.5) for a, _ in nl_groups(re.sub(r"[^A-Za-z ]", " ", q))])
        else:
            groups = nl_groups(q)
            words = [w for w in re.findall(r"[a-z]+", q.lower()) if w not in STOP]
            phrase = " ".join(words[:3]) if len(words) >= 2 else ""
        return self._search_groups(key, groups, k, exact, phrase)

    def declaration_sync(self, key: str, name: str) -> dict | None:
        con = self._connect(key)
        if con is None:
            return None
        try:
            name = name.strip().strip("`")
            r = con.execute("SELECT *, 0.0 AS bm FROM decls WHERE name = ?", (name,)).fetchone()
            if r is None:
                r = con.execute("SELECT *, 0.0 AS bm FROM decls WHERE lower(name) = lower(?)", (name,)).fetchone()
            if r is None and "." not in name:
                rows = con.execute("SELECT *, 0.0 AS bm FROM decls WHERE name LIKE ? LIMIT 2", ("%." + name,)).fetchall()
                r = rows[0] if len(rows) == 1 else None
            if r is None:
                return None
            d = row_dict(r, 1.0)
            if r["origin"]:
                o = con.execute("SELECT signature, doc FROM decls WHERE name = ?", (r["origin"],)).fetchone()
                if o is not None:
                    d["original_signature"] = o["signature"]
            return d
        finally:
            con.close()

    def suggest_sync(self, key: str, name: str, k: int = 6) -> list[dict]:
        return self._search_groups(key, [([w], 1.0) for w in name_words(name) if w not in STOP], k)

    # -------------------------------------------------------------- api.Retriever
    async def search(self, workspace_key: str, query: str, k: int = 8) -> list[dict]:
        res = await asyncio.to_thread(self.search_sync, workspace_key, query, max(k, 30) if self.embeddings else k)
        return (await self._semantic(query, res))[:k]

    async def premises(self, workspace_key: str, lean_statement: str, k: int = 8) -> list[dict]:
        def run():
            return self._search_groups(workspace_key, lean_groups(lean_statement), max(k, 30) if self.embeddings else k)
        res = await asyncio.to_thread(run)
        return (await self._semantic(lean_statement, res))[:k]

    async def declaration(self, workspace_key: str, name: str) -> dict | None:
        return await asyncio.to_thread(self.declaration_sync, workspace_key, name)

    async def suggest(self, workspace_key: str, name: str, k: int = 6) -> list[dict]:
        return await asyncio.to_thread(self.suggest_sync, workspace_key, name, k)

    async def _semantic(self, query: str, res: list[dict]) -> list[dict]:
        if not self.embeddings or len(res) < 3:
            return res
        if self._embed is None:
            self._embed = Embedder(self.ollama_url)
        try:
            return await self._embed.rerank(query, res)
        except Exception as e:  # noqa: BLE001 (semantic re-ranking is optional)
            log.info("embedding re-rank skipped: %s", e)
            return res

    async def close(self) -> None:
        if self._embed is not None:
            await self._embed.close()


def _decl_text(d: dict) -> str:
    return f"{d['name']}: {d.get('signature', '')}\n{(d.get('doc') or '')[:300]}"


class Embedder:
    """Semantic re-ranking with an Ollama embedding model (detected once; loopback only)."""

    def __init__(self, url: str):
        from .net import is_loopback_host
        from urllib.parse import urlsplit
        if not is_loopback_host(urlsplit(url).hostname):
            raise ValueError("embeddings only from a local Ollama")
        self.url = url.rstrip("/")
        self.model: str | None = None
        self.checked: float | None = None
        self._cache: dict[str, list[float]] = {}
        self._session = None

    async def _sess(self):
        import aiohttp
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30, sock_connect=1.5))
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def detect(self) -> str | None:
        if self.checked is not None and time.monotonic() - self.checked < 300:
            return self.model
        self.checked = time.monotonic()
        try:
            s = await self._sess()
            async with s.get(self.url + "/api/tags") as r:
                tags = await r.json()
        except Exception:  # noqa: BLE001
            self.model = None
            return None
        names = [m.get("name", "") for m in tags.get("models", [])]
        pick = [n for n in names if any(k in n.lower() for k in ("embed", "bge", "minilm", "e5-", "gte-"))]
        self.model = pick[0] if pick else None
        return self.model

    async def embed(self, texts: list[str], query: bool) -> list[list[float]]:
        model = self.model
        prefix = ("search_query: " if query else "search_document: ") if model and "nomic" in model else ""
        need = [t for t in texts if (prefix + t) not in self._cache]
        if need:
            s = await self._sess()
            async with s.post(self.url + "/api/embed", json={"model": model, "input": [prefix + t for t in need]}) as r:
                v = await r.json()
            for t, e in zip(need, v.get("embeddings") or []):
                self._cache[prefix + t] = e
            if len(self._cache) > 20000:
                self._cache.clear()
        return [self._cache.get(prefix + t, []) for t in texts]

    async def rerank(self, query: str, res: list[dict]) -> list[dict]:
        if not await self.detect():
            return res
        texts = [_decl_text(d) for d in res]
        qv = (await self.embed([query], True))[0]
        dv = await self.embed(texts, False)
        top = max(d["score"] for d in res) or 1.0
        out = []
        for d, v in zip(res, dv):
            cos = _cos(qv, v)
            d = dict(d)
            d["semantic"] = round(cos, 4)
            d["score"] = round(0.6 * d["score"] / top + 0.4 * cos, 4) if d["score"] < 90 else d["score"]
            out.append(d)
        out.sort(key=lambda d: d["score"], reverse=True)
        return out


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0
