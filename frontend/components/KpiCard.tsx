"use client";

import { useCountUp } from "@/hooks/useCountUp";

interface KpiCardProps {
  eyebrow: string;
  value: number | null;
  format: "currency" | "number" | "percent";
  caption?: string;
  unavailableReason?: string;
  tone?: "default" | "positive" | "negative";
}

function formatValue(value: number, format: KpiCardProps["format"]): string {
  if (format === "currency") {
    return value.toLocaleString(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: value >= 1000 ? 0 : 2,
    });
  }
  if (format === "percent") {
    return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
  }
  return Math.round(value).toLocaleString();
}

export default function KpiCard({ eyebrow, value, format, caption, unavailableReason, tone = "default" }: KpiCardProps) {
  const animated = useCountUp(value ?? 0);
  const toneClass = tone === "positive" ? "text-mint" : tone === "negative" ? "text-brick" : "text-paper";

  return (
    <div className="perforated-bottom relative bg-ink-raised px-6 pb-5 pt-6">
      <p className="text-eyebrow text-[10px] text-paper/45">{eyebrow}</p>
      {value === null ? (
        <p className="mt-3 font-mono text-sm leading-relaxed text-paper/35">
          N/A — {unavailableReason || "not enough data"}
        </p>
      ) : (
        <p className={`mt-2 font-mono text-4xl font-semibold tabular-nums ${toneClass}`}>
          {formatValue(animated, format)}
        </p>
      )}
      {caption && value !== null && <p className="mt-2 font-mono text-[11px] text-paper/40">{caption}</p>}
    </div>
  );
}
