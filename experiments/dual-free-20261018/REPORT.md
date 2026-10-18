# Archived dual-model CAD experiment, 2026-10-18

One output per model was generated from the fixed racing-kart image and prompt.
DeepSeek V4.1 Flash Free scored **50/100** and Nemotron 3.5 Super VL Free scored
**28.75/100** for visual likeness. The scores do not include CAD validity.

| Recorded measure | Nemotron 3.5 Super VL Free | DeepSeek V4.1 Flash Free |
| --- | ---: | ---: |
| Criterion medians, maximum 25/20/30/20/5 | 6.25, 5, 7.5, 5, 5 | 12.5, 15, 7.5, 10, 5 |
| Visual score | 28.75/100 | 50/100 |
| Native FCStd valid solids | 30 | 26 |
| Submitted STEP valid solids | 0, empty import | 26, bounds match |
| Generation seconds | 71.464 | 442.688 |
| Startup seconds | 8.079 | 7.912 |
| Runner wall seconds | 101.507 | 472.030 |
| Tool calls | 7 | 28 |
| HTTP requests | 8, all 200 | 26, all 200 |
| OpenCode recorded cost, USD | 0 | 0 |

These are two individual outputs, not model-population rankings. Concurrent,
single-run durations do not establish a speed advantage. Generation time includes
model waits, autonomous retries, and MCP work from generation start to OpenCode
exit. Startup and independent postprocessing are separate. HTTP counts include
auxiliary OpenCode requests. Cost is the client record, not an audited bill.
The absence of HTTP 429 in these requests does not establish a provider rate cap.

## Fixed task and independent execution

The protocol is [racing-kart-image-v2-podman](../../assets/protocol.json).
The candidate received the [reference image](../../assets/reference.jpg), the
[prompt](../../assets/prompt.txt), and execution settings. The
[plan](PLAN.json) binds image, prompt, rubric, render settings, and protocol hashes.
The exact sent UTF-8 prompt hash is also recorded separately from the prompt file.

Model IDs were `opencode/nemotron-3.5-super-vl-free` and
`opencode/deepseek-v4.1-flash-free`, through the official fixed endpoint
`https://opencode.ai/inference/openai/v1`. Runtime image
`sha256:b9e296032f921c96de5843b19e1a182ce5067d6cdca25a5d3ab7e7da23fe89cb`
contained OpenCode 1.19.3 and FreeCAD 1.0.0. Harness source was
`dc7b1273fcdd1534b903185e2d7921cb7e7784f5`. Selected model metadata cites
models.dev revision `8deeec23540f4c0e2c473be7f08130366e662c78`.

Each candidate had its own container, FreeCAD document, work volume, home volume,
and API socket volume. The [isolation audit](isolation-audit.json) records six
distinct candidate volumes and no shared writable volume or host bind mount.
Candidates ran as UID 10000 with network none, a read-only root, no capabilities,
and no-new-privileges. A separate gateway held each trial's temporary free-tier
credential. Candidates could not read host homes, other CAD, judges, or baselines.
Both trials used 2 CPUs, 4 GiB, 512 PIDs, and a 1800-second generation timeout.

There was one generation per model, with no maintainer geometry repair, follow-up
quality instruction, or manual regeneration. Autonomous tool retries remain in
the archived events. Earlier environment-variable setup rejections occurred
before inference and did not produce additional candidate samples.

This CAD run did not capture inference request bodies. Fixed image hashes,
attachment CLI execution, and image-capable metadata do not independently prove
the image payload on the wire in these trials. A separate earlier image-input
probe is outside this export and is not substituted for current-trial evidence.

## Visual review

Each identity-aware coordinator saved an initial review before two fresh-context,
model-blinded reviewers received separate image packets. The
[dispatch record](review-dispatch.json) and six original reviews preserve roles,
declared source scope, timestamps, and image hashes. Review model identifiers were
not exposed and remain unknown. JSON declarations and timestamps alone cannot
prove fresh contexts or reviewer independence. No cross-model judge robustness
claim follows from this procedure.

The five criterion medians are summed. The median of total scores is not used.
For DeepSeek the individual totals are 50, 48.75, and 45, while the required
criterion-median sum is 50. Nemotron's totals are 33.75, 23.75, and 28.75.
Judges viewed the reference and fixed isometric, top, and right white renders.
The preview is only for browsing.

Nemotron has wheel, seat, panel, engine, and frame placeholders, but disconnected
straight rods, box-shaped seating and bodywork, plain wheel faces, and little
engine or drive detail differ from the reference. DeepSeek forms a more coherent
kart layout, with a curved front bumper and recognizable wheels, seat, steering,
and engine. Box-shaped front bodywork, angular seating, simple rims, and simplified
engine and drivetrain geometry still reduce its likeness score.

| Candidate | Scores and reasons | Original reviews | CAD and views |
| --- | --- | --- | --- |
| Nemotron | [Score](nemotron/trial-01/score.json) | [Coordinator](reviews/nemotron/coordinator.json), [A](reviews/nemotron/blind-a.json), [B](reviews/nemotron/blind-b.json) | [FCStd](nemotron/trial-01/workspace/racing-kart.FCStd), [submitted STEP](nemotron/trial-01/workspace/racing-kart.step), [preview](nemotron/trial-01/renders/preview.png), [isometric](nemotron/trial-01/renders/isometric.png), [top](nemotron/trial-01/renders/top.png), [right](nemotron/trial-01/renders/right.png) |
| DeepSeek | [Score](deepseek/trial-01/score.json) | [Coordinator](reviews/deepseek/coordinator.json), [A](reviews/deepseek/blind-a.json), [B](reviews/deepseek/blind-b.json) | [FCStd](deepseek/trial-01/workspace/racing-kart.FCStd), [STEP](deepseek/trial-01/workspace/racing-kart.step), [preview](deepseek/trial-01/renders/preview.png), [isometric](deepseek/trial-01/renders/isometric.png), [top](deepseek/trial-01/renders/top.png), [right](deepseek/trial-01/renders/right.png) |

Exact dimensions, hidden connections, mechanical function, and manufacturability
cannot be established by this visual task. Earlier Windows GLM and different-runtime
Beam samples are not strict controls for these runs.

## Native validation, errors, and cleanup

Separate offline containers reopened saved FCStd and imported submitted STEP after
candidate stop. Original CAD hashes matched before and after inspection/rendering.
[Nemotron validation](nemotron/trial-01/evidence/validation.json) found 30 valid
native solids but a 1640-byte STEP importing zero objects and zero solids. That
CAD output pair failed. [DeepSeek validation](deepseek/trial-01/evidence/validation.json)
found 26 valid solids in each format, with bounds matching within 0.01 mm.

Nemotron's parser reported zero tool failures, but its raw events contain one bash
exit 127 because `file` was unavailable. DeepSeek had one permission-denied write
and three completed tool results containing FreeCAD GUI/document errors. It
recovered autonomously. Process exit zero and HTTP 200 do not prove valid CAD.

The [trial audit](trial-audit.json) records these checks and discrepancies.
Original events and gateway logs are included for each model:
[Nemotron events](nemotron/trial-01/evidence/run.events.jsonl),
[gateway](nemotron/trial-01/evidence/gateway.log),
[DeepSeek events](deepseek/trial-01/evidence/run.events.jsonl), and
[gateway](deepseek/trial-01/evidence/gateway.log).
The [final cleanup check](final-cleanup-check.json) queried each exact trial label
and found no owned container, volume, or temporary secret. Other tasks' settings
and the Podman default connection were preserved.

## Public export and data rights

The [manifest](export-manifest.json) identifies every public file, its byte size,
source SHA-256, export SHA-256, transformations, and omitted records. Original CAD,
all eight PNGs, all six reviews, generation events, and logs retain their bytes.
Portable management JSON replaces local paths and connection names. Cross-file
hashes affected by those edits are rebound to exported bytes, while original
hashes remain in the manifest. Audit references to omitted records retain
historical identifiers and are not proof that those records are bundled.

The fixed reference is reused from root assets rather than duplicated. Full host
storage/inspect records, transport commands, temporary review CAD, local decision
history, preflight management records, and full external catalogs are excluded.
The original local report is replaced by this public summary. The verifier checks
the actual file inventory, hashes, raw-artifact preservation, review aggregation,
review evidence hashes, CAD validation links, render hashes, inputs, timing and
gateway counts, local Markdown links, and publication patterns including FCStd
text members. Pattern scans do not guarantee absence of every possible secret.

The input is a user-provided screenshot whose original author, URL, and license
are unknown. No ownership or attribution is inferred. Repository code licensing
does not grant rights in the reference, generated CAD, renders, or model output.
See [NOTICE](../../NOTICE.md) and [LICENSE](../../LICENSE) for scope.

Packaging this archive ran no model inference, new visual review, host FreeCAD,
or geometry repair. These statements describe the archived 2026-10-18 experiment.
