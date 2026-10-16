import { useEffect } from "react";

interface TimerProps {
  seconds: number;
  onExpire?: () => void;
}

export function Timer({ seconds, onExpire }: TimerProps) {
  useEffect(() => {
    if (seconds <= 0 && onExpire) {
      onExpire();
    }
  }, [seconds, onExpire]);

  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const display = `${minutes.toString().padStart(2, "0")}:${secs
    .toString()
    .padStart(2, "0")}`;

  const isWarning = seconds <= 60 && seconds > 0;

  return (
    <div className="flex items-center space-x-2">
      <span className="text-sm font-medium text-gray-700">Time Left:</span>
      <span
        className={`font-mono text-xl ${isWarning
          ? "text-red-600 animate-pulse"
          : "text-gray-900"}`}
      >
        {display}
      </span>
    </div>
  );
}