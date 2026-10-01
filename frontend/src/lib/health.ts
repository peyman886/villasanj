/** System health as reported by the API's /health endpoint, shaped for the status page. */

export type ProbeOut = { ok: boolean; detail: string };

export type HealthOut = {
  status: "ok" | "degraded";
  summary: string;
  checks: Record<string, ProbeOut>;
};

export type HealthRow = { key: string; label: string; ok: boolean; detail: string };

export type HealthView =
  { kind: "ok" | "degraded"; rows: HealthRow[] } | { kind: "unreachable"; rows: [] };

const PROBE_LABELS: Record<string, string> = {
  db: "پایگاه داده",
  blob: "ذخیره‌ساز فایل",
  llm: "مدل زبانی",
};

export function isHealthOut(value: unknown): value is HealthOut {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  if (candidate.status !== "ok" && candidate.status !== "degraded") return false;
  if (typeof candidate.summary !== "string") return false;
  const checks = candidate.checks;
  if (typeof checks !== "object" || checks === null) return false;
  return Object.values(checks).every(
    (probe) =>
      typeof probe === "object" &&
      probe !== null &&
      typeof (probe as ProbeOut).ok === "boolean" &&
      typeof (probe as ProbeOut).detail === "string",
  );
}

export function toHealthView(body: HealthOut | null): HealthView {
  if (body === null) return { kind: "unreachable", rows: [] };
  const rows = Object.entries(body.checks).map(([key, probe]) => ({
    key,
    label: PROBE_LABELS[key] ?? key,
    ok: probe.ok,
    detail: probe.detail,
  }));
  return { kind: body.status, rows };
}

/** Fetches API health; returns null when the API cannot be reached or answers nonsense. */
export async function fetchHealth(apiUrl: string, timeoutMs = 5000): Promise<HealthOut | null> {
  try {
    const response = await fetch(`${apiUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    const body: unknown = await response.json();
    return isHealthOut(body) ? body : null;
  } catch {
    return null;
  }
}

export function apiBaseUrl(): string {
  return process.env.API_URL ?? "http://localhost:8000";
}
