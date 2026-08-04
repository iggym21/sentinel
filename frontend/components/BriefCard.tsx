import Link from "next/link";
import type { Brief } from "@/lib/types";
import ThesisBadge from "./ThesisBadge";
import ConfidenceMeter from "./ConfidenceMeter";

const SNIPPET_MAX_CHARS = 160;

function snippet(summary: string): string {
  if (summary.length <= SNIPPET_MAX_CHARS) {
    return summary;
  }
  return `${summary.slice(0, SNIPPET_MAX_CHARS).trimEnd()}…`;
}

function formatCreatedAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function BriefCard({ brief }: { brief: Brief }) {
  const { id, ticker_symbol, thesis, confidence, summary, created_at } = brief;

  return (
    <Link
      href={`/briefs/${id}`}
      className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {ticker_symbol}
        </span>
        <ThesisBadge thesis={thesis} />
      </div>

      <ConfidenceMeter confidence={confidence} />

      <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">{snippet(summary)}</p>

      <div className="mt-1 border-t border-zinc-100 pt-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        {formatCreatedAt(created_at)}
      </div>
    </Link>
  );
}
