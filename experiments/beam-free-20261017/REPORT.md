# Beam Free archived CAD experiment, 2026-10-17

One generated sample was scored **25/100** across **two execution attempts**.
Trial 01 returned HTTP 403 before generation, so its score is null. Trial 02
saved both CAD formats and completed 54 recorded API requests with HTTP 200.

| Measure | Recorded result |
| --- | --- |
| Criterion medians | 9/25, 9/20, 4/30, 2/20, 1/5 |
| Generation time | 152.219 seconds |
| Startup / runner wall time | 7.281 / 180.516 seconds |
| Runtime-reported cost | USD 0.00 |
| Tool calls | 53 |
| Calls with diagnostic failure evidence | 16 |
| Parser-reported tool errors | 1 |
| Native / STEP solids | 33 / 33 |

Generation time runs from the generation-start event to OpenCode exit,
including model waits, retries and MCP work. It excludes startup and later
validation/rendering. Cost is the runtime's report, not an audited bill.
The absence of HTTP 429 in this single run does not establish a rate cap.
The diagnostic audit counts nonzero exits and error text that the parser's
one-error metric omits; these are execution diagnostics, separate from likeness.

The archived model metadata declares text-only input and attachment=false.
The candidate wrote Python/PIL scripts to read reference pixels and obtained
textual ASCII grids, masks, color counts and principal-axis diagnostics.
This is not a demonstrated native vision run. The event logs do not contain
raw inference request bodies or an observed attachment-warning message.

OpenCode 1.19.3 ran in Podman/Linux with a 4 GiB memory limit, 2 CPUs, 512 PIDs
and a 1800-second timeout. The candidate had no network or host bind mounts;
a fixed-provider gateway handled inference through a Unix socket. Independent
offline postprocessing reopened FCStd and imported STEP after candidate exit.
The first attempt preceded a gateway repair that forwarded authentic received
OpenCode identity headers. See [retry plan](retry-plan.json). Its exact private
free-tier rejection rule was not established.

Three reviews use the frozen rubric and the reference plus three white-background
views. One informed coordinator recorded an initial score before two declared
fresh, model-blinded reviews. Review model IDs were not exposed. JSON declarations
and timestamps do not cryptographically establish reviewer independence. The
aggregate sums the five per-criterion medians; CAD validity adds no likeness points.
The historical GLM score of 43 came from Windows and is not a strict comparison
with this Podman/Linux sample or evidence of model-population performance.

1. Read [machine-readable result](RESULT.json), [score](trial-02/score.json),
   [validation](trial-02/evidence/validation.json) and [modality audit](modality-run-audit.json).
2. Inspect [FCStd](trial-02/workspace/racing-kart.FCStd),
   [STEP](trial-02/workspace/racing-kart.step), [preview](trial-02/renders/preview.png),
   [isometric](trial-02/renders/isometric.png), [top](trial-02/renders/top.png)
   and [right](trial-02/renders/right.png).
3. Read [raw generation events](trial-02/evidence/run.events.jsonl),
   [gateway log](trial-02/evidence/gateway.log) and the three raw reviews
   ([coordinator](trial-02/evidence/review/coordinator.json),
   [A](trial-02/evidence/review/blind-a.json), [B](trial-02/evidence/review/blind-b.json)).

This is a selected public export, not the original directory in full. The
[export manifest](export-manifest.json) records source and export SHA256 values,
byte sizes, transformations and omitted material. Events, reviews, CAD and images
retain their original bytes. Portable management JSON replaces local connection
names (including command arguments), absolute review paths and private host
home/storage and per-user runtime prefixes, then rebinds all affected cross-file hashes.
Original source records remain outside the public repository. Some immutable raw
events retain sandbox session identifiers and sandbox paths as archival metadata;
they are not configuration or credentials. This package does not include the
full models.dev catalog; its source SHA256 identifies an external historical
snapshot, while the selected model record is included.

The input is a user-provided screenshot. Its original creator, source URL and
license are unknown. No attribution or ownership is inferred. Repository code
licensing does not grant rights in that image, generated CAD, renders or model
outputs. See the repository LICENSE and NOTICE for scope and exceptions.

All results here describe the archived 2026-10-17 run. No new generation,
CAD modification, visual review or live provider capability check was performed
when packaging this export.
