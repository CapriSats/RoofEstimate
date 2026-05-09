import { Check, Loader2 } from "lucide-react";
import type { StageState } from "@/hooks/usePipeline";

const ICONS: Record<string, string> = {
  geocoding: "📍",
  imagery: "🛰️",
  footprint: "🏠",
  pitch: "📐",
  area: "📊",
  estimate: "💰",
};

export function PipelineProgress({ steps }: { steps: StageState[] }) {
  return (
    <ol className="space-y-2">
      {steps.map((s) => {
        const isDone = s.status === "done";
        const isRunning = s.status === "running";
        return (
          <li
            key={s.id}
            className={`flex items-center gap-3 rounded-lg border p-3 transition ${
              isDone
                ? "border-success/30 bg-success/5"
                : isRunning
                  ? "border-primary/30 bg-primary/5"
                  : "border-border bg-card"
            }`}
          >
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-base ${
                isDone
                  ? "bg-success text-success-foreground"
                  : isRunning
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {isDone ? (
                <Check className="h-4 w-4" />
              ) : isRunning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <span>{ICONS[s.id]}</span>
              )}
            </div>
            <div className="flex flex-1 items-center justify-between gap-3">
              <div className="flex flex-col">
                <span className="text-sm font-medium text-foreground">
                  {s.label}
                </span>
                {s.detail && (
                  <span className="text-xs text-muted-foreground">
                    {s.detail}
                  </span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
