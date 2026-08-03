import type { HTMLAttributes, ReactNode } from "react";

export interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  level?: "base" | "subtle" | "raised";
}

export function Surface({ children, level = "base", className = "", ...props }: SurfaceProps) {
  return (
    <div className={`ui-surface ui-surface-${level} ${className}`.trim()} {...props}>
      {children}
    </div>
  );
}

export function Card({ children, className = "", ...props }: Omit<SurfaceProps, "level">) {
  return (
    <Surface level="raised" className={`ui-card ${className}`.trim()} {...props}>
      {children}
    </Surface>
  );
}
