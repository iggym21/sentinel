/**
 * 1-5 confidence meter rendered as five dots, filled up to `confidence`.
 *
 * Backend range is fixed at [1, 5] (see backend/agents/heuristic_backend.py
 * and backend/agents/tools/schemas.py's `confidence` field), so this clamps
 * defensively rather than assuming callers always pass an in-range integer.
 */

const MAX_CONFIDENCE = 5;

export default function ConfidenceMeter({ confidence }: { confidence: number }) {
  const clamped = Math.max(0, Math.min(MAX_CONFIDENCE, Math.round(confidence)));
  const dots = Array.from({ length: MAX_CONFIDENCE }, (_, i) => i < clamped);

  return (
    <div className="flex items-center gap-2" title={`Confidence: ${confidence}/${MAX_CONFIDENCE}`}>
      <div className="flex items-center gap-1" role="img" aria-label={`Confidence ${confidence} out of ${MAX_CONFIDENCE}`}>
        {dots.map((filled, i) => (
          <span
            key={i}
            className={`h-2 w-2 rounded-full ${
              filled
                ? "bg-teal-500 dark:bg-teal-400"
                : "bg-zinc-200 dark:bg-zinc-700"
            }`}
            aria-hidden="true"
          />
        ))}
      </div>
      <span className="text-xs font-medium tabular-nums text-zinc-500 dark:text-zinc-400">
        {confidence}/{MAX_CONFIDENCE}
      </span>
    </div>
  );
}
