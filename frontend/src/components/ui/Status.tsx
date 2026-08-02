import type { HTMLAttributes, ReactNode } from "react";

type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

export default function Status({
  tone = "neutral",
  pill = true,
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: StatusTone;
  pill?: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={`ui-status ui-status-${tone} ${pill ? "ui-status-pill" : ""} ${className}`.trim()}
      {...props}
    >
      {children}
    </span>
  );
}
