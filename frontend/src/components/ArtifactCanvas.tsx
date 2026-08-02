"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Sparkles, Pencil, Check, X } from "lucide-react";
import Button from "./ui/Button";
import Status from "./ui/Status";
import { Surface } from "./ui/Surface";
import MarkdownRenderer from "./MarkdownRenderer";
import { getFileContent, saveFileContent } from "@/lib/api";
import { useSession } from "./SessionProvider";

const EDITABLE = /\.(md|txt|csv)$/i;

// The artifact canvas: the assistant's work output gets real room here — drafts,
// document analyses, and other generated artifacts. Renders from server state (the
// generated files in the workspace), not chat echo, so what you see is verifiable.
export default function ArtifactCanvas() {
  const { state } = useSession();
  const artifacts = useMemo(
    () => state.files.filter((f) => f.origin === "generated").sort((a, b) => (a.modified_at < b.modified_at ? 1 : -1)),
    [state.files],
  );

  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Auto-select the newest artifact as they appear.
  useEffect(() => {
    if (artifacts.length === 0) { setSelected(null); return; }
    if (!selected || !artifacts.some((a) => a.filename === selected)) setSelected(artifacts[0].filename);
  }, [artifacts, selected]);

  useEffect(() => {
    if (!selected || !state.sessionId) { setContent(""); return; }
    let cancelled = false;
    setLoading(true); setError(null); setEditing(false);
    getFileContent(state.sessionId, selected)
      .then((r) => { if (!cancelled) setContent(r.content); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load artifact."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selected, state.sessionId]);

  const editable = !!selected && EDITABLE.test(selected) && !loading && !error;
  const startEdit = () => { setDraft(content); setSaveError(null); setEditing(true); };
  const cancelEdit = () => { setEditing(false); setSaveError(null); };
  const saveEdit = async () => {
    if (!selected || !state.sessionId) return;
    setSaving(true); setSaveError(null);
    try {
      await saveFileContent(state.sessionId, selected, draft);
      setContent(draft);
      setEditing(false);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-3 min-w-0" data-testid="artifact-canvas">
      <Surface className="h-14 flex items-center justify-between px-5 shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-text-muted">Artifacts</span>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <Button variant="primary" size="small" data-testid="artifact-save" onClick={saveEdit} disabled={saving}>
                <Check size={13} strokeWidth={2.5} />{saving ? "Saving…" : "Save"}
              </Button>
              <Button size="small" data-testid="artifact-cancel" onClick={cancelEdit} disabled={saving}>
                <X size={13} strokeWidth={2.5} />Cancel
              </Button>
            </>
          ) : (
            <>
              {editable && (
                <Button size="small" data-testid="artifact-edit" onClick={startEdit}>
                  <Pencil size={13} strokeWidth={2.5} />Edit
                </Button>
              )}
              {artifacts.length > 0 && (
                <span className="text-[11px] font-semibold text-text-muted">{artifacts.length} artifact{artifacts.length === 1 ? "" : "s"}</span>
              )}
            </>
          )}
        </div>
      </Surface>

      <Surface level="raised" className="flex-1 flex min-h-0 overflow-hidden">
        {artifacts.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
            <div className="p-3 rounded-2xl bg-surface-2 text-text-muted"><Sparkles size={22} /></div>
            <p className="text-sm font-semibold text-text-secondary">No artifacts yet</p>
            <p className="text-xs text-text-muted max-w-xs leading-relaxed">
              When the assistant drafts a deliverable or analyzes a document, it appears here —
              editable and traceable to its source.
            </p>
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
            {artifacts.length > 1 && (
            <nav className="w-52 shrink-0 border-r border-border-subtle overflow-y-auto p-2">
              {artifacts.map((a) => (
                <button
                  key={a.filename}
                  type="button"
                  data-testid={`artifact-${a.filename}`}
                  onClick={() => setSelected(a.filename)}
                  className={`w-full text-left rounded-xl px-3 py-2.5 mb-1 transition-all flex items-start gap-2 ${selected === a.filename ? "bg-surface-2 border border-brand-primary/40" : "hover:bg-surface-2 border border-transparent"}`}
                >
                  <FileText size={14} className="mt-0.5 shrink-0 text-text-muted" />
                  <span className="text-[12px] font-medium text-text-secondary break-all leading-snug">{a.filename}</span>
                </button>
              ))}
            </nav>
            )}
            <div className="flex-1 min-w-0 overflow-y-auto p-6" data-testid="artifact-viewer">
              {loading ? (
                <p className="text-sm text-text-muted">Loading…</p>
              ) : error ? (
                <p className="text-sm text-brand-warning">{error}</p>
              ) : editing ? (
                <div className="flex h-full flex-col gap-2">
                  {saveError && <p className="text-xs text-brand-warning">{saveError}</p>}
                  <textarea
                    data-testid="artifact-editor"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    spellCheck={false}
                    className="flex-1 min-h-[60vh] w-full resize-none rounded-xl border border-border-subtle bg-surface-2/50 p-4 font-mono text-[13px] leading-relaxed text-text-primary outline-none focus:border-brand-primary"
                  />
                </div>
              ) : (
                <>
                  <Status data-testid="artifact-provenance" tone="warning" pill={false} className="mb-4 flex items-center gap-2 px-3 py-2 text-[11px] font-semibold">
                    <Sparkles size={13} /> AI-generated draft · unreviewed — verify before use
                  </Status>
                  <MarkdownRenderer content={content} />
                </>
              )}
            </div>
          </div>
        )}
      </Surface>
    </div>
  );
}
