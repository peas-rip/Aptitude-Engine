import type { ReactNode } from "react";
import type { ApiError } from "../lib/qme-client";
import { Button } from "./Button";

interface ErrorBannerProps {
  error: ApiError;
  /** Offer a retry affordance (transport failures and 503 only — never 422/401). */
  onRetry?: () => void;
  /** Render as a full-page takeover (503 / offline). */
  fullPage?: boolean;
  children?: ReactNode;
}

function violationText(v: { rule: string; actual?: unknown; expected?: unknown }): string {
  switch (v.rule) {
    case "count_multiple_of_5":
      return `Count must be a multiple of 5 (got ${String(v.actual)}).`;
    case "count_minimum":
      return `Count must be ${String(v.expected)} (got ${String(v.actual)}).`;
    case "mixed_counts_sum":
      return "The difficulty counts must add up to the test length.";
    case "feasibility":
      return "There are not enough questions of that difficulty in this scope.";
    case "seed_required":
      return "This submission is missing its seed — the test cannot be re-verified. Please start the test again.";
    case "unknown_source":
    case "unknown_chapter":
      return "That selection no longer exists in the question bank.";
    case "ambiguous_chapter":
      return "That chapter exists in more than one source — pick a specific one.";
    default:
      return `${v.rule}: got ${String(v.actual)}${
        v.expected !== undefined ? `, expected ${String(v.expected)}` : ""
      }`;
  }
}

/**
 * One presentation layer for every error code (API_INTEGRATION.md §5.4,
 * spec §6.3 / §8.8). Always surfaces `request_id` so a user report can be
 * matched to backend logs.
 */
export function ErrorBanner({ error, onRetry, fullPage = false, children }: ErrorBannerProps) {
  const { code, message, details, requestId } = error;

  const retryable = code === "NETWORK_ERROR" || code === "SERVICE_UNAVAILABLE";

  const title =
    code === "NETWORK_ERROR"
      ? "Can't reach the server"
      : code === "SERVICE_UNAVAILABLE"
        ? "Service unavailable"
        : code === "UNAUTHORIZED"
          ? "Not authorised"
          : "Request failed";

  const body =
    code === "NETWORK_ERROR"
      ? "The request never reached the API. Check that the backend is running, then try again."
      : code === "SERVICE_UNAVAILABLE"
        ? "The question bank is missing or does not match its contract. This needs an operator — retrying will not help yet."
        : code === "UNAUTHORIZED"
          ? "The API key is missing or incorrect. Set QME_API_KEY for the dev proxy (vite.config.ts) or clear VITE_QME_API_KEY."
          : message;

  const fields = error.fields;
  const violations = error.violations;
  const available = details.available_by_difficulty as
    | Record<string, number>
    | undefined;
  const ambiguous = details.ambiguous as string[] | undefined;
  const issues = details.issues as string[] | undefined;
  const page = details.page as number | undefined;
  const totalPages = details.total_pages as number | undefined;

  const content = (
    <>
      <div className="flex items-start justify-between gap-4">
        <p className="font-medium">{title}</p>
        {retryable && onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
      <p className="mt-1 text-sm">{body}</p>

      {fields.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-sm">
          {fields.map((f, i) => (
            <li key={i}>
              <code className="bg-white/60 px-1 rounded">{f.location}</code>: {f.message}
            </li>
          ))}
        </ul>
      )}

      {violations.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-sm">
          {violations.map((v, i) => (
            <li key={i}>{violationText(v)}</li>
          ))}
        </ul>
      )}

      {available && (
        <p className="mt-2 text-sm">
          Available here:{" "}
          {Object.entries(available)
            .map(([k, n]) => `${n} ${k}`)
            .join(" · ")}
        </p>
      )}

      {ambiguous && ambiguous.length > 0 && (
        <div className="mt-2 text-sm">
          <p>Choose one of:</p>
          <ul className="list-disc pl-5">
            {ambiguous.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {typeof page === "number" && typeof totalPages === "number" && (
        <p className="mt-2 text-sm">
          Page {page} is past the end — the pool has {totalPages} pages.
        </p>
      )}

      {issues && issues.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer">Technical details</summary>
          <ul className="list-disc pl-5">
            {issues.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        </details>
      )}

      {children}

      {requestId && (
        <p className="mt-3 text-xs opacity-70">
          request_id: <code className="bg-white/60 px-1 rounded">{requestId}</code>
        </p>
      )}
    </>
  );

  const tone =
    code === "NETWORK_ERROR"
      ? "border-amber-300 bg-amber-50 text-amber-900"
      : code === "INVALID_INPUT" || code === "VALIDATION_ERROR"
        ? "border-amber-300 bg-amber-50 text-amber-900"
        : "border-red-300 bg-red-50 text-red-900";

  if (fullPage) {
    return (
      <div role="alert" className={`min-h-[60vh] flex items-center justify-center p-6`}>
        <div className={`max-w-xl w-full rounded-lg border p-6 ${tone}`}>{content}</div>
      </div>
    );
  }

  return (
    <div role="alert" className={`rounded-lg border p-4 ${tone}`}>
      {content}
    </div>
  );
}
