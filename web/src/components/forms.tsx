"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import { Button, Card, fileInputClass, inputClass, Notice, Spinner } from "./ui";

/** Add a lease to a unit: upload one, or run one of the bundled samples. */
export function UploadLease({ unitId, onDone }: { unitId: string; onDone: () => Promise<void> | void }) {
  const [samples, setSamples] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  // What is being sent: "file" or a sample's name. Its button shows a spinner.
  const [sending, setSending] = useState<string | null>(null);

  useEffect(() => {
    api
      .sampleLeases()
      .then((items) => setSamples(items.map((item) => item.name)))
      .catch(() => setSamples([]));
  }, []);

  const send = async (key: string, form: FormData) => {
    form.set("unit_id", unitId);
    setSending(key);
    try {
      await api.uploadLease(form);
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    await onDone();
    setSending(null);
  };

  const upload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    event.currentTarget.reset();
    void send("file", form);
  };

  const runSample = (name: string) => {
    const form = new FormData();
    form.set("sample", name);
    void send(name, form);
  };

  return (
    <Card title="Add a lease">
      {error && <Notice tone="error">{error}</Notice>}
      <form onSubmit={upload} className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
        <input name="file" type="file" accept=".pdf,.txt" required aria-label="Lease document" className={fileInputClass} />
        <Button variant="primary" type="submit" disabled={sending !== null}>
          {sending === "file" && <Spinner />}
          Upload
        </Button>
        <span className="text-zinc-500">PDF (text or scanned) or plain text.</span>
      </form>
      {samples.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-t border-zinc-100 pt-4 text-sm">
          <span className="mr-1 text-zinc-600">Or try a sample:</span>
          {samples.map((name) => (
            <Button key={name} className="font-mono text-xs" disabled={sending !== null} onClick={() => runSample(name)}>
              {sending === name && <Spinner />}
              {name}
            </Button>
          ))}
        </div>
      )}
    </Card>
  );
}

/** Report an issue on a unit with one or more photos. */
export function ReportIssue({ unitId, onDone }: { unitId: string; onDone: () => Promise<void> | void }) {
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    event.currentTarget.reset();
    setSending(true);
    try {
      await api.reportIssue(unitId, form);
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    await onDone();
    setSending(false);
  };

  return (
    <Card title="Report an issue">
      {error && <Notice tone="error">{error}</Notice>}
      <form onSubmit={submit} className="space-y-3 text-sm">
        <textarea
          name="note"
          rows={2}
          placeholder="What is wrong? For example: the AC is dripping water down the wall."
          aria-label="What is wrong"
          className={inputClass}
        />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <input name="photos" type="file" accept="image/*" multiple required aria-label="Photos" className={fileInputClass} />
          <Button variant="primary" type="submit" disabled={sending}>
            {sending && <Spinner />}
            Send report
          </Button>
          <span className="text-zinc-500">Up to 6 photos.</span>
        </div>
      </form>
    </Card>
  );
}
