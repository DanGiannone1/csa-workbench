import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function Tabs({ children, className = "", ...props }: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return <nav className={`ui-tabs ${className}`.trim()} {...props}>{children}</nav>;
}

export function Tab({ active = false, className = "", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={`ui-tab ${active ? "ui-tab-active" : ""} ${className}`.trim()}
      aria-current={active ? "page" : undefined}
      {...props}
    >
      {children}
    </button>
  );
}
