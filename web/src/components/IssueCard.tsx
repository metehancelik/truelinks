"use client";

import { useState } from "react";
import { api, errorMessage, type Decision, type Issue, type WorkOrder } from "@/lib/api";
import { Badge, Button, Card, inputClass, Notice, Spinner, Trace } from "./ui";

const FLAG_TEXT: Record<string, string> = {
  INVALID_PHOTO_REFERENCE: "A finding points at a photo that was not sent. Check the assessment against the photos.",
  NO_VISIBLE_DAMAGE: "The photos show no damage. An inspection may be needed before any work.",
};

/** A reported issue: the photos, what the agent saw in them, and its draft work order. */
export function IssueCard({ issue, onChange }: { issue: Issue; onChange: () => void }) {
  const photos = Array.from({ length: issue.photo_count }, (_, index) => index + 1);

  return (
    <Card title={<>Issue: {issue.note || "no note"}</>} aside={<Badge>{issue.status}</Badge>}>
      {issue.status === "PROCESSING" && (
        <Notice tone="info">The agent is looking at the photos. A local model needs a minute or two.</Notice>
      )}
      {issue.status === "FAILED" && <Notice tone="error">The agent could not assess this report: {issue.error}</Notice>}
      {issue.flags.map((flag) => (
        <Notice key={flag} tone="error">
          {FLAG_TEXT[flag] ?? flag}
        </Notice>
      ))}

      <div className="flex flex-wrap gap-3">
        {photos.map((photo) => (
          <figure key={photo} className="space-y-1.5 text-xs text-zinc-500">
            {/* Served by the API from the uploads volume, so next/image has nothing to optimise. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={api.photoUrl(issue.id, photo)}
              alt={`Reported photo ${photo}`}
              className="h-28 w-28 rounded-lg bg-zinc-100 object-cover ring-1 ring-zinc-200 sm:h-32 sm:w-32"
            />
            <figcaption>Photo {photo}</figcaption>
          </figure>
        ))}
      </div>

      {issue.assessment && (
        <div className="grid gap-6 text-sm md:grid-cols-2">
          <div>
            <h3 className="mb-2 flex items-center gap-2 font-semibold text-zinc-900">
              Condition <Badge>{issue.assessment.overall_condition}</Badge>
            </h3>
            <ul className="list-disc space-y-1.5 pl-5 leading-relaxed marker:text-zinc-400">
              {issue.assessment.damages.map((damage, index) => (
                <li key={index}>
                  {damage.description} <span className="text-zinc-500">(photo {damage.photo})</span>
                </li>
              ))}
              {issue.assessment.damages.length === 0 && <li className="text-zinc-500">No visible damage.</li>}
            </ul>
          </div>
          <div>
            <h3 className="mb-2 font-semibold text-zinc-900">Contents and equipment</h3>
            <ul className="space-y-1.5">
              {issue.assessment.equipment.map((item, index) => (
                <li key={index} className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  {item.name} <Badge>{item.condition}</Badge> <span className="text-zinc-500">(photo {item.photo})</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {issue.work_order && <WorkOrderForm workOrder={issue.work_order} onChange={onChange} />}
      <Trace steps={issue.trace} />
    </Card>
  );
}

function WorkOrderForm({ workOrder, onChange }: { workOrder: WorkOrder; onChange: () => void }) {
  const [title, setTitle] = useState(workOrder.title);
  const [description, setDescription] = useState(workOrder.description);
  const [saving, setSaving] = useState<Decision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const decided = workOrder.decision !== "PENDING";
  const edited = workOrder.title !== workOrder.draft.title || workOrder.description !== workOrder.draft.description;

  const decide = async (decision: Decision) => {
    setSaving(decision);
    try {
      await api.decideWorkOrder(workOrder.id, decision, { title, description });
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    setSaving(null);
    onChange();
  };

  return (
    <div className={`space-y-3 rounded-lg border p-4 text-sm ${decided ? "border-zinc-200 bg-white" : "border-zinc-200 bg-zinc-50"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-1 font-semibold text-zinc-900">{decided ? "Work order" : "Draft work order"}</h3>
        <Badge>{workOrder.decision}</Badge>
        <span className="inline-flex items-center gap-1.5 text-zinc-600">
          Urgency: <Badge>{workOrder.urgency}</Badge>
        </span>
        {edited && <span className="text-xs text-zinc-500">Edited. The agent wrote: “{workOrder.draft.title}”</span>}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {decided ? (
        // A decided work order is a record of what was agreed, so it is no longer editable.
        <>
          <p className="font-medium text-zinc-900">{workOrder.title}</p>
          <p className="max-w-prose whitespace-pre-wrap leading-relaxed text-zinc-700">{workOrder.description}</p>
        </>
      ) : (
        <>
          <input
            aria-label="Work order title"
            className={`${inputClass} font-medium`}
            value={title}
            disabled={saving !== null}
            onChange={(event) => setTitle(event.target.value)}
          />
          <textarea
            aria-label="Work order description"
            className={`${inputClass} leading-relaxed`}
            rows={3}
            value={description}
            disabled={saving !== null}
            onChange={(event) => setDescription(event.target.value)}
          />
          <div className="flex gap-2">
            <Button variant="primary" disabled={saving !== null} onClick={() => decide("ACCEPTED")}>
              {saving === "ACCEPTED" && <Spinner />}
              Accept work order
            </Button>
            <Button variant="danger" disabled={saving !== null} onClick={() => decide("REJECTED")}>
              {saving === "REJECTED" && <Spinner />}
              Reject
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
