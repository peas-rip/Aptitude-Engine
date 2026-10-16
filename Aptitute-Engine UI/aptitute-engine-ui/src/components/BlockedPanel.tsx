import { ReactNode } from "react";

interface BlockedPanelProps {
  endpoint: string;
  contractDoc?: string; // e.g., "docs/API_CONTRACTS.md §1.2"
  children?: ReactNode;
}

export function BlockedPanel({ endpoint, contractDoc, children }: BlockedPanelProps) {
  return (
    <div className="max-w-xl mx-auto py-12 px-6 bg-gray-50 rounded-lg border border-gray-200">
      <h2 className="mb-4 text-xl font-semibold text-gray-800">
        Not available
      </h2>
      <p className="mb-4 text-gray-600">
        This screen requires backend endpoints that are not implemented
        (returns 404 today).
      </p>
      {contractDoc && (
        <p className="mb-4 text-sm text-gray-500">
          See <code className="bg-gray-100 px-1 py-0.5 rounded">{contractDoc}</code>
          for the specified contract.
        </p>
      )}
      <p className="mb-4 text-sm text-gray-700">
        Missing endpoint:{" "}
        <code className="bg-gray-100 px-1 py-0.5 rounded">{endpoint}</code>
      </p>
      {children && (
        <div className="mt-6 pt-4 border-t border-gray-200">
          <h3 className="font-medium text-gray-700">Placeholder</h3>
          <p className="text-gray-600">{children}</p>
        </div>
      )}
    </div>
  );
}