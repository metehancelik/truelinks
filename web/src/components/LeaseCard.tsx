"use client";

import { useState } from "react";
import { api, errorMessage, label, type Decision, type Lease, type LeaseField, type Rule } from "@/lib/api";
import { Badge, Button, Card, inputClass, Notice, Spinner, Trace } from "./ui";

/** A lease record: what the agent read, where it read it, and what a person decided. */
export function LeaseCard({ lease, onChange }: { lease: Lease; onChange: () => Promise<void> | void }) {
  const [error, setError] = useState<string | null>(null);
  // The action in flight, by key: its button shows a spinner and every other action waits.
  const [pending, setPending] = useState<string | null>(null);
  const reviewing = lease.status === "IN_REVIEW";
  const busy = pending !== null;

  /** Runs a decision; the API's refusal (and its reason) is shown as it is. */
  const act = async (key: string, action: () => Promise<unknown>) => {
    setPending(key);
    try {
      await action();
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    // Keep the spinner until the card shows the new state, not just until the API answered.
    await onChange();
    setPending(null);
  };

  // Fields that passed every check and still wait for a person: safe to accept in one go.
  const verifiedPending = lease.fields.filter((field) => field.status === "VERIFIED" && field.decision === "PENDING");
  const acceptVerified = () =>
    act("accept-verified", async () => {
      for (const field of verifiedPending) await api.decideField(lease.id, field.name, "ACCEPTED");
    });

  return (
    <Card
      title={<>Lease: {lease.filename}</>}
      aside={
        <>
          <Badge>{lease.status}</Badge>
          {reviewing && verifiedPending.length > 0 && (
            <Button disabled={busy} onClick={acceptVerified}>
              {pending === "accept-verified" && <Spinner />}
              Accept {verifiedPending.length} verified fields
            </Button>
          )}
          {reviewing && (
            <>
              <Button variant="primary" disabled={busy} onClick={() => act("activate", () => api.activateLease(lease.id))}>
                {pending === "activate" && <Spinner />}
                Activate lease
              </Button>
              <Button variant="danger" disabled={busy} onClick={() => act("reject", () => api.rejectLease(lease.id))}>
                {pending === "reject" && <Spinner />}
                Reject lease
              </Button>
            </>
          )}
        </>
      }
    >
      {error && <Notice tone="error">{error}</Notice>}
      {lease.status === "PROCESSING" && (
        <Notice tone="info">The agent is reading this lease. A local model needs a minute or two.</Notice>
      )}
      {lease.status === "FAILED" && <Notice tone="error">The agent could not process this lease: {lease.error}</Notice>}
      {lease.trace.some((step) => step.name === "read: ocr") && (
        <Notice tone="info">
          This lease is a scan and was read with OCR. A misread character shows up as an unverified field, so check those against
          the original.
        </Notice>
      )}
      {lease.trace.some((step) => step.name === "signatures") && (
        <details className="text-sm">
          <summary className="cursor-pointer text-zinc-700">Signature page the vision model checked</summary>
          {/* Served by the API from the uploads volume, so next/image has nothing to optimise. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={api.signaturePageUrl(lease.id)}
            alt="Last page of the scanned lease"
            className="mt-2 max-h-[32rem] rounded border border-zinc-200"
          />
        </details>
      )}
      {reviewing && !lease.unit_id && (
        <Notice tone="error">
          This lease is not linked to a unit. Correct the unit reference so it names one unit in the records.
        </Notice>
      )}

      {lease.fields.length > 0 && (
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full min-w-[52rem] text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-zinc-500">
              <tr className="border-b border-zinc-200">
                <th className="w-[11rem] pb-2 pl-5 pr-4 font-medium">Field</th>
                <th className="pb-2 pr-4 font-medium">Value</th>
                <th className="pb-2 pr-4 font-medium">Source in the lease</th>
                <th className="pb-2 pr-4 font-medium">Check</th>
                <th className="pb-2 pr-5 font-medium">Your decision</th>
              </tr>
            </thead>
            <tbody>
              {lease.fields.map((field) => (
                <FieldRow
                  key={field.name}
                  field={field}
                  editable={reviewing}
                  busy={busy}
                  pending={pending?.startsWith(`field:${field.name}:`) ? (pending.split(":")[2] as Decision) : null}
                  decide={(decision, value) =>
                    act(`field:${field.name}:${decision}`, () => api.decideField(lease.id, field.name, decision, value))
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {lease.rules.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-zinc-900">Owner rules</h3>
          <ul className="divide-y divide-zinc-100 overflow-hidden rounded-lg border border-zinc-200">
            {lease.rules.map((rule) => (
              <RuleRow
                key={rule.id}
                rule={rule}
                editable={reviewing}
                busy={busy}
                pending={pending?.startsWith(`rule:${rule.id}:`) ? (pending.split(":")[2] as Decision) : null}
                decide={(decision) => act(`rule:${rule.id}:${decision}`, () => api.decideRule(lease.id, rule.id, decision))}
              />
            ))}
          </ul>
        </div>
      )}

      <Trace steps={lease.trace} />
    </Card>
  );
}

function FieldRow({
  field,
  editable,
  busy,
  pending,
  decide,
}: {
  field: LeaseField;
  editable: boolean;
  busy: boolean;
  pending: Decision | null;
  decide: (decision: Decision, value?: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  // A decided field shows its decision; its buttons come back only when a person asks to change it.
  const [changing, setChanging] = useState(false);
  const corrected = field.decision === "CORRECTED";
  const decided = field.decision !== "PENDING";
  const choosing = editable && draft === null && (!decided || changing);

  const choose = async (decision: Decision, value?: string) => {
    await decide(decision, value);
    setChanging(false);
    setDraft(null);
  };

  return (
    <tr className={`border-t border-zinc-100 align-top first:border-t-0 ${field.status === "UNVERIFIED" ? "bg-amber-50/40" : ""}`}>
      <td className="py-3 pl-5 pr-4 font-medium text-zinc-700">{label(field.name)}</td>
      <td className="py-3 pr-4">
        <span
          className={
            corrected || field.decision === "REJECTED"
              ? "text-zinc-500 line-through"
              : field.value === null
                ? "italic text-zinc-500"
                : "text-zinc-900"
          }
        >
          {field.value === null ? "not found" : String(field.value)}
        </span>
        {corrected && <div className="font-medium text-zinc-900">{String(field.corrected_value)}</div>}
      </td>
      <td className="max-w-[16rem] py-3 pr-4">
        {field.quote && (
          <q className="block border-l border-zinc-300 pl-2.5 text-[13px] leading-snug text-zinc-600">{field.quote}</q>
        )}
      </td>
      <td className="py-3 pr-4">
        <Badge>{field.status}</Badge>
        {field.issue && (
          <div className="mt-1.5 text-xs font-medium text-amber-900">{field.issue.replaceAll("_", " ").toLowerCase()}</div>
        )}
        {field.explanation && <div className="mt-1 max-w-xs text-xs leading-relaxed text-zinc-600">{field.explanation}</div>}
      </td>
      <td className="py-3 pr-5">
        {decided && !choosing && draft === null && (
          <div className="flex items-center gap-2 whitespace-nowrap">
            <Badge>{field.decision}</Badge>
            {editable && (
              <ChangeButton disabled={busy} onClick={() => setChanging(true)} />
            )}
          </div>
        )}
        {choosing && (
          <div className="flex gap-1.5 whitespace-nowrap">
            <Button disabled={busy} onClick={() => choose("ACCEPTED")}>
              {pending === "ACCEPTED" && <Spinner />}
              Accept
            </Button>
            <Button disabled={busy} onClick={() => choose("REJECTED")}>
              {pending === "REJECTED" && <Spinner />}
              Reject
            </Button>
            <Button disabled={busy} onClick={() => setDraft(String(field.corrected_value ?? field.value ?? ""))}>
              Correct
            </Button>
            {changing && (
              <Button disabled={busy} onClick={() => setChanging(false)}>
                Cancel
              </Button>
            )}
          </div>
        )}
        {editable && draft !== null && (
          <form
            className="flex gap-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              void choose("CORRECTED", draft);
            }}
          >
            <input
              autoFocus
              aria-label={`Corrected ${label(field.name)}`}
              className={`${inputClass} h-8 w-40 py-0`}
              value={draft}
              disabled={busy}
              onChange={(event) => setDraft(event.target.value)}
            />
            <Button variant="primary" type="submit" disabled={busy}>
              {pending === "CORRECTED" && <Spinner />}
              Save
            </Button>
            <Button type="button" disabled={busy} onClick={() => setDraft(null)}>
              Cancel
            </Button>
          </form>
        )}
      </td>
    </tr>
  );
}

function RuleRow({
  rule,
  editable,
  busy,
  pending,
  decide,
}: {
  rule: Rule;
  editable: boolean;
  busy: boolean;
  pending: Decision | null;
  decide: (decision: Decision) => Promise<void>;
}) {
  const [changing, setChanging] = useState(false);
  const flagged = rule.outcome !== "PASS";
  const decided = rule.decision !== "PENDING";
  const choosing = flagged && editable && (!decided || changing);

  const choose = async (decision: Decision) => {
    await decide(decision);
    setChanging(false);
  };

  return (
    <li className={`flex flex-wrap items-start gap-x-3 gap-y-2 px-4 py-3 text-sm ${flagged ? "bg-white" : "bg-zinc-50/60"}`}>
      <span className="w-7 pt-0.5 font-mono text-xs font-medium text-zinc-500">{rule.id}</span>
      <Badge>{rule.outcome}</Badge>
      <div className="min-w-[12rem] flex-1">
        <div className={flagged ? "text-zinc-900" : "text-zinc-600"}>{rule.reason}</div>
        <div className="mt-0.5 text-xs leading-relaxed text-zinc-500">
          {rule.description} Severity: {rule.severity}.
        </div>
      </div>
      {flagged && decided && !choosing && (
        <div className="flex items-center gap-2 whitespace-nowrap">
          <Badge tone="gray">{rule.decision === "ACCEPTED" ? "ACKNOWLEDGED" : "DISMISSED"}</Badge>
          {editable && (
            <ChangeButton disabled={busy} onClick={() => setChanging(true)} />
          )}
        </div>
      )}
      {choosing && (
        <div className="flex gap-1.5">
          <Button disabled={busy} onClick={() => choose("ACCEPTED")}>
            {pending === "ACCEPTED" && <Spinner />}
            Acknowledge
          </Button>
          <Button disabled={busy} onClick={() => choose("REJECTED")}>
            {pending === "REJECTED" && <Spinner />}
            Dismiss
          </Button>
          {changing && (
            <Button disabled={busy} onClick={() => setChanging(false)}>
              Cancel
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

/** Reopens a decision that was already made. */
function ChangeButton({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded text-xs font-medium text-zinc-500 underline decoration-zinc-300 underline-offset-4 hover:text-zinc-900 hover:decoration-zinc-900 disabled:opacity-40"
    >
      Change
    </button>
  );
}
