import { useState } from "react";
import type { LineItem, LinearMeasurements, TierData } from "@/hooks/usePipeline";
import { formatCurrency } from "@/lib/format";

interface Props {
  tiers: { good: TierData; better: TierData; best: TierData };
  roof_sqft: number;
  pitch_x_12: number;
  valid_until?: string;
  linear_measurements?: LinearMeasurements;
  waste_rationale?: string;
}

const TIER_META: Record<string, { name: string; tone: "muted" | "primary" | "accent" }> = {
  good:   { name: "Good",   tone: "muted"   },
  better: { name: "Better", tone: "primary" },
  best:   { name: "Best",   tone: "accent"  },
};

type TierId = "good" | "better" | "best";

function TierCard({
  id,
  tier,
  highlighted,
  selected,
  onSelect,
}: {
  id: TierId;
  tier: TierData;
  highlighted: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const meta = TIER_META[id];
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`relative flex flex-1 cursor-pointer flex-col rounded-xl border bg-card p-5 text-left shadow-sm transition hover:border-primary/60 ${
        selected
          ? "border-primary shadow-md ring-2 ring-primary/30 md:-translate-y-1"
          : highlighted
          ? "border-primary/50 shadow"
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
        {selected && (
          <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
            Showing breakdown
          </span>
        )}
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
    </button>
  );
}

function LinearMeasurementsPanel({ lin }: { lin: LinearMeasurements }) {
  const stats: { label: string; value: string }[] = [
    { label: "Eaves",  value: `${lin.eaves_lf} LF`  },
    { label: "Rakes",  value: `${lin.rakes_lf} LF`  },
    { label: "Ridge",  value: `${lin.ridge_lf} LF`  },
    { label: "Hip",    value: `${lin.hip_lf} LF`    },
    { label: "Valley", value: `${lin.valley_lf} LF` },
    { label: "Perimeter", value: `${lin.total_perimeter_lf} LF` },
  ];
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Linear measurements</h3>
        <span className="text-[11px] text-muted-foreground">{lin.method}</span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-6">
        {stats.map((s) => (
          <div key={s.label}>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{s.label}</div>
            <div className="font-mono text-sm font-semibold">{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LineItemsTable({ items }: { items: LineItem[] }) {
  if (!items?.length) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        Detailed line items not available for this estimate (legacy format).
      </div>
    );
  }

  // Group by category preserving emission order
  const groups: Record<string, LineItem[]> = {};
  items.forEach((it) => {
    (groups[it.category] ??= []).push(it);
  });

  const categoryLabel: Record<string, string> = {
    materials: "Materials",
    labor: "Labor",
    permit: "Permit & fees",
  };

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Description</th>
            <th className="px-3 py-2 text-right">Qty</th>
            <th className="px-3 py-2 text-left">Unit</th>
            <th className="px-3 py-2 text-right">Unit price</th>
            <th className="px-3 py-2 text-right">Subtotal</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(groups).map(([cat, group], gi) => (
            <>
              <tr key={`hdr-${cat}`} className={gi > 0 ? "border-t border-border" : ""}>
                <td colSpan={5} className="bg-muted/20 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {categoryLabel[cat] ?? cat}
                </td>
              </tr>
              {group.map((it, idx) => (
                <tr key={`${cat}-${idx}`} className="border-t border-border/40">
                  <td className="px-3 py-2">{it.description}</td>
                  <td className="px-3 py-2 text-right font-mono">{it.qty}</td>
                  <td className="px-3 py-2 text-muted-foreground">{it.unit}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatCurrency(it.unit_price_usd)}</td>
                  <td className="px-3 py-2 text-right font-mono font-medium">{formatCurrency(it.subtotal_usd)}</td>
                </tr>
              ))}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EstimateTiers({
  tiers,
  roof_sqft,
  pitch_x_12,
  valid_until,
  linear_measurements,
  waste_rationale,
}: Props) {
  const [selected, setSelected] = useState<TierId>("better");
  const tier = tiers[selected];

  return (
    <div className="space-y-4">
      {/* Top-line: 3 tier cards */}
      <div className="flex flex-col gap-3 md:flex-row">
        <TierCard
          id="good"
          tier={tiers.good}
          highlighted={false}
          selected={selected === "good"}
          onSelect={() => setSelected("good")}
        />
        <TierCard
          id="better"
          tier={tiers.better}
          highlighted
          selected={selected === "better"}
          onSelect={() => setSelected("better")}
        />
        <TierCard
          id="best"
          tier={tiers.best}
          highlighted={false}
          selected={selected === "best"}
          onSelect={() => setSelected("best")}
        />
      </div>

      {/* Linear measurements (where the LF for line items come from) */}
      {linear_measurements && <LinearMeasurementsPanel lin={linear_measurements} />}

      {/* Itemized line items for the selected tier */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold">
            {TIER_META[selected].name} — itemized breakdown
          </h3>
          <span className="text-xs text-muted-foreground">
            {tier.line_items?.length ?? 0} line items
            {waste_rationale ? <> · waste {waste_rationale}</> : null}
          </span>
        </div>
        <LineItemsTable items={tier.line_items ?? []} />

        {tier.subtotals_by_category && (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-xs">
            {Object.entries(tier.subtotals_by_category).map(([k, v]) => (
              <span key={k}>
                <span className="text-muted-foreground">{k}: </span>
                <span className="font-mono font-semibold">{formatCurrency(v)}</span>
              </span>
            ))}
            <span className="ml-auto">
              <span className="text-muted-foreground">Total: </span>
              <span className="font-mono text-base font-bold">{formatCurrency(tier.subtotal)}</span>
            </span>
          </div>
        )}
      </div>

      {/* Footer line: roof size, pitch, validity */}
      <div className="text-xs text-muted-foreground">
        Based on {roof_sqft.toLocaleString()} sqft @ {pitch_x_12}:12 pitch
        {valid_until ? <> · Valid until {valid_until}</> : null}
      </div>
    </div>
  );
}
