import { Skeleton } from "@/components/ui/skeleton";
import { formatLatLon } from "@/lib/format";

interface Props {
  src?: string;
  address?: string;
  lat?: number;
  lon?: number;
  polygonSource?: string;        // "ms_buildings" | "osm" | undefined
  polygonFootprintSqft?: number;
}

const POLY_SOURCE_LABELS: Record<string, string> = {
  ms_buildings: "Microsoft Buildings",
  osm: "OpenStreetMap",
};

export function AerialImage({
  src,
  address,
  lat,
  lon,
  polygonSource,
  polygonFootprintSqft,
}: Props) {
  const sourceLabel = polygonSource ? POLY_SOURCE_LABELS[polygonSource] ?? polygonSource : null;
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="relative aspect-square w-full overflow-hidden rounded-xl border border-border bg-muted">
        {src ? (
          <img
            src={src}
            alt={address ? `Aerial view of ${address}` : "Aerial view"}
            className="h-full w-full animate-in fade-in object-cover duration-700"
          />
        ) : (
          <Skeleton className="h-full w-full" />
        )}
        {sourceLabel && (
          <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between gap-2 rounded-md bg-black/65 px-2.5 py-1.5 text-[11px] text-white backdrop-blur">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-sm border-2 border-emerald-400" />
              <span>polygon: <span className="font-mono">{sourceLabel}</span></span>
            </span>
            {polygonFootprintSqft && (
              <span className="font-mono">
                {polygonFootprintSqft.toLocaleString()} sqft
              </span>
            )}
          </div>
        )}
      </div>
      {(address || (lat != null && lon != null)) && (
        <div className="flex flex-col gap-1 text-sm">
          {address && (
            <span className="text-muted-foreground">{address}</span>
          )}
          {lat != null && lon != null && (
            <span className="font-mono text-xs text-muted-foreground">
              {formatLatLon(lat, lon)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
