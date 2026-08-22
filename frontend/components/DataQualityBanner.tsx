"use client";

import { AlertTriangle } from "lucide-react";

interface DataQualityBannerProps {
  warnings: string[];
}

export default function DataQualityBanner({ warnings }: DataQualityBannerProps) {
  if (warnings.length === 0) return null;

  return (
    <div className="relative border border-signal/40 bg-signal/[0.07] px-5 py-4">
      <div className="flex items-start gap-3">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-signal" />
        <div>
          <p className="text-eyebrow text-[10px] text-signal">Checked on intake</p>
          <ul className="mt-1.5 space-y-1 font-mono text-xs text-paper/70">
            {warnings.map((w, i) => (
              <li key={i}>· {w}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
