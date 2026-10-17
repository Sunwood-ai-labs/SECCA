"""Export the archived Beam experiment without running inference or changing CAD."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path

PACKAGE = "beam-free-20261017"
ROOT_FILES = ["beam-model-metadata.json", "source-check.json", "modality-observation.json",
              "modality-run-audit.json", "plan.json", "retry-plan.json"]
PRIVATE_HOME = re.compile(r"/home/(?!(?:candidate|opencode|root)(?:/|$))[^/\s\"'\\:]+")
WINDOWS_HOME = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]+Users[\\/]+[^/\\\s\"':]+", re.IGNORECASE)
HOST_RUNTIME = re.compile(r"/run/user/[0-9]+(?=/|$)")
HTTP_CONNECTION_VALUES = ("keep-alive", "close", "upgrade")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, detail) -> None:
    if not condition:
        raise ValueError(detail)


def portable(value, source: Path):
    if isinstance(value, dict):
        return {key: "local-connection" if key == "connection" and item not in HTTP_CONNECTION_VALUES else portable(item, source)
                for key, item in value.items()}
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            if index and value[index - 1] == "--connection":
                result.append("local-connection")
            elif isinstance(item, str) and item.startswith("--connection="):
                result.append("--connection=local-connection")
            else:
                result.append(portable(item, source))
        return result
    if isinstance(value, str):
        prefix = str(source).replace("/", "\\") + "\\"
        if value.lower().startswith(prefix.lower()):
            return value[len(prefix):].replace("\\", "/")
        value = PRIVATE_HOME.sub("<host-home>", value)
        value = HOST_RUNTIME.sub("<host-runtime>", value)
        return WINDOWS_HOME.sub("<host-home>", value)
    return value


def verify_portability(value, location: str) -> None:
    """Reject host-specific management state, allowing named sandbox homes."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "connection":
                require(item == "local-connection" or item in HTTP_CONNECTION_VALUES, (location, "private connection field"))
            verify_portability(item, location + "/" + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if item == "--connection":
                require(index + 1 < len(value) and value[index + 1] == "local-connection", (location, "private connection argv"))
            elif isinstance(item, str) and item.startswith("--connection="):
                require(item == "--connection=local-connection", (location, "private connection argv"))
            verify_portability(item, location + "/" + str(index))
    elif isinstance(value, str):
        require(not PRIVATE_HOME.search(value), (location, "private host home"))
        require(not WINDOWS_HOME.search(value), (location, "private Windows home"))
        require(not HOST_RUNTIME.search(value), (location, "private host runtime"))


def export(source: Path, output: Path) -> None:
    require(not output.exists() or output.is_dir() and not any(output.iterdir()),
            "Export destination must be new or empty")
    names = list(ROOT_FILES)
    for trial in ("trial-01", "trial-02"):
        for path in sorted((source / trial).rglob("*")):
            if path.is_file() and path.name not in ("commands.json", "run.claim"):
                names.append(path.relative_to(source).as_posix())
    original = {name: (source / name).read_bytes() for name in names}
    payload = dict(original)
    structured = {}
    for name, data in original.items():
        # Review declarations and generation events are raw evidence, never rewritten.
        if name.endswith(".json") and "/evidence/review/" not in name:
            value = json.loads(data)
            transformed = portable(value, source)
            if transformed != value:
                structured[name] = transformed
                payload[name] = encode(transformed)
    # Rebind every exported cross-file digest affected by a portable metadata edit.
    # Original-source digests remain separately available in export-manifest.json.
    for _ in range(len(names) + 1):
        changed = False
        replacements = {digest(original[name]): digest(payload[name]) for name in names
                        if original[name] != payload[name]}
        for name in names:
            if not name.endswith(".json") or "/evidence/review/" in name:
                continue
            text = json.dumps(portable(json.loads(original[name]), source), ensure_ascii=False)
            for old, new in replacements.items():
                text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
            value = json.loads(text)
            if value != json.loads(original[name]) or name in structured:
                data = encode(value)
                changed |= data != payload[name]
                structured[name] = value
                payload[name] = data
        if not changed:
            break
    else:
        raise RuntimeError("Cross-file hashes did not converge")
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for name in names:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload[name])
        records.append({"path": name, "source_path": name,
                        "source_sha256": digest(original[name]), "export_sha256": digest(payload[name]),
                        "bytes": len(payload[name]), "transformation": "none" if original[name] == payload[name]
                        else "portable management paths, connection fields/argv, private host home/storage paths and dependent cross-file SHA256 rebinding"})
    result = load(source / "RESULT.json")
    result["schema_version"] = 2
    result["judging_execution"].pop("packet", None)
    result["judging_execution"]["packet_id"] = "sample-20261017-f3a7"
    result["evidence_sha256"] = {name: digest(data) for name, data in payload.items()}
    result["export"] = {"source_result_sha256": digest((source / "RESULT.json").read_bytes()),
                        "manifest": "export-manifest.json", "raw_originals_retained_outside_repository": True,
                        "source_unchanged_meaning": "Original CAD unchanged during original validation; portable metadata exports are separately identified in manifest."}
    (output / "RESULT.json").write_bytes(encode(result))
    report = """# Beam Free archived CAD experiment, 2026-10-17

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
"""
    (output / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    (output / "README.md").write_text("# Beam Free experiment\n\nRead [the report](REPORT.md) for results, conditions, limitations and artifact links.\n\nVerify the public export from the repository root:\n\n```powershell\npython experiments/tools/export_beam.py --verify experiments/beam-free-20261017\n```\n", encoding="utf-8", newline="\n")
    generated = [{"path": name, "export_sha256": digest((output / name).read_bytes()),
                  "bytes": (output / name).stat().st_size}
                 for name in ("RESULT.json", "REPORT.md", "README.md")]
    manifest = {"schema_version": 1, "algorithm": "sha256", "source_record_date": "2026-10-17",
                "files": records, "generated_files": generated,
                "original_result_sha256": digest((source / "RESULT.json").read_bytes()),
                "original_report_sha256": digest((source / "REPORT.md").read_bytes()),
                "omitted": ["Full models.dev catalog and provider catalog", "ZIP and original skill package manifests",
                            "Host-load snapshots and unrelated preflight/management history", "Postprocess command transport logs and run.claim markers",
                            "Original REPORT.md and RESULT.json replaced by clearly identified public summaries"],
                "hash_scope": "Export hashes identify public bytes; source hashes identify archived pre-export bytes. External-source catalog SHA256 values remain historical external identifiers."}
    (output / "export-manifest.json").write_bytes(encode(manifest))
    verify(output)


def verify(root: Path) -> None:
    manifest = load(root / "export-manifest.json")
    entries = manifest["files"] + manifest["generated_files"]
    expected = {entry["path"] for entry in entries} | {"export-manifest.json"}
    require(len(expected) == len(entries) + 1, "Duplicate manifest paths")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    require(actual == expected,
            f"Package inventory mismatch; extra={sorted(actual - expected)}, missing={sorted(expected - actual)}")
    count = 0
    for entry in entries:
        path = root / entry["path"]
        require(path.is_file(), entry["path"])
        require(digest(path.read_bytes()) == entry["export_sha256"], entry["path"])
        require(path.stat().st_size == entry["bytes"], entry["path"])
        if path.suffix == ".json":
            verify_portability(load(path), entry["path"])
        elif path.suffix == ".jsonl":
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip():
                    verify_portability(json.loads(line), f"{entry['path']}:{line_number}")
        elif path.suffix in (".md", ".log", ".txt"):
            verify_portability(path.read_text(encoding="utf-8"), entry["path"])
        count += 1
    score = load(root / "trial-02/score.json")
    reviews = [load(root / "trial-02/evidence/review" / f"{name}.json")
               for name in ("coordinator", "blind-a", "blind-b")]
    medians = []
    for criterion in score["criteria"]:
        marks = [next(c["score"] for c in review["criteria"] if c["id"] == criterion["id"])
                 for review in reviews]
        medians.append(statistics.median(marks))
        require(medians[-1] == criterion["median"], 'Integrity check failed')
    require(medians == [9, 9, 4, 2, 1] and sum(medians) == score["score"] == 25, 'Integrity check failed')
    for entry in score["review_files"]:
        require(digest((root / entry["path"]).read_bytes()) == entry["sha256"], 'Integrity check failed')
    frozen = {entry["path"]: entry for entry in manifest["files"]}
    for path, entry in frozen.items():
        if path.endswith((".FCStd", ".step", ".png", ".jpg", ".jsonl", ".log")) or "/evidence/review/" in path:
            require(entry["source_sha256"] == entry["export_sha256"], path)
            require(entry["transformation"] == "none", path)
    inputs = root.parents[1] / "assets"
    for key, path in {"reference": inputs / "reference.jpg", "rubric": inputs / "rubric.json",
                      "isometric": root / "trial-02/renders/isometric.png",
                      "top": root / "trial-02/renders/top.png", "right": root / "trial-02/renders/right.png"}.items():
        actual = digest(path.read_bytes())
        require(score["evidence_hashes"][key] == actual, key)
        for review in reviews:
            require(review["evidence_hashes"][key] == actual, key)
    require(digest((root / "trial-02/evidence/validation.json").read_bytes()) == score["cad_validation"]["sha256"], 'Integrity check failed')
    for trial in ("trial-01", "trial-02"):
        metadata = load(root / trial / "trial.json")
        run = load(root / trial / "evidence/run.json")
        require(run["trial_sha256"] == digest((root / trial / "trial.json").read_bytes()), 'Integrity check failed')
        for name, expected in metadata["file_hashes"].items():
            require(digest((root / trial / name).read_bytes()) == expected, 'Integrity check failed')
    for name, expected in load(root / "RESULT.json")["evidence_sha256"].items():
        require(digest((root / name).read_bytes()) == expected, 'Integrity check failed')
    for record in load(root / "modality-run-audit.json")["evidence"]:
        require(digest((root / record["path"]).read_bytes()) == record["sha256"].lower(), 'Integrity check failed')
    for name in ("REPORT.md", "README.md"):
        for target in re.findall(r"\]\(([^)]+)\)", (root / name).read_text(encoding="utf-8")):
            if "://" not in target:
                require((root / target.split("#", 1)[0]).exists(), (name, target))
    print(json.dumps({"status": "ok", "manifest_files": count, "score": 25,
                      "criterion_medians": medians, "raw_artifact_hashes_match_manifest": True}))


def main() -> None:
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
