import { useCallback, useRef, useState } from "react";

export type StageId =
  | "geocoding"
  | "imagery"
  | "footprint"
  | "pitch"
  | "area"
  | "estimate";

export type StageStatus = "idle" | "running" | "done" | "error";

export interface StageState {
  id: StageId;
  status: StageStatus;
  label?: string;
  detail?: string;
}

export interface SolarSource {
  roof_sqft: number;
  footprint_sqft: number;
  pitch_x_12: number;
  pitch_deg?: number;
  num_segments?: number;
  imagery_quality?: string;
  confidence: number;
  building_offset_m?: number;
  geocode_precision?: string;
}

export interface OsmSource {
  footprint_sqft: number;
  source: string;
  confidence: number;
}

export interface VisionPitchSource {
  pitch_x_12: number;
  pitch_multiplier: number;
  method: string;
  confidence: number;
  reasoning?: string;
}

export interface SourcesBreakdown {
  google_solar: SolarSource | null;
  osm: OsmSource | null;
  ms_buildings: OsmSource | null;
  vision_llm_pitch: VisionPitchSource | null;
}

export interface PartialResult {
  address?: string;
  imageDataUrl?: string;
  lat?: number;
  lon?: number;
  footprint_sqft?: number;
  pitch_x_12?: number;
  pitch_multiplier?: number;
  roof_sqft?: number;
  data_source?: string;
  mode?: string;
  sources?: SourcesBreakdown;
  finalSource?: string;
  polygonMeta?: {
    source?: string;
    footprint_sqft?: number;
    center_lat?: number;
    center_lon?: number;
    zoom?: number;
    meters_per_pixel?: number;
  };
}

export interface FinalResult {
  id: string;
  address: string;
  geocode: { lat: number; lon: number };
  footprint: { sqft: number; source: string; confidence: number };
  pitch: { x_12: number; method: string; multiplier?: number };
  area: { roof_sqft: number };
  estimate: {
    tiers: {
      good: TierData;
      better: TierData;
      best: TierData;
    };
    roof_sqft: number;
    pitch_x_12: number;
    valid_until: string;
    // NEW (optional for back-compat):
    linear_measurements?: LinearMeasurements;
    waste_rationale?: string;
    waste_factor?: number;
    regional_factor?: number;
  };
  mode?: string;
  sources?: SourcesBreakdown;
  final_source?: string;
  method?: string;
  cross_check?: {
    divergence_pct?: number;
    threshold_pct?: number;
    solar_roof_sqft?: number;
    build_path_roof_sqft?: number;
    rationale?: string;
  };
  warning?: string;
}

export interface LineItem {
  category: string;        // "materials" | "labor" | "permit"
  sku: string;
  description: string;
  qty: number;
  unit: string;            // "bundle" | "roll" | "linear ft" | "square" | "ea" | "box" | "job"
  unit_price_usd: number;
  subtotal_usd: number;
}

export interface LinearMeasurements {
  eaves_lf: number;
  rakes_lf: number;
  ridge_lf: number;
  hip_lf: number;
  valley_lf: number;
  total_perimeter_lf: number;
  method: string;
}

export interface TierData {
  label: string;
  subtotal: number;
  range_low: number;
  range_high: number;
  warranty: string;
  // NEW (optional for back-compat with older API responses):
  line_items?: LineItem[];
  subtotals_by_category?: Record<string, number>;
  // Legacy bucket fields the API still emits:
  material_cost?: number;
  supplementary?: number;
  labor_cost?: number;
  tearoff?: number;
  disposal?: number;
  permit?: number;
}

export type Status = "idle" | "running" | "complete" | "error";

const STAGE_ORDER: StageId[] = [
  "geocoding",
  "imagery",
  "footprint",
  "pitch",
  "area",
  "estimate",
];

const STAGE_LABELS: Record<StageId, string> = {
  geocoding: "Geocoding",
  imagery: "Aerial imagery",
  footprint: "Building outline",
  pitch: "Roof pitch",
  area: "Measuring",
  estimate: "Pricing",
};

const STAGE_RUNNING_LABELS: Record<StageId, string> = {
  geocoding: "Locating address…",
  imagery: "Fetching satellite image…",
  footprint: "Tracing footprint…",
  pitch: "Estimating pitch…",
  area: "Calculating roof area…",
  estimate: "Building your estimate…",
};

function freshSteps(): StageState[] {
  return STAGE_ORDER.map((id) => ({
    id,
    status: "idle",
    label: STAGE_LABELS[id],
  }));
}

export function usePipeline() {
  const [status, setStatus] = useState<Status>("idle");
  const [steps, setSteps] = useState<StageState[]>(freshSteps());
  const [partial, setPartial] = useState<PartialResult>({});
  const [result, setResult] = useState<FinalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [address, setAddress] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setSteps(freshSteps());
    setPartial({});
    setResult(null);
    setError(null);
    setAddress("");
  }, []);

  const handleEvent = useCallback((evt: any) => {
    if (!evt || typeof evt.stage !== "string") return;

    if (evt.stage === "error") {
      setError(evt.message || "Pipeline error");
      setStatus("error");
      return;
    }

    if (evt.stage === "complete") {
      const r: FinalResult = evt.result;
      setResult(r);
      setStatus("complete");
      setSteps((prev) =>
        prev.map((s) => ({ ...s, status: "done" as StageStatus })),
      );
      setPartial((p) => ({
        ...p,
        address: r.address,
        lat: r.geocode?.lat,
        lon: r.geocode?.lon,
        footprint_sqft: r.footprint?.sqft,
        pitch_x_12: r.pitch?.x_12,
        pitch_multiplier: r.pitch?.multiplier,
        roof_sqft: r.area?.roof_sqft,
        data_source: r.footprint?.source,
      }));
      return;
    }

    // Per-source breakdown event — populate partial.sources for the UI panel.
    // Also includes the polygon-cropped annotated image; promote it to
    // imageDataUrl so the AerialImage component shows the bbox visualization.
    if (evt.stage === "sources") {
      setPartial((p) => ({
        ...p,
        mode: evt.mode,
        sources: evt.sources,
        finalSource: evt.final_source,
        imageDataUrl: evt.annotated_image || evt.cropped_image || p.imageDataUrl,
        polygonMeta: evt.polygon_meta,
      }));
      return;
    }

    const stageId = evt.stage as StageId;
    if (!STAGE_ORDER.includes(stageId)) return;

    if (evt.status === "running") {
      setSteps((prev) =>
        prev.map((s) =>
          s.id === stageId
            ? {
                ...s,
                status: "running",
                detail: evt.label || STAGE_RUNNING_LABELS[stageId],
              }
            : s,
        ),
      );
    } else if (evt.status === "done") {
      setSteps((prev) =>
        prev.map((s) =>
          s.id === stageId
            ? { ...s, status: "done", detail: evt.detail || "Done" }
            : s,
        ),
      );
      setPartial((p) => {
        const next: PartialResult = { ...p };
        if (evt.image_base64) next.imageDataUrl = evt.image_base64;
        if (typeof evt.footprint_sqft === "number")
          next.footprint_sqft = evt.footprint_sqft;
        if (typeof evt.pitch_x_12 === "number") next.pitch_x_12 = evt.pitch_x_12;
        if (typeof evt.pitch_multiplier === "number")
          next.pitch_multiplier = evt.pitch_multiplier;
        if (typeof evt.roof_sqft === "number") next.roof_sqft = evt.roof_sqft;
        if (typeof evt.lat === "number") next.lat = evt.lat;
        if (typeof evt.lon === "number") next.lon = evt.lon;
        if (typeof evt.source === "string") next.data_source = evt.source;
        return next;
      });
    }
  }, []);

  const start = useCallback(
    async (addr: string) => {
      const trimmed = addr.trim();
      if (!trimmed) return;
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      setStatus("running");
      setSteps(freshSteps());
      setPartial({ address: trimmed });
      setResult(null);
      setError(null);
      setAddress(trimmed);

      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      try {
        const response = await fetch(`${apiUrl}/estimate`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({ address: trimmed }),
          signal: ctrl.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) !== -1) {
            const chunk = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const dataLines = chunk
              .split("\n")
              .filter((l) => l.startsWith("data:"))
              .map((l) => l.replace(/^data:\s?/, ""));
            const payload = dataLines.join("\n").trim();
            if (!payload) continue;
            try {
              handleEvent(JSON.parse(payload));
            } catch {
              // ignore malformed line
            }
          }
        }
      } catch (e: any) {
        if (e?.name === "AbortError") return;
        setError(e?.message || "Failed to reach backend");
        setStatus("error");
      }
    },
    [handleEvent],
  );

  const retry = useCallback(() => {
    if (address) start(address);
  }, [address, start]);

  return { status, steps, partial, result, error, address, start, reset, retry };
}
