# RoofEstimate — short brief for NotebookLM podcast

*This doc is the input for NotebookLM's 2-host podcast generator. Keep it short, conversational, and concrete so the two AI hosts have things to discuss without padding.*

---

## What it is in one sentence

Type a street address, get back a contractor-grade roofing quote — measurements, materials, labor, and a tiered total — in under 30 seconds.

## Who built it and why

CapriSats, solo, for the JobNimbus AI Hackathon 2026. The hackathon's premise: every roofing estimate today either takes a contractor 30 minutes of manual measuring, or costs the contractor $50–150 to buy from a commercial measurement service. If AI can do it accurately in seconds, the whole industry's quoting workflow changes.

## The interesting design choice

The system is **deliberately multi-provider**. Six different data sources, each pluggable, each handled by its own module. No single API is trusted to produce the answer. The system runs *two independent computations* of the same roof and only submits a number when they agree. When they disagree, the disagreement itself is informative.

This is the *validated-build policy*. Build path = Microsoft Building Footprints polygon × Vision LLM-derived pitch. Cross-check path = Google Solar API. If they agree within 15%, submit the build path. If they diverge by more than 15%, fall back to Solar with the divergence percentage logged in the output.

## The compliance angle

The hackathon has a "build, don't buy" rule — you have to show how you compute measurements; you can't just read commercial reports. The Solar API arguably crosses that line — it's effectively buying Google's measurement.

So Solar API is **configurable**, not mandatory. There's a setting (`SOLAR_MODE`) with three values: `off`, `fusion`, `primary`. Set it to `off` and the system runs the build path only — same pipeline, same output shape, no Solar call. Submitted numbers don't depend on Solar.

This is unusual for a hackathon submission. Most teams will lock in one approach. This one is robust to either reading of the rule.

## The output

Three tiers — Good (3-Tab), Better (Architectural), Best (Designer/Impact). For each tier, ~13 SKU-level line items: 83 bundles of GAF Timberline at $38, 210 LF of drip edge at $1.55, 178 LF of ridge cap, 7 boxes of nails, 24 squares of tear-off labor pitch-adjusted by the NRCA factor, dumpster + dump fees, permit allowance.

Bucket totals tell a homeowner what to pay. SKU-level tells a contractor what to ORDER. That's the difference between a rough number and an actual quote.

Linear measurements (eaves, rakes, ridge, hip, valley) are derived from the building polygon's perimeter projected to local feet, plus segment count from Solar (when available) as a complexity proxy. The coefficients are calibrated against the hackathon's own published reference data.

## Accuracy honestly stated

MAPE 4.0% across the 5 calibration properties. Best property: 0.6% error. Worst: 11.7% over reference (Orland Park IL). Pitch exact match: 1 out of 5 — Vision LLM is the system's weak link. Off by one increment 80% of the time (5:12 when it should be 6:12).

The team's older self-evaluator scored this submission 97.4/100 with "99% top-5 probability". That score is wrong — it was checking for documentation strings rather than actual artifacts. A recalibrated evaluator gives ~88 weighted with "competitive for top 5, but not a slam dunk."

## What's actually novel

Not the AI — Vision LLM and Solar API are both off-the-shelf. The novelty is the **engineering judgment**: combining six providers with documented routing, making Solar configurable to satisfy compliance scrutiny, and refusing to ship rigged shortcuts. The previous prototype had hardcoded answer-key dictionaries (`FOOTPRINT_ESTIMATES = {address: known_answer}`). They were deleted before submission. Greppable proof.

## What it doesn't try to be

Not a research project. No model training, no novel ML architecture. No LiDAR. Not a multi-agent rewrite. Not Solar-dependent.

A deliberate pipeline composed of six pluggable parts that produces, in 30 seconds, the same kind of output a contractor would otherwise pay $50–150 and wait two days for.

## The two interesting angles for discussion

1. **Build-don't-buy interpretation**: where does "use an API" become "buy a measurement"? The team designed for both possible readings of the rule.
2. **Vision LLM as the bottleneck**: pitch is the single biggest accuracy lever. The Vision LLM hits exact pitch only 20% of the time. That's not a code problem — it's a model-capability problem. What would the next step be? Multi-shot pitch with confidence weighting? LiDAR (free from USGS 3DEP)? Photogrammetry from oblique imagery? All real options, none in scope for a 2-day hackathon.

---

*That's the whole brief. Keep the conversation focused on these themes; resist filler.*
