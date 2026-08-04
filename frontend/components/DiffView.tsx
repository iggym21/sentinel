/**
 * Callout for `Brief.diff_from_prior` — a sentence already synthesized by the
 * backend (backend/agents/*_backend.py's `_compute_diff_from_prior`, Task 11)
 * describing what changed vs. the ticker's prior brief. This is NOT a
 * line-level text diff algorithm; it just presents the given string
 * prominently in a visually distinct "What changed" box.
 *
 * Color choice mirrors the existing indigo callout used inline on the brief
 * detail page (frontend/app/briefs/[id]/page.tsx) so the same signal reads
 * consistently wherever a diff appears.
 */

export default function DiffView({ diffText }: { diffText: string }) {
  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-200">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-indigo-500 dark:text-indigo-400">
        What changed
      </span>
      {diffText}
    </div>
  );
}
