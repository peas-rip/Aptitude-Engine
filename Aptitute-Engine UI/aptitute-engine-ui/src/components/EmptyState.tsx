import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Empty / no-result / no-match presentation (spec §11.7, §16.1). */
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-10 text-center">
      <h3 className="text-base font-medium text-gray-900">{title}</h3>
      {description && <p className="mt-2 text-sm text-gray-600">{description}</p>}
      {action && <div className="mt-4 flex justify-center gap-3">{action}</div>}
    </div>
  );
}

/** Generic loading skeleton block. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-gray-200 ${className}`} />;
}
