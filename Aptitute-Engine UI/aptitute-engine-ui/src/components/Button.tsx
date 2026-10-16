import { ReactNode } from "react";

interface ButtonProps {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  disabled?: boolean;
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  children,
  onClick,
  type = "button",
}: ButtonProps) {
  const baseClasses = "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
  const variantClasses =
    variant === "primary"
      ? "bg-indigo-600 text-white hover:bg-indigo-700 focus-visible:ring-indigo-500"
      : variant === "secondary"
      ? "bg-gray-200 text-gray-900 hover:bg-gray-300 focus-visible:ring-gray-500"
      : "bg-transparent text-gray-900 hover:bg-gray-100 focus-visible:ring-gray-500";

  const sizeClasses =
    size === "sm"
      ? "h-9 px-3 text-sm"
      : size === "lg"
      ? "h-11 px-8 text-lg"
      : "h-10 px-4 text-base";

  return (
    <button
      type={type}
      disabled={loading || disabled}
      onClick={loading ? undefined : onClick}
      className={`${baseClasses} ${variantClasses} ${sizeClasses}`}
    >
      {loading ? (
        <>
          <span className="mr-2">Loading...</span>
          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
          </svg>
        </>
      ) : (
        children
      )}
    </button>
  );
}