import type { ReactNode } from "react";

export default function Field({
  label,
  htmlFor,
  hint,
  error,
  className = "",
  children,
}: {
  label: ReactNode;
  htmlFor: string;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`ui-field ${className}`.trim()}>
      <label className="ui-field-label" htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <div className="ui-field-hint">{hint}</div>}
      {error && <div className="ui-field-error" role="alert">{error}</div>}
    </div>
  );
}
