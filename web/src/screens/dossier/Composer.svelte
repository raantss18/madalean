<script lang="ts">
  // The request field at the bottom of the thread: what the request is about is always visible (« À propos de »).
  import type { Dossier, Job, FollowStage } from '../../lib/api/types';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { literature, ATTACH_ACCEPT } from '../../lib/api/literature';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  import Icon from '../../components/Icon.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import { follow, reportError } from './actions';

  let { dossier: d, job, stage = $bindable('auto') }: { dossier: Dossier; job: Job | undefined; stage?: FollowStage } = $props();
  let text = $state('');
  let loadedFor = '';
  $effect(() => { if (loadedFor !== d.id) { loadedFor = d.id; text = loadJSON<string>(`draft.thread.${d.id}`, ''); stage = 'auto'; } });
  $effect(() => { if (loadedFor === d.id) saveJSON(`draft.thread.${d.id}`, text); });
  let sending = $state(false);

  async function send() {
    if (!text.trim() || sending) return;
    sending = true;
    const msg = text.trim();
    text = '';
    const ok = await follow(d.id, msg, stage);
    if (!ok) text = msg;   // the request comes back to the input (L Katta)
    sending = false;
  }
  // S-AX (D56): attach an image / PDF / LaTeX; it is read once and can then be named in a request
  async function attachFiles(input: HTMLInputElement) {
    for (const f of Array.from(input.files ?? [])) {
      try {
        const r = await literature.attachFile(d.id, f);
        toast('ok', t('lit.attached', { name: `${t('lit.attachmentN', { n: r.attachment.n })} — ${f.name}` }));
      } catch (e) { reportError(e, d.id); }
    }
    input.value = '';
  }
</script>

<form class="composer" onsubmit={(e) => { e.preventDefault(); void send(); }}>
  <label for="follow-{d.id}" class="sr-only">{t('thread.ask')}</label>
  <textarea id="follow-{d.id}" class="input" rows="1" bind:value={text} use:enterSubmit={() => void send()} placeholder={t('thread.placeholder')} aria-describedby="follow-h-{d.id} follow-e-{d.id}"></textarea>
  <div class="row">
    <label class="lbl" for="follow-stage-{d.id}">{t('thread.aboutLabel')}</label>
    <select id="follow-stage-{d.id}" class="input stage" bind:value={stage}>
      {#each ['auto', 'statement', 'proof', 'explanation'] as s}<option value={s}>{tk(`follow.${s}`, s)}</option>{/each}
    </select>
    <span class="hints">{#if job}<span class="hint" id="follow-h-{d.id}">{t('thread.busy')}</span>{:else}<span class="sr-only" id="follow-h-{d.id}">{t('thread.hint')}</span>{/if}<span class={job ? "sr-only" : ""}><EnterHint id="follow-e-{d.id}" /></span></span>
    <input id="follow-file-{d.id}" class="sr-only" type="file" accept={ATTACH_ACCEPT} multiple onchange={(e) => void attachFiles(e.target as HTMLInputElement)} />
    <label for="follow-file-{d.id}" class="btn quiet clip" title={t('lit.attachFile')}><Icon name="paperclip" size={16} /><span class="sr-only">{t('lit.attachFile')}</span></label>
    <button class="btn primary" type="submit" disabled={!text.trim() || sending || Boolean(job)} aria-keyshortcuts="Enter"><Icon name="send" size={16} /><span class="sl">{t('thread.send')}</span></button>
  </div>
</form>

<style>
  .composer { background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--r-3); padding: var(--s-2); box-shadow: 0 -6px 14px -12px rgba(10, 20, 40, .5); }
  textarea.input { min-height: 44px; max-height: 180px; field-sizing: content; border-color: transparent; resize: none; }
  .row { margin-top: 2px; gap: 6px; flex-wrap: nowrap; }
  .lbl { flex: none; font-size: var(--fs-sm); color: var(--text-2); padding-left: 8px; }
  .composer .stage { width: auto; min-width: 8rem; max-width: 17rem; font-size: var(--fs-sm); flex: 0 1 auto; }
  .hints { display: grid; justify-items: end; text-align: right; flex: 1 1 0; min-width: 0; line-height: 1.25; }
  .composer .btn { flex: none; }
  .hints :global(*) { font-size: 0.75rem; }
  .clip:focus-within, input:focus-visible + .clip { outline: 2px solid var(--focus); }
  @media (max-width: 1100px) { .hints { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); } }
  @media (max-width: 767px) { .composer .stage { flex: 1 1 6rem; max-width: none; } .lbl { padding-left: 0; } .composer .btn { padding: 0 var(--s-3); } .sl { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); } }
</style>
