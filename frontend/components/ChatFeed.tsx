"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, Send } from "lucide-react";
import { resetChat, sendChatMessage } from "@/lib/api";
import { ApiError, ChatTurn } from "@/lib/types";
import ResponseCard from "./chat/ResponseCard";

interface ChatFeedProps {
  datasetId: string;
  currencyColumns: Set<string>;
}

function makeId() {
  return Math.random().toString(36).slice(2);
}

export default function ChatFeed({ datasetId, currencyColumns }: ChatFeedProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const chat = chatRef.current;
    if (!chat) return;

    chat.scrollTo({ top: chat.scrollHeight, behavior: "smooth" });
  }, [turns]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;

    if (!input.trim()) {
      textarea.style.height = "40px";
    }
  }, [input]);

  const submit = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isBusy) return;

      const id = makeId();
      setTurns((prev) => [...prev, { id, question: trimmed, response: null, isLoading: true, errorMessage: null }]);
      setInput("");
      setIsBusy(true);

      try {
        const response = await sendChatMessage(datasetId, trimmed);
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, response, isLoading: false } : t)));
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Something went wrong reaching the assistant.";
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, isLoading: false, errorMessage: message } : t)));
      } finally {
        setIsBusy(false);
      }
    },
    [datasetId, isBusy]
  );

  const startNewQuestion = useCallback(async () => {
    setTurns([]);
    setInput("");
    try {
      await resetChat(datasetId);
    } catch {
    }
    inputRef.current?.focus();
  }, [datasetId]);

  return (
    <div className="border border-ink-line bg-ink-raised">
      <div className="flex items-center justify-between border-b border-ink-line px-6 py-4">
        <div>
          <p className="font-display text-xl font-bold uppercase tracking-wide">Ask BAsight</p>
          <p className="mt-0.5 font-mono text-[11px] text-paper/40">Answers are computed from your data, not guessed.</p>
        </div>
        {turns.length > 0 && (
          <button
            onClick={startNewQuestion}
            className="flex shrink-0 items-center gap-1.5 border border-paper/20 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-paper/70 transition-colors hover:border-signal hover:text-signal"
          >
            <RotateCcw size={12} />
            Ask a New question
          </button>
        )}
      </div>

      {turns.length > 0 && (
        <div ref={chatRef} className="max-h-[600px] space-y-2 overflow-y-auto px-6 py-5">
          {turns.map((turn) => (
            <ResponseCard key={turn.id} turn={turn} currencyColumns={currencyColumns} />
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="flex items-end gap-3 border-t border-ink-line px-6 py-4"
      >
        <textarea
          ref={inputRef}
          value={input}
          rows={1}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(input);
            }
          }}
          disabled={isBusy}
          placeholder={
            turns.length === 0
              ? "Ask about this data — e.g. \"what's my total revenue?\""
              : "Ask a follow-up..."
          }
          className="max-h-[180px] min-h-[40px] flex-1 resize-none overflow-y-auto bg-transparent py-2 font-mono text-sm leading-6 text-paper placeholder:text-paper/30 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isBusy || !input.trim()}
          className="flex items-center gap-1.5 bg-signal px-4 py-2 font-mono text-xs uppercase tracking-wide text-ink transition-opacity disabled:opacity-30"
        >
          <Send size={13} />
          Ask
        </button>
      </form>
    </div>
  );
}
