"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { ChatMessage } from "@/lib/types";
import MessageBubble from "./MessageBubble";
import Button from "./ui/Button";

interface MessageListProps {
  messages: ChatMessage[];
  onSuggestion?: (text: string) => void;
}

// Showcase the assistant's capabilities across the whole workbench — engagements, personal
// tasks, calendar, and meeting prep — not engagements alone. Each maps to a real read/CRUD tool
// or skill; the assistant has no file-writing tool, so nothing here promises a saved document.
const SUGGESTIONS = [
  { icon: "gauge", label: "Review my engagements", description: "See the Engagements available to you", prompt: "List my engagements." },
  { icon: "checklist", label: "What's overdue?", description: "Find tasks past their due date", prompt: "Which of my tasks are overdue?" },
  { icon: "calendar", label: "What's on my calendar?", description: "See your upcoming events", prompt: "What's on my calendar this week?" },
  { icon: "strategy", label: "Prep for a meeting", description: "Get a briefing for an engagement status meeting", prompt: "Prep me for one of my engagement meetings — ask me which engagement to focus on." },
];

export default function MessageList({ messages, onSuggestion }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);
  const rafRef = useRef<number>(0);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScroll.current = distanceFromBottom < 180;
    setShowJumpToLatest(distanceFromBottom > 260);
  }, []);

  useEffect(() => {
    if (shouldAutoScroll.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        containerRef.current?.scrollTo({ top: containerRef.current.scrollHeight, behavior: "smooth" });
        setShowJumpToLatest(false);
      });
    }
  }, [messages]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-x-hidden overflow-y-auto"
      role="log"
      aria-label="Chat messages"
      aria-live="polite"
    >
      <div className="mx-auto w-full max-w-3xl px-4 py-5 md:py-10">
        {messages.length === 0 ? (
          <div className="mx-auto flex min-h-[68vh] flex-col justify-center">
            <h2 className="tw-empty-title">How can I help?</h2>
            <p className="mt-3 text-[15px] text-text-secondary">Ask about your engagements, tasks, calendar, or prep for a meeting.</p>

            {onSuggestion && (
              <div className="mt-6 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={s.prompt}
                    type="button"
                    data-testid={`starter-prompt-${i}`}
                    onClick={() => onSuggestion(s.prompt)}
                    title={s.description}
                    className="tw-chip animate-fade-in"
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg, index) => (
              <div
                key={msg.id}
                className="animate-fade-in"
                style={{ animationDelay: `${Math.min(index * 30, 160)}ms` }}
              >
                <MessageBubble message={msg} />
              </div>
            ))}
          </div>
        )}

      </div>

      {showJumpToLatest && (
        <Button
          type="button"
          data-testid="jump-latest-button"
          onClick={() => {
            shouldAutoScroll.current = true;
            containerRef.current?.scrollTo({ top: containerRef.current.scrollHeight, behavior: "smooth" });
            setShowJumpToLatest(false);
          }}
          className="animate-fade-in fixed bottom-28 left-1/2 z-20 -translate-x-1/2 gap-1.5 rounded-full px-3 py-2 text-xs md:bottom-32 md:left-auto md:right-8 md:translate-x-0"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          Jump to latest
        </Button>
      )}
    </div>
  );
}
