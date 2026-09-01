"use client";

import { ArrowUpRight, ArrowDownRight, RotateCcw } from "lucide-react";
import { DatasetResponse } from "@/lib/types";
import KpiCard from "./KpiCard";
import RevenueChart from "./RevenueChart";
import TopProductsReceipt from "./TopProductsReceipt";
import CategoryBreakdown from "./CategoryBreakdown";
import DataQualityBanner from "./DataQualityBanner";
import ChatFeed from "./ChatFeed";
import Reveal from "./Reveal";

interface DashboardProps {
  dataset: DatasetResponse;
  onReset: () => void;
}

function reasonFor(unavailable: string[], key: string): string | undefined {
  const match = unavailable.find((u) => u.toLowerCase().includes(key.toLowerCase()));
  if (!match) return undefined;
  const parts = match.split(":");
  return parts.length > 1 ? parts.slice(1).join(":").trim() : match;
}

export default function Dashboard({ dataset, onReset }: DashboardProps) {
  const { schema_summary, insights, filename, dataset_id } = dataset;
  const unavailable = insights.unavailable_metrics;

  // finds whether a numbr needs a currency symbol or not for chat
  const currencyColumns = new Set(
    [schema_summary.detected_roles.price, schema_summary.detected_roles.revenue].filter(
      (c): c is string => !!c
    )
  );

  return (
    <main className="min-h-screen bg-ink text-paper">
      <header className="sticky top-0 z-10 border-b border-ink-line bg-ink/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-signal" />
            <p className="font-display text-lg font-bold uppercase tracking-wide">BAsight</p>
          </div>
          <div className="hidden items-center gap-2 font-mono text-xs text-paper/45 sm:flex">
            <span className="max-w-[220px] truncate">{filename}</span>
            <span className="text-paper/20">·</span>
            <span>{schema_summary.row_count.toLocaleString()} rows</span>
            <span className="text-paper/20">·</span>
            <span>{schema_summary.column_count} cols</span>
          </div>
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 border border-paper/20 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-paper/70 transition-colors hover:border-signal hover:text-signal"
          >
            <RotateCcw size={12} />
            New file
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-10">
        <Reveal>
          <h1 className="font-display text-4xl font-extrabold uppercase leading-none sm:text-5xl">
            The read on <span className="text-signal">your sales.</span>
          </h1>
          <p className="mt-3 font-mono text-xs text-paper/45">
            Cleaned, itemized, and totaled.
          </p>
        </Reveal>

        {schema_summary.data_quality.warnings.length > 0 && (
          <Reveal delayMs={80} className="mt-6">
            <DataQualityBanner warnings={schema_summary.data_quality.warnings} />
          </Reveal>
        )}

        <Reveal delayMs={120} className="mt-8">
          <div className="grid grid-cols-2 gap-px bg-ink-line sm:grid-cols-4">
            <KpiCard
              eyebrow="Total Revenue"
              value={insights.total_revenue}
              format="currency"
              unavailableReason={reasonFor(unavailable, "total_revenue")}
            />
            <KpiCard
              eyebrow="Total Orders"
              value={insights.total_orders}
              format="number"
            />
            <KpiCard
              eyebrow="Avg Order Value"
              value={insights.average_order_value}
              format="currency"
              unavailableReason={reasonFor(unavailable, "average_order_value")}
            />
            <KpiCard
              eyebrow="Vs. Prior Period"
              value={insights.period_over_period_change_pct}
              format="percent"
              tone={
                insights.period_over_period_change_pct === null
                  ? "default"
                  : insights.period_over_period_change_pct >= 0
                  ? "positive"
                  : "negative"
              }
              unavailableReason={reasonFor(unavailable, "period_over_period")}
            />
          </div>
        </Reveal>

        <Reveal delayMs={160} className="mt-10">
          <div className="border border-ink-line bg-ink-raised p-6">
            <div className="mb-5 flex items-center justify-between">
              <p className="font-display text-xl font-bold uppercase tracking-wide">Revenue Over Time</p>
              {insights.period_over_period_change_pct !== null && (
                <span
                  className={`flex items-center gap-1 font-mono text-xs ${
                    insights.period_over_period_change_pct >= 0 ? "text-mint" : "text-brick"
                  }`}
                >
                  {insights.period_over_period_change_pct >= 0 ? (
                    <ArrowUpRight size={13} />
                  ) : (
                    <ArrowDownRight size={13} />
                  )}
                  {Math.abs(insights.period_over_period_change_pct).toFixed(1)}% period over period
                </span>
              )}
            </div>
            <RevenueChart
              data={insights.revenue_over_time}
              granularity={insights.revenue_time_granularity}
              unavailableReason={reasonFor(unavailable, "revenue_over_time")}
            />
          </div>
        </Reveal>

        <div className="mt-10 grid gap-px bg-ink-line md:grid-cols-2">
          <Reveal delayMs={0}>
            <div className="h-full border border-ink-line bg-ink-raised p-6">
              <p className="mb-5 font-display text-xl font-bold uppercase tracking-wide">Top Sellers</p>
              <TopProductsReceipt
                products={insights.top_products}
                unavailableReason={reasonFor(unavailable, "top_products")}
              />
            </div>
          </Reveal>
          <Reveal delayMs={100}>
            <div className="h-full border border-ink-line bg-ink-raised p-6">
              <p className="mb-5 font-display text-xl font-bold uppercase tracking-wide">By Category</p>
              <CategoryBreakdown
                categories={insights.category_breakdown}
                unavailableReason={reasonFor(unavailable, "category")}
              />
            </div>
          </Reveal>
        </div>

        <Reveal delayMs={100} className="mt-10">
          <ChatFeed datasetId={dataset_id} currencyColumns={currencyColumns} />
        </Reveal>

        <p className="mt-14 text-center font-mono text-[10px] text-paper/25">
          Dataset held for this session only
        </p>
      </div>
    </main>
  );
}
