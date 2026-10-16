interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  error?: boolean;
  errorMessage?: string;
  disabled?: boolean;
}

export function Select({
  value,
  onChange,
  options,
  placeholder = "Select...",
  error = false,
  errorMessage,
  disabled = false,
}: SelectProps) {
  return (
    <div className={error ? "mb-4" : "mb-2"}>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {placeholder}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`
          block w-full rounded-md border-gray-300 shadow-sm
          ${error ? "border-red-500" : ""}
          focus:border-indigo-500 focus:ring-indigo-500
          sm:text-sm
          ${disabled ? "bg-gray-50 cursor-not-allowed" : ""}
        `}
        disabled={disabled}
      >
        <option value=""> — {placeholder} — </option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && errorMessage && (
        <p className="mt-1 text-sm text-red-600">{errorMessage}</p>
      )}
    </div>
  );
}