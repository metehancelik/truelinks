"use client";

import { useState } from "react";
import { api, errorMessage, type Decision, type Issue, type WorkOrder } from "@/lib/api";
import { Badge, Button, Card, Notice, Trace } from "./ui";

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
          <figure key={photo} className="text-center text-xs text-zinc-500">
            {/* Served by the API from the uploads volume, so next/image has nothing to optimise. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={api.photoUrl(issue.id, photo)}
              alt={`Reported photo ${photo}`}
              className="h-32 w-32 rounded border border-zinc-200 object-cover"
            />
            <figcaption>Photo {photo}</figcaption>
          </figure>
        ))}
      </div>

      {issue.assessment && (
        <div className="grid gap-4 text-sm md:grid-cols-2">
          <div>
            <h3 className="mb-1 font-semibold">
              Condition <Badge>{issue.assessment.overall_condition}</Badge>
            </h3>
            <ul className="list-disc space-y-1 pl-5">
              {issue.assessment.damages.map((damage, index) => (
                <li key={index}>
                  {damage.description} <span className="text-zinc-500">(photo {damage.photo})</span>
                </li>
              ))}
              {issue.assessment.damages.length === 0 && <li className="text-zinc-500">No visible damage.</li>}
            </ul>
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Contents and equipment</h3>
            <ul className="space-y-1">
              {issue.assessment.equipment.map((item, index) => (
                <li key={index}>
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
  const [error, setError] = useState<string | null>(null);
  const edited = workOrder.title !== workOrder.draft.title || workOrder.description !== workOrder.draft.description;

  const decide = async (decision: Decision) => {
    try {
      await api.decideWorkOrder(workOrder.id, decision, { title, description });
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    onChange();
  };

  return (
    <div className="space-y-2 rounded border border-zinc-200 bg-zinc-50 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">Draft work order</h3>
        <Badge>{workOrder.decision}</Badge>
        <span>
          Urgency: <Badge>{workOrder.urgency}</Badge>
        </span>
        {edited && <span className="text-xs text-zinc-500">Edited. The agent wrote: “{workOrder.draft.title}”</span>}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      <input
        aria-label="Work order title"
        className="w-full rounded border border-zinc-300 bg-white px-2 py-1 font-medium"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <textarea
        aria-label="Work order description"
        className="w-full rounded border border-zinc-300 bg-white px-2 py-1"
        rows={3}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <div className="flex gap-2">
        <Button variant="primary" onClick={() => decide("ACCEPTED")}>
          Accept work order
        </Button>
        <Button variant="danger" onClick={() => decide("REJECTED")}>
          Reject
        </Button>
      </div>
    </div>
  );
}
