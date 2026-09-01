"use client";

import { ArrowRight } from "lucide-react";
import { SimulateScenarioData } from "@/lib/types";

interface ScenarioComparisonProps {
  data: SimulateScenarioData;
  label?: string;
}

function fmt(v: number | null) {
  if (v === null) return "—";
  return v.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function ScenarioComparison({ data, label }: ScenarioComparisonProps) {
  const isPositive = (data.delta_pct ?? 0) >= 0;

  return (
    <div className="mt-4 bg-ink-raised px-5 py-5">
      <p className="text-eyebrow mb-4 text-[10px] text-paper/45">{label || "Projected impact"}</p>

      <div className="flex items-center justify-between gap-3">
        <div className="flex-1">
          <p className="text-eyebrow text-[10px] text-paper/40">Current</p>
          <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-paper/70">{fmt(data.baseline_revenue)}</p>
        </div>
        <ArrowRight size={18} className="shrink-0 text-paper/30" />
        <div className="flex-1 text-right">
          <p className="text-eyebrow text-[10px] text-paper/40">Projected</p>
          <p className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${isPositive ? "text-mint" : "text-brick"}`}>
            {fmt(data.projected_revenue)}
          </p>
        </div>
      </div>

      {data.delta_pct !== null && (
        <p className={`mt-3 text-center font-mono text-xs ${isPositive ? "text-mint" : "text-brick"}`}>
          {isPositive ? "+" : ""}
          {data.delta_pct.toFixed(1)}% ({fmt(data.delta)})
        </p>
      )}

      {/* The elasticity assumption displayed to make the result a prediction */}
      <div className="mt-4 border-t border-dashed border-paper/15 pt-3">
        <p className="font-mono text-[11px] leading-relaxed text-paper/50">{data.assumptions}</p>
      </div>
    </div>
  );
}