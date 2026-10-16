/**
 * Typed client for the QME Test & Practice API (API_CONTRACTS §1.7).
 *
 *   const qme = new QmeClient({ baseUrl: "/api/qme" }); // via Vite proxy
 *   const meta = await qme.get<BankMeta>("/bank/meta");
 */

export type ErrorCode =
  | "UNAUTHORIZED"
  | "VALIDATION_ERROR"
  | "INVALID_INPUT"
  | "ANSWER_MISMATCH"
  | "NOT_FOUND"
  | "SERVICE_UNAVAILABLE"
  | "NETWORK_ERROR"   // local — transport failure, no envelope
  | "UNKNOWN_ERROR";  // local — non-envelope non-2xx (e.g. proxy 404)

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly details: Record<string, unknown>;
  readonly requestId?: string;

  constructor(
    status: number,
    code: ErrorCode,
    message: string,
    details: Record<string, unknown> = {},
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** Rule violations from an INVALID_INPUT response, if present. */
  get violations(): Array<{ rule: string; actual?: unknown; expected?: unknown }> {
    const v = this.details.violations;
    return Array.isArray(v) ? (v as Array<{ rule: string }>) : [];
  }

  /** Field errors from a VALIDATION_ERROR response, if present. */
  get fields(): Array<{ location: string; message: string }> {
    const f = this.details.fields;
    return Array.isArray(f) ? (f as Array<{ location: string; message: string }>) : [];
  }
}

const KNOWN_CODES = new Set<string>([
  "UNAUTHORIZED", "VALIDATION_ERROR", "INVALID_INPUT",
  "ANSWER_MISMATCH", "NOT_FOUND", "SERVICE_UNAVAILABLE",
]);

/** Narrow an unknown catch value to `ApiError` (hooks type their errors as
 *  `Error`, but the client only ever throws `ApiError`). */
export function toApiError(e: unknown): ApiError | null {
  return e instanceof ApiError ? e : null;
}

/** Always return something `ErrorBanner` can render. Anything that is not an
 *  `ApiError` never came from the API, so it is a local/unknown failure. */
export function asApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  const message = e instanceof Error ? e.message : String(e);
  return new ApiError(0, "UNKNOWN_ERROR", message, { cause: message });
}

export interface QmeClientOptions {
  /** API root INCLUDING /api/v1, or a proxy prefix that forwards to it. */
  baseUrl: string;
  apiKey?: string;             // omit when a server-side proxy injects it
  fetchImpl?: typeof fetch;    // injectable for tests / interceptors
  timeoutMs?: number;          // default 15000
  onRequestId?: (id: string) => void;  // hook for logging/telemetry
}

/**
 * `fetch` with an explicit global receiver. The global function object itself
 * cannot simply be stored and invoked as `client.fetchImpl(…)`: WebIDL binds
 * `this` to the calling object, and Chrome rejects any non-global receiver
 * with "Illegal invocation". A plain reference call works too, but binding the
 * receiver explicitly makes the requirement unambiguous.
 */
const globalFetch: typeof fetch = (input, init) =>
  fetch.call(globalThis, input, init);

export class QmeClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;
  private readonly onRequestId?: (id: string) => void;

  constructor(opts: QmeClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
    // `fetch` belongs to `window`. Calling it as a method (`this.fetchImpl(…)`)
    // passes the client as its receiver, and Chrome throws
    // "TypeError: Failed to execute 'fetch' on 'Window': Illegal invocation",
    // which the catch in `request()` then reports as a bogus NETWORK_ERROR for
    // every single call. Route it through an explicit global receiver.
    this.fetchImpl = opts.fetchImpl ?? globalFetch;
    this.timeoutMs = opts.timeoutMs ?? 15_000;
    this.onRequestId = opts.onRequestId;
  }

  private async request<T>(
    path: string,
    init: { method: string; body?: unknown },
    query?: Record<string, string | number | boolean | undefined>,
  ): Promise<T> {
    const qs = query
      ? new URLSearchParams(
          Object.entries(query)
            .filter(([, v]) => v !== undefined && v !== "")
            .map(([k, v]) => [k, String(v)] as [string, string]),
        ).toString()
      : "";

    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}${qs ? `?${qs}` : ""}`;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    let res: Response;
    try {
      res = await this.fetchImpl(url, {
        method: init.method,
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(this.apiKey ? { "X-API-Key": this.apiKey } : {}),
        },
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      });
    } catch (cause) {
      // No HTTP response at all: network failure, CORS, or abort.
      const aborted = cause instanceof DOMException && cause.name === "AbortError";
      throw new ApiError(
        0,
        "NETWORK_ERROR",
        aborted ? `Request timed out after ${this.timeoutMs}ms` : "Network request failed",
        { url, cause: String(cause) },
      );
    } finally {
      clearTimeout(timeout);
    }

    // 204 / empty body safety
    const text = await res.text();
    let payload: unknown = undefined;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        /* non-JSON body — fall through to the generic handler */
      }
    }

    if (res.ok) return payload as T;

    const envelope = payload as Partial<ErrorEnvelope> | undefined;
    if (envelope && typeof envelope.error?.code === "string") {
      const { code, message, details, request_id } = envelope.error;
      this.onRequestId?.(request_id);
      throw new ApiError(
        res.status,
        (KNOWN_CODES.has(code) ? code : "UNKNOWN_ERROR") as ErrorCode,
        message,
        details ?? {},
        request_id,
      );
    }

    // Not our envelope (proxy/nginx/404 from a wrong path).
    throw new ApiError(
      res.status,
      res.status === 401 ? "UNAUTHORIZED" : "UNKNOWN_ERROR",
      text ? `HTTP ${res.status}: ${text.slice(0, 200)}` : `HTTP ${res.status}`,
      { url },
    );
  }

  get<T>(path: string, query?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(path, { method: "GET" }, query);
  }

  post<T>(path: string, body?: unknown, query?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(path, { method: "POST", body }, query);
  }
}

/** Vite exposes build-time env vars on `import.meta.env` only — `process.env`
 *  does not exist in the browser bundle (and is not statically replaced), so
 *  reading it here silently fell back to the default and made `.env` dead. */
const env = import.meta.env as Record<string, string | undefined>;

/** App-wide singleton — configure once, import everywhere. */
export const qme = new QmeClient({
  // With the Vite proxy (vite.config.ts): baseUrl "/api/qme", no key in the browser.
  // Without a proxy (same-origin or non-browser): full API root INCLUDING /api/v1.
  baseUrl: env.VITE_QME_BASE_URL || "/api/qme",
  apiKey: env.VITE_QME_API_KEY || undefined,
  timeoutMs: 15_000,
  onRequestId: (id) => console.debug("[qme] request_id", id),
});