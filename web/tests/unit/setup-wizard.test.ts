// « Premiers pas » (S-AQ, D49): the assistant's pure logic.
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import fr from '../../src/lib/i18n/fr';
import en from '../../src/lib/i18n/en';
import {
  STEPS, HELP, isStep, next, prev, progress, resumeStep, shouldAutoOpen, showReminder, visitedAfterMove,
  modelChoice, modelsMissing, recommendedSage, recommendedTex, checklist, checklistSummary, type ModelFile,
} from '../../src/lib/setup/wizard';

describe('setup wizard: steps', () => {
  it('same steps as the server, welcome first, done last', () => {
    expect(STEPS).toEqual(['welcome', 'tools', 'local', 'keys', 'hf', 'claude', 'modes', 'auto', 'pair', 'done']);
    expect(next('welcome')).toBe('tools');
    expect(next('done')).toBeNull();
    expect(prev('welcome')).toBeNull();
    expect(prev('tools')).toBe('welcome');
    expect(progress('welcome')).toBe(0);
    expect(progress('done')).toBe(100);
    expect(isStep('keys')).toBe(true);
    expect(isStep('nope')).toBe(false);
    expect(isStep(undefined)).toBe(false);
  });
  it('resumes from the address, else where the user stopped, else the start', () => {
    expect(resumeStep('claude', { step: 'keys', completed: false })).toBe('claude');
    expect(resumeStep(undefined, { step: 'keys', completed: false })).toBe('keys');
    expect(resumeStep('bogus', { step: 'keys', completed: false })).toBe('keys');
    expect(resumeStep(undefined, { step: 'keys', completed: true })).toBe('welcome');   // finished: start again
    expect(resumeStep(undefined, { step: 'zzz', completed: false })).toBe('welcome');
    expect(resumeStep(undefined, null)).toBe('welcome');
  });
  it('visited steps are kept in step order, current included once left', () => {
    expect(visitedAfterMove([], 'welcome')).toEqual(['welcome']);
    expect(visitedAfterMove(['keys', 'welcome'], 'tools')).toEqual(['welcome', 'tools', 'keys']);
    expect(visitedAfterMove(['tools'], 'tools')).toEqual(['tools']);
  });
  it('every step has a help page and a title, lead and label in both languages', () => {
    for (const s of STEPS) {
      expect(HELP[s].page).toMatch(/^[a-z-]+$/);
      for (const cat of [fr, en] as Record<string, string>[]) {
        expect(cat[`setup.step.${s}`], s).toBeTruthy();
        expect(cat[`setup.step.${s}.title`], s).toBeTruthy();
        expect(cat[`setup.step.${s}.lead`], s).toBeTruthy();
      }
    }
    expect(HELP.local.anchor).toEqual({ fr: 'modeles-locaux', en: 'local-models' });
  });
  it('every help link points at an existing manual page and heading (docs/manual/index.json)', () => {
    const idx = JSON.parse(readFileSync(join(__dirname, '../../../docs/manual/index.json'), 'utf8')) as
      { pages: { id: string; lang: string; headings: { id: string }[] }[] };
    for (const s of STEPS) {
      for (const lang of ['fr', 'en'] as const) {
        const page = idx.pages.find((p) => p.id === HELP[s].page && p.lang === lang);
        expect(page, `${s} ${lang}`).toBeTruthy();
        const a = HELP[s].anchor?.[lang];
        if (a) expect(page!.headings.map((h) => h.id), `${s} ${lang}`).toContain(a);
      }
    }
  });
});

describe('setup wizard: when it shows', () => {
  it('opens by itself only on the host, on Home, while not done and the server says so', () => {
    expect(shouldAutoOpen(true, 'home', false, { auto: true })).toBe(true);
    expect(shouldAutoOpen(false, 'home', false, { auto: true })).toBe(false);          // a paired device: never
    expect(shouldAutoOpen(true, 'dossier', false, { auto: true })).toBe(false);        // a deep link is respected
    expect(shouldAutoOpen(true, 'home', true, { auto: true })).toBe(false);            // « Plus tard » / finished
    expect(shouldAutoOpen(true, 'home', false, { auto: false })).toBe(false);          // an update with existing work
    expect(shouldAutoOpen(true, 'home', undefined, { auto: true })).toBe(false);       // settings not loaded
    expect(shouldAutoOpen(true, 'home', false, null)).toBe(false);                     // older server
  });
  it('the Home card stays on the host until finished, unless hidden', () => {
    expect(showReminder(true, { completed: false, reminder: true })).toBe(true);
    expect(showReminder(true, { completed: true, reminder: true })).toBe(false);
    expect(showReminder(true, { completed: false, reminder: false })).toBe(false);
    expect(showReminder(false, { completed: false, reminder: true })).toBe(false);
    expect(showReminder(true, null)).toBe(false);
  });
});

describe('setup wizard: choices', () => {
  const files: ModelFile[] = [
    { key: 'Q4_K_M', file: 'p.gguf', present: true, bytes: 5, download_bytes: 0 },
    { key: 'formalizer', file: 'f.gguf', present: false, bytes: 0, download_bytes: 5e9 },
    { key: 'explainer', file: 'e.gguf', present: false, bytes: 0, download_bytes: 5e9 },
  ];
  it('local models: saved choice, else recommendation, else none; only the missing files are fetched', () => {
    expect(modelChoice('prover', 'all')).toBe('prover');
    expect(modelChoice('', 'all')).toBe('all');
    expect(modelChoice('', undefined)).toBe('none');
    expect(modelChoice('weird', 'weird')).toBe('none');
    expect(modelsMissing(files, 'prover')).toEqual([]);
    expect(modelsMissing(files, 'all').map((f) => f.key)).toEqual(['formalizer', 'explainer']);
    expect(modelsMissing(files, 'none')).toEqual([]);
  });
  it('reuse: the system SageMath when compatible, Madalean’s otherwise; tectonic first for LaTeX', () => {
    expect(recommendedSage({ found: true, compatible: true }, false)).toBe('system');
    expect(recommendedSage({ found: true, compatible: false }, false)).toBe('own');
    expect(recommendedSage({ found: false, compatible: false }, false)).toBe('own');
    expect(recommendedSage({ found: true, compatible: true }, true)).toBe('auto');      // own copy already there
    expect(recommendedSage(undefined, false)).toBe('auto');                            // machine not checked
    expect(recommendedTex()).toBe('auto');
  });
  it('checklist: titles in the language, optional rows do not count as left', () => {
    const rows = checklist([
      { id: 'keys', done: false, title: { fr: 'Clé', en: 'Key' }, help: 'first-config' },
      { id: 'pair', done: false, title: { fr: 'Relier', en: 'Link' }, help: 'pairing' },
      { id: 'workspace', done: true, title: { fr: 'Espace', en: 'Workspace' }, help: 'components' },
    ], 'en');
    expect(rows.map((r) => r.title)).toEqual(['Key', 'Link', 'Workspace']);
    expect(rows[1]!.optional).toBe(true);
    expect(checklistSummary(rows)).toEqual({ done: 1, total: 3, essentialLeft: 1 });
  });
});
