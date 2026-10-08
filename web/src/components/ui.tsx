import type { ButtonHTMLAttributes, ReactNode } from "react";

const TONES = {
  green: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  amber: "bg-amber-50 text-amber-900 ring-amber-600/25",
  red: "bg-red-50 text-red-800 ring-red-600/20",
  gray: "bg-zinc-50 text-zinc-600 ring-zinc-500/20",
  blue: "bg-sky-50 text-sky-800 ring-sky-600/20",
} as const;

const DOTS = {
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
  gray: "bg-zinc-400",
  blue: "bg-sky-500",
} as const;

export type Tone = keyof typeof TONES;

/** One colour per meaning across the app: green is settled, amber needs a look, red is a problem. */
const TONE_BY_WORD: Record<string, Tone> = {
  VERIFIED: "green",
  PASS: "green",
  ACTIVE: "green",
  ACCEPTED: "green",
  available: "green",
  new: "green",
  good: "green",
  UNVERIFIED: "amber",
  NOT_DETERMINABLE: "amber",
  IN_REVIEW: "amber",
  OPEN: "amber",
  CORRECTED: "amber",
  worn: "amber",
  medium: "amber",
  FAIL: "red",
  FAILED: "red",
  REJECTED: "red",
  damaged: "red",
  high: "red",
  PROCESSING: "blue",
  occupied: "blue",
};

export function Badge({ children, tone }: { children: string; tone?: Tone }) {
  const key = tone ?? TONE_BY_WORD[children] ?? "gray";
  // The only moving thing on the page: work the agent is still doing.
  const working = children === "PROCESSING";
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[key]}`}
    >
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${DOTS[key]} ${working ? "motion-safe:animate-pulse" : ""}`} />
      {children.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "plain" | "danger";
};

export function Button({ variant = "plain", className = "", ...props }: ButtonProps) {
  const variants = {
    primary: "bg-zinc-900 text-white shadow-sm hover:bg-zinc-700",
    plain: "bg-white text-zinc-800 shadow-xs ring-1 ring-inset ring-zinc-300 hover:bg-zinc-50 hover:ring-zinc-400",
    danger: "bg-white text-red-700 shadow-xs ring-1 ring-inset ring-red-200 hover:bg-red-50 hover:ring-red-300",
  };
  return (
    <button
      {...props}
      className={`inline-flex h-8 items-center justify-center whitespace-nowrap rounded-md px-3 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]} ${className}`}
    />
  );
}

/** Shared look for text inputs and textareas. */
export const inputClass =
  "w-full rounded-md bg-white px-3 py-1.5 text-sm text-zinc-900 shadow-xs ring-1 ring-inset ring-zinc-300 placeholder:text-zinc-500 focus:outline-2 focus:outline-offset-0 focus:outline-zinc-900 focus:ring-0 disabled:bg-zinc-50 disabled:text-zinc-500";

/** Shared look for native file pickers. */
export const fileInputClass =
  "max-w-full text-sm text-zinc-600 file:mr-3 file:h-8 file:cursor-pointer file:rounded-md file:border-0 file:bg-zinc-100 file:px-3 file:text-sm file:font-medium file:text-zinc-800 hover:file:bg-zinc-200";

/** Shown inside a button while its request is in flight. */
export function Spinner() {
  return (
    <span
      aria-hidden
      className="mr-1.5 inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}

export function Card({ title, aside, children }: { title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white shadow-[0_1px_2px_rgb(24_24_27/0.04)]">
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-zinc-100 px-5 py-3.5">
        <h2 className="min-w-0 break-words font-semibold tracking-tight">{title}</h2>
        {aside && <div className="flex flex-wrap items-center gap-2">{aside}</div>}
      </header>
      <div className="space-y-5 p-5">{children}</div>
    </section>
  );
}

export function Notice({ tone, children }: { tone: "error" | "info"; children: ReactNode }) {
  const colour = tone === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-sky-200 bg-sky-50 text-sky-900";
  return <p className={`rounded-lg border px-3.5 py-2.5 text-sm leading-relaxed ${colour}`}>{children}</p>;
}

/** A section heading inside a page. */
export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-lg font-semibold tracking-tight text-zinc-900">{children}</h2>;
}

export function Trace({ steps }: { steps: { name: string; model: string | null; duration_ms: number; input_tokens: number; output_tokens: number }[] }) {
  if (steps.length === 0) return null;
  return (
    <details className="group border-t border-zinc-100 pt-4 text-sm text-zinc-600">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded font-medium text-zinc-600 hover:text-zinc-900 [&::-webkit-details-marker]:hidden">
        <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5 transition-transform duration-150 group-open:rotate-90">
          <path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        What the agent did
      </summary>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-[13px]">
          <tbody>
            {steps.map((step) => (
              <tr key={step.name} className="border-t border-zinc-100 first:border-t-0">
                <td className="py-1.5 pr-4 font-medium text-zinc-800">{step.name}</td>
                <td className="pr-4 font-mono text-xs">{step.model ?? "code"}</td>
                <td className="pr-4 text-right">{(step.duration_ms / 1000).toFixed(1)}s</td>
                <td className="text-zinc-500">
                  {step.model ? `${step.input_tokens} tokens in, ${step.output_tokens} out` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
