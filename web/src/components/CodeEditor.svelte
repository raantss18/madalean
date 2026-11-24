<script lang="ts">
  // CodeMirror editor (lazy chunk). Until it is loaded, a plain textarea keeps the page usable (no blank box).
  import { onDestroy, tick } from 'svelte';
  import type { EditorHandle } from '../lib/lean/editor';
  import type { GlossEntry } from '../lib/lean/glossary';
  import { i18n } from '../lib/i18n/index.svelte';
  import { enterIntent, touchOnly } from '../lib/ui/enter';
  import { whenIdle } from '../lib/ui/idle';

  let {
    value = $bindable(''), language = 'lean', readonly = false, label, placeholder = '', errors = [], gloss = false,
    onTokenTap, onSubmit, enterSubmits = true, minLines = 3, id = '', lineNumbers = true, describedby = '', workspace = '', linkComplete,
  }: {
    value?: string; language?: 'lean' | 'natural'; readonly?: boolean; label: string; placeholder?: string;
    errors?: { line: number; text: string; severity: string }[]; gloss?: boolean;
    onTokenTap?: (token: string, entry: GlossEntry | null) => void; onSubmit?: () => void;
    /** With onSubmit: Enter submits, Shift+Enter is a new line (S-AK). false: long-form text, only Ctrl+Enter submits. */
    enterSubmits?: boolean; minLines?: number; id?: string;
    lineNumbers?: boolean; describedby?: string; workspace?: string;
    linkComplete?: (typed: string) => Promise<{ label: string; apply: string; detail?: string }[]>;
  } = $props();

  let host: HTMLDivElement | undefined = $state();
  let ed: EditorHandle | null = null;
  let ready = $state(false);
  let ta: HTMLTextAreaElement | undefined = $state();

  // S-AP: CodeMirror is fetched and built once the screen is painted and the browser idle, or at once when the plain
  // field is focused — never in the way of the first paint.
  let want = $state(false);
  $effect(() => {
    if (want || !host) return;
    return whenIdle(() => { want = true; }, 1500);
  });
  $effect(() => {
    if (!host || ed || !want) return;
    let cancelled = false;
    void import('../lib/lean/editor').then(({ createEditor }) => {
      if (cancelled || !host) return;
      const hadFocus = document.activeElement === ta;
      const caret = ta?.selectionStart ?? value.length;
      ed = createEditor({
        parent: host, doc: value, language, readOnly: readonly, ariaLabel: label, placeholder,
        lineNumbers: language === 'lean' && lineNumbers, lang: () => i18n.base, gloss, onTokenTap, onSubmit, enterSubmits,
        declLookup: gloss ? (name) => import('../lib/lean/lookup').then((m) => m.lookupToken(name, workspace || undefined)) : undefined,
        onChange: (d) => { value = d; }, linkComplete,
      });
      if (describedby) ed.view.contentDOM.setAttribute('aria-describedby', describedby);
      if (id) ed.view.contentDOM.id = id;
      ed.view.dom.classList.toggle('natural', language === 'natural');
      ed.view.dom.classList.toggle('readonly', readonly);
      ed.view.dom.style.setProperty('--min-lines', String(minLines));
      const atEnd = caret >= value.length;
      ready = true;
      // the editor is shown at the next DOM update: move the focus (and the caret) once it is visible (S-AP: it may be
      // built while the user is already typing in the plain field)
      if (hadFocus) void tick().then(() => {
        if (!ed) return;
        ed.focus();
        ed.view.dispatch({ selection: { anchor: atEnd ? ed.view.state.doc.length : Math.min(caret, ed.view.state.doc.length) } });
      });
    });
    return () => { cancelled = true; };
  });
  $effect(() => { if (ed && ready) ed.set(value); });
  $effect(() => { if (ed && ready) { ed.setReadOnly(readonly); ed.view.dom.classList.toggle('readonly', readonly); } });
  $effect(() => { if (ed && ready) ed.setErrors(errors); });
  onDestroy(() => ed?.destroy());
  export function focus() { if (ed) ed.focus(); else ta?.focus(); }
</script>

<div class="code-editor" style:--min-h="{minLines * 1.6 + 1}em">
  <div bind:this={host} class="host" hidden={!ready}></div>
  {#if !ready}
    <textarea bind:this={ta} {id} class="input fallback" class:mono={language === 'lean'} aria-label={label} aria-describedby={describedby || undefined}
      {placeholder} readonly={readonly} bind:value rows={minLines} spellcheck={language === 'natural'} onfocus={() => { want = true; }}
      onkeydown={(e) => { const k = enterIntent(e); if (onSubmit && k === 'submit' && (e.ctrlKey || e.metaKey || (enterSubmits && !touchOnly()))) { e.preventDefault(); onSubmit(); } }}></textarea>
  {/if}
</div>

<style>
  .code-editor { position: relative; }
  .host :global(.cm-editor) { min-height: var(--min-h); }
  .host :global(.cm-editor .cm-scroller) { min-height: var(--min-h); max-height: 70vh; }
  .fallback { min-height: var(--min-h); font-size: 0.9375rem; line-height: 1.6; }
  .fallback.mono { font-family: var(--font-mono); white-space: pre; }
</style>
