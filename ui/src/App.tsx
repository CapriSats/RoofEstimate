import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Wordmark } from "@/components/Wordmark";
import { AddressInput } from "@/components/AddressInput";
import { PipelineProgress } from "@/components/PipelineProgress";
import { AerialImage } from "@/components/AerialImage";
import { MeasurementsCard } from "@/components/MeasurementsCard";
import { EstimateTiers } from "@/components/EstimateTiers";
import { SendModal } from "@/components/SendModal";
import { ErrorBanner } from "@/components/ErrorBanner";
import { SourcesBreakdown } from "@/components/SourcesBreakdown";
import { SettingsDialog } from "@/components/SettingsDialog";
import { usePipeline } from "@/hooks/usePipeline";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Home />
      <Toaster />
    </QueryClientProvider>
  );
}

function Home() {
  const pipeline = usePipeline();
  const [sendOpen, setSendOpen] = useState(false);

  const showResults = pipeline.status !== "idle";
  const areaDone =
    pipeline.partial.roof_sqft != null || pipeline.status === "complete";
  const estimateDone =
    pipeline.status === "complete" && pipeline.result?.estimate;
  const pipelineComplete = pipeline.status === "complete";

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border/60 bg-card/50 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Wordmark subtitle={!showResults} />
          <div className="flex items-center gap-2">
            {showResults && (
              <Button
                variant="outline"
                size="sm"
                onClick={pipeline.reset}
                className="font-semibold"
              >
                ← New estimate
              </Button>
            )}
            <SettingsDialog />
          </div>
        </div>
      </header>

      {!showResults ? (
        <section className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col items-center justify-center px-4 py-12">
          <h1 className="mb-3 text-center text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            From address to estimate
            <span className="block bg-gradient-to-r from-primary to-primary-glow bg-clip-text text-transparent">
              in 60 seconds.
            </span>
          </h1>
          <p className="mb-8 max-w-xl text-center text-muted-foreground">
            Paste a property address. Our AI measures the roof from aerial
            imagery and prices a tiered replacement quote you can send to the
            homeowner.
          </p>
          <AddressInput
            onSubmit={pipeline.start}
            loading={pipeline.status === "running"}
            autoFocus
          />
        </section>
      ) : (
        <section className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
          {pipeline.status === "error" && pipeline.error && (
            <div className="mb-6">
              <ErrorBanner
                message={pipeline.error}
                onRetry={pipeline.retry}
                onReset={pipeline.reset}
              />
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <AerialImage
                src={pipeline.partial.imageDataUrl}
                address={pipeline.partial.address}
                lat={pipeline.partial.lat}
                lon={pipeline.partial.lon}
                polygonSource={pipeline.partial.polygonMeta?.source}
                polygonFootprintSqft={pipeline.partial.polygonMeta?.footprint_sqft}
              />
            </div>

            <div className="space-y-6 lg:col-span-3">
              {!pipelineComplete && (
                <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Running pipeline
                  </h2>
                  <PipelineProgress steps={pipeline.steps} />
                </div>
              )}

              {areaDone && (
                <MeasurementsCard
                  roof_sqft={pipeline.partial.roof_sqft}
                  footprint_sqft={pipeline.partial.footprint_sqft}
                  pitch_x_12={pipeline.partial.pitch_x_12}
                  data_source={pipeline.partial.data_source}
                  method={pipeline.result?.method}
                  divergence_pct={pipeline.result?.cross_check?.divergence_pct}
                />
              )}

              {pipeline.partial.sources && (
                <SourcesBreakdown
                  sources={pipeline.partial.sources}
                  mode={pipeline.partial.mode}
                  finalSource={
                    pipeline.result?.final_source ??
                    pipeline.partial.finalSource ??
                    pipeline.partial.data_source
                  }
                />
              )}

              {estimateDone && pipeline.result && (
                <>
                  <EstimateTiers
                    tiers={pipeline.result.estimate.tiers}
                    roof_sqft={pipeline.result.estimate.roof_sqft}
                    pitch_x_12={pipeline.result.estimate.pitch_x_12}
                    valid_until={pipeline.result.estimate.valid_until}
                    linear_measurements={pipeline.result.estimate.linear_measurements}
                    waste_rationale={pipeline.result.estimate.waste_rationale}
                  />
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      size="lg"
                      className="flex-1"
                      onClick={() => setSendOpen(true)}
                    >
                      Send to homeowner
                    </Button>
                    <Button
                      size="lg"
                      variant="outline"
                      className="flex-1"
                      onClick={pipeline.reset}
                    >
                      New estimate
                    </Button>
                  </div>
                  {pipeline.result.warning && (
                    <p className="text-xs text-muted-foreground">
                      Note: {pipeline.result.warning}
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        </section>
      )}

      <SendModal open={sendOpen} onOpenChange={setSendOpen} />
    </main>
  );
}
