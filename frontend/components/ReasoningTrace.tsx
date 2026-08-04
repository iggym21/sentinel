"use client";

/**
 * Renders an agent run's reasoning trace as an expandable vertical timeline.
 *
 * This is the demo's "wow factor" (sentinel-spec/docs/PRD.md §2) — it's the
 * one place a user watches the agent actually think, not just read its
 * conclusion. Design goals:
 *
 * - A colored left-side rail + per-type icon badge make the four step types
 *   (`tool_call` / `tool_result` / `reasoning` / `final`) instantly
 *   distinguishable at a glance, even fully collapsed.
 * - Every step is collapsed by default except the first, so the initial view
 *   is scannable rather than a wall of raw JSON.
 * - A "Step N of M" line plus a one-line preview of the step's input/output/
 *   text stays visible while collapsed, so users can decide what's worth
 *   expanding without opening it first.
 */

import { useState } from "react";
import type { TraceStep, TraceStepType } from "@/lib/types";

const PREVIEW_MAX_CHARS = 100;

function truncate(text: string, max: number): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  if (collapsed.length <= max) {
    return collapsed;
  }
  return `${collapsed.slice(0, max).trimEnd()}…`;
}

/** One-line preview of whichever field a step actually populates. */
function previewFor(step: TraceStep): string {
  const raw = step.text ?? step.input ?? step.output;
  if (raw === null || raw === undefined) {
    return "(no data)";
  }
  const text = typeof raw === "string" ? raw : JSON.stringify(raw);
  return truncate(text, PREVIEW_MAX_CHARS);
}

function ToolCallIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <path
        d="M6 4.5h8M6 4.5c0 2.5-1.5 3.5-2.5 4.5C4.5 10 6 11 6 13.5M14 4.5c0 2.5 1.5 3.5 2.5 4.5-1 1-2.5 2-2.5 4.5M6 13.5h8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ToolResultIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <path
        d="M4 3.5h9l3 3v10a.5.5 0 0 1-.5.5h-11.5a.5.5 0 0 1-.5-.5v-13a.5.5 0 0 1 .5-.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M7 10.5l2 2 4-4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ReasoningIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <path
        d="M10 3.5a5 5 0 0 0-3 9v1.5a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1V12.5a5 5 0 0 0-3-9Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M8.5 17h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function FinalIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.4" />
      <path d="M7 10.25l2 2 4-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UnknownIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.4" />
      <path d="M10 14v.01M10 6.5c1.4 0 2.25.8 2.25 1.9 0 1.4-2.25 1.6-2.25 3.35" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

interface StepStyle {
  label: string;
  icon: () => React.JSX.Element;
  /** Icon badge (circle) colors. */
  badgeClassName: string;
  /** Rail/connector line color below this step's badge. */
  railClassName: string;
  /** Accent color for the step's label text. */
  labelClassName: string;
}

const STEP_STYLES: Record<TraceStepType, StepStyle> = {
  tool_call: {
    label: "Tool Call",
    icon: ToolCallIcon,
    badgeClassName:
      "bg-indigo-50 text-indigo-600 ring-indigo-300 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-800",
    railClassName: "bg-indigo-200 dark:bg-indigo-900",
    labelClassName: "text-indigo-700 dark:text-indigo-300",
  },
  tool_result: {
    label: "Tool Result",
    icon: ToolResultIcon,
    badgeClassName:
      "bg-teal-50 text-teal-600 ring-teal-300 dark:bg-teal-950 dark:text-teal-300 dark:ring-teal-800",
    railClassName: "bg-teal-200 dark:bg-teal-900",
    labelClassName: "text-teal-700 dark:text-teal-300",
  },
  reasoning: {
    label: "Reasoning",
    icon: ReasoningIcon,
    badgeClassName:
      "bg-zinc-100 text-zinc-500 ring-zinc-300 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700",
    railClassName: "bg-zinc-200 dark:bg-zinc-800",
    labelClassName: "text-zinc-600 dark:text-zinc-400",
  },
  final: {
    label: "Final Answer",
    icon: FinalIcon,
    badgeClassName:
      "bg-emerald-50 text-emerald-600 ring-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
    railClassName: "bg-emerald-200 dark:bg-emerald-900",
    labelClassName: "text-emerald-700 dark:text-emerald-300",
  },
};

/**
 * Fallback used if a step's `type` isn't one of the four known
 * TraceStepType values. `TraceStep.type` is typed as the `TraceStepType`
 * literal union in lib/types.ts (not plain `string`), so this should be
 * unreachable given well-typed backend JSON — kept anyway since the trace
 * is untrusted JSON at runtime and a crash-safe lookup costs nothing
 * (mirrors StatusBadge.tsx's UNKNOWN_STATUS_STYLE pattern).
 */
const UNKNOWN_STEP_STYLE: StepStyle = {
  label: "Unknown Step",
  icon: UnknownIcon,
  badgeClassName:
    "bg-amber-50 text-amber-600 ring-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800",
  railClassName: "bg-amber-200 dark:bg-amber-900",
  labelClassName: "text-amber-700 dark:text-amber-300",
};

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

function PrettyField({ label, value }: { label: string; value: unknown }) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
        {label}
      </span>
      <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-50 p-3 font-mono text-xs leading-relaxed text-zinc-700 dark:bg-zinc-950 dark:text-zinc-300">
        {text}
      </pre>
    </div>
  );
}

function TraceStepItem({
  step,
  index,
  total,
  expanded,
  onToggle,
  isLast,
}: {
  step: TraceStep;
  index: number;
  total: number;
  expanded: boolean;
  onToggle: () => void;
  isLast: boolean;
}) {
  const style = STEP_STYLES[step.type] ?? UNKNOWN_STEP_STYLE;
  const Icon = style.icon;
  const contentId = `trace-step-${step.step}-content`;

  return (
    <li className="relative flex gap-4">
      <div className="flex flex-col items-center">
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1 ring-inset ${style.badgeClassName}`}
        >
          <Icon />
        </span>
        {!isLast && <span className={`w-px flex-1 ${style.railClassName}`} aria-hidden="true" />}
      </div>

      <div className="flex-1 pb-5">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={contentId}
          className="flex w-full flex-col gap-1 rounded-lg text-left"
        >
          <div className="flex items-center justify-between gap-3">
            <span className={`text-sm font-semibold ${style.labelClassName}`}>
              {style.label}
              {step.tool_name && (
                <span className="ml-1.5 font-mono text-xs font-normal text-zinc-500 dark:text-zinc-400">
                  {step.tool_name}
                </span>
              )}
            </span>
            <span className="flex shrink-0 items-center gap-2 text-xs text-zinc-400 dark:text-zinc-500">
              Step {index + 1} of {total}
              <svg
                viewBox="0 0 20 20"
                fill="none"
                className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
                aria-hidden="true"
              >
                <path d="M5 7.5l5 5 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </div>

          {!expanded && (
            <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{previewFor(step)}</p>
          )}
        </button>

        {expanded && (
          <div
            id={contentId}
            className="mt-2 flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
          >
            {step.text !== null && <PrettyField label="Text" value={step.text} />}
            {step.input !== null && <PrettyField label="Input" value={step.input} />}
            {step.output !== null && <PrettyField label="Output" value={step.output} />}
            {step.text === null && step.input === null && step.output === null && (
              <p className="text-xs text-zinc-400 dark:text-zinc-500">No data recorded for this step.</p>
            )}
            <span className="text-[11px] text-zinc-400 dark:text-zinc-500">
              {formatTimestamp(step.timestamp)}
            </span>
          </div>
        )}
      </div>
    </li>
  );
}

export default function ReasoningTrace({ trace }: { trace: TraceStep[] }) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(
    () => new Set(trace.length > 0 ? [trace[0].step] : [])
  );

  function toggle(stepNumber: number) {
    setExpandedSteps((current) => {
      const next = new Set(current);
      if (next.has(stepNumber)) {
        next.delete(stepNumber);
      } else {
        next.add(stepNumber);
      }
      return next;
    });
  }

  if (trace.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">No reasoning trace recorded for this run.</p>
    );
  }

  return (
    <ol className="flex flex-col">
      {trace.map((step, index) => (
        <TraceStepItem
          key={step.step}
          step={step}
          index={index}
          total={trace.length}
          expanded={expandedSteps.has(step.step)}
          onToggle={() => toggle(step.step)}
          isLast={index === trace.length - 1}
        />
      ))}
    </ol>
  );
}
