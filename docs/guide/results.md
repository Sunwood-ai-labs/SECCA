# Results

The published record contains one scored Beam Free artifact. It is an experiment report, not a model leaderboard or a population estimate.

![Beam Free output, canonical white-background preview](/beam-preview.png)

## Beam Free · 2026-10-17

| Field | Recorded value |
| --- | --- |
| OpenCode model | `opencode/beam-free` |
| API model | `beam-free` |
| Attempts | 2, with 1 scored artifact |
| Likeness | **25/100** |
| Generation time | 152.219 seconds |
| Usage cost | $0 recorded by OpenCode |
| Saved formats | FCStd and STEP |
| Reopened geometry | 33 solids in each, 0 invalid shapes |

The first attempt returned HTTP 403 during a free-tier connection check and produced no CAD. It has no generation-performance score. The successful second attempt recorded 54 API requests, all HTTP 200. No HTTP 429 was observed; this was not a rate-limit load test and establishes no numerical capacity limit.

The first relay dropped client identification headers. A separate retry followed a source-backed fix that forwards four observed client headers without changing their values. The experiment does not establish which header is necessary for the provider's current free-tier decision.

## Score evidence

| Criterion | Median | Visible reason |
| --- | ---: | --- |
| Silhouette and proportions | 9/25 | Low four-wheel form, but a long exposed rectangular frame replaces the reference's compact body silhouette |
| Component layout | 9/20 | Seat, steering wheel, and engine-like part exist; engine placement differs and side pods are absent |
| Characteristic geometry | 4/30 | Cylinders and boxes replace curved seat, tapered nose, bodywork, and tire or rim shapes |
| Mechanical detail | 2/20 | Axles and a simple exhaust exist; cooling fins, chain, sprocket, steering links, and joints remain limited |
| Color and material regions | 1/5 | Black tires correspond; gray frame, blue-purple seat, and red body regions differ |

The coordinator's initial total was 33. Two fresh-context, model-blinded reviewers returned totals of 24 and 25. The final 25 is the **sum of criterion medians**, not an average of totals. Evaluator model IDs were unavailable and are recorded as unknown. Every reviewer inspected the reference and the three rendered views.

## Interpret the measurements

Generation time runs from generation start to OpenCode termination. It includes model waiting, internal corrections, and MCP work. It excludes image build, setup, and later inspection and rendering. Setup took 7.281 seconds. The run including preparation, collection, and cleanup took 180.516 seconds.

The $0 cost is an OpenCode usage-record value, not an audited billing statement. The transcript audit found error signals in 16 tool calls. The simple run-summary parser counted only one error, so the audit accompanies the summary. Final-file validation and intermediate errors remain separate evidence.

FCStd reopen and STEP reimport succeeded in a separate offline container. The recorded bounding-box difference was 0 mm, with 33 solids and no invalid shapes in each format. Original file hashes remained unchanged after inspection and rendering. This establishes the recorded round-trip checks, not accuracy to the reference's unknown dimensions.

## Input modality and comparison limits

Beam Free's published model metadata declares no native image input. The candidate used Python and PIL to inspect pixels and produce ASCII, color, region, and axis-analysis text. The coordinator did not supply a generated image description. This measures the agent's use of an image file through tools, not native visual-input capability. Raw inference request bodies and an observed attachment-warning instance were not retained.

The historical GLM fixture scored 43 under a Windows-host runtime. It is retained for provenance and replay, not a strict 25-versus-43 model comparison. No repeated-run uncertainty or general model ranking is established.

## Inspect the published files

[Experiment report](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/REPORT.md) · [Structured result](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/RESULT.json) · [Score and reviews](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/trial-02/score.json) · [CAD validation](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/trial-02/evidence/validation.json) · [Published file hashes](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/export-manifest.json)
