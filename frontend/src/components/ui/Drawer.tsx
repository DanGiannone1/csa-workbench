import { forwardRef } from "react";
import type { HTMLAttributes, ReactNode } from "react";

const Drawer = forwardRef<HTMLElement, HTMLAttributes<HTMLElement> & { children: ReactNode; open: boolean }>(function Drawer(
  { children, open, className = "", ...props },
  ref,
) {
  return (
    <nav ref={ref} className={`ui-drawer ${open ? "ui-drawer-open" : ""} ${className}`.trim()} {...props}>
      {children}
    </nav>
  );
});

export default Drawer;
