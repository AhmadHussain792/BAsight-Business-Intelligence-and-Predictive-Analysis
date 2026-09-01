"use client";

import { useCountUp } from "@/hooks/useCountUp";

interface InlineMetricProps {
  label: string;
  value: number;
  isCurrency?: boolean;
  groupLabel?: string | null;
}

export default function InlineMetric({ label, value, isCurrency = true, groupLabel }: InlineMetricProps) {
  const animated = useCountUp(value);
  const formatted = isCurrency
    ? animated.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: animated >= 1000 ? 0 : 2 })
    : Math.round(animated).toLocaleString();

  return (
    <div className="perforated-top mt-4 bg-ink-raised px-6 pt-5 pb-4">
      <p className="text-eyebrow text-[10px] text-paper/45">{label}</p>
      {groupLabel && (
        <p className="mt-1 font-display text-xl font-bold leading-tight text-paper sm:text-2xl">{groupLabel}</p>
      )}
      <p className="mt-1 font-mono text-4xl font-semibold tabular-nums text-signal">{formatted}</p>
    </div>
  );
}