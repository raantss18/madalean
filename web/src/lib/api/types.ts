// Types of docs/API.md §5 (source of truth). Keep in sync with the server.

export type Message = { key: string; params: Record<string, unknown>; text: string };
export type Mode = 'local' | 'auto' | 'online';
export type Strategy = 'goedel' | 'agent' | 'auto';
export type Stage = 'understand' | 'route' | 'statement' | 'notes' | 'verify' | 'proof' | 'explanation' | 'informal' | 'mathlib';
export type FollowStage = 'auto' | 'statement' | 'proof' | 'explanation';
export type Role = 'understand' | 'route' | 'formalize' | 'prove' | 'explain' | 'assistant';
export const ROLES: Role[] = ['prove', 'formalize', 'understand', 'explain', 'route', 'assistant'];

export interface Device {
  id: string; name: string; created: number; last_seen: number; last_ip: string;
  kind?: 'app' | 'browser'; client?: string; sessions?: number; expires_in?: number;   // browser: seconds left
}

export interface Project {
  id: string; title: string; description: string; workspace: string; created: number; updated: number;
  archived: boolean; refs_file: string; sources: unknown[]; [extra: string]: unknown;
}

export interface VersionMeta {
  axioms?: string[] | null; lean?: string; mathlib?: string; workspace?: string; seconds?: number;
  strategy?: Strategy | 'mathlib'; attempts?: number; checked?: number;
  /** S-K: statement check verdict (statement versions); Mathlib lemma used (proof versions) */
  check?: Record<string, unknown>; mathlib_lemma?: string; mathlib_source?: string;
}
export interface Version {
  code: string; t: number; source: 'ai' | 'user'; ok: boolean; parent: number | null; note: string;
  model: string; meta: VersionMeta;
}
export type VersionKind = 'statement' | 'proof' | 'explanation';

export type EventKind = 'user' | 'understood' | 'statement' | 'notes' | 'check' | 'proof' | 'explanation' | 'informal' | 'info' | 'error';
/** `check` event params (statement check, S-K). */
export interface CheckIssue { kind: string; severity: 'high' | 'low'; explanation: string; fix: string; checked: string }
export type CheckVerdict = 'faithful' | 'doubtful' | 'false' | 'unknown';
export interface DossierEvent {
  kind: EventKind; text: string; t: number; ref: number | null; stage: string; model: string; key: string;
  params: Record<string, unknown>; job: string;
}

export type DossierStatus = 'draft' | 'translating' | 'proving' | 'proved' | 'failed' | 'stopped';
export interface Dossier {
  id: string; title: string; problem: string; understood: string; understood_display: string;
  workspace: string; theorem: string; created: number; updated: number; events: DossierEvent[];
  statements: Version[]; proofs: Version[]; explanations: Version[]; statement_notes: Version[];
  informal_proofs: Version[]; cur_statement: number; cur_proof: number; cur_explanation: number;
  lemmas_used: string[]; project_id: string; status: DossierStatus; parent_id: string; retry_parent: boolean;
  archived: boolean; kind: 'theorem' | 'lemma' | 'definition' | 'claim';
  refs: { key: string; locator?: string; note?: string }[];
  source: { paper_key: string; locator: string; original_text: string } | null;
  uses: string[];
  current: { statement: string; proof: string; explanation: string; statement_notes: string; informal_proof: string;
    proof_is_current: boolean };
  [extra: string]: unknown;
}
export interface DossierSummary {
  id: string; title: string; project_id: string; status: DossierStatus; parent_id: string; kind: string;
  theorem: string; workspace: string; created: number; updated: number; archived: boolean;
  has_statement: boolean; proved: boolean;
}

export interface Attempt {
  index: number; stage: Stage;
  kind: 'initial' | 'correction' | 'refinement' | 'translation' | 'agent' | 'recheck';
  status: 'generating' | 'compiling' | 'accepted' | 'rejected' | 'error' | 'cancelled';
  summary: string; errors_text: string; code: string; raw?: string; model: string;
  gen_seconds: number; compile_seconds: number; tokens: number; finish: string; t: number;
  round?: number;               // proof tournament round (0 = best models, 1… = races), -1 = none
}
export type JobState = 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
export interface Job {
  id: string; dossier_id: string; plan: { stage: Stage; request?: string }[]; mode: Mode; strategy: Strategy;
  user: boolean; state: JobState; stage: Stage | ''; waiting: '' | 'gpu' | 'online' | 'lean';
  created: number; started: number | null; ended: number | null; attempts: Attempt[]; done_stages: Stage[];
  summary: Message | Record<string, never>; error: string;
  tournament?: Tournament | Record<string, never>;
  /** D38: every stage running now (several at once after the statement); `stage` is the main one. */
  stages?: Stage[];
  /** D38: one row per stage run (unix seconds; end/seconds null while it runs). */
  timings?: { stage: Stage; start: number; end: number | null; seconds: number | null }[];
  /** S-AI (D41): who directs the request, its cost so far, the plan with the model of each step, the cap question. */
  conductor?: Conductor | Record<string, never>;
}
export interface ConductorStep { id: string; kind: string; goal: string; model: string; model_name: string; why: string;
  wave: number; depends_on: string[]; advisory: boolean; stage: string }
export interface Conductor { by: string; name: string; tier: '' | 'haiku' | 'sonnet' | 'opus' | 'free'; usd: number; cap: number;
  difficulty: '' | 'easy' | 'medium' | 'hard'; summary: string; plan: ConductorStep[];
  ask: { spent: number; cap: number; step: number; estimate: number; t: number } | null;
  state: 'planning' | 'running' | 'asking' | 'off' | 'done'; decisions?: number; claude?: boolean;
  final?: { consistent: boolean; issues: { part: string; text: string }[]; summary: string } }
export interface Tournament { round: number; models: string[]; names: string[]; state: string; domain: string;
  winner?: string; tried?: string[]; rounds?: number; minutes?: number }
export interface LeaderboardRow { model: string; task: string; domain: string; tasks: number; solved: number;
  score: number; mean_attempts: number | null; mean_seconds: number | null; lean_errors: number; pauses: number;
  last_success: number | null; updated: number | null }

export interface RankingSource { kind: 'measured' | 'public' | 'estimate'; score?: number; solved?: number; tasks?: number;
  confidence?: number; source?: string; license?: string; url?: string; value?: number; family?: string;
  rows?: { slice: string; name: string; rating: number; rank: number | null; total: number | null; published: string }[] }
export interface RankingRow { key: string; name: string; provider: string; paid: boolean; local: boolean; score: number;
  evidence: 'measured' | 'public' | 'estimate'; new: boolean; sources: RankingSource[] }
export interface RankingDomain { domain: string; task: string | null; public_slices: string[]; rows: RankingRow[] }
export interface ModelNews { t: number; kind: 'new' | 'gone' | 'provider_added'; key?: string; name?: string;
  provider: string; models?: number }
export interface Rankings {
  domains: RankingDomain[];
  public: { source?: string; dataset?: string; url?: string; license?: string; verified?: string; fetched?: number | null;
    published?: string; error?: string; slices?: string[] };
  catalogue_updated: number | null; next: { catalogue?: number | null; public?: number | null }; auto: boolean;
  news: ModelNews[]; new_days?: number;
}

export interface CheckResult {
  ok: boolean; statement_ok: boolean; summary: string;
  errors: { line: number; col: number; text: string; severity: string }[];
  axioms: string[] | null; has_sorry: boolean; reasons: string[]; seconds: number; timed_out: boolean;
  cancelled: boolean; infra_error: string;
}

export interface LibEntry { name: string; title: string; statement: string; code: string; workspace: string;
  dossier: string; deps: string[]; t: number }

export interface ModelRef { key: string; provider: string; model_id: string; name: string; local: boolean; paid: boolean;
  why?: string; score?: number }
export interface ProviderStatus { id: string; name: string; keyed: boolean; key_set: boolean; ok: boolean;
  paused_until: number | null; reason: string }
export interface LocalStatus { state: string; model: string | null; port?: number; offload?: string; error?: string | null;
  holder?: string | null; roles?: Record<string, string>; [k: string]: unknown }
export interface ModelsInfo {
  brain: string; mode: Mode; local: LocalStatus;
  local_files: { file: string; path: string; size?: number; quant?: string; arch?: string; n_layers?: number; error?: string }[];
  roles: Record<string, { preferred: string; candidates: ModelRef[] }>;
  status: { online?: boolean; providers?: ProviderStatus[]; [k: string]: unknown };
  keys: Record<string, boolean>;
}

export interface Settings {
  language: 'fr' | 'en'; mode: Mode; prove_strategy: Strategy; prefer: Record<string, string>;
  workspace: string; model_path: string; prove_attempts: number; translate_attempts: number;
  pause_after_translation: boolean; profile: string; statement_notes: boolean; informal_proof: boolean;
  statement_check: boolean; mathlib_first: boolean; lean_warm: boolean; lean_warm_idle_minutes: number; calcul_warm: boolean;
  compile_timeout_s: number; check_updates: boolean; overleaf_url: string; autoload_model: boolean;
  agent_max_steps: number; agent_max_seconds: number; host_name: string; wizard_done: boolean; offline: boolean;
  lan_listener: boolean; lan_port: number; remote_jupyter: boolean; agent_exec: boolean;
  server: { port: number; ctx_size: number; gpu_layers: number; batch_size: number; ubatch_size: number;
    kv_type: 'f16' | 'q8_0' | 'q4_0'; flash_attn: boolean; threads: number };
  sampling: { temperature: number; top_p: number; max_tokens: number };
  [k: string]: unknown;
}

export interface Monitor {
  gpu: { name: string; total: number; used: number; free: number; temp: number; util: number; apps: Record<string, number> } | null;
  gpu_ok: boolean | null; gpu_error: string; disk: { path: string; total_gb: number; free_gb: number }[]; t: number;
}
export type SlotName = 'gpu' | 'online' | 'lean';
export type Slots = Record<SlotName, { capacity: number; used: number; holders: string[]; waiting: number }>;
export interface WorkspaceInfo { key: string; label: string; path: string; toolchain: string; readonly: boolean;
  description: string; problems: string[]; ready: boolean }
export interface HealthCheck { id: string; ok: boolean; level: 'ok' | 'warn'; repair: string; message: Message; rerun?: boolean }

export interface UpdateCandidate { kind: string; key: string; title: string; current: string; latest: string;
  installable: boolean; note: string; size: number; spec: object; description: string }
export interface UpdatesStatus {
  checking: boolean; t: number | null; errors: string[];
  installed: { mathlib: string | null; models: Record<string, string> };
  candidates: UpdateCandidate[];
  install: { key: string; title: string; step: string; step_text: string; progress: string } | null;
  last_result: (Message & { ok: boolean; details?: string }) | null;
  tracked?: TrackedComponents | null;
}
export interface TrackedComponent { id: string; current: string; latest: string; pending: boolean; installable: boolean;
  key: string; policy: 'auto' | 'auto_pin' | 'with_mathlib'; state?: string; pinned?: string }
export interface TrackedComponents { components: TrackedComponent[]; last_check: number | null; next_check: number | null;
  every_days: number }
export interface JupyterStatus { state: 'stopped' | 'starting' | 'ready' | 'failed'; port: number | null; root_dir: string;
  kernels: string[]; error: string; available: boolean; lean_kernel: { available: boolean; note: string } }

export interface SystemLight { monitor: Monitor; slots: Slots; lean_running: number | unknown[] }
export interface SystemInfo extends SystemLight { workspaces: WorkspaceInfo[]; checks?: HealthCheck[]; local?: unknown; brain?: string }

export interface StateSnapshot {
  version: string; host_name: string; local: boolean; device: Device | null; demo: boolean; brain: string;
  lang: 'fr' | 'en'; seq: number; boot: number; settings: Settings; host_only_settings: string[];
  projects: Project[]; dossiers: DossierSummary[]; jobs: { active: Job[]; recent: Job[] };
  models: ModelsInfo; system: SystemInfo; library: { count: number }; updates: UpdatesStatus;
  jupyter: JupyterStatus; migration: unknown;
}

export interface Hello { name: string; version: string; paired: boolean; local: boolean; host_name: string; demo?: boolean; lang?: string }

/** WebSocket events (docs/API.md §4). Unknown types are ignored. */
export type ServerEvent =
  | { type: 'hello'; seq: number; boot: number; version: string; local: boolean }
  | { type: 'resync'; seq: number; boot: number }
  | { type: 'pong'; t: number }
  | ({ seq: number; ts: number } & (
      | { type: 'job.updated'; job: Job }
      | { type: 'job.token'; job_id: string; stage: Stage; attempt: number; kind: TokenKind; text: string }
      | { type: 'job.info'; job_id: string; stage: Stage; text: string; data: Record<string, unknown> }
      | { type: 'dossier.updated'; dossier: Dossier }
      | { type: 'dossier.deleted'; id: string }
      | { type: 'project.updated'; project: Project }
      | { type: 'project.deleted'; id: string }
      | { type: 'library.updated'; added?: string; removed?: string }
      | { type: 'system.status'; system: SystemLight }
      | { type: 'models.status'; local?: LocalStatus; keys?: Record<string, boolean> }
      | { type: 'settings.updated'; settings: Settings }
      | { type: 'devices.updated'; devices: Device[] }
      | { type: 'updates.status'; updates: UpdatesStatus }
      | { type: 'jupyter.status'; jupyter: JupyterStatus }
      | { type: 'assistant.token'; request_id: string; kind: string; text: string }
      | { type: 'assistant.done'; request_id: string; text: string; model: string; finish: string }
      | { type: 'assistant.error'; request_id: string; error: string; text: string }
      | { type: 'toast'; level: 'info' | 'ok' | 'warn' | 'error'; key: string; params: Record<string, unknown>; text: string }
      | { type: string; [k: string]: unknown }
    ));
export type TokenKind = 'text' | 'thinking' | 'tool_call' | 'tool_result' | 'info';
export type SeqEvent = Extract<ServerEvent, { seq: number; ts: number }>;

/** GET /api/usage (S-AK status panel). */
export interface UsageTotals { tokens_in: number; tokens_out: number; calls: number; usd: number }
export interface UsageStatus {
  mode: Mode;
  resources: {
    cpu_percent: number | null; cpus: number | null; load: number | null;
    memory: { total_mb: number; used_mb: number } | null;
    gpu: { name: string; total: number; used: number; util: number; temp: number } | null;
    t: number;
  };
  tokens: { today: UsageTotals; month: UsageTotals; by_provider_today: Record<string, UsageTotals> };
  spend: { today_usd: number; month_usd: number; cap_month_usd: number; cap_request_usd: number };
  requests: Record<string, UsageTotals & { models: string[] }>;
}
