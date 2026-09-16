/** A short, unobtrusive reminder chime, synthesized with the Web Audio API
 * so no external asset needs to be downloaded or shipped. Autoplay policies
 * block audio before any user gesture on the page -- `.play()`'s rejection
 * (here, `AudioContext.resume()`'s) is always swallowed so a blocked chime
 * never throws or crashes the reminder flow (§7 of the reminder spec).
 */
let sharedContext: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (sharedContext) return sharedContext;
  const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  sharedContext = new Ctor();
  return sharedContext;
}

export function playReminderChime(): void {
  try {
    const ctx = getContext();
    if (!ctx) return;
    const resume = ctx.state === 'suspended' ? ctx.resume() : Promise.resolve();
    resume
      .then(() => {
        const now = ctx.currentTime;
        [880, 1320].forEach((frequency, index) => {
          const oscillator = ctx.createOscillator();
          const gain = ctx.createGain();
          oscillator.type = 'sine';
          oscillator.frequency.value = frequency;
          const start = now + index * 0.12;
          gain.gain.setValueAtTime(0, start);
          gain.gain.linearRampToValueAtTime(0.16, start + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.001, start + 0.22);
          oscillator.connect(gain).connect(ctx.destination);
          oscillator.start(start);
          oscillator.stop(start + 0.24);
        });
      })
      .catch(() => undefined);
  } catch {
    // Never let a blocked/unsupported audio API break the reminder itself.
  }
}
