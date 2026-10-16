interface ProgressBarProps {
  value: number;
  max: number;
}

export function ProgressBar({ value, max }: ProgressBarProps) {
  const percent = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className="mb-2">
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className="h-2.5 bg-indigo-600 rounded"
          style={{ width: `${percent}%` }}
        ></div>
      </div>
      <div className="mt-1 flex justify-between text-sm text-gray-500">
        <span>{value}/{max}</span>
        <span>{Math.round(percent)}%</span>
      </div>
    </div>
  );
}