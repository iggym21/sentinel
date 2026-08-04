/**
 * Small pill badge showing a brief's thesis.
 *
 * Color mapping mirrors the day-change convention established in
 * WatchlistCard.tsx (emerald = positive/bullish, rose = negative/bearish)
 * rather than reusing StatusBadge's indigo/rose/zinc set, so a thesis badge
 * never gets visually confused with a watch-status badge:
 * - bullish -> emerald  (positive outlook)
 * - bearish -> rose     (negative outlook)
 * - neutral -> zinc     (no directional lean)
 */

import type { Thesis } from "@/lib/types";

const THESIS_STYLES: Record<Thesis, { label: string; className: string }> = {
  bullish: {
    label: "Bullish",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
  },
  bearish: {
    label: "Bearish",
    className:
      "bg-rose-50 text-rose-700 ring-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-800",
  },
  neutral: {
    label: "Neutral",
    className:
      "bg-zinc-100 text-zinc-600 ring-zinc-300 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700",
  },
};

/**
 * Fallback used if `thesis` isn't one of the known Thesis values. `Brief.thesis`
 * is typed as the `Thesis` literal union in lib/types.ts (unlike
 * WatchlistEntry.status, which is plain `string`), so this should be
 * unreachable given well-typed backend JSON — kept anyway since the type
 * system can't guarantee runtime JSON actually matches it, and a crash-safe
 * lookup costs nothing (mirrors StatusBadge.tsx's UNKNOWN_STATUS_STYLE).
 */
const UNKNOWN_THESIS_STYLE = {
  label: "Unknown",
  className:
    "bg-amber-50 text-amber-700 ring-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800",
};

export default function ThesisBadge({ thesis }: { thesis: Thesis }) {
  const style = THESIS_STYLES[thesis] ?? UNKNOWN_THESIS_STYLE;

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {style.label}
    </span>
  );
}
