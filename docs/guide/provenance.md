# Provenance

SECCA preserves the origin and limits of its code, task inputs, historical fixtures, and published experiments. The public name does not grant rights to every file in the benchmark.

## Code and original identity

Project code and the original geometric SECCA artwork are covered by the repository's [license](https://github.com/Sunwood-ai-labs/SECCA/blob/main/LICENSE), subject to its exclusions. The snow-crystal and CAD-cube SVGs were created for this project. They contain no third-party brand mark.

Vendored FreeCAD MCP retains its [MIT license](https://github.com/Sunwood-ai-labs/SECCA/blob/main/container/vendor/freecad-mcp/LICENSE) and [source manifest](https://github.com/Sunwood-ai-labs/SECCA/blob/main/container/vendor/source-manifest.json). The container also installs FreeCAD and other dependencies under their respective licenses. The project license does not replace those licenses.

## Reference image and CAD data

The reference is a user-provided screenshot. Its original source, author, and license were not recorded. Do not treat the MIT code license as permission to use or redistribute the image or depicted design. Generated CAD and renders do not resolve rights to that design. See [data provenance](https://github.com/Sunwood-ai-labs/SECCA/blob/main/NOTICE.md) for the repository's data notice.

The image's SHA-256 is preserved in the fixed protocol and asset manifest. That hash establishes which bytes the trial used; it does not establish ownership or licensing.

## Historical baseline

`assets/baseline/` preserves a single `opencode/glm-5.3-flash-free` Windows-host run. Its original score is 43, aggregated from an identity-aware coordinator's 45 and two independent 42-point reviews using criterion medians. It is not a Podman-generated baseline or three fully blinded ratings.

Offline replay demonstrates that saved fixture CAD can be reopened and rendered under the recorded runtime. Replay does not mean a model regenerated the fixture. Recalculate the historical score with:

```sh
uv run --frozen python scripts/scores.py verify-baseline
```

## Published Beam experiment

The [experiment export](https://github.com/Sunwood-ai-labs/SECCA/tree/main/experiments/beam-free-20261017) preserves the report, scored CAD, views, review evidence, run events, and selected execution records. The export manifest records published file hashes and source-to-export transformations. Read its notice when checking portable copies of original management records.

The Beam runtime image ID and model-catalog source belong to that experiment. The older runtime-verification snapshot and a later public-release runtime can have different image IDs. Match every claim to its own record.

## Reproducibility scope

The source recipe pins important versions and base-image digests and records package state, inputs, and resolved image IDs. Some external dependency availability, provider behavior, service load, and evaluation conditions remain outside the repository's control. Preserve the OCI image and raw evidence when reproducing a result. A fixed prompt alone does not guarantee identical model output or render bytes.
