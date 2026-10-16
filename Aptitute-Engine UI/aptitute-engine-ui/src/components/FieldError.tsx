interface FieldErrorProps {
  message: string;
  className?: string;
}

export function FieldError({ message, className = "" }: FieldErrorProps) {
  return <p className={`mt-1 text-sm text-red-600 ${className}`}>{message}</p>;
}