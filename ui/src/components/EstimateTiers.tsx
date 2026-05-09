import type { TierData } from "@/hooks/usePipeline";
import { formatCurrency } from "@/lib/format";

interface Props {
  tiers: { good: TierData; better: TierData; best: TierData };
  roof_sqft: number;
  pitch_x_12: number;
  valid_until?: string;
}

const TIER_META: Record<string, { name: string; tone: "muted" | "primary" | "accent" }> = {
  good: { name: "Good", tone: "muted" },
  better: { name: "Better", tone: "primary" },
  best: { name: "Best", tone: "accent" },
};

function TierCard({
  id,
  tier,
  highlighted,
}: {
  id: "good" | "better" | "best";
  tier: TierData;
  highlighted: boolean;
}) {
  const meta = TIER_META[id];
  return (
    <div
      className={`relative flex flex-1 flex-col rounded-xl border bg-card p-5 shadow-sm transition ${
        highlighted
          ? "border-primary shadow-md ring-2 ring-primary/20 md:-translate-y-1"
          : "border-border"
      }`}
    >
      {highlighted && (
        <span className="absolute -top-2 right-4 rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-foreground">
          Recommended
        </span>
      )}
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {meta.name}
        </span>
      </div>
      <div className="mt-1 text-sm text-foreground/80">{tier.label}</div>
      <div className="mt-3 font-mono text-3xl font-bold text-foreground">
        {formatCurrency(tier.subtotal)}
      </div>
      <div className="mt-1 font-mono text-xs text-muted-foreground">
        {formatCurrency(tier.range_low)} – {formatCurrency(tier.range_high)}
      </div>
      <div className="mt-4 border-t border-border/60 pt-3 text-xs text-muted-foreground">
        {tier.warranty}
      </div>
    </div>
  );
}

export function EstimateTiers({ tiers, roof_sqft, pitch_x_12, valid_until }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
        <TierCard id="good" tier={tiers.good} highlighted={false} />
        <TierCard id="better" tier={tiers.better} highlighted={true} />
        <TierCard id="best" tier={tiers.best} highlighted={false} />
      </div>
      <p className="text-center text-xs text-muted-foreground">
        {valid_until ? `Valid until ${valid_until}` : "Valid for 30 days"} · Based
        on {roof_sqft.toLocaleString()} sqft at {pitch_x_12}:12 pitch
      </p>
    </div>
  );
}
