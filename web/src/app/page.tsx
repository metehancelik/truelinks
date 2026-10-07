"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { UploadLease } from "@/components/forms";
import { LeaseCard } from "@/components/LeaseCard";
import { Badge, Card, Notice } from "@/components/ui";

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
    <main className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Marina Crest Residences</h1>
        <p className="text-sm text-zinc-600">
          Open a unit to see its lease and the issues raised on it, and to accept or reject what the agents produced.
        </p>
      </header>

      {units.error && <Notice tone="error">Could not reach the API: {units.error}</Notice>}

      <Card title="Units">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-zinc-500">
            <tr>
              <th className="py-2">Unit</th>
              <th>Type</th>
              <th>Occupancy</th>
              <th>Lease</th>
              <th>Open issues</th>
            </tr>
          </thead>
          <tbody>
            {(units.data ?? []).map((unit) => (
              <tr key={unit.unit_id} className="border-t border-zinc-100">
                <td className="py-2">
                  <Link href={`/units/${unit.unit_id}`} className="font-medium text-sky-700 underline">
                    {unit.label}, {unit.building_name}
                  </Link>
                  <div className="text-xs text-zinc-500">{unit.unit_id}</div>
                </td>
                <td>{unit.unit_type}</td>
                <td>
                  <Badge>{unit.status}</Badge>
                </td>
                <td>{unit.lease_status ? <Badge>{unit.lease_status}</Badge> : <span className="text-zinc-400">none</span>}</td>
                <td className="tabular-nums">{unit.open_issues}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <UploadLease onDone={refresh} />

      {unlinked.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Leases not linked to a unit</h2>
          {unlinked.map((lease) => (
            <LeaseCard key={lease.id} lease={lease} onChange={refresh} />
          ))}
        </section>
      )}
    </main>
  );
}
