// A shared one-second clock for elapsed times (one timer for the whole app).
export const clock = $state({ now: Date.now() / 1000 });
if (typeof window !== 'undefined') setInterval(() => { clock.now = Date.now() / 1000; }, 1000);
