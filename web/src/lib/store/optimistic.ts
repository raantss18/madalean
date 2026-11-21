// Optimistic UI: apply a change locally, send it, roll back if the server refuses.

export interface OptimisticResult<T> {
  ok: boolean;
  value?: T;
  error?: unknown;
}

/**
 * `apply` mutates local state and returns the function that undoes it.
 * On success the server's own event (or `onSuccess`) brings the authoritative state; on failure we roll back.
 */
export async function optimistic<T>(
  apply: () => () => void,
  send: () => Promise<T>,
  hooks: { onSuccess?: (v: T) => void; onError?: (e: unknown) => void } = {},
): Promise<OptimisticResult<T>> {
  const rollback = apply();
  try {
    const value = await send();
    hooks.onSuccess?.(value);
    return { ok: true, value };
  } catch (error) {
    try { rollback(); } finally { hooks.onError?.(error); }
    return { ok: false, error };
  }
}

/** Sets `obj[key] = value` and returns the undo function (handles keys that did not exist). */
export function setWithUndo<O extends object, K extends keyof O>(obj: O, key: K, value: O[K]): () => void {
  const had = Object.prototype.hasOwnProperty.call(obj, key);
  const prev = obj[key];
  obj[key] = value;
  return () => {
    if (had) obj[key] = prev;
    else delete obj[key];
  };
}
