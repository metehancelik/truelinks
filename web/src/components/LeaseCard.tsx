"use client";

import { useState } from "react";
import { api, errorMessage, label, type Decision, type Lease, type LeaseField, type Rule } from "@/lib/api";
import { Badge, Button, Card, Notice, Trace } from "./ui";

/** A lease record: what the agent read, where it read it, and what a person decided. */
export function LeaseCard({ lease, onChange }: { lease: Lease; onChange: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const reviewing = lease.status === "IN_REVIEW";

  /** Runs a decision; the API's refusal (and its reason) is shown as it is. */
  const act = async (action: () => Promise<unknown>) => {
    try {
      await action();
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    onChange();
  };

  // Fields that passed every check and still wait for a person: safe to accept in one go.
  const verifiedPending = lease.fields.filter((field) => field.status === "VERIFIED" && field.decision === "PENDING");
  const acceptVerified = () =>
    act(async () => {
      for (const field of verifiedPending) await api.decideField(lease.id, field.name, "ACCEPTED");
    });

  return (
    <Card
      title={<>Lease: {lease.filename}</>}
      aside={
        <>
          <Badge>{lease.status}</Badge>
          {reviewing && verifiedPending.length > 0 && (
            <Button onClick={acceptVerified}>Accept {verifiedPending.length} verified fields</Button>
          )}
          {reviewing && (
            <>
              <Button variant="primary" onClick={() => act(() => api.activateLease(lease.id))}>
                Activate lease
              </Button>
              <Button variant="danger" onClick={() => act(() => api.rejectLease(lease.id))}>
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
      {reviewing && !lease.unit_id && (
        <Notice tone="error">
          This lease is not linked to a unit. Correct the unit reference so it names one unit in the records.
        </Notice>
      )}

      {lease.fields.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-500">
              <tr>
                <th className="py-2 pr-3">Field</th>
                <th className="pr-3">Value</th>
                <th className="pr-3">Source in the lease</th>
                <th className="pr-3">Check</th>
                <th>Your decision</th>
              </tr>
            </thead>
            <tbody>
              {lease.fields.map((field) => (
                <FieldRow
                  key={field.name}
                  field={field}
                  editable={reviewing}
                  decide={(decision, value) => act(() => api.decideField(lease.id, field.name, decision, value))}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {lease.rules.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Owner rules</h3>
          <ul className="space-y-2">
            {lease.rules.map((rule) => (
              <RuleRow
                key={rule.id}
                rule={rule}
                editable={reviewing}
                decide={(decision) => act(() => api.decideRule(lease.id, rule.id, decision))}
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
  decide,
}: {
  field: LeaseField;
  editable: boolean;
  decide: (decision: Decision, value?: string) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const corrected = field.decision === "CORRECTED";

  return (
    <tr className="border-t border-zinc-100 align-top">
      <td className="py-2 pr-3 font-medium">{label(field.name)}</td>
      <td className="pr-3">
        <span className={corrected || field.decision === "REJECTED" ? "text-zinc-400 line-through" : ""}>
          {field.value === null ? "not found" : String(field.value)}
        </span>
        {corrected && <div className="font-medium">{String(field.corrected_value)}</div>}
      </td>
      <td className="max-w-[16rem] pr-3 text-zinc-600">{field.quote ? <q>{field.quote}</q> : ""}</td>
      <td className="pr-3">
        <Badge>{field.status}</Badge>
        {field.issue && <div className="mt-1 text-xs text-amber-900">{field.issue.replaceAll("_", " ").toLowerCase()}</div>}
        {field.explanation && <div className="mt-1 max-w-xs text-xs text-zinc-600">{field.explanation}</div>}
      </td>
      <td>
        {field.decision !== "PENDING" && <Badge>{field.decision}</Badge>}
        {editable && draft === null && (
          <div className="mt-1 flex gap-1 whitespace-nowrap">
            <Button onClick={() => decide("ACCEPTED")}>Accept</Button>
            <Button onClick={() => decide("REJECTED")}>Reject</Button>
            <Button onClick={() => setDraft(String(field.corrected_value ?? field.value ?? ""))}>Correct</Button>
          </div>
        )}
        {editable && draft !== null && (
          <form
            className="mt-1 flex gap-1"
            onSubmit={(event) => {
              event.preventDefault();
              decide("CORRECTED", draft);
              setDraft(null);
            }}
          >
            <input
              autoFocus
              aria-label={`Corrected ${label(field.name)}`}
              className="w-40 rounded border border-zinc-300 px-2 py-1 text-sm"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <Button variant="primary" type="submit">
              Save
            </Button>
            <Button type="button" onClick={() => setDraft(null)}>
              Cancel
            </Button>
          </form>
        )}
      </td>
    </tr>
  );
}

function RuleRow({ rule, editable, decide }: { rule: Rule; editable: boolean; decide: (decision: Decision) => void }) {
  const flagged = rule.outcome !== "PASS";
  return (
    <li className="flex flex-wrap items-start gap-3 rounded border border-zinc-100 px-3 py-2 text-sm">
      <span className="w-8 font-mono font-medium">{rule.id}</span>
      <Badge>{rule.outcome}</Badge>
      <div className="min-w-0 flex-1">
        <div>{rule.reason}</div>
        <div className="text-xs text-zinc-500">
          {rule.description} Severity: {rule.severity}.
        </div>
      </div>
      {flagged && rule.decision !== "PENDING" && (
        <Badge tone="gray">{rule.decision === "ACCEPTED" ? "ACKNOWLEDGED" : "DISMISSED"}</Badge>
      )}
      {flagged && editable && (
        <div className="flex gap-1">
          <Button onClick={() => decide("ACCEPTED")}>Acknowledge</Button>
          <Button onClick={() => decide("REJECTED")}>Dismiss</Button>
        </div>
      )}
    </li>
  );
}
