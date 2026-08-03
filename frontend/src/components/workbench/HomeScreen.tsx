"use client";

import { ArrowRight, Clock } from "lucide-react";
import type { AppState } from "@/lib/types";
import { Stat, absDate, dayLabel, isOverdue } from "./PersonalWorkspaceUI";
import { EngagementPortfolioRow } from "./EngagementScreens";

// Home is the day's digest, per the design reference: greeting, one summary line,
// the aggregate strip, engagements needing attention first, then Today | Your tasks.
export default function HomeScreen({ appState, onNavigate }: {
  appState: AppState; onNavigate: (route: string) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const tasks = appState.personalTasks ?? [];
  const events = appState.calendarEvents ?? [];
  const engagements = appState.engagements ?? [];

  const openTasks = tasks.filter((task) => task.status !== "Done");
  const overdue = tasks.filter((task) => isOverdue(task, today));
  const dueToday = openTasks.filter((task) => (task.dueDate || "").slice(0, 10) === today);
  const eventsToday = events.filter((event) => (event.date || "").slice(0, 10) === today)
    .sort((a, b) => ((a.start || "") < (b.start || "") ? -1 : 1));
  const nextEvents = events.filter((event) => (event.date || "").slice(0, 10) >= today)
    .sort((a, b) => (`${a.date}${a.start || ""}` < `${b.date}${b.start || ""}` ? -1 : 1))
    .slice(0, 5);

  const attention = engagements.filter((engagement) => engagement.status !== "green");
  // Attention-first ordering: off-track engagements lead, healthy ones follow.
  const ordered = [...attention, ...engagements.filter((engagement) => engagement.status === "green")];
  const firstName = appState.user?.displayName?.split(" ")[0];

  return (
    <div className="tw-screen" data-testid="home-screen">
      <div className="tw-microcap" style={{ marginBottom: 4 }}>{absDate(today)}</div>
      <h1 className="tw-h1">{firstName ? `Welcome back, ${firstName}.` : "Home"}</h1>
      <p className="tw-subtle" style={{ maxWidth: "62ch" }}>
        {attention.length} of {engagements.length} engagement{engagements.length === 1 ? "" : "s"} need attention
        and {overdue.length} {overdue.length === 1 ? "thing is" : "things are"} overdue.
      </p>

      <div className="tw-stats">
        <Stat label="need attention" value={attention.length} />
        <Stat label="overdue" value={overdue.length} />
        <Stat label="due today" value={dueToday.length} />
        <Stat label="events today" value={eventsToday.length} />
      </div>

      <section className="tw-section" data-testid="home-engagements">
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
          <h2 className="tw-h2">{attention.length > 0 ? "Needs attention" : "Engagements"}</h2>
          <button type="button" className="tw-btn-ghost" data-testid="home-view-all-engagements" onClick={() => onNavigate("/engagements")}>
            All engagements <ArrowRight size={13} />
          </button>
        </div>
        {engagements.length === 0 ? (
          <div className="tw-empty-sm">
            No engagements yet.{" "}
            <button type="button" className="tw-btn-ghost" data-testid="home-create-engagement" onClick={() => onNavigate("/engagements")}>
              Create your first engagement <ArrowRight size={13} />
            </button>
          </div>
        ) : (
          <div data-testid="home-engagement-cards">
            {ordered.map((engagement) => (
              <EngagementPortfolioRow
                key={engagement.id}
                engagement={engagement}
                today={today}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )}
      </section>

      <div className="tw-twocol">
        <section>
          <h2 className="tw-h2">{eventsToday.length > 0 ? "Today" : "Next up"}</h2>
          {(eventsToday.length > 0 ? eventsToday : nextEvents).length === 0 ? (
            <div className="tw-empty-sm">No upcoming events.</div>
          ) : (
            <div data-testid="home-events">
              {(eventsToday.length > 0 ? eventsToday : nextEvents).map((event) => (
                <div key={event.id} className="tw-listrow" data-testid={`home-event-${event.id}`}>
                  {event.start ? (
                    <span className="tw-time">{event.start}</span>
                  ) : (
                    <span className="tw-time"><Clock size={13} /></span>
                  )}
                  <span className="flex flex-col min-w-0">
                    <span className="tw-td-title">{event.title}</span>
                    <span className="tw-td-sub">
                      {dayLabel(event.date, today)}
                      {event.start && event.end ? ` · until ${event.end}` : ""}
                      {event.type ? ` · ${event.type}` : ""}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
        <section>
          <h2 className="tw-h2">Your tasks</h2>
          {openTasks.length === 0 ? (
            <div className="tw-empty-sm">Nothing open. Add tasks from My work.</div>
          ) : (
            <div data-testid="home-tasks">
              {openTasks.slice(0, 6).map((task) => (
                <button
                  key={task.id}
                  type="button"
                  className="tw-listrow"
                  data-testid={`home-task-${task.id}`}
                  onClick={() => onNavigate(`/todo/${task.id}`)}
                >
                  <span className="flex flex-col min-w-0 flex-1">
                    <span className="tw-td-title">{task.title}</span>
                    <span className="tw-td-sub">{task.group || "General"} · {task.status}</span>
                  </span>
                  <span className={`tw-td-sub ${isOverdue(task, today) ? "tw-due-overdue" : ""}`} style={{ whiteSpace: "nowrap" }}>
                    {task.dueDate ? dayLabel(task.dueDate.slice(0, 10), today) : ""}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="tw-section" data-testid="home-quicklinks">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <span className="tw-microcap" style={{ marginBottom: 0 }}>Jump to</span>
          <button type="button" className="tw-chip" data-testid="quicklink--todo" onClick={() => onNavigate("/todo")}>Tasks</button>
          <button type="button" className="tw-chip" data-testid="quicklink--calendar" onClick={() => onNavigate("/calendar")}>Calendar</button>
          <button type="button" className="tw-chip" data-testid="quicklink--reminders" onClick={() => onNavigate("/reminders")}>Reminders</button>
        </div>
      </section>
    </div>
  );
}
