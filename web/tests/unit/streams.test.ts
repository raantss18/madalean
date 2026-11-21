import { describe, it, expect } from 'vitest';
import { StreamStore } from '../../src/lib/store/streams';

describe('StreamStore', () => {
  it('coalesces notifications to one per frame and merges consecutive parts', () => {
    const frames: (() => void)[] = [];
    const st = new StreamStore((cb) => frames.push(cb));
    let calls = 0;
    st.subscribe('j', () => calls++);
    for (let i = 0; i < 100; i++) st.token('j', 'proof', 0, 'text', `line ${i}\n`);
    expect(frames.length).toBe(1);
    frames.shift()!();
    expect(calls).toBe(1);
    expect(st.get('j').parts.length).toBe(1);
    expect(st.get('j').parts[0]!.lines).toBe(100);
    st.token('j', 'proof', 0, 'thinking', 'hmm');
    st.token('j', 'proof', 1, 'text', 'next attempt');
    expect(st.get('j').parts.length).toBe(3);
  });
  it('restart info drops the partial text of the stage and records the model', () => {
    const st = new StreamStore(() => {});
    st.token('j', 'proof', 0, 'text', 'partial');
    st.info('j', 'proof', '', { event: 'restart', model: 'groq:x' });
    expect(st.get('j').parts.length).toBe(0);
    expect(st.get('j').model).toBe('groq:x');
  });
});
