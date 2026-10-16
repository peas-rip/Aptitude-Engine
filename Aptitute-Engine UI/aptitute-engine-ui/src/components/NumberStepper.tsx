interface NumberStepperProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  error?: boolean;
  errorMessage?: string;
  disabled?: boolean;
}

export function NumberStepper({
  value,
  onChange,
  min = 1,
  max = 1000,
  step = 1,
  error = false,
  errorMessage,
  disabled = false,
}: NumberStepperProps) {
  return (
    <div className={error ? "mb-4" : "mb-2"}>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Number
      </label>
      <div className="flex items-center space-x-2">
        <button
          onClick={() => onChange(Math.max(min, value - step))}
          disabled={disabled || value <= min}
          className={`
            flex-shrink-0 rounded-l-md bg-white px-2 py-1.5 text-sm font-medium
            border border-gray-300 ${disabled ? "bg-gray-200 cursor-not-allowed" : ""}
            hover:bg-gray-50
          `}
        >
          −
        </button>
        <input
          type="number"
          value={value}
          onChange={(e) => {
            const num = Number(e.target.value);
            if (!isNaN(num)) onChange(num);
          }}
          className={`
            flex-1 bg-white px-3 py-1.5 text-sm font-medium text-center
            border-t border-b border-gray-300
            ${disabled ? "bg-gray-200 cursor-not-allowed" : ""}
          `}
          readOnly
          min={min}
          max={max}
        />
        <button
          onClick={() => onChange(Math.min(max, value + step))}
          disabled={disabled || value >= max}
          className={`
            flex-shrink-0 rounded-r-md bg-white px-2 py-1.5 text-sm font-medium
            border border-gray-300 ${disabled ? "bg-gray-200 cursor-not-allowed" : ""}
            hover:bg-gray-50
          `}
        >
          +
        </button>
      </div>
      {error && errorMessage && (
        <p className="mt-1 text-sm text-red-600">{errorMessage}</p>
      )}
    </div>
  );
}