import type { HTMLAttributes, ReactNode } from "react";

export default function Toast({
  tone = "neutral",
  children,
  className = "",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  tone?: "neutral" | "success" | "warning" | "danger";
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={`ui-toast ui-toast-${tone} ${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  );
}
