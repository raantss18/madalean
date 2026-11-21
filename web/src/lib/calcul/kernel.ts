// What a cell's error output says about the kernel (S-W): a kernel that could not start or stopped, or Sage that is
// not installed, is shown as one plain sentence and one action; the raw server log stays under « Détails ».
export type KernelProblem = 'nosage' | 'nostart' | 'stopped';

export function kernelProblem(o: { type: string; ename?: string; evalue?: string }): KernelProblem | null {
  if (o.type !== 'error') return null;
  const v = String(o.evalue ?? '');
  if (o.ename === 'unavailable' || /^kernel_(unavailable|died)\b/.test(v)) {
    if (/^kernel_unavailable\b/.test(v) && /\bsage\b/i.test(v)) return 'nosage';
    return 'nostart';
  }
  return o.ename === 'died' ? 'stopped' : null;
}
