"use client";

import { AlertTriangle } from "lucide-react";
import { ChatToolCall, ChatTurn, CustomAnalysisData, QueryMetricData, SimulateScenarioData } from "@/lib/types";
import Reveal from "../Reveal";
import InlineMetric from "./InlineMetric";
import InlineChart from "./InlineChart";
import ScenarioComparison from "./ScenarioComparison";
import CustomResult from "./CustomResult";

interface ResponseCardProps {
  turn: ChatTurn;
  // column names the dataset detected as money (its "price" and/or "revenue" role columns) 
  // this is checked against the `metric_column` of the tool result
  currencyColumns: Set<string>;
}

type Visual =
  | { type: "metric"; label: string; value: number; isCurrency: boolean; groupLabel: string | null }
  | { type: "chart"; rows: QueryMetricData["rows"]; isTimeSeries: boolean; label: string }
  | { type: "scenario"; data: SimulateScenarioData; label: string }
  | { type: "custom"; result: unknown };

/**
 * one visual per successful tool call in the order they were made
 * failed attempts are excluded.
 */
function pickVisuals(toolCalls: ChatToolCall[], currencyColumns: Set<string>): Visual[] {
  const visuals: Visual[] = [];

  for (const tc of toolCalls) {
    if (!tc.ok) continue;

    if (tc.name === "query_metric") {
      const data = tc.data as unknown as QueryMetricData;
      if (!data.rows || data.rows.length === 0) continue;
      if (data.rows.length === 1) {
        const v = data.rows[0].value;
        if (v === null) continue;
        const isCurrency = !!data.metric_column && currencyColumns.has(data.metric_column);
        // A grouped query limited to one row (e.g. "top product") carries a
        // real group name here; an ungrouped total (e.g. "total revenue")
        // always has group: null — that distinction is exactly what decides
        // whether a headline shows above the number.
        visuals.push({ type: "metric", label: data.trace, value: v, isCurrency, groupLabel: data.rows[0].group });
      } else {
        visuals.push({ type: "chart", rows: data.rows, isTimeSeries: !!data.granularity_used, label: data.trace });
      }
    } else if (tc.name === "simulate_scenario") {
      const data = tc.data as unknown as SimulateScenarioData;
      visuals.push({ type: "scenario", data, label: data.trace });
    } else if (tc.name === "execute_custom_analysis") {
      const data = tc.data as unknown as CustomAnalysisData;
      if (data.result === null || data.result === undefined) continue;
      visuals.push({ type: "custom", result: data.result });
    }
  }

  return visuals;
}

function LoadingLine() {
  return (
    <div className="mt-3 flex items-center gap-2 font-mono text-xs text-paper/40">
      <span>Working it out</span>
      <span className="animate-blink">...</span>
    </div>
  );
}

export default function ResponseCard({ turn, currencyColumns }: ResponseCardProps) {
  const visuals = turn.response ? pickVisuals(turn.response.tool_calls, currencyColumns) : [];

  return (
    <Reveal className="border-b border-ink-line pb-8 pt-2 last:border-0">
      <p className="text-eyebrow mb-2 text-[10px] text-signal">You asked</p>
      <p className="font-display text-xl font-bold leading-snug text-paper sm:text-2xl">{turn.question}</p>

      <div className="mt-4">
        {turn.errorMessage ? (
          <div className="flex items-start gap-2 border border-brick/40 bg-brick/10 px-4 py-3 font-mono text-xs text-brick">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <span>{turn.errorMessage}</span>
          </div>
        ) : turn.isLoading ? (
          <LoadingLine />
        ) : turn.response?.hit_iteration_limit ? (
          <p className="font-mono text-sm leading-relaxed text-paper/60">
            This one needed more steps than usual and didn&apos;t finish — try narrowing the question (e.g. naming a
            specific product or date range).
          </p>
        ) : (
          <>
            <p className="font-mono text-sm leading-relaxed text-paper/85">{turn.response?.answer}</p>

            {visuals.map((visual, i) => {
              const key = `${turn.id}-${i}`;
              if (visual.type === "metric") {
                return (
                  <InlineMetric
                    key={key}
                    label={visual.label}
                    value={visual.value}
                    isCurrency={visual.isCurrency}
                    groupLabel={visual.groupLabel}
                  />
                );
              }
              if (visual.type === "chart") {
                return <InlineChart key={key} rows={visual.rows} isTimeSeries={visual.isTimeSeries} label={visual.label} />;
              }
              if (visual.type === "scenario") {
                return <ScenarioComparison key={key} data={visual.data} label={visual.label} />;
              }
              return <CustomResult key={key} result={visual.result} />;
            })}
          </>
        )}
      </div>
    </Reveal>
  );
}