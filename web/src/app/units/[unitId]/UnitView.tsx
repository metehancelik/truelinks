"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { ReportIssue } from "@/components/forms";
import { IssueCard } from "@/components/IssueCard";
import { LeaseCard } from "@/components/LeaseCard";
import { Badge, Notice } from "@/components/ui";

/** The one screen an owner opens: a unit, its lease record and the issues raised on it. */
export function UnitView({ unitId }: { unitId: string }) {
  const load = useCallback(() => api.unit(unitId), [unitId]);
  const { data, error, refresh } = useResource(load);

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <Link href="/" className="text-sm text-sky-700 underline">
        All units
      </Link>

      {error && <Notice tone="error">{error}</Notice>}

      {data && (
        <>
          <header className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold">
              {data.unit.label}, {data.unit.building_name}
            </h1>
            <Badge>{data.unit.status}</Badge>
            <span className="text-sm text-zinc-600">
              {data.unit.unit_type} · {data.unit.property_name} · {data.unit.unit_id}
            </span>
          </header>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Lease</h2>
            {data.leases.length === 0 && data.unit.status === "occupied" && (
              <p className="text-sm text-zinc-600">
                Occupied according to the owner&apos;s records. No lease is on file for this unit yet.
              </p>
            )}
            {data.leases.length === 0 && data.unit.status !== "occupied" && (
              <p className="text-sm text-zinc-600">
                No lease is linked to this unit. Add one from the <Link href="/" className="underline">units page</Link>.
              </p>
            )}
            {data.leases.map((lease) => (
              <LeaseCard key={lease.id} lease={lease} onChange={refresh} />
            ))}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Issues</h2>
            <ReportIssue unitId={unitId} onDone={refresh} />
            {data.issues.map((issue) => (
              <IssueCard key={issue.id} issue={issue} onChange={refresh} />
            ))}
          </section>
        </>
      )}
    </main>
  );
}
