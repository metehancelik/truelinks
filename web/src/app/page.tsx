"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { UploadLease } from "@/components/forms";
import { LeaseCard } from "@/components/LeaseCard";
import { Badge, Card, Notice, SectionTitle } from "@/components/ui";

export default function Home() {
  const units = useResource(api.units);
  const leases = useResource(api.leases);

  const refresh = () => {
    void units.refresh();
    void leases.refresh();
  };

  // Leases the agent could not place on a unit still need a person.
  const unlinked = (leases.data ?? []).filter((lease) => lease.unit_id === null && lease.status !== "REJECTED");

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8 px-4 py-8 sm:px-6 sm:py-12">
      <header className="space-y-1.5">
        <h1 className="text-[1.75rem] font-semibold leading-tight tracking-tight text-balance">Marina Crest Residences</h1>
        <p className="max-w-2xl text-pretty text-[15px] leading-relaxed text-zinc-600">
          Open a unit to see its lease and the issues raised on it, and to accept or reject what the agents produced.
        </p>
      </header>

      {units.error && <Notice tone="error">Could not reach the API: {units.error}</Notice>}

      <Card title="Units">
        <div className="-mx-5 -my-5 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="py-2.5 pl-5 pr-3 font-medium">Unit</th>
                <th className="px-3 font-medium">Type</th>
                <th className="px-3 font-medium">Occupancy</th>
                <th className="px-3 font-medium">Lease</th>
                <th className="pl-3 pr-5 text-right font-medium">Open issues</th>
              </tr>
            </thead>
            <tbody>
              {(units.data ?? []).map((unit) => (
                <tr key={unit.unit_id} className="group border-t border-zinc-100 transition-colors hover:bg-zinc-50">
                  <td className="py-3 pl-5 pr-3">
                    <Link
                      href={`/units/${unit.unit_id}`}
                      className="font-medium text-zinc-900 underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900"
                    >
                      {unit.label}, {unit.building_name}
                    </Link>
                    <div className="mt-0.5 font-mono text-xs text-zinc-500">{unit.unit_id}</div>
                  </td>
                  <td className="px-3 text-zinc-700">{unit.unit_type}</td>
                  <td className="px-3">
                    <Badge>{unit.status}</Badge>
                  </td>
                  <td className="px-3">
                    {unit.lease_status ? <Badge>{unit.lease_status}</Badge> : <span className="text-zinc-500">none</span>}
                  </td>
                  <td className={`pl-3 pr-5 text-right ${unit.open_issues > 0 ? "font-semibold text-zinc-900" : "text-zinc-500"}`}>
                    {unit.open_issues}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <UploadLease onDone={refresh} />

      {unlinked.length > 0 && (
        <section className="space-y-3">
          <SectionTitle>Leases not linked to a unit</SectionTitle>
          {unlinked.map((lease) => (
            <LeaseCard key={lease.id} lease={lease} onChange={refresh} />
          ))}
        </section>
      )}
    </main>
  );
}
