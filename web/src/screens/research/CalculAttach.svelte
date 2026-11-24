<script lang="ts">
  // S-BA (D59): the paperclip of a Calcul « Demande » cell. The file becomes a Source of the PROJECT, read once
  // (same digest as a dossier's attachment); the cell lists its attachments as chips (number, name, state) and a
  // request naming « pièce jointe N » gets the digest's quotes. Model-written code keeps Calcul's approval rule.
  import { calculAttachments, ATTACH_ACCEPT, type Attachment } from '../../lib/api/literature';
  import { app } from '../../lib/store/app.svelte';
  import { ct } from '../../lib/calcul/strings';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  let { pid, cell, n }: { pid: string; cell: string; n: number } = $props();
  let atts = $state<Attachment[]>([]);
  let busy = $state(false);

  async function load() {
    try { atts = (await calculAttachments.list(pid, cell)).attachments; } catch { /* the chips are optional */ }
  }
  $effect(() => { void pid; void cell; void load(); });
  $effect(() => app.on('calcul.attachments', (ev) => { if ((ev as { project_id?: string }).project_id === pid) void load(); }));

  async function attach(input: HTMLInputElement) {
    busy = true;
    for (const f of Array.from(input.files ?? [])) {
      try {
        const r = await calculAttachments.attachFile(pid, cell, f);
        toast('ok', ct('attached', { n: r.attachment.n, name: f.name }));
      } catch (e) { toast('error', errorText(e)); }
    }
    input.value = '';
    busy = false;
    await load();
  }
  async function unlink(a: Attachment) {
    try { await calculAttachments.unlink(pid, cell, a.n); await load(); } catch (e) { toast('error', errorText(e)); }
  }
</script>

<span class="ca">
  <input id="cfile-{cell}" class="sr-only" type="file" accept={ATTACH_ACCEPT} multiple disabled={busy}
    onchange={(e) => void attach(e.target as HTMLInputElement)} />
  <label for="cfile-{cell}" class="btn small quiet clip" title={ct('attachFile')} aria-busy={busy}>
    <Icon name="paperclip" size={14} /><span class="sr-only">{ct('attachFile')} ({n})</span></label>
  {#if atts.length}
    <ul class="chips" aria-label={ct('attachList')}>
      {#each atts as a (a.n)}
        <li class="chip xs st-{a.state}">
          <Icon name={a.kind === 'image' ? 'image' : 'file'} size={12} />
          <span>{ct('attachN', { n: a.n })} — {a.name.slice(0, 40)} · {ct(`attachState_${a.state}`)}</span>
          <button class="x" aria-label={ct('attachUnlink', { n: a.n })} onclick={() => unlink(a)}><Icon name="x" size={12} /></button>
        </li>
      {/each}
    </ul>
  {/if}
</span>

<style>
  .ca { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; }
  .chips { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 4px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--line-strong); border-radius: 999px; padding: 2px 4px 2px 8px; background: var(--surface-2); max-width: 100%; }
  .chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip.st-reading { border-style: dashed; }
  .chip.st-error, .chip.st-unread { border-style: dotted; }
  .x { display: inline-grid; place-items: center; min-width: 24px; min-height: 24px; border: 0; background: transparent; color: var(--text-2); cursor: pointer; border-radius: 999px; }
  .x:focus-visible { outline: 2px solid var(--focus); }
</style>
