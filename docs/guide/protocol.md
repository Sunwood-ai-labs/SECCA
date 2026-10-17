# Fixed protocol

The canonical protocol is [`assets/protocol.json`](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/protocol.json), ID `racing-kart-image-v2-podman`, version `2.0`, frozen on 2026-10-17. The public SECCA name does not change this identifier or any frozen asset bytes.

## Candidate inputs

The candidate receives the original image and this Japanese prompt:

> 添付画像のレーシングカートをFreeCAD MCPで作成し、racing-kart.FCStdとracing-kart.stepに保存してください。

The requested outputs are `racing-kart.FCStd` and `racing-kart.step`. The reference image, prompt, rubric, and render settings have recorded SHA-256 values. `candidate.py verify-assets` checks all manifest entries.

The candidate does not receive the rubric, historical CAD, previous results, reviewer material, or the management skill. Generic runtime instructions and selected model configuration remain part of the execution environment.

## Execution contract

| Setting | Fixed condition |
| --- | --- |
| Agent runtime | OpenCode 1.19.3, `run --pure`, selected model |
| CAD runtime | FreeCAD GUI on Xvfb and stdio FreeCAD MCP |
| Trial limit | 1,800 seconds by default |
| Model substitution | No automatic switch, including a free-to-paid switch |
| Candidate environment | Fresh workspace, home, document, and per-trial API socket |
| Generation boundary | Podman Linux, network `none`, no host CAD access |
| Temperature and seed | Provider default and unspecified, recorded if changed or exposed |

API refusal or missing CAD is an observed outcome. A manually restarted attempt is a separate trial. Model-side tool retries remain inside the original attempt and its generation time.

## Render contract

[`assets/render-spec.json`](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/render-spec.json) fixes orthographic projection, white background, Flat Lines display, model colors and visibility, and camera quaternions.

| View | Size |
| --- | --- |
| Isometric | 1600 × 1000 |
| Top | 1280 × 900 |
| Right | 1280 × 900 |
| Preview derived from isometric | 960 × 600 |

The renderer uses `fitAll`. Do not rotate or move geometry to choose a more flattering camera. Supplemental views need separate filenames and recorded transforms. Rendering must not resave the source document. Identical PNG bytes are not promised across FreeCAD, Qt, GPU, or driver environments.

## Comparison boundary

Changing the input, tools, runtime image, render conditions, or rubric is a protocol deviation. Preserve the changed conditions rather than merge unlike results. Provider stochasticity and service load remain uncontrolled.

The rubric was designed after historical baseline generation, before its numeric scoring, and frozen before future model runs. The 43-point Windows-host fixture predates the v2 Podman environment. Strict comparisons require regeneration and evaluation under the same runtime and reviewer settings.
