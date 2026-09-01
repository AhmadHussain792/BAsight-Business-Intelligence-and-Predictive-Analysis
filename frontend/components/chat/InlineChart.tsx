"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { QueryMetricRow } from "@/lib/types";

interface InlineChartProps {
  rows: QueryMetricRow[];
  isTimeSeries: boolean;
  label: string;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-paper px-3 py-2 font-mono text-xs text-paper-ink shadow-lg">
      <p className="text-paper-ink/50">{label}</p>
      <p className="mt-1 font-semibold">{Number(payload[0].value).toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
    </div>
  );
}

export default function InlineChart({ rows, isTimeSeries, label }: InlineChartProps) {
  const data = rows.map((r) => ({ name: r.group ?? "—", value: r.value ?? 0 }));

  return (
    <div className="mt-4 bg-ink-raised px-5 py-5">
      <p className="text-eyebrow mb-3 text-[10px] text-paper/45">{label}</p>
      <div className="h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {isTimeSeries ? (
            <AreaChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="inlineFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F0631F" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#F0631F" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#2C2519" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey="name" stroke="#F6F1E4" strokeOpacity={0.2} tick={{ fill: "#F6F1E4", fillOpacity: 0.45, fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} minTickGap={20} />
              <YAxis stroke="#F6F1E4" strokeOpacity={0.2} tick={{ fill: "#F6F1E4", fillOpacity: 0.45, fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} width={40} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#F0631F", strokeOpacity: 0.4 }} />
              <Area type="monotone" dataKey="value" stroke="#F0631F" strokeWidth={2} fill="url(#inlineFill)" animationDuration={700} />
            </AreaChart>
          ) : (
            <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="#2C2519" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey="name" stroke="#F6F1E4" strokeOpacity={0.2} tick={{ fill: "#F6F1E4", fillOpacity: 0.45, fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis stroke="#F6F1E4" strokeOpacity={0.2} tick={{ fill: "#F6F1E4", fillOpacity: 0.45, fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} width={40} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "#F0631F", fillOpacity: 0.08 }} />
              <Bar dataKey="value" fill="#F0631F" radius={[3, 3, 0, 0]} animationDuration={700} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
