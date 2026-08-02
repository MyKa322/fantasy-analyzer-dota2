import type { ReactNode } from "react";

export function Panel({
  title,
  subtitle,
  actions,
  children,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[#2a2e3a] bg-[#16181e] p-5">
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && (
              <h2 className="text-sm font-semibold tracking-[0.14em] text-[#c8a24a] uppercase">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-1 text-xs text-neutral-400">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-[#c8a24a] text-black hover:bg-[#e0c987]",
    ghost: "border border-[#2a2e3a] text-neutral-200 hover:border-[#c8a24a]",
    danger: "border border-red-900 text-red-300 hover:bg-red-950",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles}`}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] tracking-wide text-neutral-400 uppercase">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-neutral-500">{hint}</span>}
    </label>
  );
}

export const selectClass =
  "rounded border border-[#2a2e3a] bg-[#1d2029] px-2 py-1.5 text-sm text-neutral-100 outline-none focus:border-[#c8a24a]";

export function Notice({
  kind = "info",
  children,
}: {
  kind?: "info" | "warn" | "error";
  children: ReactNode;
}) {
  const styles = {
    info: "border-[#2a2e3a] bg-[#1d2029] text-neutral-300",
    warn: "border-amber-900 bg-amber-950/40 text-amber-200",
    error: "border-red-900 bg-red-950/40 text-red-200",
  }[kind];
  return (
    <div className={`rounded border px-3 py-2 text-xs ${styles}`}>{children}</div>
  );
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded border border-[#2a2e3a] bg-[#1d2029] px-3 py-2">
      <div className="text-[11px] tracking-wide text-neutral-400 uppercase">{label}</div>
      <div className="tabular mt-0.5 text-lg text-neutral-100">{value}</div>
      {hint && <div className="text-[11px] text-neutral-500">{hint}</div>}
    </div>
  );
}

export const COLOR_CLASS: Record<string, string> = {
  red: "text-red-400",
  blue: "text-sky-400",
  green: "text-emerald-400",
};
