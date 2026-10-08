"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { ReportIssue } from "@/components/forms";
import { IssueCard } from "@/components/IssueCard";
import { LeaseCard } from "@/components/LeaseCard";
import { Badge, Notice, SectionTitle } from "@/components/ui";

/** The one screen an owner opens: a unit, its lease record and the issues raised on it. */
export function UnitView({ unitId }: { unitId: string }) {
  const load = useCallback(() => api.unit(unitId), [unitId]);
  const { data, error, refresh } = useResource(load);

  const muted = "text-sm leading-relaxed text-zinc-600";

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8 px-4 py-8 sm:px-6 sm:py-12">
      <Link
        href="/"
        className="-ml-1 inline-flex items-center gap-1 rounded text-sm font-medium text-zinc-600 hover:text-zinc-900"
      >
        <svg aria-hidden viewBox="0 0 16 16" className="h-4 w-4">
          <path d="M10 4l-4 4 4 4" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        All units
      </Link>

      {error && <Notice tone="error">{error}</Notice>}

      {data && (
        <>
          <header className="-mt-4 space-y-1.5">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h1 className="text-[1.75rem] font-semibold leading-tight tracking-tight text-balance">
                {data.unit.label}, {data.unit.building_name}
              </h1>
              <Badge>{data.unit.status}</Badge>
            </div>
            <p className="text-sm text-zinc-600">
              {data.unit.unit_type} · {data.unit.property_name} · <span className="font-mono text-xs">{data.unit.unit_id}</span>
            </p>
          </header>

          <section className="space-y-3">
            <SectionTitle>Lease</SectionTitle>
            {data.leases.length === 0 && data.unit.status === "occupied" && (
              <p className={muted}>
                Occupied according to the owner&apos;s records. No lease is on file for this unit yet.
              </p>
            )}
            {data.leases.length === 0 && data.unit.status !== "occupied" && (
              <p className={muted}>
                No lease is linked to this unit. Add one from the{" "}
                <Link href="/" className="font-medium text-zinc-900 underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900">
                  units page
                </Link>
                .
              </p>
            )}
            {data.leases.map((lease) => (
              <LeaseCard key={lease.id} lease={lease} onChange={refresh} />
            ))}
          </section>

          <section className="space-y-3">
            <SectionTitle>Issues</SectionTitle>
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
