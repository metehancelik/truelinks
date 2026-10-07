"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import { Button, Card, Notice } from "./ui";

/** Upload a lease, or run one of the bundled samples. */
export function UploadLease({ onDone }: { onDone: () => void }) {
  const [samples, setSamples] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .sampleLeases()
      .then((items) => setSamples(items.map((item) => item.name)))
      .catch(() => setSamples([]));
  }, []);

  const send = async (form: FormData) => {
    try {
      await api.uploadLease(form);
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    onDone();
  };

  const upload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    event.currentTarget.reset();
    void send(form);
  };

  const runSample = (name: string) => {
    const form = new FormData();
    form.set("sample", name);
    void send(form);
  };

  return (
    <Card title="Add a lease">
      {error && <Notice tone="error">{error}</Notice>}
      <form onSubmit={upload} className="flex flex-wrap items-center gap-2 text-sm">
        <input name="file" type="file" accept=".pdf,.txt" required aria-label="Lease document" />
        <Button variant="primary" type="submit">
          Upload
        </Button>
        <span className="text-zinc-500">PDF with a text layer, or plain text.</span>
      </form>
      {samples.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-zinc-600">Or try a sample:</span>
          {samples.map((name) => (
            <Button key={name} onClick={() => runSample(name)}>
              {name}
            </Button>
          ))}
        </div>
      )}
    </Card>
  );
}

/** Report an issue on a unit with one or more photos. */
export function ReportIssue({ unitId, onDone }: { unitId: string; onDone: () => void }) {
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    event.currentTarget.reset();
    try {
      await api.reportIssue(unitId, form);
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    onDone();
  };

  return (
    <Card title="Report an issue">
      {error && <Notice tone="error">{error}</Notice>}
      <form onSubmit={submit} className="space-y-2 text-sm">
        <textarea
          name="note"
          rows={2}
          placeholder="What is wrong? For example: the AC is dripping water down the wall."
          aria-label="What is wrong"
          className="w-full rounded border border-zinc-300 px-2 py-1"
        />
        <div className="flex flex-wrap items-center gap-2">
          <input name="photos" type="file" accept="image/*" multiple required aria-label="Photos" />
          <Button variant="primary" type="submit">
            Send report
          </Button>
          <span className="text-zinc-500">Up to 6 photos.</span>
        </div>
      </form>
    </Card>
  );
}
