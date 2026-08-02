"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { ChatMessage, MessagePart } from "@/lib/types";
import ToolTrace from "./ToolTrace";
import MarkdownRenderer from "./MarkdownRenderer";

interface MessageBubbleProps {
  message: ChatMessage;
}

type RenderedSegment =
  | { kind: "text"; part: MessagePart & { type: "text" }; index: number }
  | { kind: "reasoning"; part: MessagePart & { type: "reasoning" }; index: number }
  | { kind: "tool_group"; parts: (MessagePart & { type: "tool_call" })[]; startIndex: number };

function groupParts(parts: MessagePart[]): RenderedSegment[] {
  const segments: RenderedSegment[] = [];
  let toolBatch: (MessagePart & { type: "tool_call" })[] = [];
  let toolBatchStart = 0;

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (part.type === "tool_call") {
      if (toolBatch.length === 0) toolBatchStart = i;
      toolBatch.push(part);
    } else {
      if (toolBatch.length > 0) {
        segments.push({ kind: "tool_group", parts: toolBatch, startIndex: toolBatchStart });
        toolBatch = [];
      }
      if (part.type === "reasoning") segments.push({ kind: "reasoning", part, index: i });
      else segments.push({ kind: "text", part, index: i });
    }
  }
  if (toolBatch.length > 0) {
    segments.push({ kind: "tool_group", parts: toolBatch, startIndex: toolBatchStart });
  }
  return segments;
}

// Muted, collapsible "thinking" block — the model's reasoning summary (reasoning models only).
function ReasoningBlock({ content }: { content: string }) {
  const [open, setOpen] = useState(true);
  if (!content.trim()) return null;
  return (
    <div className="reasoning-block" data-testid="reasoning-block">
      <button type="button" className="reasoning-header" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <span>Thinking</span>
      </button>
      {open && (
        <div className="reasoning-body">
          <MarkdownRenderer content={content} />
        </div>
      )}
    </div>
  );
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const segments = useMemo(() => groupParts(message.parts), [message.parts]);
  const isThinking = message.isStreaming && message.parts.length === 0;
  const meta = message.meta;

  // The streaming cursor rides the last text segment while TEXT_MESSAGE_CONTENT
  // deltas are still arriving (removed by RUN_FINISHED via isStreaming).
  const lastTextIndex = segments.reduce(
    (last, seg, index) => (seg.kind === "text" ? index : last),
    -1,
  );

  return (
    <article className={`message-row ${isUser ? "message-row-user" : "message-row-assistant"}`}>
      <div className={`message-body ${isUser ? "message-body-user" : "message-body-assistant"}`}>
        <div className="message-parts">
          {segments.map((seg, segIndex) => {
            if (seg.kind === "text") {
              return (
                <div key={seg.index} className="animate-fade-in">
                  <MarkdownRenderer content={seg.part.content} />
                  {!isUser && message.isStreaming && segIndex === lastTextIndex && (
                    <span className="tw-cursor" aria-hidden="true" />
                  )}
                </div>
              );
            } else if (seg.kind === "reasoning") {
              return <ReasoningBlock key={seg.index} content={seg.part.content} />;
            } else {
              return (
                <ToolTrace
                  key={seg.startIndex}
                  parts={seg.parts}
                  isStreaming={message.isStreaming}
                />
              );
            }
          })}
        </div>

        {!isUser && !message.isStreaming && meta && meta.steps > 0 && (
          <div className="turn-meta" data-testid="turn-meta">
            {meta.steps} tool call{meta.steps === 1 ? "" : "s"} · {(meta.durationMs / 1000).toFixed(1)}s
          </div>
        )}

        {isThinking && (
          <div className="thinking-row">
            <div className="thinking-dots"><span/><span/><span/></div>
            <span className="thinking-label">Thinking</span>
          </div>
        )}
      </div>
    </article>
  );
}
