import Link from "next/link";
import ThesisBadge from "@/components/ThesisBadge";
import ConfidenceMeter from "@/components/ConfidenceMeter";
import ReasoningTrace from "@/components/ReasoningTrace";
import { getBrief } from "@/lib/api";
import type { BriefDetail } from "@/lib/types";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const SUGGESTED_ACTION_STYLES: Record<string, string> = {
  buy: "bg-emerald-50 text-emerald-700 ring-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
  sell: "bg-rose-50 text-rose-700 ring-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-800",
  hold: "bg-zinc-100 text-zinc-600 ring-zinc-300 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700",
};

export default async function BriefDetailPage(props: PageProps<"/briefs/[id]">) {
  const { id } = await props.params;
  const briefId = Number(id);

  let brief: BriefDetail | null = null;
  let error: string | null = null;

  if (!Number.isInteger(briefId)) {
    error = `Invalid brief id: "${id}"`;
  } else {
    try {
      brief = await getBrief(briefId);
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to load brief";
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-10">
      <Link
        href="/briefs"
        className="flex w-fit items-center gap-1.5 text-sm font-medium text-zinc-500 transition-colors hover:text-teal-600 dark:text-zinc-400 dark:hover:text-teal-400"
      >
        <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
          <path d="M12.5 15 7.5 10l5-5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back to Briefs
      </Link>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}

      {brief && (
        <>
          <div className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                  {brief.ticker_symbol}
                </h1>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  Brief #{brief.id} · {formatDateTime(brief.created_at)}
                </p>
              </div>
              <ThesisBadge thesis={brief.thesis} />
            </div>

            <ConfidenceMeter confidence={brief.confidence} />

            <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{brief.summary}</p>

            {brief.suggested_action && (
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium text-zinc-500 dark:text-zinc-400">Suggested action:</span>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium uppercase tracking-wide ring-1 ring-inset ${
                    SUGGESTED_ACTION_STYLES[brief.suggested_action] ?? SUGGESTED_ACTION_STYLES.hold
                  }`}
                >
                  {brief.suggested_action}
                </span>
              </div>
            )}

            {brief.diff_from_prior && (
              <div className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-200">
                <span className="font-semibold">Change since prior brief: </span>
                {brief.diff_from_prior}
              </div>
            )}

            {brief.evidence.length > 0 && (
              <div className="flex flex-col gap-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
                <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Evidence</h2>
                <ul className="flex flex-col gap-2">
                  {brief.evidence.map((item, i) => (
                    <li
                      key={i}
                      className="rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"
                    >
                      <p>{item.claim}</p>
                      <p className="mt-1 font-mono text-xs text-zinc-400 dark:text-zinc-500">
                        {item.source_tool}
                        {item.source_ref ? ` · ${item.source_ref}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                Reasoning Trace
              </h2>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                Step-by-step record of how the agent reached this brief.
              </p>
            </div>
            <ReasoningTrace trace={brief.agent_run.trace} />
          </div>
        </>
      )}
    </div>
  );
}
