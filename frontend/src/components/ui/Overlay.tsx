import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function Overlay({
  onDismiss,
  label = "Close overlay",
  className = "",
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  onDismiss: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      className={`ui-overlay ${className}`.trim()}
      aria-label={label}
      onClick={onDismiss}
      {...props}
    />
  );
}

export function OverlayLayer({ children, className = "", ...props }: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return <div className={`ui-overlay-layer ${className}`.trim()} {...props}>{children}</div>;
}
