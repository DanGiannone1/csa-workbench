"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Download,
  Files,
  FolderKanban,
  Plus,
  Settings as SettingsIcon,
  Trash2,
  Upload,
  Users,
} from "lucide-react";
import type {
  AppState,
  Artifact,
  Engagement,
  EngagementRole,
  EngagementStatus,
  Task,
  TimelineEntry,
  TimelineEntryType,
} from "@/lib/types";
import {
  addConvention,
  addEngagementContact,
  addEngagementMember,
  addKeyDate,
  addObjective,
  addTimelineEntry,
  createEngagement,
  createEngagementTask,
  deleteEngagementArtifact,
  deleteEngagementTask,
  listUsers,
  downloadEngagementArtifact,
  promoteArtifact,
  removeConvention,
  removeEngagementMember,
  toggleKeyDate,
  updateEngagement,
  updateEngagementTask,
  uploadEngagementArtifact,
} from "@/lib/api";
import { parseEngagementRoute } from "@/lib/engagementRoute";
import { friendlyError } from "@/lib/utils";
import { Tab, Tabs } from "@/components/ui/Tabs";

const statusLabel: Record<EngagementStatus, string> = {
  green: "Green",
  yellow: "Yellow",
  red: "Red",
};

function openTasks(engagement: Engagement) {
  return (engagement.tasks ?? []).filter((task) => task.status !== "Done")
    .length;
}

function roleOf(
  engagement: Engagement,
  userId: string | undefined,
): EngagementRole | null {
  return (
    engagement.members.find((member) => member.userId === userId)?.role ?? null
  );
}

function canEdit(role: EngagementRole | null) {
  return role === "owner" || role === "editor";
}

function isOverdue(task: Task, today: string) {
  return (
    task.status !== "Done" &&
    !!task.dueDate &&
    task.dueDate.slice(0, 10) < today
  );
}

function useBusy(onRefresh: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>) => {
    if (busy) return false;
    setBusy(true);
    setError(null);
    try {
      await action();
      await onRefresh();
      return true;
    } catch (err) {
      setError(friendlyError(err, "Action failed."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { busy, error, run, setError };
}

export function EngagementsList({
  appState,
  onNavigate,
  onRefresh,
}: {
  appState: AppState;
  onNavigate: (route: string) => void;
  onRefresh: () => Promise<void>;
}) {
  const engagements = appState.engagements ?? [];
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [customer, setCustomer] = useState("");
  const [description, setDescription] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);
  const { busy, error, run, setError } = useBusy(onRefresh);

  const create = async () => {
    if (!name.trim()) {
      setError("Enter an engagement name.");
      requestAnimationFrame(() => nameRef.current?.focus());
      return;
    }

    let createdId = "";
    const saved = await run(async () => {
      const created = await createEngagement({
        name: name.trim(),
        customer: customer.trim(),
        description: description.trim(),
      });
      createdId = created.id;
    });
    if (!saved || !createdId) return;

    setAdding(false);
    setName("");
    setCustomer("");
    setDescription("");
    onNavigate(`/engagements/${createdId}`);
  };

  return (
    <div className="tw-screen" data-testid="engagements-screen">
      <h1 className="tw-h1">Engagements</h1>
      <p className="tw-subtle">
        Shared customer-delivery workspaces — status, durable artifacts, and the
        team&apos;s record in one place.
      </p>

      <div className="tw-stats" style={{ marginTop: 14 }}>
        <StatBox
          label="Engagements"
          value={engagements.length}
          testid="eng-stat-total"
        />
        <StatBox
          label="Red"
          value={
            engagements.filter((engagement) => engagement.status === "red")
              .length
          }
          testid="eng-stat-red"
        />
        <StatBox
          label="Yellow"
          value={
            engagements.filter((engagement) => engagement.status === "yellow")
              .length
          }
          testid="eng-stat-yellow"
        />
        <StatBox
          label="Open tasks"
          value={engagements.reduce(
            (count, engagement) => count + openTasks(engagement),
            0,
          )}
          testid="eng-stat-tasks"
        />
      </div>

      {!adding ? (
        <button
          type="button"
          className="tw-addbar"
          data-testid="add-engagement-btn"
          onClick={() => setAdding(true)}
        >
          <Plus size={14} /> New engagement
        </button>
      ) : (
        <div className="tw-addform" data-testid="add-engagement-form">
          <label>
            Engagement name
            <input
              ref={nameRef}
              id="engagement-name-input"
              autoFocus
              className="tw-input"
              value={name}
              data-testid="engagement-name-input"
              onChange={(event) => setName(event.target.value)}
              aria-invalid={!!error && !name.trim()}
              aria-describedby={error && !name.trim() ? "engagement-name-error" : undefined}
            />
          </label>
          <label>
            Customer <span className="tw-optional">optional</span>
            <input
              className="tw-input"
              value={customer}
              data-testid="engagement-customer-input"
              onChange={(event) => setCustomer(event.target.value)}
            />
          </label>
          <label>
            Description <span className="tw-optional">optional</span>
            <input
              className="tw-input"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <div className="tw-form-actions">
            <button
              type="button"
              className="tw-btn"
              data-testid="engagement-save-btn"
              disabled={busy}
              onClick={() => void create()}
            >
              Create
            </button>
            <button
              type="button"
              className="tw-btn-ghost"
              onClick={() => setAdding(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && (
        <p id="engagement-name-error" className="tw-error" data-testid="engagement-error" role="alert">
          {error}
        </p>
      )}

      {engagements.length === 0 ? (
        <section className="tw-section">
          <div className="tw-empty-card" data-testid="engagement-empty">
            <FolderKanban size={24} />
            <div>
              <strong>Your Engagement portfolio is empty.</strong>
              <p>
                Create an Engagement to keep customer status, delivery work,
                people, and durable artifacts together. You can also ask the
                assistant to create one.
              </p>
            </div>
          </div>
        </section>
      ) : (
        <section className="tw-section">
          <div className="tw-doclist tw-engagement-portfolio">
            {engagements.map((engagement) => (
              <EngagementPortfolioRow
                key={engagement.id}
                engagement={engagement}
                userId={appState.user?.id}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// Portfolio row per the design reference's `pf-row`: status dot, name + customer
// inline, a one-line "why", and quiet metadata on the right.
export function EngagementPortfolioRow({
  engagement,
  onNavigate,
}: {
  engagement: Engagement;
  userId?: string;
  onNavigate: (route: string) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const overdueCount = (engagement.tasks ?? []).filter((task) => isOverdue(task, today)).length;
  const right = [
    overdueCount ? `${overdueCount} overdue` : "",
    `${openTasks(engagement)} open`,
    engagement.targetDate ? `target ${engagement.targetDate}` : "",
  ].filter(Boolean);
  return (
    <button
      type="button"
      className="tw-pf-row"
      data-testid={`engagement-row-${engagement.id}`}
      onClick={() => onNavigate(`/engagements/${engagement.id}`)}
    >
      <span
        className={`tw-dot tw-dot-${engagement.status}`}
        data-testid={`engagement-status-${engagement.id}`}
        aria-label={statusLabel[engagement.status]}
      />
      <span style={{ minWidth: 0, display: "block" }}>
        <span className="tw-pf-name tw-td-title">{engagement.name}</span>
        {engagement.customer && <span className="tw-pf-cust">{engagement.customer}</span>}
        <span className="tw-pf-why">
          {engagement.status !== "green" && engagement.statusNote
            ? engagement.statusNote
            : engagement.description || "No description"}
        </span>
      </span>
      <span className="tw-pf-right">
        {overdueCount > 0 && <span className="tw-alert">{right[0]}</span>}
        {(overdueCount > 0 ? right.slice(1) : right).map((part, index) => (
          <span key={part}>{(index > 0 || overdueCount > 0) ? " · " : ""}{part}</span>
        ))}
      </span>
    </button>
  );
}

export function EngagementScreen({
  appState,
  viewRoute,
  onNavigate,
  onRefresh,
}: {
  appState: AppState;
  viewRoute: string;
  onNavigate: (route: string) => void;
  onRefresh: () => Promise<void>;
}) {
  const route = parseEngagementRoute(viewRoute);
  if (!route)
    return (
      <div className="tw-empty">
        Engagement not found (or you are not a member).
      </div>
    );

  const { id, sub, recordId } = route;
  const engagement = (appState.engagements ?? []).find(
    (candidate) => candidate.id === id,
  );
  if (!engagement)
    return (
      <div className="tw-empty">
        Engagement not found (or you are not a member).
      </div>
    );

  const role = roleOf(engagement, appState.user?.id);
  const editable = canEdit(role);
  const base = `/engagements/${engagement.id}`;
  const today = new Date().toISOString().slice(0, 10);
  const header = (
    <EngagementHeader
      engagement={engagement}
      role={role}
      sub={sub}
      base={base}
      editable={editable}
      onNavigate={onNavigate}
    />
  );

  if (sub === "tasks" && recordId) {
    const task = engagement.tasks.find(
      (candidate) => candidate.id === recordId,
    );
    return (
      <div className="tw-screen" data-testid="engagement-task-detail">
        {header}
        {task ? (
          <EngagementTaskDetail
            engagement={engagement}
            task={task}
            editable={editable}
            onRefresh={onRefresh}
            onNavigate={onNavigate}
          />
        ) : (
          <div className="tw-empty">Task not found.</div>
        )}
      </div>
    );
  }
  if (sub === "tasks")
    return (
      <div className="tw-screen" data-testid="engagement-tasks-screen">
        {header}
        <EngagementTasks
          engagement={engagement}
          editable={editable}
          today={today}
          onNavigate={onNavigate}
          onRefresh={onRefresh}
        />
      </div>
    );
  if (sub === "artifacts")
    return (
      <div className="tw-screen" data-testid="engagement-artifacts-screen">
        {header}
        <EngagementArtifacts
          engagement={engagement}
          editable={editable}
          onRefresh={onRefresh}
        />
      </div>
    );
  if (sub === "timeline")
    return (
      <div className="tw-screen" data-testid="engagement-timeline-screen">
        {header}
        <EngagementTimeline
          engagement={engagement}
          editable={editable}
          onRefresh={onRefresh}
        />
      </div>
    );
  if (sub === "settings")
    return (
      <div className="tw-screen" data-testid="engagement-settings-screen">
        {header}
        <EngagementSettings
          engagement={engagement}
          myRole={role}
          onRefresh={onRefresh}
        />
      </div>
    );

  const editorKey = JSON.stringify([
    engagement.id,
    engagement.name,
    engagement.description,
    engagement.customer,
    engagement.startDate,
    engagement.targetDate,
    engagement.status,
    engagement.statusNote,
    engagement.businessValue,
    engagement.value,
    engagement.currentState,
  ]);
  return (
    <div className="tw-screen" data-testid="engagement-overview">
      {header}
      <RecordOverview
        engagement={engagement}
        editable={editable}
        today={today}
        onNavigate={onNavigate}
        onRefresh={onRefresh}
      />
      {editable && (
        <EditableRecordSection
          editorKey={editorKey}
          engagement={engagement}
          role={role}
          onRefresh={onRefresh}
        />
      )}
    </div>
  );
}

// The record editor stays reachable but no longer leads the page: the Overview
// is a reading surface first, per the design reference.
function EditableRecordSection({ editorKey, engagement, role, onRefresh }: {
  editorKey: string;
  engagement: Engagement;
  role: EngagementRole | null;
  onRefresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="tw-section">
      <button
        type="button"
        className="tw-btn-ghost"
        data-testid="engagement-edit-record"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? "Close the record editor" : "Edit record"}
      </button>
      {open && (
        <EngagementDetailEditor
          key={editorKey}
          engagement={engagement}
          role={role}
          onRefresh={onRefresh}
        />
      )}
    </section>
  );
}

function EngagementHeader({
  engagement,
  role,
  sub,
  base,
  editable,
  onNavigate,
}: {
  engagement: Engagement;
  role: EngagementRole | null;
  sub: string;
  base: string;
  editable: boolean;
  onNavigate: (route: string) => void;
}) {
  const timelineCount = (engagement.timeline ?? []).length;
  const openCount = openTasks(engagement);
  const docsCount = (engagement.library ?? []).length;
  const tabs: [string, string, number | null][] = [
    ["", "Overview", null],
    ["timeline", "Timeline", timelineCount],
    ["tasks", "Tasks", openCount],
    ["artifacts", "Docs", docsCount],
    ["settings", "Team & conventions", null],
  ];
  return (
    <>
      <button
        type="button"
        className="tw-back"
        onClick={() => onNavigate("/engagements")}
      >
        <ArrowLeft size={14} /> All engagements
      </button>
      <h1 className="tw-h1">{engagement.name}</h1>
      <div className="tw-engagement-header">
        {engagement.customer && (
          <span className="tw-td-sub">{engagement.customer}</span>
        )}
        <span className="tw-status-word" data-testid="engagement-status-badge">
          <span className={`tw-dot tw-dot-${engagement.status}`} />
          {statusLabel[engagement.status]}
        </span>
        {(engagement.value ?? 0) > 0 && (
          <span className="tw-count">{money(engagement.value ?? 0)}</span>
        )}
        <span className="tw-badge tw-badge-gray" data-testid="my-role">
          {role ?? "viewer"}
        </span>
        {engagement.targetDate && (
          <span className="tw-td-sub">Target {engagement.targetDate}</span>
        )}
      </div>
      {engagement.status !== "green" && engagement.statusNote && (
        <p className="tw-subtle" data-testid="engagement-status-note">
          Why: {engagement.statusNote}
        </p>
      )}
      {!editable && (
        <p className="tw-role-note" data-testid="viewer-note">
          View-only: your role lets you review this Engagement but not change
          its delivery record, team, tasks, conventions, or artifacts.
        </p>
      )}
      <Tabs className="tw-tabs" data-testid="engagement-tabs" aria-label="Engagement sections">
        {tabs.map(([tab, label, count]) => (
          <Tab
            key={tab}
            active={sub === tab}
            className={`tw-tab ${sub === tab ? "tw-tab-active" : ""}`}
            data-testid={`engagement-tab-${tab || "overview"}`}
            onClick={() => onNavigate(tab ? `${base}/${tab}` : base)}
          >
            {label}
            {count !== null && count > 0 && <span className="tw-tab-n">{count}</span>}
          </Tab>
        ))}
      </Tabs>
    </>
  );
}

function money(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${Math.round(value)}`;
}

function TimelineEntryRow({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="tw-entry">
      <span className={`tw-mark tw-mark-${entry.type}`} />
      <div style={{ minWidth: 0 }}>
        <div className="tw-e-top">
          <span className="tw-e-title">{entry.title}</span>
          <span className={`tw-e-type tw-e-type-${entry.type}`}>{entry.type}</span>
          <span className="tw-e-date">{entry.date}</span>
        </div>
        {entry.body && <div className="tw-e-body">{entry.body}</div>}
        <div className="tw-e-byline">
          {entry.author}
          {entry.source ? ` · from ${entry.source}` : ""}
        </div>
      </div>
    </div>
  );
}

// A rail section with an inline "+ Add" affordance, per the reference's overview rail.
function RailSection({ label, addLabel, adding, onToggleAdd, editable, children, form }: {
  label: string;
  addLabel?: string;
  adding?: boolean;
  onToggleAdd?: () => void;
  editable: boolean;
  children: React.ReactNode;
  form?: React.ReactNode;
}) {
  return (
    <section className="tw-rail-section">
      <div className="tw-rail-head">
        <span className="tw-microcap" style={{ marginBottom: 0 }}>{label}</span>
        {editable && onToggleAdd && (
          <button type="button" className="tw-rail-add" onClick={onToggleAdd}>
            {adding ? "Cancel" : addLabel ?? "+ Add"}
          </button>
        )}
      </div>
      {children}
      {adding && form}
    </section>
  );
}

// The Overview reading surface: what this is, where it stands, needs attention,
// recent log — with objectives, key dates, and people in the rail.
function RecordOverview({ engagement, editable, today, onNavigate, onRefresh }: {
  engagement: Engagement;
  editable: boolean;
  today: string;
  onNavigate: (route: string) => void;
  onRefresh: () => Promise<void>;
}) {
  const { busy, error, run } = useBusy(onRefresh);
  const [addObj, setAddObj] = useState(false);
  const [objDraft, setObjDraft] = useState("");
  const [addKd, setAddKd] = useState(false);
  const [kdDate, setKdDate] = useState("");
  const [kdLabel, setKdLabel] = useState("");
  const [addPerson, setAddPerson] = useState(false);
  const [personName, setPersonName] = useState("");
  const [personRole, setPersonRole] = useState("");

  const objectives = engagement.objectives ?? [];
  const keyDates = engagement.keyDates ?? [];
  const contacts = engagement.contacts ?? [];
  const timeline = engagement.timeline ?? [];
  const overdueTasks = engagement.tasks.filter((task) => isOverdue(task, today));
  const nextKeyDate = keyDates.find((kd) => !kd.done && kd.date >= today);

  const submitObjective = async () => {
    const text = objDraft.trim();
    if (!text) return;
    if (await run(() => addObjective(engagement.id, text))) { setObjDraft(""); setAddObj(false); }
  };
  const submitKeyDate = async () => {
    if (!kdDate || !kdLabel.trim()) return;
    if (await run(() => addKeyDate(engagement.id, kdDate, kdLabel.trim()))) {
      setKdDate(""); setKdLabel(""); setAddKd(false);
    }
  };
  const submitContact = async () => {
    const name = personName.trim();
    if (!name) return;
    if (await run(() => addEngagementContact(engagement.id, name, personRole.trim()))) {
      setPersonName(""); setPersonRole(""); setAddPerson(false);
    }
  };

  return (
    <div className="tw-ebody">
      <div style={{ minWidth: 0 }}>
        <section style={{ marginBottom: 22 }}>
          <div className="tw-microcap">What this is</div>
          <p className="tw-prose">{engagement.description || "No description yet."}</p>
          {engagement.businessValue && (
            <p className="tw-prose tw-prose-muted">{engagement.businessValue}</p>
          )}
        </section>
        <section style={{ marginBottom: 22 }}>
          <div className="tw-microcap">
            Where it stands{engagement.stateDate ? ` · ${engagement.stateDate}` : ""}
          </div>
          <p className="tw-prose tw-prose-lead" data-testid="engagement-current-state">
            {engagement.currentState ||
              "No standing summary yet — set one in the record editor, or ask the assistant to draft it after your next call."}
          </p>
        </section>
        {(overdueTasks.length > 0 || nextKeyDate) && (
          <section style={{ marginBottom: 22 }}>
            <div className="tw-microcap">Needs attention</div>
            {overdueTasks.map((task) => (
              <div className="tw-attn" key={task.id}>
                <span className="tw-dot tw-dot-red" style={{ width: 7, height: 7 }} />
                <span style={{ minWidth: 0 }}>Overdue: {task.title}</span>
                <span className="tw-e-date">due {task.dueDate?.slice(0, 10)}</span>
              </div>
            ))}
            {nextKeyDate && (
              <div className="tw-attn">
                <span className="tw-dot tw-dot-yellow" style={{ width: 7, height: 7 }} />
                <span style={{ minWidth: 0 }}>{nextKeyDate.label}</span>
                <span className="tw-e-date">{nextKeyDate.date}</span>
              </div>
            )}
          </section>
        )}
        <section>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <div className="tw-microcap">Recent activity</div>
            <button
              type="button"
              className="tw-btn-ghost"
              style={{ minHeight: 0, padding: "2px 6px" }}
              data-testid="overview-full-timeline"
              onClick={() => onNavigate(`/engagements/${engagement.id}/timeline`)}
            >
              Full timeline →
            </button>
          </div>
          {timeline.length === 0 ? (
            <div className="tw-empty-sm">
              Nothing logged yet — drop a transcript on the assistant or log a note on the Timeline tab.
            </div>
          ) : (
            timeline.slice(0, 3).map((entry) => <TimelineEntryRow key={entry.id} entry={entry} />)
          )}
        </section>
        {error && <p className="tw-error" role="alert">{error}</p>}
      </div>

      <div className="tw-rail">
        <RailSection
          label="Objectives" editable={editable} adding={addObj}
          onToggleAdd={() => { setAddObj(!addObj); setObjDraft(""); }}
          form={
            <input
              className="tw-input" placeholder="What does good look like?" autoFocus
              value={objDraft} disabled={busy} data-testid="objective-input"
              onChange={(event) => setObjDraft(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") void submitObjective(); }}
            />
          }
        >
          {objectives.length === 0 && !addObj && <div className="tw-empty-sm">None yet.</div>}
          {objectives.map((objective) => (
            <div className="tw-obj" key={objective}>{objective}</div>
          ))}
        </RailSection>

        <RailSection
          label="Key dates" editable={editable} adding={addKd}
          onToggleAdd={() => { setAddKd(!addKd); setKdDate(""); setKdLabel(""); }}
          form={
            <div style={{ display: "grid", gap: 6 }}>
              <input
                type="date" className="tw-input" value={kdDate} disabled={busy}
                data-testid="key-date-date" onChange={(event) => setKdDate(event.target.value)}
              />
              <input
                className="tw-input" placeholder="Milestone" value={kdLabel} disabled={busy}
                data-testid="key-date-label"
                onChange={(event) => setKdLabel(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter") void submitKeyDate(); }}
              />
            </div>
          }
        >
          {keyDates.length === 0 && !addKd && <div className="tw-empty-sm">None yet.</div>}
          {keyDates.map((kd) => (
            <button
              key={`${kd.date}-${kd.label}`}
              type="button"
              className={`tw-kd ${kd.done ? "tw-kd-done" : nextKeyDate === kd ? "tw-kd-next" : ""}`}
              title={editable ? (kd.done ? "Reopen" : "Mark done") : undefined}
              disabled={!editable || busy}
              onClick={() => void run(() => toggleKeyDate(engagement.id, kd.label))}
            >
              <span className="tw-kd-date">{kd.date.slice(5)}</span>
              <span className="tw-kd-t">{kd.label}</span>
            </button>
          ))}
        </RailSection>

        <RailSection
          label="Customer" editable={editable} adding={addPerson}
          onToggleAdd={() => { setAddPerson(!addPerson); setPersonName(""); setPersonRole(""); }}
          form={
            <div style={{ display: "grid", gap: 6 }}>
              <input
                className="tw-input" placeholder="Name" value={personName} disabled={busy}
                data-testid="contact-name" onChange={(event) => setPersonName(event.target.value)}
              />
              <input
                className="tw-input" placeholder="Their role, e.g. Digital sponsor"
                value={personRole} disabled={busy} data-testid="contact-role"
                onChange={(event) => setPersonRole(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter") void submitContact(); }}
              />
            </div>
          }
        >
          {contacts.length === 0 && !addPerson && (
            <div className="tw-empty-sm">No customer contacts yet.</div>
          )}
          {contacts.map((contact) => (
            <div className="tw-contact" key={contact.name}>
              <span className="tw-avatar" style={{ width: 24, height: 24, fontSize: 10 }}>
                {contact.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}
              </span>
              <span style={{ minWidth: 0 }}>
                <span className="tw-c-n">{contact.name}</span>
                <span className="tw-c-r">{contact.role}</span>
              </span>
            </div>
          ))}
        </RailSection>

        <RailSection label="Our team" editable={false}>
          {engagement.members.map((member) => (
            <div className="tw-contact" key={member.userId}>
              <span className="tw-avatar" style={{ width: 24, height: 24, fontSize: 10 }}>
                {member.userId.slice(0, 2).toUpperCase()}
              </span>
              <span style={{ minWidth: 0 }}>
                <span className="tw-c-n">{member.userId}</span>
                <span className="tw-c-r">{member.role}</span>
              </span>
            </div>
          ))}
        </RailSection>
      </div>
    </div>
  );
}

// The Timeline tab: the record's append-only log, grouped by month, with the
// note composer at the top.
function EngagementTimeline({ engagement, editable, onRefresh }: {
  engagement: Engagement;
  editable: boolean;
  onRefresh: () => Promise<void>;
}) {
  const { busy, error, run } = useBusy(onRefresh);
  const [draft, setDraft] = useState("");
  const [entryType, setEntryType] = useState<TimelineEntryType>("note");
  const timeline = engagement.timeline ?? [];

  const submit = async () => {
    const title = draft.trim();
    if (!title) return;
    if (await run(() => addTimelineEntry(engagement.id, { type: entryType, title }))) setDraft("");
  };

  const months: { month: string; entries: TimelineEntry[] }[] = [];
  const monthOf = (iso: string) => {
    const [year, month] = iso.split("-").map(Number);
    return `${["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][month - 1]} ${year}`;
  };
  for (const entry of timeline) {
    const month = monthOf(entry.date);
    const group = months.find((candidate) => candidate.month === month);
    if (group) group.entries.push(entry);
    else months.push({ month, entries: [entry] });
  }

  return (
    <div style={{ maxWidth: "42rem" }}>
      {editable && (
        <div style={{ display: "flex", gap: 7, marginBottom: 14 }}>
          <select
            className="tw-input" style={{ width: "7.5rem", flex: "none" }}
            value={entryType} disabled={busy} aria-label="Entry type"
            data-testid="timeline-type"
            onChange={(event) => setEntryType(event.target.value as TimelineEntryType)}
          >
            <option value="note">Note</option>
            <option value="decision">Decision</option>
            <option value="risk">Risk</option>
            <option value="meeting">Meeting</option>
          </select>
          <input
            className="tw-input" placeholder="Log a note, decision or risk…"
            value={draft} disabled={busy} data-testid="timeline-input"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Enter") void submit(); }}
          />
          <button
            type="button" className="tw-btn-ghost" style={{ flexShrink: 0 }}
            disabled={busy || !draft.trim()} data-testid="timeline-add"
            onClick={() => void submit()}
          >
            Add
          </button>
        </div>
      )}
      {error && <p className="tw-error" role="alert">{error}</p>}
      {timeline.length === 0 ? (
        <div className="tw-empty-sm">
          Nothing logged yet. Entries are append-only and attributed — the record&apos;s memory.
        </div>
      ) : (
        months.map((group) => (
          <div key={group.month} style={{ marginBottom: 20 }}>
            <div className="tw-microcap">{group.month}</div>
            {group.entries.map((entry) => <TimelineEntryRow key={entry.id} entry={entry} />)}
          </div>
        ))
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  testid,
}: {
  label: string;
  value: number | string;
  testid?: string;
}) {
  return (
    <div className="tw-stat" data-testid={testid}>
      <div className="tw-stat-value">{value}</div>
      <div className="tw-stat-label">{label}</div>
    </div>
  );
}

function EngagementDetailEditor({
  engagement,
  role,
  onRefresh,
}: {
  engagement: Engagement;
  role: EngagementRole | null;
  onRefresh: () => Promise<void>;
}) {
  const editable = canEdit(role);
  const owner = role === "owner";
  const { busy, error, run } = useBusy(onRefresh);
  const reasonRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(engagement.name);
  const [description, setDescription] = useState(engagement.description);
  const [customer, setCustomer] = useState(engagement.customer);
  const [startDate, setStartDate] = useState(engagement.startDate);
  const [targetDate, setTargetDate] = useState(engagement.targetDate);
  const [status, setStatus] = useState<EngagementStatus>(engagement.status);
  const [statusNote, setStatusNote] = useState(engagement.statusNote);
  const [statusError, setStatusError] = useState("");
  const [businessValue, setBusinessValue] = useState(engagement.businessValue ?? "");
  const [value, setValue] = useState(String(engagement.value || ""));
  const [currentState, setCurrentState] = useState(engagement.currentState ?? "");
  if (!editable)
    return (
      <section className="tw-section">
        <h2 className="tw-h2">Delivery record</h2>
        <p className="tw-subtle">
          {engagement.description || "No description provided."}
        </p>
      </section>
    );
  const save = async () => {
    if ((status === "yellow" || status === "red") && !statusNote.trim()) {
      setStatusError(
        `${statusLabel[status]} needs a reason before it can be saved.`,
      );
      requestAnimationFrame(() => reasonRef.current?.focus());
      return;
    }
    setStatusError("");
    await run(() =>
      updateEngagement(engagement.id, {
        ...(owner && name.trim() !== engagement.name
          ? { name: name.trim() }
          : {}),
        description: description.trim(),
        customer: customer.trim(),
        startDate,
        targetDate,
        status,
        statusNote: status === "green" ? "" : statusNote.trim(),
        businessValue: businessValue.trim(),
        value: Number(value.replace(/[^0-9.]/g, "")) || 0,
        currentState: currentState.trim(),
      }),
    );
  };
  return (
    <section className="tw-section" data-testid="engagement-detail-editor">
      <h2 className="tw-h2">Delivery record</h2>
      <div className="tw-edit-grid">
        {owner && (
          <label>
            Engagement name
            <input
              className="tw-input"
              value={name}
              data-testid="engagement-name-edit"
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
        )}
        <label>
          Description
          <textarea
            className="tw-input"
            value={description}
            data-testid="engagement-description-edit"
            disabled={busy}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <label>
          Customer
          <input
            className="tw-input"
            value={customer}
            data-testid="engagement-customer-edit"
            disabled={busy}
            onChange={(event) => setCustomer(event.target.value)}
          />
        </label>
        <label>
          Why it matters to the customer
          <input
            className="tw-input"
            value={businessValue}
            data-testid="engagement-business-value-edit"
            placeholder="The outcome behind the work"
            disabled={busy}
            onChange={(event) => setBusinessValue(event.target.value)}
          />
        </label>
        <label>
          Value (USD)
          <input
            className="tw-input"
            inputMode="numeric"
            value={value}
            data-testid="engagement-value-edit"
            placeholder="150000"
            disabled={busy}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <label>
          Where it stands
          <textarea
            className="tw-input"
            value={currentState}
            data-testid="engagement-current-state-edit"
            placeholder="The paragraph a stand-in could read to take over"
            disabled={busy}
            onChange={(event) => setCurrentState(event.target.value)}
          />
        </label>
        <label>
          Start date
          <input
            type="date"
            className="tw-input"
            value={startDate}
            disabled={busy}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label>
          Target date
          <input
            type="date"
            className="tw-input"
            value={targetDate}
            data-testid="engagement-target-edit"
            disabled={busy}
            onChange={(event) => setTargetDate(event.target.value)}
          />
        </label>
        <label>
          Status
          <select
            className="tw-input"
            value={status}
            data-testid="status-select"
            disabled={busy}
            onChange={(event) => {
              const next = event.target.value as EngagementStatus;
              setStatus(next);
              if (next === "green") {
                setStatusNote("");
                setStatusError("");
              } else requestAnimationFrame(() => reasonRef.current?.focus());
            }}
          >
            <option value="green">Green</option>
            <option value="yellow">Yellow</option>
            <option value="red">Red</option>
          </select>
        </label>
        {status !== "green" && (
          <label>
            Reason <span className="tw-required">required</span>
            <input
              ref={reasonRef}
              className="tw-input"
              value={statusNote}
              data-testid="status-note-input"
              aria-invalid={!!statusError}
              aria-describedby={statusError ? "status-note-error" : undefined}
              disabled={busy}
              onChange={(event) => {
                setStatusNote(event.target.value);
                setStatusError("");
              }}
            />
          </label>
        )}
      </div>
      {statusError && (
        <p id="status-note-error" className="tw-error" role="alert">
          {statusError}
        </p>
      )}
      {error && (
        <p className="tw-error" data-testid="detail-error" role="alert">
          {error}
        </p>
      )}
      <div className="tw-form-actions">
        <button
          type="button"
          className="tw-btn"
          disabled={busy || (owner && !name.trim())}
          onClick={() => void save()}
        >
          {busy ? "Saving…" : "Save delivery record"}
        </button>
      </div>
    </section>
  );
}

function EngagementTasks({
  engagement,
  editable,
  today,
  onNavigate,
  onRefresh,
}: {
  engagement: Engagement;
  editable: boolean;
  today: string;
  onNavigate: (route: string) => void;
  onRefresh: () => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [titleError, setTitleError] = useState("");
  const [dueDate, setDueDate] = useState("");
  const titleRef = useRef<HTMLInputElement>(null);
  const { busy, error, run } = useBusy(onRefresh);
  const create = async () => {
    if (!title.trim()) {
      setTitleError("Enter a task title.");
      requestAnimationFrame(() => titleRef.current?.focus());
      return;
    }
    setTitleError("");
    const saved = await run(() =>
      createEngagementTask(engagement.id, { title: title.trim(), dueDate }),
    );
    if (!saved) return;
    setAdding(false);
    setTitle("");
    setDueDate("");
  };
  return (
    <section className="tw-section">
      <div className="tw-section-heading">
        <h2 className="tw-h2">Tasks</h2>
        {editable && !adding && (
          <button
            type="button"
            className="tw-btn"
            data-testid="engagement-add-task-btn"
            onClick={() => setAdding(true)}
          >
            <Plus size={14} /> Add task
          </button>
        )}
      </div>
      {editable && adding && (
        <div className="tw-addform" data-testid="engagement-add-task-form">
          <label>
            Task title
            <input
              ref={titleRef}
              autoFocus
              className="tw-input"
              value={title}
              data-testid="engagement-task-title-input"
              aria-invalid={!!titleError}
              aria-describedby={titleError ? "engagement-task-title-error" : undefined}
              onChange={(event) => {
                setTitle(event.target.value);
                setTitleError("");
              }}
            />
          </label>
          <label>
            Due date
            <input
              type="date"
              className="tw-input"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
            />
          </label>
          <div className="tw-form-actions">
            <button
              type="button"
              className="tw-btn"
              data-testid="engagement-task-save-btn"
              disabled={busy}
              onClick={() => void create()}
            >
              Save
            </button>
            <button
              type="button"
              className="tw-btn-ghost"
              onClick={() => {
                setAdding(false);
                setTitleError("");
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {titleError && (
        <p id="engagement-task-title-error" className="tw-error" data-testid="engagement-task-title-error" role="alert">
          {titleError}
        </p>
      )}
      {error && (
        <p className="tw-error" role="alert">
          {error}
        </p>
      )}
      {!engagement.tasks.length ? (
        <div className="tw-empty-sm">No tasks in this Engagement yet.</div>
      ) : (
        <div className="tw-task-list" data-testid="engagement-tasks-table">
          {engagement.tasks.map((task) => (
            <div
              key={task.id}
              className="tw-task-row"
              data-testid={`engagement-task-row-${task.id}`}
            >
              <button
                type="button"
                className="tw-task-open"
                onClick={() =>
                  onNavigate(`/engagements/${engagement.id}/tasks/${task.id}`)
                }
              >
                <span className="tw-td-title">{task.title}</span>
                <span
                  className={`tw-badge ${task.status === "Done" ? "tw-badge-green" : task.status === "Blocked" ? "tw-badge-red" : "tw-badge-gray"}`}
                >
                  {task.status}
                </span>
                <span className="tw-td-sub">
                  {task.dueDate || "No due date"}
                  {isOverdue(task, today) ? " · overdue" : ""}
                </span>
              </button>
              {editable && (
                <ArmedDelete
                  testid={`engagement-task-delete-${task.id}`}
                  onConfirm={() =>
                    void run(() => deleteEngagementTask(engagement.id, task.id))
                  }
                />
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EngagementTaskDetail({
  engagement,
  task,
  editable,
  onRefresh,
  onNavigate,
}: {
  engagement: Engagement;
  task: Task;
  editable: boolean;
  onRefresh: () => Promise<void>;
  onNavigate: (route: string) => void;
}) {
  const { busy, error, run } = useBusy(onRefresh);
  return (
    <section className="tw-section" data-testid="engagement-task-editor">
      <button
        type="button"
        className="tw-back"
        onClick={() => onNavigate(`/engagements/${engagement.id}/tasks`)}
      >
        <ArrowLeft size={14} /> All tasks
      </button>
      <h2 className="tw-h2">{task.title}</h2>
      {editable ? (
        <div className="tw-addform">
          <label>
            Status
            <select
              className="tw-input"
              value={task.status}
              data-testid="engagement-task-status"
              disabled={busy}
              onChange={(event) =>
                void run(() =>
                  updateEngagementTask(engagement.id, task.id, {
                    status: event.target.value,
                  }),
                )
              }
            >
              {["To do", "In progress", "Blocked", "Done"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Priority
            <select
              className="tw-input"
              value={task.priority}
              data-testid="engagement-task-priority"
              disabled={busy}
              onChange={(event) =>
                void run(() =>
                  updateEngagementTask(engagement.id, task.id, {
                    priority: event.target.value,
                  }),
                )
              }
            >
              {["Low", "Medium", "High"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Due date
            <input
              type="date"
              className="tw-input"
              value={(task.dueDate || "").slice(0, 10)}
              disabled={busy}
              onChange={(event) =>
                void run(() =>
                  updateEngagementTask(engagement.id, task.id, {
                    dueDate: event.target.value,
                  }),
                )
              }
            />
          </label>
        </div>
      ) : (
        <p className="tw-subtle">View-only task details.</p>
      )}
      {error && (
        <p className="tw-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function EngagementSettings({
  engagement,
  myRole,
  onRefresh,
}: {
  engagement: Engagement;
  myRole: EngagementRole | null;
  onRefresh: () => Promise<void>;
}) {
  const owner = myRole === "owner";
  const editable = canEdit(myRole);
  const [directory, setDirectory] = useState<
    { id: string; username: string; displayName: string }[]
  >([]);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<EngagementRole>("viewer");
  const [convention, setConvention] = useState("");
  const { busy, error, run } = useBusy(onRefresh);
  useEffect(() => {
    void listUsers()
      .then(setDirectory)
      .catch(() => setDirectory([]));
  }, []);
  const displayUser = (id: string) => {
    const user = directory.find((candidate) => candidate.id === id);
    return user?.displayName || user?.username || id;
  };
  const candidates = directory.filter(
    (user) => !engagement.members.some((member) => member.userId === user.id),
  );
  return (
    <>
      <section className="tw-section">
        <h2 className="tw-h2">
          <Users size={14} /> Members
        </h2>
        <div className="tw-doclist" data-testid="member-list">
          {engagement.members.map((member) => (
            <div
              key={member.userId}
              className="tw-docitem tw-member-row"
              data-testid={`member-${member.userId}`}
            >
              <span>
                <span className="tw-td-title">
                  {displayUser(member.userId)}
                </span>
                <span className="tw-td-sub tw-stable-id">{member.userId}</span>
              </span>
              <span className="tw-badge tw-badge-gray">{member.role}</span>
              {owner && <OwnerMemberControls key={`${member.userId}-${member.role}`} engagementId={engagement.id} member={member} busy={busy} run={run} />}
            </div>
          ))}
        </div>
        {owner && (
          <div className="tw-addform" data-testid="add-member-form">
            <label>
              Add member
              <select
                className="tw-input"
                value={userId}
                data-testid="member-user-select"
                onChange={(event) => setUserId(event.target.value)}
              >
                <option value="">Choose a user…</option>
                {candidates.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.displayName || user.username} (
                    {user.username || user.id})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Role
              <select
                className="tw-input"
                value={role}
                data-testid="member-role-select"
                onChange={(event) =>
                  setRole(event.target.value as EngagementRole)
                }
              >
                {(["viewer", "editor", "owner"] as const).map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <div className="tw-form-actions">
              <button
                type="button"
                className="tw-btn"
                data-testid="member-add-btn"
                disabled={busy || !userId}
                onClick={() =>
                  void run(async () => {
                    await addEngagementMember(engagement.id, userId, role);
                    setUserId("");
                  })
                }
              >
                Add member
              </button>
            </div>
          </div>
        )}
      </section>
      <section className="tw-section">
        <h2 className="tw-h2">
          <SettingsIcon size={14} /> Conventions
        </h2>
        <div className="tw-doclist">
          {engagement.conventions.map((item) => (
            <div
              key={item.id}
              className="tw-docitem"
              data-testid={`convention-row-${item.id}`}
            >
              <span className="tw-td-sub">{item.text}</span>
              {editable && (
                <ArmedDelete
                  testid={`convention-delete-${item.id}`}
                  onConfirm={() =>
                    void run(() => removeConvention(engagement.id, item.id))
                  }
                />
              )}
            </div>
          ))}
        </div>
        {editable && (
          <div className="tw-addform">
            <label>
              Working agreement
              <input
                className="tw-input"
                value={convention}
                data-testid="convention-input"
                onChange={(event) => setConvention(event.target.value)}
              />
            </label>
            <div className="tw-form-actions">
              <button
                type="button"
                className="tw-btn"
                data-testid="convention-add-btn"
                disabled={busy || !convention.trim()}
                onClick={() =>
                  void run(async () => {
                    await addConvention(engagement.id, convention.trim());
                    setConvention("");
                  })
                }
              >
                Add convention
              </button>
            </div>
          </div>
        )}
      </section>
      {error && (
        <p className="tw-error" data-testid="settings-error" role="alert">
          {error}
        </p>
      )}
    </>
  );
}

function OwnerMemberControls({ engagementId, member, busy, run }: { engagementId: string; member: Engagement["members"][number]; busy: boolean; run: (action: () => Promise<unknown>) => Promise<boolean> }) {
  const [role, setRole] = useState<EngagementRole>(member.role);
  return (
    <span className="tw-member-actions">
      <label className="tw-visually-hidden" htmlFor={`member-role-${member.userId}`}>Role for {member.userId}</label>
      <select id={`member-role-${member.userId}`} className="tw-input" aria-label={`Role for ${member.userId}`} value={role} disabled={busy} onChange={(event) => setRole(event.target.value as EngagementRole)}>
        {(["viewer", "editor", "owner"] as const).map((value) => <option key={value}>{value}</option>)}
      </select>
      <button type="button" className="tw-btn-ghost" disabled={busy || role === member.role} onClick={() => void run(() => addEngagementMember(engagementId, member.userId, role))}>Update role</button>
      <ArmedDelete testid={`member-remove-${member.userId}`} onConfirm={() => void run(() => removeEngagementMember(engagementId, member.userId))} />
    </span>
  );
}

function EngagementArtifacts({
  engagement,
  editable,
  onRefresh,
}: {
  engagement: Engagement;
  editable: boolean;
  onRefresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const artifacts: Artifact[] = engagement.library ?? [];
  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await uploadEngagementArtifact(engagement.id, file);
      await onRefresh();
    } catch (err) {
      setError(friendlyError(err, "Artifact action failed."));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };
  const download = async (artifact: Artifact) => {
    setError("");
    try {
      const blob = await downloadEngagementArtifact(engagement.id, artifact.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = artifact.name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (err) {
      setError(friendlyError(err, "Unable to download artifact."));
    }
  };
  const remove = async (artifact: Artifact) => {
    setError("");
    try {
      await deleteEngagementArtifact(engagement.id, artifact.id);
      await onRefresh();
    } catch (err) {
      setError(friendlyError(err, "Artifact action failed."));
    }
  };
  return (
    <section className="tw-section">
      <div className="tw-section-heading">
        <h2 className="tw-h2">Documents</h2>
        {editable && (
          <>
            <input
              ref={fileInput}
              type="file"
              data-testid="artifact-upload-input"
              className="tw-visually-hidden"
              onChange={(event) => void upload(event.target.files?.[0])}
            />
            <button
              type="button"
              className="tw-btn"
              data-testid="artifact-upload-btn"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
            >
              <Upload size={13} /> {busy ? "Uploading…" : "Upload"}
            </button>
          </>
        )}
      </div>
      {error && (
        <div className="tw-error" data-testid="artifact-error" role="alert">
          {error}
        </div>
      )}
      {!artifacts.length ? (
        <div className="tw-empty-sm">No documents on this Engagement yet.</div>
      ) : (
        (
          [
            ["bronze", "Bronze", "Raw sources — uploads, never edited"],
            ["silver", "Silver", "Working documents"],
            ["gold", "Gold", "Curated and vetted — safe to share or hand over"],
          ] as const
        ).map(([tier, label, help]) => {
          const rows = artifacts.filter((artifact) => (artifact.tier ?? "bronze") === tier);
          if (!rows.length) return null;
          return (
            <div key={tier} style={{ marginBottom: 22 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 9, marginBottom: 2 }}>
                <span className="tw-microcap" style={{ marginBottom: 0 }}>{label}</span>
                <span className="tw-td-sub">{help}</span>
              </div>
              <div className="tw-doclist">
                {rows.map((artifact) => (
                  <div
                    key={artifact.id}
                    className="tw-docitem tw-artifact-row"
                    data-testid={`artifact-row-${artifact.id}`}
                  >
                    <Files size={15} />
                    <span className="tw-td-title">{artifact.name}</span>
                    <span className="tw-td-sub">{humanSize(artifact.size)}</span>
                    <span className="tw-td-sub">
                      {artifact.tier === "gold" && artifact.promotedBy
                        ? `promoted by ${artifact.promotedBy}`
                        : artifact.uploadedBy}
                    </span>
                    {editable && artifact.tier !== "gold" && (
                      <button
                        type="button"
                        className="tw-btn-ghost"
                        data-testid={`artifact-promote-${artifact.id}`}
                        disabled={busy}
                        title="Promote to gold — curated and vetted"
                        onClick={() =>
                          void (async () => {
                            setError("");
                            try {
                              await promoteArtifact(engagement.id, artifact.id);
                              await onRefresh();
                            } catch (err) {
                              setError(friendlyError(err, "Artifact action failed."));
                            }
                          })()
                        }
                      >
                        Promote to gold
                      </button>
                    )}
                    <button
                      type="button"
                      className="tw-btn-ghost"
                      data-testid={`artifact-download-${artifact.id}`}
                      title={`Download ${artifact.name}`}
                      onClick={() => void download(artifact)}
                    >
                      <Download size={13} /> Download
                    </button>
                    {editable && (
                      <ArmedDelete
                        testid={`artifact-delete-${artifact.id}`}
                        onConfirm={() => void remove(artifact)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </section>
  );
}

function humanSize(bytes: number) {
  return bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(1)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function ArmedDelete({
  onConfirm,
  testid,
}: {
  onConfirm: () => void;
  testid: string;
}) {
  const [armed, setArmed] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (armed) requestAnimationFrame(() => confirmRef.current?.focus());
  }, [armed]);
  const cancel = () => {
    setArmed(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  };
  if (!armed)
    return (
      <button
        ref={triggerRef}
        type="button"
        className="tw-btn-ghost"
        data-testid={testid}
        title="Delete"
        aria-label="Delete"
        onClick={(event) => {
          event.stopPropagation();
          setArmed(true);
        }}
      >
        <Trash2 size={13} />
      </button>
    );
  return (
    <span className="tw-confirm-actions">
      <button
        ref={confirmRef}
        type="button"
        className="tw-btn"
        data-testid={`${testid}-confirm`}
        onClick={(event) => {
          event.stopPropagation();
          cancel();
          onConfirm();
        }}
      >
        Confirm
      </button>
      <button
        type="button"
        className="tw-btn-ghost"
        data-testid={`${testid}-cancel`}
        onClick={(event) => {
          event.stopPropagation();
          cancel();
        }}
      >
        Cancel
      </button>
    </span>
  );
}
