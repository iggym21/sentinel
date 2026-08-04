/**
 * Small pill badge showing a ticker's current watch status.
 *
 * Color mapping is intentional (see task-17-report.md for rationale):
 * - quiet         -> neutral zinc  (nothing happening)
 * - investigating -> indigo        (agent actively working)
 * - triggered     -> rose          (needs attention now)
 */

export type Status = "quiet" | "triggered" | "investigating";

const STATUS_STYLES: Record<Status, { label: string; className: string }> = {
  quiet: {
    label: "Quiet",
    className:
      "bg-zinc-100 text-zinc-600 ring-zinc-300 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700",
  },
  investigating: {
    label: "Investigating",
    className:
      "bg-indigo-50 text-indigo-700 ring-indigo-300 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-800",
  },
  triggered: {
    label: "Triggered",
    className:
      "bg-rose-50 text-rose-700 ring-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-800",
  },
};

export default function StatusBadge({ status }: { status: Status }) {
  const style = STATUS_STYLES[status];

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {style.label}
    </span>
  );
}
