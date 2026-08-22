"use client";

import { Lock, Send } from "lucide-react";

export default function ChatComingSoon() {
  return (
    <div className="border border-paper/15 bg-ink-raised px-6 py-6">
      <div className="mb-4 flex items-center gap-2">
        <Lock size={13} className="text-paper/35" />
        <p className="text-eyebrow text-[10px] text-paper/45">Ask Ledger &nbsp;·&nbsp; Coming soon</p>
      </div>
      <p className="mb-5 max-w-md font-mono text-xs leading-relaxed text-paper/50">
        Next up: ask questions in plain English, for example,  &quot;what if I raise Wireless
        Earbuds by 15%?&quot;, and get an answer worked out against this exact
        dataset.
      </p>
      <div className="flex items-center gap-3 border border-dashed border-paper/20 bg-ink px-4 py-3 opacity-50">
        <input
          disabled
          placeholder="Ask about this data..."
          className="flex-1 bg-transparent font-mono text-sm text-paper placeholder:text-paper/30 focus:outline-none"
        />
        <Send size={15} className="text-paper/30" />
      </div>
    </div>
  );
}
