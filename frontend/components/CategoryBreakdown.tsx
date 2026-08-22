"use client";

import { CategoryInsight } from "@/lib/types";

interface CategoryBreakdownProps {
  categories: CategoryInsight[];
  unavailableReason?: string;
}

const BAR_COLORS = ["bg-signal", "bg-mint", "bg-paper/60", "bg-signal/50", "bg-mint/50", "bg-paper/35"];

export default function CategoryBreakdown({ categories, unavailableReason }: CategoryBreakdownProps) {
  if (categories.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center border border-dashed border-paper/15 font-mono text-xs text-paper/40">
        N/A — {unavailableReason || "no category column detected"}
      </div>
    );
  }

  const total = categories.reduce((sum, c) => sum + c.revenue, 0);

  return (
    <ul className="space-y-4">
      {categories.map((cat, i) => {
        const share = total > 0 ? (cat.revenue / total) * 100 : 0;
        return (
          <li key={cat.category}>
            <div className="mb-1.5 flex items-baseline justify-between font-mono text-xs">
              <span className="text-paper/70">{cat.category}</span>
              <span className="text-paper/40">{share.toFixed(1)}%</span>
            </div>
            <div className="h-2.5 w-full bg-ink-line/60">
              <div
                className={`h-2.5 transition-all duration-700 ${BAR_COLORS[i % BAR_COLORS.length]}`}
                style={{ width: `${Math.max(share, 2)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
