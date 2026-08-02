import { useEffect, useRef, useState } from 'react';
import { fmtPoints } from '../engine/scoring.js';

/**
 * CountUp — animates a score to its new value instead of snapping.
 *
 * "Watch a projected total move" is the payoff of the roll, so this is one of
 * the few places the motion budget is spent. It also announces the settled
 * value to a polite live region, because the number changing is information,
 * not decoration.
 *
 * Honours prefers-reduced-motion by jumping straight to the value — the
 * information is identical, only the theatre is removed.
 */
export default function CountUp({ value, className = '', style, announce = false, live = 'polite' }) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const rafRef = useRef(null);

  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const from = fromRef.current;
    const to = value;

    // requestAnimationFrame does not fire in a hidden tab. Without this the
    // score silently freezes at whatever it read when the tab was backgrounded
    // and never catches up — a stale score is worse than an unanimated one.
    if (reduced || document.hidden || from === to) {
      fromRef.current = to;
      setDisplay(to);
      return;
    }

    const ms = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--countup-duration')
    ) || 900;

    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      fromRef.current = to;
      setDisplay(to);
    };

    const start = performance.now();
    const tick = (now) => {
      const t = Math.min((now - start) / ms, 1);
      // easeOutCubic — fast then settling, matching --easing-settle
      const eased = 1 - Math.pow(1 - t, 3);
      if (t < 1) {
        setDisplay(from + (to - from) * eased);
        rafRef.current = requestAnimationFrame(tick);
      } else {
        settle();
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    // Backstop: if rAF is throttled or the tab is hidden mid-animation, the
    // value still lands. Deliberately NOT called from cleanup — in StrictMode
    // that would settle before the second effect pass and kill the animation.
    const guard = setTimeout(settle, ms + 150);

    return () => {
      cancelAnimationFrame(rafRef.current);
      clearTimeout(guard);
    };
  }, [value]);

  return (
    <span
      data-score
      data-target={Math.round(value)}
      className={className}
      style={style}
      aria-live={announce ? live : undefined}
      aria-atomic={announce ? 'true' : undefined}
    >
      {fmtPoints(display)}
    </span>
  );
}
