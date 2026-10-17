# Verify the runtime without model inference

Run these commands from the SECCA repository root. The host needs Python 3.12 or later and uv. The integration check also needs Podman and a built runtime image.

## Check the fixed contract and host code

```sh
uv sync --frozen
uv run --frozen python scripts/candidate.py verify-assets
uv run --frozen python scripts/scores.py verify-baseline
uv run --frozen python scripts/validate_skill.py
uv run --frozen python -m unittest discover -s scripts -p 'test_*.py'
```

After dependencies are installed, these checks use local files, child fixtures, and local HTTP servers. They do not contact model providers, start Podman, or require FreeCAD. Unix-socket tests can skip on hosts without Unix sockets. Run the integration check on Linux to exercise them.

The baseline command recalculates the historical 43/100 result. It does not generate or judge a new CAD artifact.

## Check real FreeCAD and MCP in Podman

Use an explicit named connection. Keep the default connection unchanged.

```sh
uv run --frozen python scripts/candidate.py build --connection CONNECTION --tag localhost/kart-sbx-secca:v0.1.0
uv run --frozen python scripts/verify_runtime.py --connection CONNECTION --image localhost/kart-sbx-secca:v0.1.0 --output /absolute/path/to/new-runtime-evidence
```

The build downloads dependencies. The verification container has no external network, host bind mounts, API socket, or credentials. It runs as UID 10000 with a read-only root, zero effective, permitted, and bounding capabilities, and `no-new-privileges`. Only the check's own container is removed afterward.

The check resolves and records the immutable image ID, then compares all embedded runtime and vendored MCP source hashes against the checkout. It fails on a mismatch. Rebuild the image after changing `container/` sources.

The check creates a 2 by 3 by 4 box through MCP, saves FCStd and STEP files, reopens both in headless FreeCAD, and verifies a valid solid with volume 24. It downloads a 640 by 480 PNG, checks that the image is nonempty and all four background corners are white, and verifies the downloaded artifact hashes. It also runs the gateway's local HTTP and Unix-socket tests inside Linux, including rejected model changes, remote history, remote content, and malformed identity headers. No inference request leaves the container.

The new evidence directory contains `verification.json`, `smoke-result.json`, the CAD files, PNG, gateway test output, and Podman command evidence. A failed check returns a nonzero status and retains the available evidence. An existing output directory is rejected.

For native Linux CI, start the user Podman socket and register a local named connection before invoking the same commands:

```sh
systemctl --user start podman.socket
podman system connection add secca-ci "unix:///run/user/$(id -u)/podman/podman.sock"
```

Use `--connection secca-ci` for both build and verification. This registration does not select a new default. On systems without a user systemd session, start `podman system service` on an explicit Unix socket and register that socket instead.

## Reproducibility limits

The Containerfile pins base-image digests, the direct FreeCAD package version, OpenCode 1.19.3, and uv 0.9.4. The bundled MCP lockfile fixes its Python dependency graph. `container/vendor/source-manifest.json` fixes the included MCP bytes and records upstream HEAD `5dbfe2c80b53c3102bff0723951676e16edf2d84`. It explicitly includes local working-tree files, so that HEAD alone does not reproduce the bundled source.

APT indexes and transitive Debian packages are not captured in a package snapshot. Availability of the pinned FreeCAD package, npm artifacts, PyPI artifacts, and base-image registries can change. A later build is not guaranteed to produce the same image ID. Inspect `/opt/debian-packages.lock` in the built image for its resolved Debian packages. Transfer an OCI archive when the exact existing runtime is required, as described in [the run guide](run.md).

PNG bytes can differ across FreeCAD, Qt, or graphics environments. Geometry validity and fixed camera rules remain separate from visual likeness scores. This smoke test proves runtime operation and isolation checks; it does not measure model performance or prove a complete denial-of-service boundary.

## Verify the historical public records

`references/verification/` and `references/verified-runtime.json` contain transformed historical records. Host home paths and Podman connection names are replaced with placeholders. Each record identifies itself as a public transformation rather than a raw record. [The export manifest](public-export-manifest.json) records the source and export SHA-256 values and the applied transformations. Fixed assets and CAD bytes are excluded from this export.

```sh
uv run --frozen python scripts/export_reference_records.py --verify --output .
```

This check validates the exported hashes, record markers, and manifest coverage without access to the private originals. Exporting again requires the separate original skill root through `--source` and an explicit public repository root through `--output`. It does not run FreeCAD or generate a new model result.
