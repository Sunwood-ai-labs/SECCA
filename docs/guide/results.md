# Results

The published record contains one scored output each from Nemotron, DeepSeek, and Beam Free. These are experiment reports, not a model leaderboard or a population estimate.

## Nemotron and DeepSeek · 2026-10-18

| Nemotron 3.5 Super VL Free | DeepSeek V4.1 Flash Free |
| --- | --- |
| ![Nemotron output on a white background](/nemotron-20261018-preview.png) | ![DeepSeek output on a white background](/deepseek-20261018-preview.png) |
| **28.75/100** likeness | **50/100** likeness |
| FCStd: 30 valid solids. STEP: 0 objects and 0 solids. | FCStd and STEP: 26 valid solids each. |
| Generation: 71.464 seconds. | Generation: 442.688 seconds. |

Each model made one generation attempt with the fixed image and Japanese prompt. Separate containers, FreeCAD documents, workspaces, homes, and communication volumes kept their execution state independent. Neither candidate received other outputs or judging material. Both used FreeCAD 1.0.0 and OpenCode 1.19.3 in the same image:

```text
sha256:b9e296032f921c96de5843b19e1a182ce5067d6cdca25a5d3ab7e7da23fe89cb
```

The model IDs were `opencode/nemotron-3.5-super-vl-free` and `opencode/deepseek-v4.1-flash-free`. The source revision was `dc7b1273fcdd1534b903185e2d7921cb7e7784f5`. No maintainer repaired the geometry or requested a new generation.

### Score evidence for the two outputs

| Criterion | Nemotron median | DeepSeek median |
| --- | ---: | ---: |
| Silhouette and proportions | 6.25/25 | 12.5/25 |
| Component layout | 5/20 | 15/20 |
| Characteristic geometry | 7.5/30 | 7.5/30 |
| Mechanical detail | 5/20 | 10/20 |
| Color and material regions | 5/5 | 5/5 |
| Total | **28.75/100** | **50/100** |

Nemotron produced separate straight frame rods, flat wheel shapes, and box-shaped seating and bodywork. The parts did not form the reference's connected silhouette. DeepSeek assembled a more coherent kart with four wheels, frame, seat, steering wheel, bodywork, and engine. Its large front box, angular seat, and simple rims, engine, and drivetrain still differed from the reference.

For each output, the identity-aware coordinator saved an initial score before two fresh-context, model-blinded reviewers inspected separate packets. Every reviewer viewed the reference and the fixed isometric, top, and right images. The coordinator and blind-review totals were 33.75, 23.75, and 28.75 for Nemotron, and 50, 48.75, and 45 for DeepSeek. The final score is the **sum of criterion medians**. DeepSeek's total-score median of 48.75 is not the protocol result. Evaluator model IDs were unavailable and are recorded as unknown.

### CAD checks and measurement limits

Independent offline containers reopened the saved CAD after candidate termination. Nemotron's FCStd contains 30 valid solids, but its 1,640-byte STEP imports no geometry. Its CAD output pair fails validation. DeepSeek's FCStd and STEP both contain 26 valid solids, with bounding boxes matching within 0.01 mm. Original CAD hashes remained unchanged through inspection and rendering. Format validity, time, cost, and solid count do not add to the visual score.

Generation time runs from generation start to OpenCode termination and includes model waiting, autonomous retries, and MCP work. It excludes setup and later inspection and rendering. These single concurrent runs establish no speed advantage or repeated-run uncertainty. OpenCode recorded $0 for both; billing was not independently audited. Nemotron's 8 API requests and DeepSeek's 26 all returned HTTP 200. This was not a rate-limit load test. The event audit found one failed shell call for Nemotron and four tool failures for DeepSeek, including errors inside responses marked complete.

The CAD runs did not retain inference request bodies. Fixed input hashes, attachment commands, and image-capable model metadata are recorded, but the actual CAD-run image payloads cannot be verified against wire records. A separate image-input probe is distinct evidence and does not fill that gap. These scores assess one saved output per model. They do not establish dimensional accuracy, mechanical function, manufacturing suitability, or general model performance. The earlier Beam and Windows GLM records used different runtimes and are not controls for this pair.

[Experiment files and provenance](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/README.md) · [Structured result](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/RESULT.json) · [Nemotron score](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/nemotron/trial-01/score.json) · [DeepSeek score](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/deepseek/trial-01/score.json)

## Beam Free · 2026-10-17

![Beam Free output, canonical white-background preview](/beam-preview.png)

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
