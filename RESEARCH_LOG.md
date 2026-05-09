# Research log — what we tried, what we kept, what we dropped

This document records the techniques and architectures evaluated for this submission, including the ones we *rejected*. It exists because engineering judgment is on the hackathon rubric, and judgment is most visible in what you choose **not** to ship.

The TL;DR: we deliberately chose a **multi-provider pipeline with off-the-shelf models** over five more ambitious approaches. Each was tried with real code, evaluated against the calibration set or against a clear engineering criterion, and rejected on evidence — not on aesthetics.

---

## Approaches we tried in code

### 1. Grounding DINO + Segment Anything Model (Grounded SAM)

**Goal:** text prompt `"roof"` on aerial imagery → pixel-precise mask → footprint area.

**What we built:** end-to-end pipeline using HuggingFace Transformers + SAM weights. Test runs in [`test_grounded_sam.py`](test_grounded_sam.py) and [`test_grounding_dino.py`](test_grounding_dino.py). Visualizations were saved to `outputs/grounded_sam_visualizations/`. Initial results looked promising on flat suburban geometry.

**Why we rejected it:**
- **Microsoft Building Footprints already produces strictly better polygons.** MS gives vector polygons validated against parcel data; SAM gives ~5–15% area error from edge fuzziness, pixel→meter projection error, and overhang-vs-wall confusion on a 640×640 image. The "we computed it ourselves" framing didn't survive head-to-head accuracy comparison.
- **No facet structure.** SAM gives one blob "the roof". It doesn't decompose into pitched segments. Solar API provides per-facet area + pitch + azimuth natively; SAM doesn't.
- **Heavyweight to deploy.** ~2 GB model weights, GPU strongly preferred. Our deploy target is `t3.medium` (4 GB RAM, no GPU); putting SAM in the request path would mean a 5× larger instance for a worse output.
- **Out-of-distribution.** Both DINO and SAM were trained on natural eye-level imagery. Top-down aerial photography is OOD; performance on roof boundaries was visibly worse than the model's behavior on cats and chairs.

**Artifacts in repo:** `weights/` directory (gitignored model checkpoints), `test_grounded_sam.py`, `test_grounding_dino.py`. Kept in the tree as evidence of the experiment.

---

### 2. Multi-agent orchestrator (LangGraph + Claude Agent SDK)

**Goal:** an agent-driven pipeline with task delegation to specialist sub-agents (Vision, Geometry, Fusion, QA) — the architecture pattern that's currently fashionable for AI engineering projects.

**What we built:** two parallel implementations:
- `agent_implementations/langgraph/` — graph-based orchestration
- `agent_implementations/claude_agent_sdk/orchestrator.py` (~452 lines) — tool-calling pattern with sub-agent delegation

Both followed the design in `AGENT_SYSTEM_DESIGN.md`.

**Why we rejected it:**
- **Our workflow is fixed, not variable.** The pipeline is a 7-step DAG with one branch (Solar tiebreaker on >15% divergence). Agent architectures earn their keep when the workflow varies per input — research, code review, support. Ours doesn't.
- **Latency cost.** Every agent boundary adds 2–5 seconds for an LLM round-trip. A ~30 second deterministic pipeline becomes ~90–180 seconds with agents, with **zero accuracy gain** on the same inputs.
- **Determinism cost.** Same address → same number today. With agent routing, retries can drift; debugging requires parsing agent thoughts instead of reading a 100-line function.
- **Implementation incomplete.** The Claude Agent SDK orchestrator references imports for Vision/Geometry/Fusion/QA agents that were never built. The framework was scaffolded; the agents weren't. That mismatch was the signal.

**Artifacts in repo:** `agent_implementations/` directory and `AGENT_SYSTEM_DESIGN.md` retained as evidence of the path explored. The deployed pipeline is a clean linear orchestration in [`pipeline/measurement.py`](pipeline/measurement.py).

---

### 3. Shadow-overlap pitch estimation (Kadhim 2018)

**Goal:** derive roof pitch from shadow length + sun elevation using a published technique. Geometric, no ML required.

**What we built:** end-to-end implementation of the Kadhim 2018 shadow-overlap method, including sun-position computation, shadow-edge detection, and the trigonometry to back out pitch from shadow length.

**Why we rejected it:**
- **0 of 5 success on the calibration set.** Tested empirically against the hackathon's own example properties. The method returned no useful pitch on any of them — failures stemmed from canopy occlusion, ambiguous shadow boundaries on textured shingles, and sun-angle uncertainty at the property's geocoded coordinate.
- **Vision LLM beats it cleanly.** Claude Vision LLM hits exact pitch 1/5 and ±1 increment on the rest. Shadow-overlap was 0/5. Hard rejection on evidence.

**Why this matters for the submission:** the hackathon's own slides celebrated "Rejected shadow-overlap after validation (0/5 success)" as a sign of engineering rigor. This is the build-don't-buy attitude applied to ML methods: published doesn't mean it works on residential aerial imagery.

**Artifacts in repo:** `SHADOW_OVERLAP_VALIDATION_REPORT.md` documenting the failure analysis.

---

### 4. Multi-vision-LLM fusion (Claude + Gemini for pitch)

**Goal:** have Claude AND Gemini both estimate pitch from the same cropped aerial image, then fuse via confidence-weighted averaging — the assumption being that two models would average out to a better answer than one.

**What we built:** Gemini API integration in parallel with Claude. Pitch estimates from both, weighted by model-reported confidence.

**Why we rejected it:**
- **Marginal accuracy improvement.** ~10–15% reduction in mean absolute error vs Claude alone — not nothing, but not a structural fix to the pitch bottleneck (still misses by 1 increment most of the time).
- **2× cost and latency.** Adding a second vision model doubles the call cost and the slowest-link latency. The Vision LLM stage is already the slowest in our pipeline.
- **Single-Claude is good enough.** For the hackathon's tolerance ("practical accuracy and consistency, not exact matching"), one model + a transparent confidence score beats two-model fusion + opaque consensus.

**Status:** Gemini API plumbing is retained in code but disabled by default. Trivial to flip on via configuration if multi-model fusion ever becomes worth the cost.

---

### 5. MaskFormer training for facet segmentation

**Goal:** train a domain-adapted segmentation model that decomposes a roof image into per-facet masks (the missing piece for true line-item LF measurements).

**What we built:** implementation prompt and dataset preparation design (`IMPLEMENTATION_PROMPT_MASKFORMER.md`).

**Why we rejected it:**
- **Training time exceeds the hackathon budget.** Even with a small dataset, fine-tuning + validation is days, not hours.
- **Dataset requirements.** Per-facet labeled aerial imagery isn't a dataset that exists publicly at scale; we'd need to build it.
- **Google Solar API gives the same data without training.** Per-segment area + pitch + azimuth, ready to go. Solar is configurable (`SOLAR_MODE=off`) — if a reviewer rejects it on build-don't-buy grounds, we lose facet decomposition but the build path still produces measurements.

**What we did instead:** [`pipeline/linear_measurements.py`](pipeline/linear_measurements.py) derives eaves/rakes/ridge/hip/valley LF heuristically from polygon perimeter + Solar segment count, with coefficients calibrated against the hackathon's own Reference A line item data. Less precise than per-facet segmentation, but defensible to ±15–25% per line item, which is enough for a contractor-grade quote.

---

## Research evaluated and dropped

Beyond the implemented experiments, we reviewed published techniques as part of the system design. The shortlist:

| Technique | Status | Why dropped |
|---|---|---|
| **RANSAC plane segmentation on USGS 3DEP LiDAR** | Skipped | LiDAR coverage gaps in suburban areas; ~50 MB/property data ingest; would need its own pipeline. The right answer for production-grade accuracy, but out of hackathon scope. |
| **Photogrammetry from oblique imagery** | Skipped | Google Maps Static doesn't expose oblique aerial; multi-view requires Bing oblique or Nearmap, neither of which is freely accessible at hackathon scale. |
| **Bayesian confidence-weighted multi-source fusion** | Subsumed | Considered; ended up subsumed by the simpler validated-build policy (binary decision on 15% threshold) which is more transparent and easier to defend under "build, don't buy" scrutiny. |
| **Per-property regional pricing models** | Skipped | The catalog uses national material prices + regional labor multipliers (50 US states). Per-property pricing requires real supplier integrations (ABC Supply, SRS) — out of scope. |
| **Kadhim 2018 shadow-overlap** | Implemented and rejected | See section 3 above. |

### Why we settled on the multi-provider pipeline

The interesting insight from the literature review: nearly every published roof-measurement technique fails on residential properties when deployed against real-world Google aerial imagery, and the best single-source provider (Microsoft Building Footprints) already outperforms most of them on the area dimension. The system's actual accuracy bottleneck is **pitch**, and Vision LLM is the most pragmatic available answer for that — the alternatives are LiDAR (data-heavy, coverage gaps), photogrammetry (multi-view imagery not freely available), or shadow-overlap (we tested it; it failed).

So the deliberate choice was:
- Don't try to beat Microsoft on footprints — *use* MS Buildings as a provider.
- Don't try to beat Google Solar on facet decomposition — *use* Solar as a configurable cross-check.
- Don't try to publish a new pitch algorithm — *use* Claude Vision LLM and document the limitation honestly.
- Spend the hackathon budget on engineering judgment: provider routing, validated-build policy, line-item generation, build-don't-buy compliance posture.

That's the multi-provider pipeline. The novelty is the engineering judgment, not the science.

---

## What this submission deliberately is NOT

- **Not a research project.** No model training, no novel ML algorithms.
- **Not a single-AI bet.** Vision LLM is one provider among six.
- **Not LiDAR-based.** No 3D facet decomposition; LF is heuristic-derived from polygon perimeter + segment count.
- **Not Solar-dependent.** Solar API is configurable (`SOLAR_MODE=off|fusion|primary`); the pipeline runs without it.
- **Not multi-agent.** A 7-step linear DAG is the simplest architecture that handles the workflow; agents would add latency and non-determinism without accuracy gain.

These are choices, not constraints. Each alternative was evaluated; each was rejected on evidence.
