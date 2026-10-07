import type { ButtonHTMLAttributes, ReactNode } from "react";

const TONES = {
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-900",
  red: "bg-red-100 text-red-800",
  gray: "bg-zinc-100 text-zinc-700",
  blue: "bg-sky-100 text-sky-800",
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
  const colour = TONES[tone ?? TONE_BY_WORD[children] ?? "gray"];
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${colour}`}>
      {children.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "plain" | "danger";
};

export function Button({ variant = "plain", className = "", ...props }: ButtonProps) {
  const variants = {
    primary: "bg-zinc-900 text-white hover:bg-zinc-700",
    plain: "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-50",
    danger: "border border-red-300 bg-white text-red-700 hover:bg-red-50",
  };
  return (
    <button
      {...props}
      className={`rounded px-2.5 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]} ${className}`}
    />
  );
}

/** Shown inside a button while its request is in flight. */
export function Spinner() {
  return (
    <span
      aria-hidden
      className="mr-1.5 inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent align-[-1px]"
    />
  );
}

export function Card({ title, aside, children }: { title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3">
        <h2 className="font-semibold">{title}</h2>
        <div className="flex items-center gap-2">{aside}</div>
      </header>
      <div className="space-y-4 p-4">{children}</div>
    </section>
  );
}

export function Notice({ tone, children }: { tone: "error" | "info"; children: ReactNode }) {
  const colour = tone === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-sky-200 bg-sky-50 text-sky-900";
  return <p className={`rounded border px-3 py-2 text-sm ${colour}`}>{children}</p>;
}

export function Trace({ steps }: { steps: { name: string; model: string | null; duration_ms: number; input_tokens: number; output_tokens: number }[] }) {
  if (steps.length === 0) return null;
  return (
    <details className="text-sm text-zinc-600">
      <summary className="cursor-pointer">What the agent did</summary>
      <table className="mt-2 w-full text-left">
        <tbody>
          {steps.map((step) => (
            <tr key={step.name} className="border-t border-zinc-100">
              <td className="py-1 pr-4 font-medium">{step.name}</td>
              <td className="pr-4">{step.model ?? "code"}</td>
              <td className="pr-4 tabular-nums">{(step.duration_ms / 1000).toFixed(1)}s</td>
              <td className="tabular-nums">
                {step.model ? `${step.input_tokens} tokens in, ${step.output_tokens} out` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
