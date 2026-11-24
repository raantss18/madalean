// Typed client of the problem graph (S-AY, docs/PROOF_GRAPH.md) and of the lessons store (D57b).
import { request } from './client';

const enc = encodeURIComponent;

export type GraphStatus = 'proved' | 'mathlib' | 'certified' | 'cited' | 'open' | 'refuted' | 'abandoned';
export type GraphState = 'verified' | 'conditional' | 'open' | 'refuted' | 'abandoned';
export interface GraphAttempt { t: number; how: string; ok: boolean; error: string; model: string; seconds: number; tactics: string[] }
export interface GraphTrack { id: string; idea: string; lemmas: string[]; active: boolean; abandoned: boolean; why: string; check: string }
export interface GraphNode {
  id: string; key: string; kind: string; title: string; statement_nl: string; lean: string; status: GraphStatus; reason: string;
  why: string; source: { kind: string; name?: string; model?: string; [k: string]: unknown }; citation: Record<string, unknown> | null;
  dossier_id: string; depth: number; viability: { score: number; signals: { code: string; params: Record<string, unknown> }[]; model: { score: number | null; reason: string; model: string } | null } | null;
  attempts: GraphAttempt[]; attempts_n: number; proof: string; tactics: string[]; self_contained: boolean; admitted: boolean;
  proposal: boolean; tracks?: GraphTrack[]; state: GraphState; composed: boolean; rests_on: string[]; rests_external?: string[];
  reason_text: string; uses: string[]; used_by: string[]; claimed?: string; by_user?: boolean; how?: string;
  /** D59: the same statement under other names; the small-instance probe's evidence / candidate counterexample */
  aliases?: { title: string; lean: string; exact: string }[];
  tested?: { text: string; points: number; dom: string; complete: boolean };
  probe?: { candidate: string; confirmed: boolean };
}
export interface GraphRunSummary { id: string; end: number; reason: string; steps: number; root_state: GraphState;
  spent: Record<string, number>; budgets: Record<string, number>; tried: { node: string; title: string; status: string; reason: string }[] }
export interface Graph {
  v: number; rev: number; dossier_id: string; root: string; nodes: Record<string, GraphNode>; edges: [string, string, string][];
  runs: GraphRunSummary[]; counts: Record<string, number>; budgets: Record<string, number>;
  run: { id: string; running: boolean; steps: number; budgets: Record<string, number>; spent: Record<string, number>; stopping: boolean } | null;
  memory: { digest_chars: number; project_rows: number }; log: { rev: number; t: number; kind: string; node: string }[];
}
export interface Explanation {
  node: string; title: string; lean: string; state: GraphState; composed: boolean; conditional: boolean; text: string; proof: string;
  rests_on: { node: string; title: string }[];
  tactics: { name: string; count: number; description: string }[];
  bibliography: { mathlib: { name: string; url: string; how: string }[]; works: { key: string; reference: string; verified: boolean; quote: string; doi: string; url: string }[]; bibtex: string };
}
export interface Why { node: string; title: string; why: string; reason_text: string; status: string; reason: string;
  alternatives: { parent: string; idea: string; active: boolean; abandoned: boolean; why: string; lemmas: { node: string; title: string; state: string; score: number | null }[] }[];
  attempts: GraphAttempt[]; attempts_n: number; source: { kind: string } | null; citation: Record<string, unknown> | null }
export interface Lesson { id: string; kind: 'rename' | 'fix' | 'approach' | 'strategy'; ok: number; bad: number; used: number; updated: number;
  old?: string; new?: string; mathlib?: string; pattern?: string; shape?: string; tactics?: string[]; approach?: string; reason?: string;
  strategy?: string; evidence: { dossier?: string; workspace?: string; mathlib?: string; t: number }[] }

const g = (id: string) => `/dossiers/${enc(id)}/graph`;

export const graphApi = {
  get: (id: string, lang: string) => request<{ graph: Graph }>('GET', `${g(id)}?lang=${enc(lang)}`),
  search: (id: string, budgets?: Record<string, number>) => request<{ graph: Graph }>('POST', `${g(id)}/search`, { budgets }),
  stop: (id: string) => request<{ stopping: boolean }>('POST', `${g(id)}/stop`, {}),
  why: (id: string, nid: string, lang: string) => request<Why>('GET', `${g(id)}/nodes/${enc(nid)}/why?lang=${enc(lang)}`),
  abandon: (id: string, nid: string, reason = '') => request<{ graph: Graph }>('POST', `${g(id)}/nodes/${enc(nid)}/abandon`, { reason }),
  resume: (id: string, nid: string) => request<{ graph: Graph }>('POST', `${g(id)}/nodes/${enc(nid)}/resume`, {}),
  open: (id: string, nid: string) => request<{ dossier_id: string; created: boolean; shared?: boolean }>('POST', `${g(id)}/nodes/${enc(nid)}/open`, {}),
  adapt: (id: string, nid: string) => request<{ added: string[]; refused: { title: string; reason: string }[]; graph: Graph }>('POST', `${g(id)}/nodes/${enc(nid)}/adapt`, {}),
  adopt: (id: string, nid: string) => request<{ graph: Graph }>('POST', `${g(id)}/nodes/${enc(nid)}/adopt`, {}),
  literature: (id: string, node?: string) => request<{ available: boolean; graph?: Graph }>('POST', `${g(id)}/literature`, node ? { node } : {}),
  explain: (id: string, lang: string, node?: string) =>
    request<{ explanation: Explanation }>('GET', `${g(id)}/explain?lang=${enc(lang)}${node ? `&node=${enc(node)}` : ''}`),
  exportAs: (id: string, format: 'note' | 'latex' | 'bibtex' | 'markdown', lang: string, node?: string) =>
    request<{ note?: { id: string; title: string }; latex?: string; bibtex?: string; markdown?: string }>('POST', `${g(id)}/export`, { format, lang, node }),
  lessons: () => request<{ lessons: Lesson[]; max: number }>('GET', '/lessons'),
  deleteLesson: (lid: string) => request<{ deleted: boolean }>('DELETE', `/lessons/${enc(lid)}`),
  clearLessons: () => request<{ deleted: number }>('DELETE', '/lessons'),
  exportLessons: () => request<Record<string, unknown>>('GET', '/lessons/export'),
  importLessons: (data: unknown) => request<{ imported: number }>('POST', '/lessons/import', data),
};

/** Status shown for a node (state first, then the raw status for detail). Icon + words, never colour alone. */
export const STATE_ICON: Record<string, string> = {
  verified: 'check', conditional: 'warn', open: 'info', refuted: 'x', abandoned: 'stop',
};

/** The DAG as a tree for lists: each node under its FIRST user (creation order); other users show « utilise aussi ». */
export function treeOf(graph: Graph): { order: { id: string; depth: number }[]; alsoUsedBy: Record<string, string[]> } {
  const firstParent: Record<string, string> = {};
  const alsoUsedBy: Record<string, string[]> = {};
  for (const [src, kind, dst] of graph.edges) {
    if (kind !== 'uses') continue;
    if (!(dst in firstParent)) firstParent[dst] = src;
    else (alsoUsedBy[dst] ??= []).push(src);
  }
  const kids: Record<string, string[]> = {};
  for (const [dst, src] of Object.entries(firstParent)) (kids[src] ??= []).push(dst);
  const order: { id: string; depth: number }[] = [];
  const seen = new Set<string>();
  const walk = (id: string, depth: number) => {
    if (seen.has(id) || !graph.nodes[id] || depth > 12) return;
    seen.add(id);
    order.push({ id, depth });
    for (const k of (kids[id] ?? []).sort((a, b) => (graph.nodes[a]?.title ?? '').localeCompare(graph.nodes[b]?.title ?? ''))) walk(k, depth + 1);
  };
  walk(graph.root, 0);
  // known results and proposals not (yet) used by the goal: listed after the tree, at depth 0
  for (const id of Object.keys(graph.nodes).sort()) if (!seen.has(id)) walk(id, 0);
  return { order, alsoUsedBy };
}
