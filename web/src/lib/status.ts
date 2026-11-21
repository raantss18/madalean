// One vocabulary for dossier/job status everywhere (list, header, activity centre).
import type { DossierStatus, Job } from './api/types';

export type Phase = 'draft' | 'queued' | 'running' | 'proved' | 'failed' | 'stopped';

export function phaseOf(status: DossierStatus | string, job?: Job | null): Phase {
  if (job && (job.state === 'queued' || job.state === 'running')) {
    return job.state === 'queued' || job.waiting ? 'queued' : 'running';
  }
  switch (status) {
    case 'proved': return 'proved';
    case 'failed': return 'failed';
    case 'stopped': return 'stopped';
    case 'translating':
    case 'proving': return 'running';
    default: return 'draft';
  }
}

/** Model key "provider:model_id" → readable name + where it runs. */
export function modelLabel(key: string): { name: string; provider: string; local: boolean } {
  if (!key) return { name: '', provider: '', local: true };
  // Some server paths send a Python repr instead of the key (docs/UI.md « Requests to the server »).
  const repr = /^ModelRef\(provider='([^']*)', model_id='([^']*)'/.exec(key);
  if (repr) key = `${repr[1]}:${repr[2]}`;
  const i = key.indexOf(':');
  const provider = i > 0 ? key.slice(0, i) : '';
  let name = i > 0 ? key.slice(i + 1) : key;
  name = name.replace(/\.gguf$/i, '').replace(/[-.]Q\d_K(_[MS])?$/i, '').replace(/:free$/, '');
  const slash = name.lastIndexOf('/');
  if (slash >= 0) name = name.slice(slash + 1);
  if (provider === 'mathlib') return { name: `Mathlib : ${key.slice(i + 1)}`, provider, local: true };   // S-K
  return { name, provider, local: provider === 'local' || provider === 'ollama' };
}

export const PROVIDER_NAMES: Record<string, string> = {
  local: 'Madalean (local)', ollama: 'Ollama', anthropic: 'Anthropic', gemini: 'Google Gemini', openrouter: 'OpenRouter',
  groq: 'Groq', mistral: 'Mistral', cerebras: 'Cerebras', openai: 'OpenAI', deepseek: 'DeepSeek', huggingface: 'Hugging Face', llm7: 'LLM7',
  ovh: 'OVHcloud', kilo: 'Kilo', pollinations: 'Pollinations', fake: 'Démo', 'lean': 'Lean', mathlib: 'Mathlib',
};

export function providerName(p: string): string {
  return PROVIDER_NAMES[p] ?? p;
}

/** Role that the current stage uses (for the « who receives what » indicator). */
export function roleOfStage(stage: string): string {
  switch (stage) {
    case 'understand': return 'understand';
    case 'route': return 'route';
    case 'verify': return 'understand';
    case 'statement': return 'formalize';
    case 'proof': return 'prove';
    case 'notes':
    case 'explanation':
    case 'informal': return 'explain';
    default: return '';
  }
}

/** Last model that worked on a job (attempt model, else ""). */
export function jobModel(job: Job | undefined | null): string {
  if (!job) return '';
  for (let i = job.attempts.length - 1; i >= 0; i--) if (job.attempts[i]!.model) return job.attempts[i]!.model;
  return '';
}
