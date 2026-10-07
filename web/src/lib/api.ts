/** Types and calls for the Python API, reached through the /api proxy. */

export type Unit = {
  unit_id: string;
  label: string;
  unit_type: string;
  status: "available" | "occupied";
  building_name: string;
  property_name: string;
};

export type UnitSummary = Unit & {
  lease_status: string | null;
  open_issues: number;
};

export type FieldValue = string | number | boolean | null;

export type LeaseField = {
  name: string;
  value: FieldValue;
  quote: string | null;
  status: "VERIFIED" | "UNVERIFIED" | "MISSING";
  issue: string | null;
  explanation: string | null;
  decision: Decision;
  corrected_value: FieldValue;
};

export type Decision = "PENDING" | "ACCEPTED" | "REJECTED" | "CORRECTED";

export type Rule = {
  id: string;
  description: string;
  severity: "low" | "medium" | "high";
  outcome: "PASS" | "FAIL" | "NOT_DETERMINABLE";
  reason: string;
  inputs: string[];
  decision: Decision;
};

export type Step = {
  name: string;
  model: string | null;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
};

export type Lease = {
  id: string;
  filename: string;
  status: "PROCESSING" | "IN_REVIEW" | "ACTIVE" | "REJECTED" | "FAILED";
  error: string | null;
  unit_id: string | null;
  created_at: string;
  fields: LeaseField[];
  rules: Rule[];
  trace: Step[];
};

export type Finding = { photo: number };
export type Damage = Finding & { description: string };
export type Equipment = Finding & { name: string; condition: string };

export type WorkOrder = {
  id: string;
  title: string;
  description: string;
  urgency: "low" | "medium" | "high";
  draft: { title: string; description: string; urgency: string };
  decision: Decision;
};

export type Issue = {
  id: string;
  unit_id: string;
  note: string;
  status: "PROCESSING" | "OPEN" | "FAILED";
  error: string | null;
  photo_count: number;
  assessment: {
    overall_condition: string;
    damages: Damage[];
    equipment: Equipment[];
  } | null;
  flags: string[];
  trace: Step[];
  created_at: string;
  work_order: WorkOrder | null;
};

export type UnitDetail = { unit: Unit; leases: Lease[]; issues: Issue[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : response.statusText);
  }
  return response.json();
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const api = {
  units: () => request<UnitSummary[]>("/units"),
  unit: (unitId: string) => request<UnitDetail>(`/units/${unitId}`),
  leases: () => request<Lease[]>("/leases"),
  sampleLeases: () => request<{ name: string }[]>("/samples/leases"),

  uploadLease: (form: FormData) => request<Lease>("/leases", { method: "POST", body: form }),
  decideField: (leaseId: string, name: string, decision: Decision, value?: FieldValue) =>
    post<Lease>(`/leases/${leaseId}/fields/${name}/decision`, { decision, value }),
  decideRule: (leaseId: string, ruleId: string, decision: Decision) =>
    post<Lease>(`/leases/${leaseId}/rules/${ruleId}/decision`, { decision }),
  activateLease: (leaseId: string) => post<Lease>(`/leases/${leaseId}/activate`),
  rejectLease: (leaseId: string) => post<Lease>(`/leases/${leaseId}/reject`),

  reportIssue: (unitId: string, form: FormData) =>
    request<Issue>(`/units/${unitId}/issues`, { method: "POST", body: form }),
  decideWorkOrder: (
    workOrderId: string,
    decision: Decision,
    edits?: { title?: string; description?: string },
  ) => post<Issue>(`/work-orders/${workOrderId}/decision`, { decision, ...edits }),

  photoUrl: (issueId: string, photo: number) => `/api/issues/${issueId}/photos/${photo}`,
};

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

/** "monthly_rent" -> "Monthly rent" */
export function label(name: string): string {
  const words = name.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
