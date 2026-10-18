<p align="center"><img src="brand/secca-header.svg" alt="SECCA · 雪華. Solid-model Evaluation of CAD Construction Agents." width="900"></p>

<p align="center"><strong>English</strong> · <a href="README.ja.md">日本語</a></p>

<p align="center">
  <a href="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/ci.yml"><img src="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/ci.yml/badge.svg" alt="CI workflow status"></a>
  <a href="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/pages.yml"><img src="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/pages.yml/badge.svg" alt="Documentation deployment status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-087f8c" alt="Code license MIT"></a>
  <img src="https://img.shields.io/badge/runtime-Podman-123b4a" alt="Podman runtime">
</p>

SECCA evaluates how a CAD construction agent turns a fixed racing-kart image and prompt into saved FreeCAD and STEP files. The repository preserves the protocol, isolated execution tools, white-background renders, and review evidence. **SECCA** stands for **Solid-model Evaluation of CAD Construction Agents**. Its Japanese name is **雪華**, read **せっか** (sekka).

[Documentation](https://sunwood-ai-labs.github.io/SECCA/) · [Run a trial](docs/guide/run.md) · [Results and limits](docs/guide/results.md) · [Protocol](assets/protocol.json)

## ❄️ One task, inspectable evidence

- Give the candidate the original image and one fixed Japanese prompt.
- Run OpenCode, FreeCAD, and FreeCAD MCP in a fresh Podman container. Keep host CAD, other trials, and judging material outside it.
- Reopen the saved CAD in a separate offline container and render fixed isometric, top, and right views on white.
- Record one identity-aware coordinator review and two independent, fresh-context, model-blinded reviews. Sum the median score for each criterion.

The current task is a visual reconstruction experiment. It does not establish dimensional accuracy, mechanical function, manufacturing suitability, or general model performance.

## 🧪 Published experiments

### Compare the four saved outputs

Compare each saved output by its image, score, and CAD checks.

| Model and score evidence | Score | Conditions |
| --- | ---: | --- |
| [GLM 5.3 Flash Free](assets/baseline/likeness-score.json) | **43/100** | Windows, no isolation |
| [Beam Free](experiments/beam-free-20261017/trial-02/score.json) | **25/100** | Podman B, Python pixel inspection |
| [Nemotron 3.5 Super VL Free](experiments/dual-free-20261018/nemotron/trial-01/score.json) | **28.75/100** | Independent Podman A, image attached |
| [DeepSeek V4.1 Flash Free](experiments/dual-free-20261018/deepseek/trial-01/score.json) | **50/100** | Independent Podman A, image attached |

| GLM 5.3 Flash Free · 43/100 | Beam Free · 25/100 |
| --- | --- |
| ![GLM 5.3 Flash Free](assets/baseline/evidence/kart-front-isometric-white.png) | ![Beam Free](experiments/beam-free-20261017/trial-02/renders/preview.png) |
| **Nemotron 3.5 Super VL Free · 28.75/100** | **DeepSeek V4.1 Flash Free · 50/100** |
| ![Nemotron 3.5 Super VL Free](experiments/dual-free-20261018/nemotron/trial-01/renders/preview.png) | ![DeepSeek V4.1 Flash Free](experiments/dual-free-20261018/deepseek/trial-01/renders/preview.png) |

| Model | FCStd | STEP | Generation |
| --- | --- | --- | ---: |
| GLM | 77 valid solids | 77 valid solids | 509.969 s |
| Beam | 33 valid solids | 33 valid solids | 152.219 s |
| Nemotron | 30 valid solids | No geometry | 71.464 s |
| DeepSeek | 26 valid solids | 26 valid solids | 442.688 s |

| Criterion and maximum | GLM | Beam | Nemotron | DeepSeek |
| --- | ---: | ---: | ---: | ---: |
| Silhouette and proportions /25 | 13 | 9 | 6.25 | 12.5 |
| Component layout /20 | 13 | 9 | 5 | 15 |
| Characteristic geometry /30 | 8 | 4 | 7.5 | 7.5 |
| Mechanical detail /20 | 4 | 2 | 5 | 10 |
| Color and material regions /5 | 5 | 1 | 5 | 5 |
| Sum of criterion medians /100 | **43** | **25** | **28.75** | **50** |

This is a reference comparison of one saved output per model. Podman A used the same pinned FreeCAD 1.0.0 image for two candidates; B used a different image. Beam did not use native image input. GLM used FreeCAD 1.1.3, with its rubric authored after generation and before numeric scoring. The later Podman trials fixed the rubric before generation. GLM, Nemotron, and DeepSeek each made one generation. Beam had two attempts with one scored output.

These are archived white-background views, not rerenders of all four outputs with an identical camera. Visual likeness and CAD validity are separate checks. Single records with differing conditions do not establish general model rankings or speed advantages.

### Nemotron and DeepSeek · 2026-10-18

Each model generated one output in its own Podman environment using the same fixed inputs and runtime image. One coordinator and two fresh-context, model-blinded reviewers scored each output. The final score sums the criterion medians. CAD validity is separate from likeness: Nemotron's empty STEP fails the output-pair check.

These are two saved outputs, not a general model ranking or a speed comparison. The CAD runs did not retain inference request bodies, so their image payloads cannot be checked against wire records. OpenCode recorded $0 for each run; billing was not independently audited. The earlier Beam and Windows GLM samples used different runtimes and remain separate records.

[Experiment files and evidence](experiments/dual-free-20261018/README.md) · [Results and score reasons](docs/guide/results.md)

### Beam Free · 2026-10-17

| Experiment | Outcome | Scope |
| --- | --- | --- |
| Beam Free, 2026-10-17 | **25/100** for one generated artifact | Two attempts, one scored output. The first attempt returned HTTP 403 during setup. |

The scored run recorded 152.219 seconds of generation time and $0 in the OpenCode usage log. The cost is a recorded client value, not an audited invoice. Saved FCStd and STEP files reopened successfully with 33 solids each and no invalid shapes. CAD validity does not add to the likeness score.

Beam Free's catalog declares text-only input. The agent independently used Python to inspect the supplied image's pixels. This result is **not a measurement of native image-input capability**. The historical GLM result of 43/100 used a Windows host runtime and is not a strict comparison with this isolated run.

[Read the experiment report](experiments/beam-free-20261017/REPORT.md) · [Scores](experiments/beam-free-20261017/trial-02/score.json) · [CAD validation](experiments/beam-free-20261017/trial-02/evidence/validation.json)

### GLM 5.3 Flash Free · 2026-10-17, historical baseline

`opencode/glm-5.3-flash-free` produced one output on a Windows host with OpenCode 1.19.3 and FreeCAD 1.1.3. It scored **43/100**, and both saved formats reopened with 77 valid solids and matching bounds. Generation took 509.969 seconds. A flat seat, simple nose and bumper, steering-wheel orientation, and limited mechanical detail reduced likeness.

The rubric was authored after generation and before scoring. One initial review of 45 and two fresh-context, model-blinded reviews of 42 and 42 yielded 43 by summing criterion medians. The reviewers shared an assistant model family. The host run had no OS isolation, and its scored camera settings differ from the later fixed-render procedure. It remains a reference comparison with those condition differences.

[Baseline notes](references/baseline.md) · [Score](assets/baseline/likeness-score.json) · [CAD validation](assets/baseline/evidence/geometry-validation.json) · [FCStd](assets/baseline/workspace/racing-kart.FCStd) · [STEP](assets/baseline/workspace/racing-kart.step) · [Scored oblique view](assets/baseline/evidence/kart-front-isometric-white.png)

## 🚀 Get started

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Podman with a working **named connection**. Host FreeCAD and OpenCode installations are not required. Run commands from this repository's root.

1. Clone and verify the fixed assets. This step does not call a model API.

   ```sh
   git clone https://github.com/Sunwood-ai-labs/SECCA.git
   cd SECCA
   uv run --frozen python scripts/candidate.py verify-assets
   ```

2. Inspect your Podman machine and connections, then build the runtime. Replace `<CONNECTION>` with the live connection name. The `localhost/kart-sbx-` tag prefix is required by the runner.

   ```sh
   podman machine list
   podman system connection list
   uv run --frozen python scripts/candidate.py build --connection "<CONNECTION>" --tag localhost/kart-sbx-secca:v0.1.0
   ```

3. Follow [Run a trial](docs/guide/run.md) to select an authorized provider and model, prepare a fresh trial, generate CAD, and collect evidence. Running a trial calls the provider and may incur charges under your account's existing settings.

The container recipe records versions and resolved image IDs. It does not promise an indefinitely rebuildable dependency environment. Preserve an OCI image archive when you need the same runtime on another machine.

## 📐 Scoring and comparison

| Criterion | Maximum |
| --- | ---: |
| Silhouette and proportions | 25 |
| Component layout | 20 |
| Characteristic geometry | 30 |
| Mechanical detail | 20 |
| Color and material regions | 5 |

Reviewers inspect the reference and all three canonical views. Each score needs visible evidence. Time, cost, format export, solid count, and unverified dimensions are excluded. Failed or unscorable attempts retain their status rather than receiving invented numeric scores. [Scoring procedure](docs/guide/scoring.md).

Changing the prompt, reference, tool versions, runtime, render settings, or rubric changes the comparison conditions. Record deviations and rerun the baseline under the same conditions before making a strict comparison. No leaderboard or model ranking is established here.

## 🗂️ Repository map

| Path | Contents |
| --- | --- |
| `assets/` | Frozen prompt, image, protocol, rubric, render settings, historical fixture |
| `scripts/` and `container/` | Trial runner, provider gateway, CAD inspection, scoring, vendored MCP |
| `references/` | Detailed execution notes and recorded verification evidence |
| `experiments/` | Published experiment reports and artifacts |
| `docs/` and `brand/` | English and Japanese documentation, original SVG identity |

## 🛠️ Develop and verify

```sh
uv run --frozen python -m unittest discover -s scripts -p "test_*.py"
uv run --frozen python scripts/candidate.py verify-assets
npm ci
npm run docs:check
npm run docs:build
npm run docs:dev
```

The docs build writes `docs/.vitepress/dist` with the `/SECCA/` base path. Browser previews use the URL printed by VitePress. Unit tests, runtime smoke checks, and offline replay are distinct from a new model generation. [Verification and isolation limits](docs/guide/isolation.md).

## 📄 Rights and provenance

The [MIT license](LICENSE) covers project code and original artwork as stated in the license. Vendored FreeCAD MCP has its [own MIT license](container/vendor/freecad-mcp/LICENSE). The reference image is a user-provided screenshot whose original source, author, and license were not recorded. **Do not infer a data license or redistribution permission from the code license.** Generated CAD and renders do not establish rights to the depicted design. See [provenance](docs/guide/provenance.md) and [data provenance](NOTICE.md).

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Citation](CITATION.cff)
