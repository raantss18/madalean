// Safe maths expressions for figures and curves: a small parser compiled to closures. Never eval / new Function
// (CSP). Syntax: + - * / ^, unary minus, implicit multiplication (2x, 2(x+1), x y, xy when x and y are names),
// functions sin cos tan asin acos atan sinh cosh tanh exp ln log log10 sqrt abs floor ceil sign, constants pi π e.
// Decimal point only (the comma separates arguments).
export type Env = Record<string, number>;
export type Fn = (env: Env) => number;

export class ExprError extends Error {
  constructor(message: string, public pos = 0) { super(message); }
}

type Node =
  | { k: 'num'; v: number }
  | { k: 'var'; n: string }
  | { k: 'neg'; a: Node }
  | { k: 'bin'; op: '+' | '-' | '*' | '/' | '^'; a: Node; b: Node }
  | { k: 'call'; f: string; a: Node };

const FUNCS: Record<string, (x: number) => number> = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
  arcsin: Math.asin, arccos: Math.acos, arctan: Math.atan, sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
  exp: Math.exp, ln: Math.log, log: Math.log, log10: Math.log10, sqrt: Math.sqrt, abs: Math.abs,
  floor: Math.floor, ceil: Math.ceil, sign: Math.sign,
};
const CONSTS: Record<string, number> = { pi: Math.PI, 'π': Math.PI, e: Math.E };
export const DEFAULT_VARS = ['x', 'y', 't', 'θ', 'theta', 'n'];

type Tok = { t: 'num' | 'id' | 'op'; v: string; pos: number };

function tokenize(src: string): Tok[] {
  const s = src.replace(/[−–]/g, '-').replace(/[·×]/g, '*').replace(/\*\*/g, '^').replace(/²/g, '^2').replace(/³/g, '^3');
  const out: Tok[] = [];
  let i = 0;
  while (i < s.length) {
    const c = s[i]!;
    if (/\s/.test(c)) { i++; continue; }
    const num = /^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?/i.exec(s.slice(i));
    if (num && /[\d.]/.test(c)) { out.push({ t: 'num', v: num[0], pos: i }); i += num[0].length; continue; }
    const id = /^[A-Za-zα-ωΑ-Ω_][A-Za-z0-9α-ωΑ-Ω_']*/.exec(s.slice(i));
    if (id) { out.push({ t: 'id', v: id[0], pos: i }); i += id[0].length; continue; }
    if ('+-*/^(),'.includes(c)) { out.push({ t: 'op', v: c, pos: i }); i++; continue; }
    throw new ExprError(`unexpected « ${c} »`, i);
  }
  return out;
}

export function parse(src: string, names: string[] = DEFAULT_VARS): Node {
  const known = new Set([...names, ...DEFAULT_VARS]);
  const toks = tokenize(src);
  let i = 0;
  const peek = () => toks[i];
  const isOp = (v: string) => peek()?.t === 'op' && peek()!.v === v;
  const expect = (v: string) => {
    if (!isOp(v)) throw new ExprError(`« ${v} » expected`, peek()?.pos ?? src.length);
    i++;
  };
  const startsPrimary = () => { const p = peek(); return !!p && (p.t !== 'op' || p.v === '('); };

  function ident(tok: Tok): Node {
    const n = tok.v;
    if (n === 'theta') return { k: 'var', n: 'θ' };
    if (known.has(n)) return { k: 'var', n: n === 'θ' ? 'θ' : n };
    if (n in CONSTS) return { k: 'num', v: CONSTS[n]! };
    // « xy » = x·y, « 2pi » handled by the tokenizer, « tpi » = t·π
    const parts: Node[] = [];
    let rest = n;
    while (rest) {
      const c = ['pi', 'π', 'theta', ...[...known].sort((a, b) => b.length - a.length), 'e'].find((k) => rest.startsWith(k));
      if (!c) throw new ExprError(`unknown name « ${n} »`, tok.pos);
      parts.push(c === 'pi' || c === 'π' || c === 'e' ? { k: 'num', v: CONSTS[c]! } : { k: 'var', n: c === 'theta' ? 'θ' : c });
      rest = rest.slice(c.length);
    }
    return parts.reduce((a, b) => ({ k: 'bin', op: '*', a, b }));
  }
  function primary(): Node {
    const p = peek();
    if (!p) throw new ExprError('incomplete expression', src.length);
    if (p.t === 'num') { i++; return { k: 'num', v: Number(p.v) }; }
    if (p.t === 'id') {
      i++;
      if (p.v in FUNCS) {
        if (isOp('(')) { i++; const a = expr(); expect(')'); return { k: 'call', f: p.v, a }; }
        if (isOp('^')) {               // sin^2(x)
          i++; const e = power(); const a = primary();
          return { k: 'bin', op: '^', a: { k: 'call', f: p.v, a }, b: e };
        }
        return { k: 'call', f: p.v, a: power() };
      }
      return ident(p);
    }
    if (p.v === '(') { i++; const a = expr(); expect(')'); return a; }
    throw new ExprError(`unexpected « ${p.v} »`, p.pos);
  }
  function power(): Node {
    const a = primary();
    if (isOp('^')) { i++; return { k: 'bin', op: '^', a, b: unary() }; }
    return a;
  }
  function unary(): Node {
    if (isOp('-')) { i++; return { k: 'neg', a: unary() }; }
    if (isOp('+')) { i++; return unary(); }
    return power();
  }
  function term(): Node {
    let a = unary();
    for (;;) {
      if (isOp('*') || isOp('/')) { const op = peek()!.v as '*' | '/'; i++; a = { k: 'bin', op, a, b: unary() }; }
      else if (startsPrimary()) a = { k: 'bin', op: '*', a, b: power() };
      else return a;
    }
  }
  function expr(): Node {
    let a = term();
    while (isOp('+') || isOp('-')) { const op = peek()!.v as '+' | '-'; i++; a = { k: 'bin', op, a, b: term() }; }
    return a;
  }
  if (!toks.length) throw new ExprError('empty expression', 0);
  const n = expr();
  if (i < toks.length) throw new ExprError(`unexpected « ${toks[i]!.v} »`, toks[i]!.pos);
  return n;
}

function build(n: Node): Fn {
  switch (n.k) {
    case 'num': { const v = n.v; return () => v; }
    case 'var': { const name = n.n; return (env) => { const v = env[name]; return v === undefined ? NaN : v; }; }
    case 'neg': { const a = build(n.a); return (env) => -a(env); }
    case 'call': { const f = FUNCS[n.f]!; const a = build(n.a); return (env) => f(a(env)); }
    case 'bin': {
      const a = build(n.a), b = build(n.b);
      switch (n.op) {
        case '+': return (env) => a(env) + b(env);
        case '-': return (env) => a(env) - b(env);
        case '*': return (env) => a(env) * b(env);
        case '/': return (env) => a(env) / b(env);
        case '^': return (env) => {
          const x = a(env), p = b(env);
          // real odd roots of negatives: (-8)^(1/3) = -2
          if (x < 0 && !Number.isInteger(p)) { const q = 1 / p; if (Number.isInteger(q) && Math.abs(q) % 2 === 1) return -Math.pow(-x, p); }
          return Math.pow(x, p);
        };
      }
    }
  }
}

export function variables(n: Node, out = new Set<string>()): Set<string> {
  if (n.k === 'var') out.add(n.n);
  else if (n.k === 'neg' || n.k === 'call') variables(n.a, out);
  else if (n.k === 'bin') { variables(n.a, out); variables(n.b, out); }
  return out;
}

export interface Compiled { fn: Fn; vars: Set<string> }
export function compile(src: string, names: string[] = DEFAULT_VARS): Compiled {
  const n = parse(src, names);
  return { fn: build(n), vars: variables(n) };
}

/** Numeric value of a constant expression (« 2pi », « -3/2 »); NaN when it uses variables or is invalid. */
export function evalConst(src: string, env: Env = {}): number {
  try { return compile(src, Object.keys(env)).fn(env); } catch { return NaN; }
}

/** Split at top-level separators (outside parentheses and brackets). */
export function splitTop(s: string, sep = ','): string[] {
  const out: string[] = [];
  let depth = 0, start = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i]!;
    if (c === '(' || c === '[') depth++;
    else if (c === ')' || c === ']') depth--;
    else if (c === sep && depth === 0) { out.push(s.slice(start, i)); start = i + 1; }
  }
  out.push(s.slice(start));
  return out.map((x) => x.trim());
}
