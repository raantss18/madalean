// On-screen keyboard on phones and tablets (Android app, remote browsers).
// The Android shell resizes the web view (adjustResize) and the viewport asks browsers to do the same
// (interactive-widget=resizes-content), so the page height shrinks while the keyboard is up. We detect that,
// set html[data-kb="open"] (fixed bars marked .kb-hide disappear: the bottom navigation, floating panels) and
// keep the caret of the field being typed in visible above the keyboard. Inspired by Mahay's single bottom inset
// (max of system bar and keyboard) — here the shell already applies the inset, the page only has to react.

/** Height ratio under which the viewport is considered covered by a keyboard (rotation resets the baseline). */
export const KB_RATIO = 0.78;

export function isEditable(el: Element | null): boolean {
  if (!el) return false;
  if ((el as HTMLElement).isContentEditable) return true;
  if (el instanceof HTMLTextAreaElement) return !el.readOnly;
  if (el instanceof HTMLInputElement) return !el.readOnly && !['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file', 'image', 'hidden'].includes(el.type);
  return false;
}

/** Pure decision: is the keyboard open, given the tallest height seen for this width and the current height? */
export function keyboardOpen(baseline: number, current: number, editing: boolean): boolean {
  return editing && baseline > 0 && current < baseline * KB_RATIO;
}

/** How far to scroll so that `target` (caret or field) sits `margin` px above the visible bottom (0 = nothing). */
export function scrollNeeded(target: { top: number; bottom: number }, visibleTop: number, visibleBottom: number, margin = 24): number {
  if (target.bottom > visibleBottom - margin) return target.bottom - visibleBottom + margin;
  if (target.top < visibleTop + margin) return target.top - visibleTop - margin;
  return 0;
}

function caretRect(el: Element): DOMRect | null {
  const sel = window.getSelection();
  if (sel && sel.rangeCount && el.contains(sel.anchorNode)) {
    const r = sel.getRangeAt(0).getBoundingClientRect();
    if (r.height > 0) return r;
  }
  return null;
}

export function watchKeyboard(): () => void {
  if (typeof window === 'undefined' || !matchMedia('(pointer: coarse)').matches) return () => {};
  const vv = window.visualViewport;
  const height = () => Math.min(window.innerHeight, vv?.height ?? Infinity);
  let width = window.innerWidth;
  let baseline = height();
  let open = false;
  let raf = 0;

  const reveal = () => {
    const el = document.activeElement;
    if (!el || !isEditable(el)) return;
    const box = caretRect(el) ?? (() => {
      const r = el.getBoundingClientRect();
      // Tall fields (editors): keep their top part visible rather than their bottom.
      return r.height > height() / 2 ? new DOMRect(r.left, r.top, r.width, Math.min(r.height, 96)) : r;
    })();
    const top = (vv?.offsetTop ?? 0) + (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar-h')) || 0);
    const dy = scrollNeeded(box, top, (vv?.offsetTop ?? 0) + height());
    if (dy) {
      const scroller = el.closest('.cm-scroller');
      if (scroller && scroller.scrollHeight > scroller.clientHeight + 4) scroller.scrollTop += dy;
      else window.scrollBy({ top: dy, behavior: 'auto' });
    }
  };

  const update = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const h = height();
      const editing = isEditable(document.activeElement);
      if (window.innerWidth !== width) { width = window.innerWidth; baseline = h; } // rotation, split screen
      if (!editing || h > baseline) baseline = Math.max(h, editing ? baseline : 0);
      const now = keyboardOpen(baseline, h, editing);
      if (now !== open) {
        open = now;
        if (open) document.documentElement.dataset['kb'] = 'open';
        else delete document.documentElement.dataset['kb'];
      }
      if (open) reveal();
    });
  };

  window.addEventListener('resize', update);
  vv?.addEventListener('resize', update);
  document.addEventListener('focusin', update);
  document.addEventListener('focusout', update);
  return () => {
    window.removeEventListener('resize', update);
    vv?.removeEventListener('resize', update);
    document.removeEventListener('focusin', update);
    document.removeEventListener('focusout', update);
  };
}
