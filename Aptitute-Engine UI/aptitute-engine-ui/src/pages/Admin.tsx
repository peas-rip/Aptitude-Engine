import { NavLink, Outlet } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";

/**
 * Admin shell (spec §8.9). The screens behind it are BLOCKED because the
 * backend endpoints do not exist — this section exists only to document the
 * intended experience honestly.
 */
export default function Admin() {
  const tabs = [
    { to: "/admin/batches", label: "Batches" },
    { to: "/admin/review", label: "Review queue" },
    { to: "/admin/metrics", label: "Metrics" },
  ];

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
      <PageHeader title="Admin" />
      <p className="mt-2 text-sm text-gray-600">
        Operational screens for the ingestion and review pipeline. Not wired up yet.
      </p>

      <nav className="mt-4 flex flex-wrap gap-4 border-b border-gray-200 pb-2 text-sm">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              isActive
                ? "border-b-2 border-indigo-600 pb-2 font-medium text-indigo-600"
                : "pb-2 text-gray-500 hover:text-gray-700"
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}
