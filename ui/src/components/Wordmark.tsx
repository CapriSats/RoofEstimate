export function Wordmark({ subtitle = true }: { subtitle?: boolean }) {
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 11 12 4l9 7" />
            <path d="M5 10v10h14V10" />
          </svg>
        </div>
        <span className="text-lg font-bold tracking-tight text-foreground">
          RoofEstimate
        </span>
      </div>
      {subtitle && (
        <p className="ml-9 text-xs text-muted-foreground">
          Instant roof measurements. Send an estimate in 60 seconds.
        </p>
      )}
    </div>
  );
}
