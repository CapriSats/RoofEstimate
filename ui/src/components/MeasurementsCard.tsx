import { formatSqft } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

interface Props {
  roof_sqft?: number;
  footprint_sqft?: number;
  pitch_x_12?: number;
  data_source?: string;
  method?: string;
  divergence_pct?: number;
}

const METHOD_LABELS: Record<string, { label: string; tone: "build" | "solar" | "default" }> = {
  build_path_solar_validated: { label: "Build path (Solar cross-check passed)", tone: "build" },
  solar_tiebreaker_on_divergence: { label: "Solar tiebreaker (build path diverged)", tone: "solar" },
  build_path_no_cross_check: { label: "Build path (no Solar available)", tone: "build" },
  solar_only_no_polygon_available: { label: "Solar (no polygon available)", tone: "solar" },
  ms_preferred_polygon_x_vision_pitch: { label: "Build path (MS Buildings × Vision LLM)", tone: "build" },
  solar_api_slope_corrected: { label: "Solar API direct", tone: "solar" },
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-border/60 py-2 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-mono text-sm font-semibold text-foreground">{value}</span>
    </div>
  );
}

export function MeasurementsCard({
  roof_sqft,
  footprint_sqft,
  pitch_x_12,
  data_source,
  method,
  divergence_pct,
}: Props) {
  const methodMeta = method ? METHOD_LABELS[method] : undefined;
  const toneClasses = {
    build: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
    solar: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
    default: "",
  } as const;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Measurements
        </h3>
        {methodMeta && (
          <Badge variant="outline" className={`text-[10px] font-medium ${toneClasses[methodMeta.tone]}`}>
            {methodMeta.label}
          </Badge>
        )}
      </div>
      <Row label="Roof area" value={roof_sqft != null ? `${formatSqft(roof_sqft)} sqft` : "—"} />
      <Row label="Footprint" value={footprint_sqft != null ? `${formatSqft(footprint_sqft)} sqft` : "—"} />
      <Row label="Pitch" value={pitch_x_12 != null ? `${pitch_x_12}:12` : "—"} />
      <Row label="Data source" value={data_source ?? "—"} />
      {divergence_pct != null && (
        <Row
          label="Build vs Solar divergence"
          value={`${divergence_pct.toFixed(1)}%${divergence_pct > 15 ? " (tiebreaker triggered)" : " (within tolerance)"}`}
        />
      )}
    </div>
  );
}
