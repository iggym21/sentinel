"use client";

import Link from "next/link";
import type { WatchlistEntry } from "@/lib/types";
import StatusBadge, { type Status } from "./StatusBadge";

interface WatchlistCardProps {
  entry: WatchlistEntry;
  onRemove: (symbol: string) => void;
}

function formatPrice(price: number | null): string {
  if (price === null) {
    return "—";
  }
  return `$${price.toFixed(2)}`;
}

function formatChangePct(pct: number | null): string {
  if (pct === null) {
    return "—";
  }
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function changeColorClass(pct: number | null): string {
  if (pct === null || pct === 0) {
    return "text-zinc-500 dark:text-zinc-400";
  }
  return pct > 0
    ? "text-emerald-600 dark:text-emerald-400"
    : "text-rose-600 dark:text-rose-400";
}

function formatLastBrief(iso: string | null): string {
  if (!iso) {
    return "No briefs yet";
  }
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function WatchlistCard({ entry, onRemove }: WatchlistCardProps) {
  const { symbol, latest_price, day_change_pct, status, last_brief_at } = entry;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between gap-3">
        <Link
          href={`/tickers/${symbol}`}
          className="text-lg font-semibold tracking-tight text-zinc-900 hover:text-teal-600 dark:text-zinc-50 dark:hover:text-teal-400"
        >
          {symbol}
        </Link>
        <StatusBadge status={status as Status} />
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
          {formatPrice(latest_price)}
        </span>
        <span className={`text-sm font-medium tabular-nums ${changeColorClass(day_change_pct)}`}>
          {formatChangePct(day_change_pct)}
        </span>
      </div>

      <div className="flex items-center justify-between border-t border-zinc-100 pt-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        <span>Last brief: {formatLastBrief(last_brief_at)}</span>
        <button
          type="button"
          onClick={() => onRemove(symbol)}
          className="rounded-md px-2 py-1 font-medium text-zinc-500 transition-colors hover:bg-rose-50 hover:text-rose-600 dark:text-zinc-400 dark:hover:bg-rose-950 dark:hover:text-rose-400"
        >
          Remove
        </button>
      </div>
    </div>
  );
}
