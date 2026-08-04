import Link from "next/link";
import BriefCard from "@/components/BriefCard";
import DiffView from "@/components/DiffView";
import { getTickerHistory } from "@/lib/api";
import type { Brief } from "@/lib/types";

export default async function TickerHistoryPage(props: PageProps<"/tickers/[symbol]">) {
  const { symbol } = await props.params;

  let briefs: Brief[] = [];
  let diff: string | null = null;
  let error: string | null = null;

  try {
    const history = await getTickerHistory(symbol);
    briefs = history.briefs;
    diff = history.diff;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load ticker history";
  }

  const sorted = [...briefs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-10">
      <Link
        href="/"
        className="flex w-fit items-center gap-1.5 text-sm font-medium text-zinc-500 transition-colors hover:text-teal-600 dark:text-zinc-400 dark:hover:text-teal-400"
      >
        <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
          <path d="M12.5 15 7.5 10l5-5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back to Watchlist
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {symbol}
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          {briefs.length} brief{briefs.length === 1 ? "" : "s"} on record
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}

      {!error && diff && <DiffView diffText={diff} />}

      {!error &&
        (sorted.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-300 px-6 py-16 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
            No briefs yet for {symbol}.
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
              Brief history
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {sorted.map((brief) => (
                <BriefCard key={brief.id} brief={brief} />
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}
