import { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  actions?: ReactNode;
}

export function PageHeader({ title, actions }: PageHeaderProps) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold tracking-tight text-gray-900">{title}</h1>
      {actions && (
        <div className="mt-4 flex justify-end">{actions}</div>
      )}
    </div>
  );
}