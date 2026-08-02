/**
 * Button — flat, hairline, monochrome.
 *
 * No gradients, no bevels, no accent colour. Emphasis comes from surface value
 * and border weight, which is what keeps a dark minimal UI from looking heavy.
 */
export default function Button({
  children,
  variant = 'default',   // default | primary | ghost
  size = 'md',           // sm | md
  disabled = false,
  className = '',
  ...rest
}) {
  const surfaces = {
    default: { background: 'var(--color-bg-raised)', border: 'var(--color-border)', color: 'var(--color-text-primary)' },
    primary: { background: 'var(--n-050)', border: 'var(--n-050)', color: 'var(--n-950)' },
    ghost:   { background: 'transparent', border: 'transparent', color: 'var(--color-text-secondary)' },
  };
  const s = surfaces[variant] ?? surfaces.default;

  return (
    <button
      type="button"
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-md border font-body
        transition-[background-color,border-color,opacity] duration-fast
        min-h-touch md:min-h-control
        ${size === 'sm' ? 'px-3 text-xs' : 'px-4 text-sm'}
        ${disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer hover:brightness-110'}
        ${className}`}
      style={{
        background: s.background,
        borderColor: s.border,
        color: s.color,
        fontWeight: 'var(--weight-medium)',
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
