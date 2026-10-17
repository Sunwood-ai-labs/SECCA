"""Create neutral image packets and validate evidence-bound visual reviews."""
import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import sys
from datetime import datetime
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
IDS = ("silhouette_proportions", "component_layout", "characteristic_geometry",
       "mechanical_detail", "color_material_regions")
WEIGHTS = (25, 20, 30, 20, 5)
ROLES = ("coordinator", "blind-a", "blind-b")
VIEWS = ("isometric", "top", "right")
TERMINAL_STATUSES = {"completed", "failed", "timeout", "runner_error", "interrupted", "timed_out", "error", "cancelled", "succeeded", "success"}
LIMITATION = "JSON declarations and timestamps cannot prove actual fresh contexts, independence or model blinding."


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def contract():
    protocol = read_json(ASSETS / "protocol.json")
    rubric_path = ASSETS / "rubric.json"
    rubric = read_json(rubric_path)
    actual = [(item["id"], item["max"]) for item in rubric["criteria"]]
    if actual != list(zip(IDS, WEIGHTS)) or rubric["max_score"] != 100:
        raise ValueError("Rubric must contain exactly the five protocol criteria and weights 25/20/30/20/5")
    if protocol["scoring"]["criterion_ids"] != list(IDS) or protocol["scoring"]["weights"] != list(WEIGHTS):
        raise ValueError("Protocol scoring does not match the fixed rubric")
    for name, key in (("reference.jpg", "reference_image_sha256"), ("rubric.json", "rubric_sha256"),
                      ("render-spec.json", "render_spec_sha256")):
        if digest(ASSETS / name) != protocol[key]:
            raise ValueError(f"Bundled {name} hash does not match protocol")
    return rubric


def trial_path(trial, value):
    if not isinstance(value, str) or not value:
        raise ValueError("Evidence requires a nonempty file path")
    path = Path(value)
    path = (path if path.is_absolute() else trial / path).resolve()
    if not path.is_relative_to(trial):
        raise ValueError("Evidence path must stay inside the trial")
    return path


def checked_file(trial, entry, expected=None):
    if not isinstance(entry, dict) or entry.get("exists") is not True:
        raise ValueError("Evidence file must be recorded as existing")
    path = trial_path(trial, entry.get("path"))
    if expected is not None and path != expected.resolve():
        raise ValueError("CAD source path differs from the trial workspace")
    if not path.is_file() or digest(path) != entry.get("sha256") or path.stat().st_size != entry.get("bytes"):
        raise ValueError("Evidence file hash or byte count mismatch")
    return path


def quaternion_matches(value, expected):
    if not (isinstance(value, list) and len(value) == 4
            and all(type(number) in (int, float) and math.isfinite(number) for number in value)):
        return False
    return min(max(abs(number - sign * target) for number, target in zip(value, expected))
               for sign in (1, -1)) <= 1e-6


def validate_podman_provenance(prepared, run, render):
    sandbox = prepared.get("sandbox")
    if (type(prepared.get("schema_version")) is not int or prepared["schema_version"] != 2
            or not isinstance(sandbox, dict)
            or sandbox.get("backend") != "podman-network-none-uds"):
        raise ValueError("Visual scoring requires a schema 2 Podman sandbox trial")
    image = sandbox.get("image_id")
    connection = sandbox.get("connection")
    if (not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image)
            or not isinstance(connection, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", connection)):
        raise ValueError("Trial sandbox requires an immutable image ID and named Podman connection")
    if run.get("candidate_stopped") is not True:
        raise ValueError("Candidate must be stopped before visual scoring")
    renderer = render.get("sandbox")
    if (not isinstance(renderer, dict)
            or renderer.get("backend") != "podman-offline-postprocess"
            or renderer.get("network") != "none"
            or renderer.get("api_channel") is not False
            or renderer.get("bind_mounts") != []
            or renderer.get("image_id") != image
            or renderer.get("connection") != connection
            or render.get("host_source_unchanged") is not True):
        raise ValueError("Render requires matching offline Podman provenance and unchanged host CAD")


def evidence_files(trial):
    trial = Path(trial).resolve()
    contract()
    protocol_path = trial / "protocol.json"
    protocol = read_json(protocol_path)
    prepared = read_json(trial / "trial.json")
    protocol_hash = digest(protocol_path)
    if (protocol_hash != digest(ASSETS / "protocol.json")
            or prepared.get("protocol_sha256") != protocol_hash
            or prepared.get("file_hashes", {}).get("protocol.json") != protocol_hash
            or prepared.get("protocol_id") != protocol.get("id")):
        raise ValueError("Trial protocol hash or identity differs from the installed canonical protocol")
    run = read_json(trial / "evidence" / "run.json")
    if run.get("status") not in TERMINAL_STATUSES:
        raise ValueError("Candidate run must be terminal before visual scoring")
    reference = trial_path(trial, "workspace/reference.jpg")
    if digest(reference) != digest(ASSETS / "reference.jpg"):
        raise ValueError("Trial reference differs from the fixed reference")
    manifest = read_json(trial / "evidence" / "render.json")
    validate_podman_provenance(prepared, run, manifest)
    if manifest.get("success") is not True or manifest.get("source_unchanged") is not True:
        raise ValueError("Visual scoring requires a successful render with unchanged CAD sources")
    for name in protocol["outputs"]:
        for phase in ("source_before", "source_after"):
            checked_file(trial, manifest.get(phase, {}).get(name), trial / "workspace" / name)
    if manifest.get("render_spec", {}).get("sha256") != protocol["render_spec_sha256"]:
        raise ValueError("Render evidence specification differs from the fixed protocol")
    spec = read_json(ASSETS / "render-spec.json")
    presentation = manifest.get("presentation", {})
    for key in ("background", "projection", "animation_enabled", "display_mode", "preserve_model_colors", "preserve_model_visibility"):
        if type(presentation.get(key)) is not type(spec[key]) or presentation[key] != spec[key]:
            raise ValueError(f"Render presentation {key} differs from the fixed specification")
    images = manifest.get("images", manifest.get("views"))
    if isinstance(images, list):
        if len({entry.get("name", entry.get("view")) for entry in images}) != len(images):
            raise ValueError("Render view names must be unique")
        images = {entry.get("name", entry.get("view")): entry for entry in images}
    if not isinstance(images, dict):
        raise ValueError("render.json requires an images mapping")
    files = {"reference": reference, "rubric": ASSETS / "rubric.json"}
    for view in VIEWS:
        entry = images.get(view)
        path = checked_file(trial, entry)
        fixed = next(item for item in spec["views"] if item["id"] == view)
        if entry.get("camera_type") != spec["projection"]:
            raise ValueError(f"{view} camera projection differs from the fixed specification")
        for key in ("requested_quaternion_xyzw", "actual_quaternion_xyzw"):
            if not quaternion_matches(entry.get(key), fixed["quaternion_xyzw"]):
                raise ValueError(f"{view} camera quaternion differs from the fixed specification")
        with path.open("rb") as stream:
            header = stream.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR" or len(header) != 24:
            raise ValueError(f"{view} image must be a PNG with dimensions")
        dimensions = tuple(int.from_bytes(header[start:start + 4], "big") for start in (16, 20))
        if (dimensions != (fixed["width"], fixed["height"])
                or any(type(entry.get(key)) is not int or entry[key] != fixed[key] for key in ("width", "height"))):
            raise ValueError(f"{view} image dimensions differ from the fixed specification")
        files[view] = path
    return files


def evidence_hashes(files):
    return {name: digest(path) for name, path in files.items()}


def timestamp(text):
    if not isinstance(text, str):
        raise ValueError("context_provenance.recorded_at requires an ISO8601 timestamp")
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Provenance timestamp requires a timezone")
    return value


def nonempty(value):
    return isinstance(value, str) and len(value.strip()) >= 12


def validate_review(review, expected_role, hashes):
    if not isinstance(review, dict) or review.get("role") != expected_role:
        raise ValueError(f"Reviews must be ordered {' '.join(ROLES)}")
    if not isinstance(review.get("review_id"), str) or not review["review_id"].strip():
        raise ValueError("Each review needs a nonempty review_id")
    if not isinstance(review.get("reviewer_model"), str) or not review["reviewer_model"].strip():
        raise ValueError("Each review needs reviewer_model provenance; use unknown if historical")
    if type(review.get("fresh_context")) is not bool or type(review.get("model_blinded")) is not bool:
        raise ValueError("Fresh-context/model-blinded declarations must be booleans")
    if expected_role != "coordinator" and (not review["fresh_context"] or not review["model_blinded"]):
        raise ValueError("Independent reviews require fresh_context=true and model_blinded=true")
    provenance = review.get("context_provenance")
    if not isinstance(provenance, dict) or not nonempty(provenance.get("statement")):
        raise ValueError("context_provenance requires a concrete statement")
    if provenance.get("other_reviews_read") is not False:
        raise ValueError("Each initial review must declare other_reviews_read=false")
    if not isinstance(provenance.get("signed_by"), str) or not provenance["signed_by"].strip():
        raise ValueError("context_provenance requires signed_by")
    timestamp(provenance.get("recorded_at"))
    if review.get("evidence_hashes") != hashes:
        raise ValueError("Review evidence hashes do not match the actual four images and rubric")
    criteria = review.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 5:
        raise ValueError("Each review requires exactly five criteria")
    if {item.get("id") for item in criteria} != set(IDS):
        raise ValueError("Criterion ids missing, duplicated or unexpected")
    result = {}
    for item in criteria:
        expected_max = WEIGHTS[IDS.index(item["id"])]
        score = item.get("score")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= expected_max:
            raise ValueError(f"{item['id']} score must be finite and within 0..{expected_max}")
        if type(item.get("max")) not in (int, float) or item["max"] != expected_max:
            raise ValueError(f"{item['id']} has the wrong maximum")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{item['id']} requires concrete image evidence")
        kinds = set()
        for observation in evidence:
            if not isinstance(observation, dict) or observation.get("kind") not in ("positive", "deduction", "no_deduction", "no_positive"):
                raise ValueError("Evidence entries require kind and concrete observation")
            if not nonempty(observation.get("observation")):
                raise ValueError("Evidence observations must describe concrete visible features")
            kinds.add(observation["kind"])
        if not kinds.intersection({"positive", "no_positive"}) or not kinds.intersection({"deduction", "no_deduction"}):
            raise ValueError("Each criterion needs positive and deduction evidence, or an explicit no-positive/no-deduction explanation")
        if score < expected_max and "deduction" not in kinds:
            raise ValueError("A non-full score requires concrete deduction evidence")
        if score > 0 and "positive" not in kinds:
            raise ValueError("A positive score requires concrete positive evidence")
        result[item["id"]] = score
    return result


def aggregate_reviews(reviews, hashes):
    if len(reviews) != 3:
        raise ValueError("Exactly three reviews are required")
    values = [validate_review(review, role, hashes) for review, role in zip(reviews, ROLES)]
    if len({review["review_id"] for review in reviews}) != 3:
        raise ValueError("Review ids must be unique")
    times = [timestamp(review["context_provenance"]["recorded_at"]) for review in reviews]
    if not all(times[0] < value for value in times[1:]):
        raise ValueError("Coordinator initial review must be signed before the independent reviews")
    criteria = [{"id": name, "median": statistics.median([value[name] for value in values]), "max": maximum}
                for name, maximum in zip(IDS, WEIGHTS)]
    return {"method": "sum of per-criterion medians", "score": sum(item["median"] for item in criteria),
            "max_score": 100, "criteria": criteria, "review_ids": [r["review_id"] for r in reviews],
            "review_provenance": [{key: r[key] for key in ("review_id", "role", "fresh_context", "model_blinded", "reviewer_model", "context_provenance")} for r in reviews],
            "evidence_hashes": hashes, "scope": "Visual likeness of this one output only. No CAD-validity bonus or model-population ranking.",
            "limitations": [LIMITATION, "One oblique reference cannot establish exact dimensions or mechanical function."]}


def packet(trial, output):
    contract()
    files = evidence_files(trial)
    hashes = evidence_hashes(files)
    output = Path(output)
    if output.exists():
        raise ValueError("Packet output must be a new directory")
    output.mkdir(parents=True)
    (output / "renders").mkdir()
    destinations = {"reference": "reference.jpg", "rubric": "rubric.json", **{v: f"renders/{v}.png" for v in VIEWS}}
    for name, source in files.items():
        target = output / destinations[name]
        shutil.copyfile(source, target)
        if digest(target) != hashes[name]:
            raise ValueError(f"Packet copy failed integrity check for {name}")
    template = {"review_id": "", "role": "blind-a", "fresh_context": True, "model_blinded": True,
                "reviewer_model": "", "context_provenance": {"statement": "", "other_reviews_read": False, "recorded_at": "", "signed_by": ""},
                "evidence_hashes": hashes, "criteria": [{"id": name, "score": None, "max": maximum, "evidence": [
                    {"kind": "positive", "observation": ""}, {"kind": "deduction", "observation": ""}]} for name, maximum in zip(IDS, WEIGHTS)]}
    write_json(output / "review-template.json", template)
    (output / "README.txt").write_text(
        "Review only reference.jpg, the three renders and rubric.json. Image bytes and aspect ratios are preserved.\n"
        "Record all five criteria with concrete positive and deduction observations naming visible features/views. At full marks use no_deduction with a reason; at zero use no_positive with a reason.\n"
        "Set your unique review_id, role, reviewer_model and signed context provenance with a timezone timestamp.\n"
        "The coordinator signs and saves its initial review before reading or requesting independent reviews. Each independent reviewer receives this neutral packet in a genuinely fresh context, without model identity or other reviews.\n"
        "The required order is coordinator, blind-a, blind-b. Independents declare fresh_context=true, model_blinded=true and other_reviews_read=false.\n"
        + LIMITATION + "\n", encoding="utf-8")
    return {"packet": str(output.resolve()), "evidence_hashes": hashes}


def aggregate(trial, paths):
    contract()
    hashes = evidence_hashes(evidence_files(trial))
    reviews = [read_json(path) for path in paths]
    result = aggregate_reviews(reviews, hashes)
    result["review_files"] = [{"path": str(Path(path).resolve()), "sha256": digest(path)} for path in paths]
    validation = Path(trial) / "evidence" / "validation.json"
    result["cad_validation"] = {"path": "evidence/validation.json", "sha256": digest(validation), "separate_from_visual_score": True} if validation.exists() else {"status": "not provided", "separate_from_visual_score": True}
    write_json(Path(trial) / "score.json", result)
    return result


def verify_baseline():
    rubric = contract()
    root = ASSETS / "baseline" / "evidence"
    historical_rubric = root / "likeness-rubric-original.json"
    original = read_json(historical_rubric)
    if {key: value for key, value in original.items() if key != "method"} != {key: value for key, value in rubric.items() if key != "method"}:
        raise ValueError("Historical and canonical rubrics differ beyond the method clarification")
    files = {"reference": ASSETS / "reference.jpg", "rubric": historical_rubric,
             "isometric": root / "kart-front-isometric-white.png", "top": root / "score-top-white.png", "right": root / "score-right-white.png"}
    hashes = evidence_hashes(files)
    reviews = []
    for index, role in enumerate(ROLES):
        source = root / f"likeness-{'parent-initial' if index == 0 else role}.json"
        raw = read_json(source)
        if index == 0:
            criteria = [{"id": name, "score": raw["scores"][name], "max": maximum, "evidence": [
                {"kind": "positive", "observation": raw["observations"][i]},
                {"kind": "deduction" if raw["scores"][name] < maximum else "no_deduction", "observation": raw["observations"][i]}]} for i, (name, maximum) in enumerate(zip(IDS, WEIGHTS))]
        else:
            criteria = []
            for item in raw.get("categories", raw.get("criteria", [])):
                score = item.get("point", item.get("points"))
                if index == 1:
                    evidence = [{"kind": kind, "observation": text} for kind, key in (("positive", "positive_image_evidence"), ("deduction", "deduction_image_evidence")) for text in item[key]]
                else:
                    evidence = [{"kind": "positive" if score == item["max"] or i == 0 else "deduction", "observation": text} for i, text in enumerate(item["evidence"])]
                if score == item["max"]:
                    evidence.append({"kind": "no_deduction", "observation": "Historical review assigns full points for corresponding broad blue, silver, dark seat and black tire color regions."})
                criteria.append({"id": item["id"], "score": score, "max": item["max"], "evidence": evidence})
        reviews.append({"review_id": f"historical-{role}", "role": role, "fresh_context": index != 0,
                        "model_blinded": index != 0, "reviewer_model": "unknown; historical reviewer identity not recorded",
                        "context_provenance": {"statement": "Historical conversion from bundled raw evidence. Coordinator knew candidate identity and scored before independents; blind reviewers declared image-only fresh contexts. Conversion timestamps encode documented order, not recovered wall-clock times.",
                                               "other_reviews_read": False, "signed_by": "historical-evidence-conversion", "recorded_at": f"2026-10-17T00:00:0{index}+00:00"},
                        "evidence_hashes": hashes, "criteria": criteria,
                        "historical_source_sha256": digest(source)})
    result = aggregate_reviews(reviews, hashes)
    totals = [sum(c["score"] for c in review["criteria"]) for review in reviews]
    if totals != [45, 42, 42] or result["score"] != 43:
        raise ValueError("Historical baseline must reproduce 45/42/42 and per-criterion median sum 43")
    result.update({"historical_review_totals": totals, "canonical_comparison_reviews": reviews,
                   "rubric_method_clarification": "Canonical rubric method wording clarifies the existing three-review per-criterion median aggregation. Criteria, anchors, weights and exclusions match the preserved original; historical evidence hashes use the original rubric bytes.",
                   "canonical_rubric_sha256": digest(ASSETS / "rubric.json"),
                   "historical_conversion": "In-memory comparison only. Original baseline untouched. Order timestamps are synthetic and explicitly declared; no historical signature or actual wall-clock timestamp is asserted."})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("packet")
    command.add_argument("--trial", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("aggregate")
    command.add_argument("--trial", type=Path, required=True)
    command.add_argument("--reviews", type=Path, nargs=3, required=True, metavar=("COORDINATOR", "BLIND_A", "BLIND_B"))
    commands.add_parser("verify-baseline")
    args = parser.parse_args(argv)
    try:
        result = packet(args.trial, args.output) if args.command == "packet" else aggregate(args.trial, args.reviews) if args.command == "aggregate" else verify_baseline()
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"scores: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
