"""Export or verify the archived 2026-10-18 dual-model experiment offline."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics
import zipfile

MODELS = {"nemotron": 28.75, "deepseek": 50.0}
RAW_SUFFIXES = (".FCStd", ".step", ".png", ".jsonl", ".log")
ROOT_FILES = ("PLAN.json", "isolation-audit.json", "trial-audit.json",
              "final-cleanup-check.json", "review-dispatch.json")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def portable(value, source: Path, repository: Path):
    if isinstance(value, dict):
        return {portable(key, source, repository):
                "local-connection" if key == "connection" else portable(item, source, repository)
                for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item, source, repository) for item in value]
    if isinstance(value, str):
        text = value.replace("\\", "/")
        for prefix, replacement in ((source.as_posix() + "/", ""),
                                     (repository.as_posix() + "/", "../../")):
            if text.lower().startswith(prefix.lower()):
                return replacement + text[len(prefix):]
        if text.startswith("C:/Prj/cad-review/"):
            return "<private-image-packet>/" + text.rsplit("/", 1)[-1]
        if value in ("runtime-input/reference.jpg", "workspace/reference.jpg"):
            return "../../../../assets/reference.jpg"
        return text if "\\" in value and not value.startswith("HTTP") else value
    return value


def export(source: Path, output: Path):
    require(not output.exists() or not any(output.iterdir()), "Destination must be new or empty")
    repository = Path(__file__).resolve().parents[2]
    names = list(ROOT_FILES)
    for model in MODELS:
        names += [f"reviews/{model}/{role}.json" for role in ("coordinator", "blind-a", "blind-b")]
        base = f"{model}/trial-01/"
        names += [base + name for name in ("trial.json", "protocol.json", "score.json",
                 "runtime-input/runtime.json", "runtime-input/model-metadata.json",
                 "workspace/racing-kart.FCStd", "workspace/racing-kart.step",
                 "evidence/run.json", "evidence/run.events.jsonl", "evidence/gateway.log",
                 "evidence/stderr.log", "evidence/validation.json", "evidence/render.json",
                 "renders/isometric.png", "renders/top.png", "renders/right.png", "renders/preview.png")]
    original = {name: (source / name).read_bytes() for name in names}
    payload = dict(original)
    structured = {name: portable(json.loads(data), source, repository)
                  for name, data in original.items()
                  if name.endswith(".json") and not name.startswith("reviews/")}
    for _ in range(len(names) + 1):
        replacements = {digest(original[name]): digest(payload[name]) for name in names
                        if original[name] != payload[name]}
        changed = False
        for name, value in structured.items():
            text = json.dumps(value, ensure_ascii=False)
            for old, new in replacements.items():
                text = text.replace(old, new)
            candidate = encode(json.loads(text))
            if json.loads(candidate) == json.loads(original[name]):
                candidate = original[name]
            changed |= candidate != payload[name]
            payload[name] = candidate
        if not changed:
            break
    else:
        raise RuntimeError("Cross-file hashes did not converge")
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, data in payload.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append({"path": name, "source_path": name, "bytes": len(data),
                        "source_sha256": digest(original[name]), "export_sha256": digest(data),
                        "transformation": "none" if data == original[name] else
                        "portable paths and local connection; affected exported cross-file SHA256 rebound"})
    result = portable(load(source / "RESULT.json"), source, repository)
    result.pop("related_image_probe", None)
    result["publication"] = {"manifest": "export-manifest.json", "raw_source_retained_outside_repository": True,
                             "wire_image_payload_captured_in_cad_trials": False,
                             "reference": "../../assets/reference.jpg"}
    (output / "RESULT.json").write_bytes(encode(result))
    (output / "REPORT.md").write_text(REPORT, encoding="utf-8", newline="\n")
    (output / "README.md").write_text(README, encoding="utf-8", newline="\n")
    generated = [{"path": name, "bytes": (output / name).stat().st_size,
                  "export_sha256": digest((output / name).read_bytes())}
                 for name in ("RESULT.json", "REPORT.md", "README.md")]
    manifest = {"schema_version": 1, "algorithm": "sha256", "source_record_date": "2026-10-18",
                "files": entries, "generated_files": generated,
                "original_result_sha256": digest((source / "RESULT.json").read_bytes()),
                "original_report_sha256": digest((source / "REPORT.md").read_bytes()),
                "omitted": ["Original REPORT.md and RESULT.json replaced by public summaries",
                            "Duplicate reference images; use repository assets/reference.jpg",
                            "Full Podman inspect storage/host state, transport commands, temporary review FCStd copies",
                            "Local decision trail, preflight management records, original host paths and connection name",
                            "Separate earlier image-input probe and complete external model catalogs"],
                "hash_scope": "Export hashes identify published bytes; source hashes identify archived originals. "
                              "Hashes in audit source references to omitted files remain historical identifiers. "
                              "Review JSON, CAD, PNG, events and logs retain their source bytes."}
    (output / "export-manifest.json").write_bytes(encode(manifest))
    verify(output)


def verify(root: Path):
    repository = Path(__file__).resolve().parents[2]
    manifest = load(root / "export-manifest.json")
    entries = manifest["files"] + manifest["generated_files"]
    expected = {entry["path"] for entry in entries} | {"export-manifest.json"}
    require(len(expected) == len(entries) + 1, "Duplicate manifest paths")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    require(actual == expected, f"Package inventory differs: {actual ^ expected}")
    spec = importlib.util.spec_from_file_location("publication_scan", repository / "tools/check_publication.py")
    scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scan)
    for entry in entries:
        path = root / entry["path"]
        data = path.read_bytes()
        require(len(data) == entry["bytes"] and digest(data) == entry["export_sha256"], entry["path"])
        require(not scan.scan_payload(entry["path"], data), f"Publication scan: {entry['path']}")
        if path.suffix.lower() == ".fcstd":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith((".xml", ".json", ".txt")):
                        require(not scan.scan_payload(name, archive.read(name)), f"CAD metadata: {name}")
        if entry["path"].endswith(RAW_SUFFIXES) or entry["path"].startswith("reviews/"):
            require(entry["source_sha256"] == entry["export_sha256"], f"Raw bytes changed: {entry['path']}")
            require(entry["transformation"] == "none", entry["path"])
    summary = load(root / "RESULT.json")
    for model, total in MODELS.items():
        trial = root / model / "trial-01"
        score = load(trial / "score.json")
        reviews = [load(root / "reviews" / model / (role + ".json"))
                   for role in ("coordinator", "blind-a", "blind-b")]
        medians = [statistics.median(next(mark["score"] for mark in review["criteria"] if mark["id"] == item["id"])
                                    for review in reviews) for item in score["criteria"]]
        require(medians == [item["median"] for item in score["criteria"]], f"Medians: {model}")
        require(sum(medians) == score["score"] == total, f"Total: {model}")
        require([review["role"] for review in reviews] == ["coordinator", "blind-a", "blind-b"], model)
        require(all(review["fresh_context"] and review["reviewer_model"].startswith("unknown") for review in reviews), model)
        require(not reviews[0]["model_blinded"] and all(review["model_blinded"] for review in reviews[1:]), model)
        for key, path in {"reference": repository / "assets/reference.jpg", "rubric": repository / "assets/rubric.json",
                          **{view: trial / "renders" / (view + ".png") for view in ("isometric", "top", "right")}}.items():
            measured = digest(path.read_bytes())
            require(score["evidence_hashes"][key] == measured, key)
            require(all(review["evidence_hashes"][key] == measured for review in reviews), key)
        for entry in score["review_files"]:
            require(digest((root / entry["path"]).read_bytes()) == entry["sha256"], entry["path"])
        validation = load(trial / "evidence/validation.json")
        require(digest((trial / "evidence/validation.json").read_bytes()) == score["cad_validation"]["sha256"], model)
        for kind in ("native", "step"):
            state = validation[kind]
            data = (trial / state["file_before"]["path"]).read_bytes()
            require(digest(data) == state["file_before"]["sha256"] == state["file_after"]["sha256"], model)
            require(state["source_unchanged"] and validation["host_source_unchanged"], model)
        require(validation["native"]["geometry_valid"], model)
        require(validation["step"]["geometry_valid"] == (model == "deepseek"), model)
        require(validation["native"]["render_selection"]["solid_count"] == (30 if model == "nemotron" else 26), model)
        require(validation["step"]["render_selection"]["solid_count"] == (0 if model == "nemotron" else 26), model)
        rendering = load(trial / "evidence/render.json")
        require(rendering["success"] and rendering["host_source_unchanged"], model)
        for state in rendering["images"].values():
            require(digest((trial / state["path"]).read_bytes()) == state["sha256"], state["path"])
        metadata = load(trial / "trial.json")
        run = load(trial / "evidence/run.json")
        require(run["trial_sha256"] == digest((trial / "trial.json").read_bytes()), model)
        for name, expected_hash in metadata["file_hashes"].items():
            require(digest((trial / name).read_bytes()) == expected_hash, name)
        require(run["candidate_stopped"] and not run["cleanup_errors"], model)
        require(run["sandbox"]["image_id"] == summary["runtime_image"], model)
        gateway = [json.loads(line) for line in (trial / "evidence/gateway.log").read_text("utf-8").splitlines() if line.strip()]
        counts = Counter(str(row["status"]) for row in gateway if row.get("type") == "gateway_request")
        record = next(item for item in summary["models"] if item["model"].split("/")[-1].startswith(model))
        require(dict(counts) == record["gateway_http_status_counts"], model)
        require(run["duration_seconds"] == record["generation_seconds"] and record["generation_attempts"] == 1, model)
    for name in ("REPORT.md", "README.md"):
        require(not scan.markdown_links(root / name), name)
    print(json.dumps({"status": "ok", "manifest_files": len(entries), "scores": MODELS,
                      "original_CAD_images_reviews_logs_unchanged": True,
                      "publication_pattern_scan": "passed; not a guarantee of absence"}))


README = """# Two free-model CAD samples, 2026-10-18

DeepSeek V4.1 Flash Free scored **50/100**. Nemotron 3.5 Super VL Free scored
**28.75/100**. Each model ran once in an independent Podman sandbox.

| DeepSeek V4.1 Flash Free | Nemotron 3.5 Super VL Free |
| --- | --- |
| ![DeepSeek preview](deepseek/trial-01/renders/preview.png) | ![Nemotron preview](nemotron/trial-01/renders/preview.png) |
| FCStd and STEP valid, 26 solids each | FCStd valid, 30 solids; STEP imports zero shapes |

Read the [report](REPORT.md), [result JSON](RESULT.json), and
[export manifest](export-manifest.json) for conditions, scores, original hashes,
transformations, and omitted records.

Verify this public package from the repository root, without model inference:

```sh
uv run --frozen python experiments/tools/export_dual.py --verify experiments/dual-free-20261018
```

日本語要約：同じ画像と依頼文で各モデルを1回ずつ実行し、別々のPodman環境で生成した。
DeepSeekは50点で、FCStdとSTEPがともに有効だった。Nemotronは28.75点で、FCStdは
有効だがSTEPには形状がなかった。見た目の採点はCAD形式の検査と分けている。
今回の各1生成物の評価であり、モデル全体の性能順位ではない。
"""

REPORT = """# Archived dual-model CAD experiment, 2026-10-18

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
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve())
    elif args.source and args.output:
        export(args.source.resolve(), args.output.resolve())
    else:
        parser.error("Use --verify PACKAGE or --source ARCHIVE --output PACKAGE")


if __name__ == "__main__":
    main()
