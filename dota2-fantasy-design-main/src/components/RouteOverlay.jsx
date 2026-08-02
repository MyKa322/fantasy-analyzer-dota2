import { useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * RouteOverlay — the shared chrome and behaviour for every modal in the app.
 *
 * Every modal here is a real route, so this has to do more than a styled div:
 *
 *  - Focus is trapped while open and restored to the trigger on close.
 *  - Escape closes; so does the backdrop and the close button.
 *  - Closing returns to the route underneath rather than popping the stack
 *    blindly — a cold deep-link has no history to go back to, so it falls
 *    through to /build instead of exiting the app.
 *  - Background scroll is locked without the layout shifting.
 *
 * Written once so the team picker, titles, glossary, roll panel, and player
 * detail all behave identically.
 */
export default function RouteOverlay({
  title,
  children,
  onClose,
  size = 'lg',          // md | lg | full
  labelledBy = 'overlay-title',
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const panelRef = useRef(null);
  const restoreRef = useRef(null);

  const close = useCallback(() => {
    if (onClose) return onClose();
    // Prefer the route we were opened from; fall back to the builder so a
    // cold deep-link never dead-ends or exits the app.
    const background = location.state?.backgroundLocation;
    if (background) navigate(-1);
    else navigate('/build', { replace: true });
  }, [navigate, location, onClose]);

  // Remember what had focus, move focus in, restore on unmount.
  useEffect(() => {
    restoreRef.current = document.activeElement;
    const first = panelRef.current?.querySelector(FOCUSABLE);
    (first ?? panelRef.current)?.focus();
    return () => {
      const el = restoreRef.current;
      if (el && document.contains(el)) el.focus();
    };
  }, []);

  // Lock background scroll without shifting layout when the bar disappears.
  useEffect(() => {
    const { body } = document;
    const prevOverflow = body.style.overflow;
    const prevPad = body.style.paddingRight;
    const barWidth = window.innerWidth - document.documentElement.clientWidth;
    body.style.overflow = 'hidden';
    if (barWidth > 0) body.style.paddingRight = `${barWidth}px`;
    return () => {
      body.style.overflow = prevOverflow;
      body.style.paddingRight = prevPad;
    };
  }, []);

  // Escape to close; Tab cycles within the panel.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        close();
        return;
      }
      if (e.key !== 'Tab') return;
      const nodes = [...(panelRef.current?.querySelectorAll(FOCUSABLE) ?? [])]
        .filter((n) => n.offsetParent !== null);
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [close]);

  const maxWidth =
    size === 'full' ? 'min(1400px, 96vw)'
    : size === 'md' ? 'min(680px, 94vw)'
    : 'min(1040px, 94vw)';

  return (
    /* Scrolling structure matters here. A flex child with `my-auto` inside an
       overflow container becomes partly unreachable as soon as it is taller
       than the viewport — the auto margins eat the overflow and you cannot
       scroll to the ends. The team grid is tall enough to hit that.
       The fix is the standard two-layer pattern: the OUTER element scrolls,
       an INNER wrapper with min-h-full does the centring, so a tall panel
       simply grows the wrapper and scrolls normally. */
    <div
      className="overflow-y-auto overscroll-contain"
      style={{
        // Insets are set inline, not via `inset-0`. The utility was not being
        // applied, which left the element at `top/right/bottom/left: auto` —
        // a fixed box with auto insets stays at its STATIC position, so the
        // overlay rendered in flow at the bottom of the page with no backdrop
        // and nothing to scroll. Inline values cannot be dropped.
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
        zIndex: 'var(--z-overlay)',
        background: 'var(--color-overlay)',
        backdropFilter: 'blur(6px)',
      }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
    >
      <div
        className="flex min-h-full items-center justify-center p-3 md:p-6"
        onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
      >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className="relative w-full rounded-lg border outline-none"
        style={{
          maxWidth,
          background: 'var(--color-bg-base)',
          borderColor: 'var(--color-border-strong)',
          boxShadow: 'var(--shadow-overlay)',
        }}
      >
        {/* Sticky so Close and the title stay reachable on a long panel.
            `top` is inline for the same reason as the overlay insets — a
            sticky element with `top: auto` never sticks. */}
        <header
          className="flex items-center gap-4 rounded-t-lg border-b px-5 py-4 md:px-7"
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 10,
            borderColor: 'var(--color-border)',
            background: 'color-mix(in srgb, var(--color-bg-base) 96%, transparent)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <h1 id={labelledBy} className="flex-1" style={{ fontSize: 'var(--text-lg)' }}>
            {title}
          </h1>

          <button
            type="button"
            onClick={close}
            aria-label="Close"
            className="grid h-touch w-touch place-items-center rounded-md transition-colors duration-fast hover:bg-bg-hover md:h-control md:w-control"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        <div className="px-5 py-6 md:px-7">{children}</div>
      </div>
      </div>
    </div>
  );
}
