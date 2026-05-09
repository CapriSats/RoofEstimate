import type { SourcesBreakdown as Sources } from "@/hooks/usePipeline";
import { formatSqft } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

interface Props {
  sources?: Sources;
  mode?: string;
  finalSource?: string;
}

const MODE_LABELS: Record<string, string> = {
  off: "Off (build path)",
  fusion: "Fusion (multi-source)",
  primary: "Primary (Solar API first)",
};

function isUsed(finalSource: string | undefined, sourceName: string): boolean {
  if (!finalSource) return false;
  if (finalSource.includes("outlier_rejected")) {
    // Source label like "ms_buildings_outlier_rejected+vision_llm" — only the
    // un-rejected source actually contributed.
    return finalSource.startsWith(sourceName);
  }
  return finalSource.includes(sourceName);
}

function isRejected(finalSource: string | undefined, sourceName: string): boolean {
  if (!finalSource) return false;
  // When outlier rejection fired, the *other* polygon source was rejected.
  if (!finalSource.includes("outlier_rejected")) return false;
  if (sourceName === "osm" && finalSource.startsWith("ms_buildings")) return true;
  if (sourceName === "ms_buildings" && finalSource.startsWith("osm")) return true;
  return false;
}

export function SourcesBreakdown({ sources, mode, finalSource }: Props) {
  if (!sources) return null;

  const { google_solar, osm, ms_buildings, vision_llm_pitch } = sources;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Sources breakdown
        </h3>
        {mode && (
          <Badge variant="outline" className="font-mono text-xs">
            mode = {MODE_LABELS[mode] ?? mode}
          </Badge>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <SourceCard
          name="Google Solar API"
          highlighted={isUsed(finalSource, "google_solar") || finalSource === "fusion"}
        >
          {google_solar ? (
            <>
              <Row label="Roof area" value={`${formatSqft(google_solar.roof_sqft)} sqft`} />
              <Row label="Footprint" value={`${formatSqft(google_solar.footprint_sqft)} sqft`} />
              <Row label="Pitch" value={`${google_solar.pitch_x_12}:12 (${google_solar.pitch_deg?.toFixed?.(1)}°)`} />
              <Row label="Segments" value={String(google_solar.num_segments ?? "—")} />
              <Row label="Imagery quality" value={google_solar.imagery_quality ?? "—"} />
              <Row label="Confidence" value={`${Math.round(google_solar.confidence * 100)}%`} />
            </>
          ) : (
            <Empty reason={mode === "off" ? "Disabled by SOLAR_MODE=off" : "No coverage / API miss"} />
          )}
        </SourceCard>

        <SourceCard
          name="MS Buildings"
          highlighted={isUsed(finalSource, "ms_buildings") || finalSource === "fusion"}
          rejected={isRejected(finalSource, "ms_buildings")}
        >
          {ms_buildings ? (
            <>
              <Row label="Footprint" value={`${formatSqft(ms_buildings.footprint_sqft)} sqft`} />
              <Row label="Source" value={ms_buildings.source} />
              <Row label="Confidence" value={`${Math.round(ms_buildings.confidence * 100)}%`} />
            </>
          ) : (
            <Empty reason="No nearby building in MS data" />
          )}
        </SourceCard>

        <SourceCard
          name="OSM polygon"
          highlighted={isUsed(finalSource, "osm") || finalSource === "fusion"}
          rejected={isRejected(finalSource, "osm")}
        >
          {osm ? (
            <>
              <Row label="Footprint" value={`${formatSqft(osm.footprint_sqft)} sqft`} />
              <Row label="Source" value={osm.source} />
              <Row label="Confidence" value={`${Math.round(osm.confidence * 100)}%`} />
            </>
          ) : (
            <Empty reason="No building polygon nearby in OSM" />
          )}
        </SourceCard>

        <SourceCard name="Vision LLM pitch" highlighted={false}>
          {vision_llm_pitch ? (
            <>
              <Row label="Pitch" value={`${vision_llm_pitch.pitch_x_12}:12`} />
              <Row label="Multiplier" value={`×${vision_llm_pitch.pitch_multiplier}`} />
              <Row label="Method" value={vision_llm_pitch.method} />
              <Row label="Confidence" value={`${Math.round(vision_llm_pitch.confidence * 100)}%`} />
              {vision_llm_pitch.reasoning && (
                <p className="mt-2 line-clamp-3 text-[11px] italic leading-snug text-muted-foreground">
                  "{vision_llm_pitch.reasoning}"
                </p>
              )}
            </>
          ) : (
            <Empty reason="Skipped (mode=primary with Solar hit)" />
          )}
        </SourceCard>
      </div>
    </div>
  );
}

function SourceCard({
  name,
  highlighted,
  rejected = false,
  children,
}: {
  name: string;
  highlighted: boolean;
  rejected?: boolean;
  children: React.ReactNode;
}) {
  let cls = "border-border/60 bg-background";
  if (rejected) cls = "border-destructive/40 bg-destructive/5 opacity-70";
  else if (highlighted) cls = "border-primary/40 bg-primary/5";

  return (
    <div className={`rounded-lg border p-3 ${cls}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">{name}</span>
        {rejected && (
          <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-destructive">
            outlier
          </span>
        )}
        {!rejected && highlighted && (
          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
            used
          </span>
        )}
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-border/40 py-1 text-xs last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-semibold text-foreground">{value}</span>
    </div>
  );
}

function Empty({ reason }: { reason: string }) {
  return (
    <p className="py-2 text-center text-xs italic text-muted-foreground">{reason}</p>
  );
}
