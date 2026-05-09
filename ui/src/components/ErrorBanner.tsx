import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  message: string;
  onRetry?: () => void;
  onReset?: () => void;
}

export function ErrorBanner({ message, onRetry, onReset }: Props) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 sm:flex-row sm:items-center"
    >
      <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />
      <div className="flex-1 text-sm text-foreground">
        <strong className="font-semibold">Something went wrong.</strong>{" "}
        <span className="text-muted-foreground">{message}</span>
      </div>
      <div className="flex gap-2">
        {onRetry && (
          <Button size="sm" onClick={onRetry}>
            Retry
          </Button>
        )}
        {onReset && (
          <Button size="sm" variant="outline" onClick={onReset}>
            New estimate
          </Button>
        )}
      </div>
    </div>
  );
}
