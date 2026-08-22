"use client";

import { ProductInsight } from "@/lib/types";

interface TopProductsReceiptProps {
  products: ProductInsight[];
  unavailableReason?: string;
}

export default function TopProductsReceipt({ products, unavailableReason }: TopProductsReceiptProps) {
  if (products.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center border border-dashed border-paper/15 font-mono text-xs text-paper/40">
        N/A — {unavailableReason || "no product column detected"}
      </div>
    );
  }

  const maxRevenue = Math.max(...products.map((p) => p.revenue));

  return (
    <div className="bg-paper px-6 py-6 text-paper-ink">
      <div className="mb-4 flex items-center justify-between border-b border-dashed border-paper-ink/20 pb-3">
        <p className="text-eyebrow text-[10px] text-paper-ink/50">Item</p>
        <p className="text-eyebrow text-[10px] text-paper-ink/50">Revenue</p>
      </div>
      <ul className="space-y-3">
        {products.map((product, i) => (
          <li key={product.name}>
            <div className="flex items-baseline font-mono text-sm">
              <span className="text-paper-ink/40">{String(i + 1).padStart(2, "0")}</span>
              <span className="ml-3 truncate">{product.name}</span>
              <span className="dotted-leader" />
              <span className="font-semibold tabular-nums">
                {product.revenue.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="ml-7 mt-1 h-1 w-full bg-paper-ink/10">
              <div
                className="h-1 bg-signal transition-all duration-700"
                style={{ width: `${Math.max((product.revenue / maxRevenue) * 100, 3)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
