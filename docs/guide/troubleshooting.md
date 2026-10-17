# Troubleshooting

Keep the failed attempt and its evidence. Apply setup fixes to a fresh trial rather than overwrite the record.

## Podman or runtime is unavailable

Run `podman machine list`, `podman system connection list`, and `podman --connection "<CONNECTION>" info`. Use the live named connection explicitly. Do not change the default connection or fall back to host FreeCAD.

Runtime tags must start with `localhost/kart-sbx-`. A public project rename does not remove this validation rule. Use the tag in [Get started](./getting-started) and record the resolved image ID.

## Asset verification fails

Compare the file with the committed version and inspect `assets/manifest.json`. Restore accidental changes. Intentional changes require a new documented protocol condition; do not silently refresh hashes and keep the old comparison claim.

## The provider returns 403, 429, or a timeout

Read the gateway and event logs without exposing credentials. Confirm the recorded endpoint and model, account authorization, and client compatibility. A 403 is a setup failure, not a likeness score. A 429 records provider throttling for that attempt, not a general rate limit measurement.

Preserve response status and timing. Do not substitute another endpoint, paid tier, or model. Retry manually only as a separate recorded trial after resolving the cause.

## The model is absent or text-only

For a missing catalog entry, use documented `--model-metadata` support and preserve its official source URL and original hash. Keep attachment support and modalities truthful. Text-only status must remain text-only. See [Run a trial](./run).

Tool-based pixel inspection can occur if the model reads the supplied file. Describe that observed path separately from native image input. If no CAD is produced, record the failure rather than infer visual capability.

## CAD or rendering fails

Inspect `evidence/run.events.jsonl`, `evidence/validation.json`, and `evidence/render.json`. An exit code of zero or a model's completion message does not prove valid saved CAD. Tool text can contain exceptions that summary counters miss.

Confirm that the candidate stopped before postprocessing and that the offline container uses the recorded image ID. Do not repair source geometry to make scoring possible. Keep missing outputs or failed rendering as unscorable outcomes.

## The documentation has missing pages or assets

Run `npm ci`, `npm run docs:check`, and `npm run docs:build`. The base is `/SECCA/` and the artifact directory is `docs/.vitepress/dist`. Open the development server's printed URL or the deployed `/SECCA/` URL. A successful local build alone does not establish a successful Pages deployment.
