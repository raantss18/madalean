import { describe, expect, it } from 'vitest';
import { jobRuns, roleOfStage, sideStages } from '../../src/lib/status';

// D38: several stages of one job run at once; `stage` is the main one, `stages` all of them (older servers: none).
describe('parallel stages', () => {
  it('sees a stage running beside the main one', () => {
    const job = { stage: 'proof', stages: ['proof', 'notes', 'verify'] };
    expect(jobRuns(job, 'proof')).toBe(true);
    expect(jobRuns(job, 'notes')).toBe(true);
    expect(jobRuns(job, 'explanation')).toBe(false);
    expect(sideStages(job)).toEqual(['notes', 'verify']);
  });

  it('works with a server that only sends `stage`', () => {
    expect(jobRuns({ stage: 'notes' }, 'notes')).toBe(true);
    expect(sideStages({ stage: 'notes' })).toEqual([]);
    expect(jobRuns(undefined, 'notes')).toBe(false);
  });

  it('maps the Mathlib search to the prover role', () => {
    expect(roleOfStage('mathlib')).toBe('prove');
  });
});
