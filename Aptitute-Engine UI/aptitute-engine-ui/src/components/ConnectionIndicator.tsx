import { useHealth } from "../hooks/useHealth";

export function ConnectionIndicator() {
  const { data, loading, error } = useHealth();

  if (loading) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100">
        Checking...
      </span>
    );
  }

  if (error) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"
        title="Cannot reach the server"
      >
        ● Offline
      </span>
    );
  }

  if (data?.status === "ok") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
        title={`Backend ${data.version} (${data.environment})`}
      >
        ● Online
      </span>
    );
  }

  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
      Unknown
    </span>
  );
}