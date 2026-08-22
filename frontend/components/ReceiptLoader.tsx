"use client";

import { useEffect, useRef, useState } from "react";
import { DatasetResponse } from "@/lib/types";

interface ReceiptLoaderProps {
  fileName: string;
  result: DatasetResponse | null;
  errorMessage: string | null;
  onFinished: () => void;
  onDismissError: () => void;
}

type LineTone = "default" | "positive" | "warning" | "error";
interface PrintedLine {
  text: string;
  tone: LineTone;
}

const SCRIPTED_LINES = [
  "OPENING FILE...",
  "DECODING TEXT...",
  "SPLITTING COLUMNS...",
  "CLEARING BLANKS...",
  "TYPING COLUMNS...",
  "READING SCHEMA...",
];

const LINE_INTERVAL_MS = 340;

function buildFinalLines(result: DatasetResponse): PrintedLine[] {
  const { schema_summary, insights } = result;
  const lines: PrintedLine[] = [];

  lines.push({ text: `${schema_summary.row_count.toLocaleString()} ROWS FOUND`, tone: "default" });
  lines.push({ text: `${schema_summary.column_count} COLUMNS TYPED`, tone: "default" });

  const roles = schema_summary.detected_roles;
  const roleCount = Object.keys(roles).length;
  lines.push({
    text: roleCount > 0 ? `${roleCount} FIELDS IDENTIFIED` : "NO FAMILIAR FIELDS FOUND",
    tone: roleCount > 0 ? "default" : "warning",
  });

  if (schema_summary.data_quality.duplicate_rows > 0) {
    lines.push({
      text: `${schema_summary.data_quality.duplicate_rows} DUPLICATE ROW(S) FLAGGED`,
      tone: "warning",
    });
  }

  if (schema_summary.data_quality.warnings.length > 0) {
    lines.push({
      text: `${schema_summary.data_quality.warnings.length} NOTE(S) ON DATA QUALITY`,
      tone: "warning",
    });
  }

  if (insights.total_revenue !== null) {
    lines.push({
      text: `REVENUE TOTAL: ${insights.total_revenue.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      })}`,
      tone: "positive",
    });
  } else {
    lines.push({ text: "NO REVENUE FIELD DETECTED", tone: "warning" });
  }

  lines.push({ text: "READY", tone: "positive" });
  return lines;
}

export default function ReceiptLoader({
  fileName,
  result,
  errorMessage,
  onFinished,
  onDismissError,
}: ReceiptLoaderProps) {
  const [printed, setPrinted] = useState<PrintedLine[]>([]);
  const [scriptDone, setScriptDone] = useState(false);
  const [tornOff, setTornOff] = useState(false);
  const finalPrintStarted = useRef(false);
  const finishedCalled = useRef(false);

  // Phase 1: print the scripted "working" lines at a steady cadence.
  useEffect(() => {
    if (errorMessage) return;
    let index = 0;
    const interval = setInterval(() => {
      index += 1;
      setPrinted(SCRIPTED_LINES.slice(0, index).map((text) => ({ text, tone: "default" as LineTone })));
      if (index >= SCRIPTED_LINES.length) {
        clearInterval(interval);
        setScriptDone(true);
      }
    }, LINE_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [errorMessage]);

  // Phase 2: once the script is done AND the real result has arrived,
  // print the derived summary lines, then tear off and hand back control.
  useEffect(() => {
    if (!scriptDone || !result || finalPrintStarted.current || errorMessage) return;
    finalPrintStarted.current = true;

    const finalLines = buildFinalLines(result);
    let index = 0;
    const interval = setInterval(() => {
      index += 1;
      setPrinted((prev) => [...prev, finalLines[index - 1]]);
      if (index >= finalLines.length) {
        clearInterval(interval);
        setTimeout(() => setTornOff(true), 260);
        setTimeout(() => {
          if (!finishedCalled.current) {
            finishedCalled.current = true;
            onFinished();
          }
        }, 900);
      }
    }, LINE_INTERVAL_MS + 60);
    return () => clearInterval(interval);
  }, [scriptDone, result, errorMessage, onFinished]);

  const stillWaiting = scriptDone && !result && !errorMessage;

  return (
    <main className="halftone flex min-h-screen items-center justify-center bg-ink px-6 py-16">
      <div className="w-full max-w-sm">
        <div
          className={`bg-paper text-paper-ink shadow-[0_20px_60px_rgba(0,0,0,0.5)] transition-all duration-500 ${
            tornOff ? "translate-y-1 rotate-[0.6deg]" : ""
          }`}
        >
          <div className="border-b border-dashed border-paper-ink/20 px-6 pb-4 pt-6 text-center">
            <p className="text-eyebrow text-[10px] text-paper-ink/50">Ledger Intake Receipt</p>
            <p className="mt-1 truncate font-mono text-xs font-medium text-paper-ink/80">{fileName}</p>
          </div>

          <div className="min-h-[220px] px-6 py-5 font-mono text-[13px] leading-[1.9]">
            {errorMessage ? (
              <div className="animate-print-line">
                <p className="text-brick">! COULD NOT PROCESS FILE</p>
                <p className="mt-2 text-paper-ink/70">{errorMessage}</p>
              </div>
            ) : (
              <>
                {printed.map((line, i) => (
                  <p
                    key={i}
                    className={`animate-print-line ${
                      line.tone === "positive"
                        ? "font-semibold text-mint"
                        : line.tone === "warning"
                        ? "text-signal"
                        : line.tone === "error"
                        ? "text-brick"
                        : "text-paper-ink/80"
                    }`}
                  >
                    {line.text}
                  </p>
                ))}
                {stillWaiting && (
                  <p className="text-paper-ink/50">
                    STILL TOTALING
                    <span className="animate-blink">...</span>
                  </p>
                )}
              </>
            )}
          </div>

          <div className="perforated-bottom mx-6" />
          <div className="flex items-center justify-center gap-2 px-6 py-4 text-paper-ink/30">
            <div className="barcode h-4 w-32 text-paper-ink/30" />
          </div>
        </div>

        {errorMessage && (
          <button
            onClick={onDismissError}
            className="mt-6 w-full rounded-sm border border-paper/25 bg-ink-raised px-4 py-3 font-mono text-xs uppercase tracking-wide text-paper/80 transition-colors hover:border-signal hover:text-signal"
          >
            Try a different file
          </button>
        )}
      </div>
    </main>
  );
}
