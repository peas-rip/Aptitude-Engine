import { useState } from "react";

interface QuestionNavigatorProps {
  total: number;
  answered: Set<number>;
  onJump?: (index: number) => void;
}

export function QuestionNavigator({
  total,
  answered,
  onJump,
}: QuestionNavigatorProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  return (
    <div className="flex flex-wrap gap-1">
      {Array.from({ length: total }, (_, i) => i + 1).map((num) => {
        const isAnswered = answered.has(num);
        const isHover = hoverIndex === num;
        return (
          <button
            key={num}
            onClick={() => onJump?.(num - 1)}
            onMouseEnter={() => setHoverIndex(num)}
            onMouseLeave={() => setHoverIndex(null)}
            disabled={false}
            className={`
              flex-shrink-0 w-8 h-8 rounded-md font-medium
              ${isAnswered
                ? "bg-green-100 text-green-800"
                : isHover
                ? "bg-indigo-100 text-indigo-800 hover:bg-indigo-200"
                : "bg-gray-100 text-gray-500 hover:bg-gray-200"}
            `}
          >
            {num}
          </button>
        );
      })}
    </div>
  );
}