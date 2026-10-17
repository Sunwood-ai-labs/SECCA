# Run a trial

Produce one new candidate artifact with the [prepared runtime](./getting-started). Run commands from the repository root. Replace every angle-bracket placeholder before execution.

## Prepare a fresh trial

```sh
uv run --frozen python scripts/candidate.py prepare --trial "trials/my-model-001" --model "<provider/model-id>" --connection "<CONNECTION>" --image localhost/kart-sbx-secca:v0.1.0 --api-base-url "<HTTPS_PROVIDER_API_BASE_URL>"
```

Use the provider's authorized public HTTPS inference API. Preparation records the selected model, provider endpoint, resolved image ID, and input hashes. It does not call the model.

If the API model name differs from the suffix of the OpenCode model ID, add `--api-model "<API_MODEL_ID>"`. The gateway permits that recorded value. It does not choose another model automatically.

If authentication is required, set the credential through your normal secret-management process and add `--credential-env PROVIDER_API_KEY`. The argument is an environment variable's **name**, never its value. The gateway receives a temporary Podman secret. The candidate does not receive the API key. Keep existing billing and auto-charge settings unchanged.

## Run once

```sh
uv run --frozen python scripts/candidate.py run --trial "trials/my-model-001"
```

This command invokes the selected provider and can incur charges under your account's existing settings. The default trial limit is 1,800 seconds. Generation time includes model waiting, internal retries, and MCP work. It excludes setup and later inspection or rendering.

Keep refusals, timeouts, API errors, and tool errors in the trial record. Do not repair geometry, send quality-improvement prompts, or switch models. A manual retry belongs in a new trial directory. A successful outer tool response can still contain a Python exception, so inspect event content as well as summary counters.

## Inspect and render saved CAD

After the candidate has stopped, run:

```sh
uv run --frozen python scripts/cad_artifacts.py inspect --trial "trials/my-model-001"
uv run --frozen python scripts/cad_artifacts.py render --trial "trials/my-model-001"
```

Inspection and rendering use a fresh container with the same image ID, no external network, and no inference socket. The tools reopen FCStd, reimport STEP, and write validation evidence. They render copies without resaving the source CAD.

Check `evidence/run.json`, `evidence/validation.json`, `evidence/render.json`, and `renders/`. Confirm source CAD hashes remain unchanged. Continue with [Score a result](./scoring). Missing output, failed renders, or incomplete review material make the attempt unscorable.

## Add a model missing from the bundled catalog

Save the provider's published model metadata to a JSON file. Pass its path as `--model-metadata "<FILE>"` to `prepare`. Record the source URL and SHA-256 of the original catalog. Rebuild the runtime when adding support absent from an older runtime image.

The accepted structure and field constraints are documented in the [execution reference](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/run.md). Keep the declared attachment support and input modalities unchanged. Do not enable image input when the source says text-only. The fixed image remains available as a workspace file, but that does not establish native vision support.

## Preserve a runtime

```sh
podman --connection "<CONNECTION>" save --format oci-archive --output "runtime.oci.tar" "<IMAGE_ID>"
podman --connection "<CONNECTION>" load --input "runtime.oci.tar"
```

The source repository contains a build recipe, not an OCI image. Rebuilding depends on external package availability. An image archive preserves the resolved runtime more directly than a mutable tag.
