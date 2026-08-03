"use client";

import type { AppState } from "@/lib/types";
import WorkbenchNav from "./WorkbenchNav";
import { EngagementScreen, EngagementsList } from "./EngagementScreens";
import SettingsScreen from "./SettingsScreen";
import HomeScreen from "./HomeScreen";
import TasksScreen from "./TasksScreen";
import CalendarScreen from "./CalendarScreen";
import RemindersScreen from "./RemindersScreen";
import Button from "@/components/ui/Button";
import Toast from "@/components/ui/Toast";

interface WorkbenchAppProps {
  appState: AppState | null;
  loading: boolean;
  viewRoute: string;
  onNavigate: (route: string) => void;
  agentWorking: boolean;
  onRefresh: () => Promise<void>;
  workspaceStale?: string | null;
  sessionError?: string | null;
  onRetrySession?: () => Promise<void>;
  onDrawerOpenChange?: (open: boolean) => void;
}

export default function WorkbenchApp({
  appState, loading, viewRoute, onNavigate, agentWorking, onRefresh, workspaceStale, sessionError, onRetrySession, onDrawerOpenChange,
}: WorkbenchAppProps) {
  return (
    <div className="tw-app" data-testid="workbench-app">
      <div className="tw-body">
        <WorkbenchNav
          appState={appState}
          viewRoute={viewRoute}
          onNavigate={onNavigate}
          statusLabel={agentWorking ? "Assistant working…" : "Ready"}
          onDrawerOpenChange={onDrawerOpenChange}
        />
        <main className="tw-content" data-testid="workbench-content">
          {loading && !appState ? <div className="tw-empty" data-testid="workspace-loading" role="status">Loading workspace…</div>
            : sessionError && !appState ? <div className="tw-empty" role="alert">{sessionError} <Button variant="primary" size="small" data-testid="workspace-retry" onClick={() => void onRetrySession?.()}>Retry</Button></div>
              : !appState ? <div className="tw-empty" role="alert">{workspaceStale ?? "Workspace unavailable."}</div>
                : <RouteContent appState={appState} viewRoute={viewRoute} onNavigate={onNavigate} onRefresh={onRefresh} />}
          {workspaceStale && appState && <Toast tone="warning" className="tw-workspace-stale" data-testid="workspace-stale">Showing the last refreshed workspace. {workspaceStale} <Button variant="ghost" size="small" data-testid="workspace-retry" onClick={() => void onRefresh().catch(() => undefined)}>Retry</Button></Toast>}
        </main>
      </div>
    </div>
  );
}

function RouteContent({ appState, viewRoute, onNavigate, onRefresh }: { appState: AppState; viewRoute: string; onNavigate: (route: string) => void; onRefresh: () => Promise<void> }) {
  if (viewRoute === "/settings") return <SettingsScreen appState={appState} onRefresh={onRefresh} />;
  if (viewRoute === "/engagements") return <EngagementsList appState={appState} onNavigate={onNavigate} onRefresh={onRefresh} />;
  if (viewRoute === "/home") return <HomeScreen appState={appState} onNavigate={onNavigate} />;
  if (viewRoute === "/todo" || viewRoute.startsWith("/todo/")) {
    return <TasksScreen appState={appState} viewRoute={viewRoute} onNavigate={onNavigate} onRefresh={onRefresh} />;
  }
  if (viewRoute === "/calendar") return <CalendarScreen appState={appState} onNavigate={onNavigate} onRefresh={onRefresh} />;
  if (viewRoute === "/reminders") return <RemindersScreen appState={appState} onRefresh={onRefresh} />;
  return <EngagementScreen appState={appState} viewRoute={viewRoute} onNavigate={onNavigate} onRefresh={onRefresh} />;
}
