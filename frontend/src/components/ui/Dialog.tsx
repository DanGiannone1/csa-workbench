import { forwardRef } from "react";
import type { HTMLAttributes, ReactNode } from "react";

const Dialog = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement> & { children: ReactNode }>(function Dialog(
  { children, className = "", ...props },
  ref,
) {
  return (
    <div ref={ref} role="dialog" aria-modal="true" className={`ui-dialog ${className}`.trim()} {...props}>
      {children}
    </div>
  );
});

export default Dialog;
