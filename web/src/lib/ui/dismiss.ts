// Click / tap outside closes a panel, and so does Escape (session S-AK, docs/UI.md §14.4). One action for every
// non-modal panel: menus, popovers, the logo menu, the context switcher, the status panel, side sheets.
// - a `pointerdown` outside the panel and outside its button closes it (the button's own click then does not reopen
//   it: it toggles from the closed state, so the panel's button keeps working as a toggle);
// - Escape closes the most recently opened panel only (panels can be nested: a « ⋯ » menu inside the status panel);
// - when the focus was inside the panel, it goes back to the button;
// - a modal <dialog> opened from a panel owns its events: clicks and Escape inside it never close the panel below.

export interface DismissOptions {
  onclose: () => void;
  /** The button that opened the panel: clicks on it are not « outside », the focus returns to it. */
  trigger?: HTMLElement | null;
  /** Default true. */
  enabled?: boolean;
}

const stack: HTMLElement[] = [];

/** Pure test of « outside » (unit-tested). */
export function isOutside(target: Node | null, panel: Node, trigger?: Node | null): boolean {
  if (!target) return false;
  if (panel.contains(target)) return false;
  if (trigger && trigger.contains(target)) return false;
  return true;
}

function inForeignModal(target: Node | null, panel: HTMLElement): boolean {
  const el = target instanceof Element ? target : target?.parentElement ?? null;
  const dlg = el?.closest?.('dialog[open]');
  // a dialog opened above the panel (not the dialog the panel itself lives in)
  return Boolean(dlg && !panel.contains(dlg) && !dlg.contains(panel));
}

export function dismiss(node: HTMLElement, opts: DismissOptions) {
  let o = opts;
  stack.push(node);
  const close = (refocus: boolean) => {
    if (o.enabled === false) return;
    const inside = node.contains(document.activeElement);
    o.onclose();
    if (refocus && (inside || document.activeElement === document.body)) o.trigger?.focus();
  };
  const down = (e: PointerEvent) => {
    if (o.enabled === false || e.button > 0) return;
    const tgt = e.target as Node | null;
    if (!isOutside(tgt, node, o.trigger) || inForeignModal(tgt, node)) return;
    // only the outermost panel that the click left closes itself; nested ones are inside it or also outside
    close(false);
  };
  const key = (e: KeyboardEvent) => {
    if (o.enabled === false || e.key !== 'Escape' || e.defaultPrevented) return;
    if (stack[stack.length - 1] !== node) return;
    if (document.querySelector('dialog[open]') && inForeignModal(document.activeElement, node)) return;
    e.preventDefault();
    close(true);
  };
  document.addEventListener('pointerdown', down, true);
  document.addEventListener('keydown', key);
  return {
    update(n: DismissOptions) { o = n; },
    destroy() {
      document.removeEventListener('pointerdown', down, true);
      document.removeEventListener('keydown', key);
      const i = stack.lastIndexOf(node);
      if (i >= 0) stack.splice(i, 1);
    },
  };
}
