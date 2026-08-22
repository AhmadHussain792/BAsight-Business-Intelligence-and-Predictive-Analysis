"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TimeSeriesPoint } from "@/lib/types";

interface RevenueChartProps {
  data: TimeSeriesPoint[];
  granularity: string | null;
  unavailableReason?: string;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as TimeSeriesPoint;
  return (
    <div className="bg-paper px-3 py-2 font-mono text-xs text-paper-ink shadow-lg">
      <p className="text-paper-ink/50">{label}</p>
      <p className="mt-1 font-semibold">
        {point.revenue.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })}
      </p>
      <p className="text-paper-ink/50">{point.order_count} order{point.order_count === 1 ? "" : "s"}</p>
    </div>
  );
}

export default function RevenueChart({ data, granularity, unavailableReason }: RevenueChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center border border-dashed border-paper/15 font-mono text-xs text-paper/40">
        N/A — {unavailableReason || "not enough data"}
      </div>
    );
  }

  return (
    <div>
      {granularity && (
        <p className="text-eyebrow mb-3 text-[10px] text-paper/40">{granularity} totals</p>
      )}
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <defs>
              <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#F0631F" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#F0631F" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#2C2519" strokeDasharray="3 4" vertical={false} />
            <XAxis
              dataKey="period"
              stroke="#F6F1E4"
              strokeOpacity={0.2}
              tick={{ fill: "#F6F1E4", fillOpacity: 0.45, fontSize: 11, fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              stroke="#F6F1E4"
              strokeOpacity={0.2}
              tick={{ fill: "#F6F1E4", fillOpacity: 0.45, fontSize: 11, fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)}
              width={44}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#F0631F", strokeOpacity: 0.4 }} />
            <Area
              type="monotone"
              dataKey="revenue"
              stroke="#F0631F"
              strokeWidth={2}
              fill="url(#revenueFill)"
              animationDuration={900}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
