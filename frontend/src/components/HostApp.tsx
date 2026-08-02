"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Sparkles } from "lucide-react";
import WorkbenchApp from "./workbench/WorkbenchApp";
import CoPilotDock from "./CoPilotDock";
import BespokeIcon from "./ui/BespokeIcon";
import Button from "./ui/Button";
import { Overlay } from "./ui/Overlay";
import { useSession } from "./SessionProvider";

// The host route ("/"): the CSA Workbench app is primary and full-width; the assistant
// rides along as a collapsible docked co-pilot. Collapsed, the app gets the whole canvas
// and the assistant becomes an unobtrusive launcher pill.
export default function HostApp() {
  const {
    state,
    navigateView,
    isChatUploading,
    refresh,
    startSession,
  } = useSession();
  const [wideDockOpen, setWideDockOpen] = useState(true);
  const [compactDockOpen, setCompactDockOpen] = useState(false);
  const [navDrawerOpen, setNavDrawerOpen] = useState(false);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const compactSheetRef = useRef<HTMLDivElement>(null);

  // Responsive: below 1200px the side-by-side rail crushes the host content, so the dock
  // auto-collapses to the launcher (host gets the full width) and, when opened, overlays the
  // host instead of squeezing it. Auto-adapts on resize while respecting in-regime toggles.
  const narrow = useCompactLayout();
  const dockOpen = narrow ? compactDockOpen : wideDockOpen;
  const setDockOpen = useCallback((open: boolean) => {
    if (narrow) setCompactDockOpen(open);
    else setWideDockOpen(open);
  }, [narrow]);
  const closeDock = useCallback(() => {
    setDockOpen(false);
    if (narrow) requestAnimationFrame(() => launcherRef.current?.focus());
  }, [narrow, setDockOpen]);

  useEffect(() => {
    if (!narrow || !dockOpen) return;
    const sheet = compactSheetRef.current;
    const focusable = () => [...(sheet?.querySelectorAll<HTMLElement>("button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])") ?? [])].filter((element) => element.offsetParent !== null);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { closeDock(); return; }
      if (event.key !== "Tab") return;
      const controls = focusable();
      if (!controls.length) return;
      const first = controls[0]; const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    requestAnimationFrame(() => (focusable()[0] ?? sheet)?.focus());
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [closeDock, dockOpen, narrow]);

  const agentWorking = state.isStreaming || isChatUploading;

  return (
    <div className="relative flex h-screen w-full bg-app text-text-primary font-sans overflow-clip" data-testid="host-shell">
      <div className="relative z-10 flex h-full w-full" data-testid="host-layout">
        <div className="flex-1 min-w-0 h-full">
          <WorkbenchApp
            appState={state.appState}
            loading={state.isInitializing}
            viewRoute={state.viewRoute}
            onNavigate={navigateView}
            agentWorking={agentWorking}
            onRefresh={refresh}
            workspaceStale={state.workspaceStale}
            sessionError={state.sessionError}
            onRetrySession={startSession}
            onDrawerOpenChange={setNavDrawerOpen}
          />
        </div>

        {dockOpen && !narrow && (
          <div
            data-testid="copilot-dock"
            className="tw-dock w-[372px] shrink-0 h-full"
          >
            <CoPilotDock onCollapse={closeDock} />
          </div>
        )}
      </div>

      {/* Narrow: the dock overlays the host (with a tap-to-dismiss backdrop) instead of squeezing it. */}
      {dockOpen && narrow && (
        <>
          <Overlay className="z-20" label="Close assistant" onDismiss={closeDock} />
          <div
            ref={compactSheetRef}
            role="dialog"
            aria-modal="true"
            aria-label="Assistant"
            tabIndex={-1}
            data-testid="copilot-dock"
            className="fixed right-3 top-3 bottom-3 z-30 w-[min(440px,92vw)]"
          >
            <CoPilotDock onCollapse={closeDock} />
          </div>
        </>
      )}

      {!dockOpen && !navDrawerOpen && (
        <Button
          data-testid="dock-launcher"
          ref={launcherRef}
          onClick={() => setDockOpen(true)}
          variant="primary"
          size="icon"
          aria-label={agentWorking ? "Assistant working — open assistant" : "Ask the Assistant"}
          title="Ask the Assistant"
          className={`tw-fab fixed bottom-5 right-5 z-20 ${agentWorking ? "agent-working" : ""}`}
        >
          <BespokeIcon icon={Sparkles} size={17} />
        </Button>
      )}
    </div>
  );
}

function useCompactLayout() {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia("(max-width: 1199px)");
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => window.matchMedia("(max-width: 1199px)").matches,
    // Render the safe compact state on the server and during hydration. The
    // browser snapshot immediately opens the dock on wide layouts, while a
    // compact first paint never exposes an overlay the user did not request.
    () => true,
  );
}
