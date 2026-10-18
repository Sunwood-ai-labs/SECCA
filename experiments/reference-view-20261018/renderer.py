"""Render, export and verify supplemental reference-oriented CAD images."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sandbox_postprocess import OfflineContainer, bounded_capture, digest, read_json, write_json


@dataclass(frozen=True)
class SupplementalJob:
    request_id: str
    connection: str
    image_id: str
    timeout: int = 240
    operation: str = "render"


def safe_source(relative):
    path = ROOT / relative
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ValueError("Expected regular source: " + relative)
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError("Source escapes repository")
    return path


def quaternion(base, yaw):
    angle = math.radians(yaw) / 2
    x, y, z, w = base
    s, c = math.sin(angle), math.cos(angle)
    result = [c*x - s*y, c*y + s*x, c*z + s*w, c*w - s*z]
    length = math.sqrt(sum(v*v for v in result))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError("Invalid camera quaternion")
    return [v / length for v in result]


def protected_snapshot(sources):
    return {item["path"]: digest(safe_source(item["path"])) for item in sources["protected_files"]}


def execution_sources():
    files = [HERE / name for name in ("renderer.py", "worker.py", "spec.json", "sources.json", "camera-analysis.json")]
    files.extend(ROOT / "scripts" / name for name in ("sandbox_postprocess.py", "freecad_worker.py", "gui_lease.py"))
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in files}


def git_canonical_checks(paths):
    checks = {}
    for relative in sorted(paths):
        data = safe_source(relative).read_bytes()
        raw = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        filtered = subprocess.run(["git", "hash-object", "--path=" + relative, "--stdin"],
                                  cwd=ROOT, input=data, capture_output=True, timeout=30, check=True).stdout.decode("ascii").strip()
        if raw != filtered:
            raise ValueError("Git filters change execution/source bytes: " + relative)
        checks[relative] = {"raw_git_blob": raw, "canonical_git_blob": filtered}
    return checks


def verify_inputs(sources):
    snapshot = protected_snapshot(sources)
    expected = {item["path"]: item["sha256"] for item in sources["protected_files"]}
    if snapshot != expected:
        raise ValueError("Historical source/evidence or helper hashes changed")
    if digest(HERE / "camera-analysis.json") != sources["axis_evidence_sha256"]:
        raise ValueError("Axis evidence hash mismatch")
    ids = [entry["id"] for entry in sources["models"]]
    if len(ids) != 4 or len(set(ids)) != 4 or any(not re.fullmatch(r"[a-z]+", name) for name in ids):
        raise ValueError("Expected four distinct safe model IDs")
    for entry in sources["models"]:
        if digest(safe_source(entry["cad"])) != entry["cad_sha256"]:
            raise ValueError("CAD source mismatch")
    return snapshot


def image_check(path, expected):
    from PIL import Image, ImageChops
    with Image.open(path) as image:
        image.load()
        rgb = image.convert("RGB")
        if list(rgb.size) != expected or image.format != "PNG":
            raise ValueError("Invalid PNG dimensions")
        difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white"))
        mask = difference.point(lambda value: 255 if value > 12 else 0).convert("L")
        bbox = mask.getbbox()
        if bbox is None or bbox[2] - bbox[0] < 40 or bbox[3] - bbox[1] < 40:
            raise ValueError("Blank or tiny model image")
        width, height = rgb.size
        corners = [rgb.getpixel(point) for point in ((0,0),(width-1,0),(0,height-1),(width-1,height-1))]
        if any(min(pixel) < 250 for pixel in corners):
            raise ValueError("Background corners are not white")
        if min(bbox[0], bbox[1], width-bbox[2], height-bbox[3]) < 4:
            raise ValueError("Geometry reaches image edge")
        return {"width": width, "height": height, "nonwhite_bounds_px": list(bbox),
                "white_corners": True, "nonblank": True, "edge_margin_at_least_4px": True,
                "sha256": digest(path), "bytes": path.stat().st_size}


def render_one(entry, spec, args, attempt):
    job = SupplementalJob(uuid.uuid4().hex, args.connection, args.image_id)
    output = attempt / entry["id"]
    output.mkdir()
    request = {"schema": "secca-supplemental-render-v1", "request_id": job.request_id,
               "model": entry["id"], "source_sha256": entry["cad_sha256"],
               "quaternion_xyzw": quaternion(spec["base_quaternion_xyzw"], entry["yaw_degrees"]),
               "runtime_files_sha256": {"worker.py": digest(HERE / "worker.py"),
                                        "freecad_worker.py": digest(ROOT / "scripts/freecad_worker.py"),
                                        "gui_lease.py": digest(ROOT / "scripts/gui_lease.py")},
               "images": spec["images"]}
    container = OfflineContainer(job)
    result = {"request": request, "success": False}
    try:
        with tempfile.TemporaryDirectory(prefix="secca-reference-") as temporary:
            stage = Path(temporary)
            write_json(stage / "request.json", request)
            with container:
                uploads = [(safe_source(entry["cad"]), "/job/workspace/source.FCStd"),
                           (stage / "request.json", "/job/request.json"),
                           (HERE / "worker.py", "/job/runtime/worker.py"),
                           (ROOT / "scripts/freecad_worker.py", "/job/runtime/freecad_worker.py"),
                           (ROOT / "scripts/gui_lease.py", "/job/runtime/gui_lease.py")]
                for source, remote in uploads:
                    container.upload(source, remote)
                code = "import runpy\nresult=runpy.run_path('/job/runtime/worker.py')['render_reference_view']('/job/request.json')\nprint(result)\n"
                rpc = "from xmlrpc.client import ServerProxy\nr=ServerProxy('http://127.0.0.1:9875').execute_code(" + repr(code) + ")\nassert r.get('success') is True,repr(r)"
                container.exec("/usr/bin/python3", "-c", rpc)
                raw = stage / "worker-result.json"
                container.download("/job/evidence/supplemental.json", raw, 32*1024**2)
                result["worker"] = read_json(raw)
                worker = result["worker"]
                if not worker["success"] or worker["request_id"] != job.request_id or worker["source_before"]["sha256"] != entry["cad_sha256"]:
                    raise ValueError("Worker source/result validation failed")
                if worker["source_before"] != worker["source_after"] or worker["quaternion_max_delta"] > 1e-6:
                    raise ValueError("Worker integrity or camera failed")
                for name, dimensions in spec["images"].items():
                    image_path = output / (name + ".png")
                    container.download("/job/renders/" + name + ".png", image_path, 64*1024**2)
                    record = image_check(image_path, dimensions)
                    if record["sha256"] != worker["images"][name]["sha256"]:
                        raise ValueError("Downloaded PNG differs from worker evidence")
                    result.setdefault("image_checks", {})[name] = record
                result["success"] = True
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["cleanup_error"] = container.cleanup_error
        result["sandbox"] = {"image_id": args.image_id, "container_inspection": container.inspection,
                             "process_isolation": container.runtime_isolation,
                             "remaining_container_id": container.container_id}
        result["commands"] = container.log
        result["source_host_unchanged"] = digest(safe_source(entry["cad"])) == entry["cad_sha256"]
        result["success"] = result["success"] and result["source_host_unchanged"] and container.cleanup_error is None and container.container_id is None
        write_json(output / "result.json", result)
    return result


def run(args):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.connection) or not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image_id):
        raise ValueError("Explicit named connection and immutable image ID required")
    sources, spec = read_json(HERE / "sources.json"), read_json(HERE / "spec.json")
    selftest(args)
    executed = execution_sources()
    before = verify_inputs(sources)
    canonical = git_canonical_checks(set(executed) | set(before))
    attempt = Path(args.output).resolve() / "attempts" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    archive = attempt / "execution-sources"
    for relative in executed:
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
        if digest(target) != executed[relative]:
            raise ValueError("Execution source changed during capture")
    write_json(attempt / "execution-inputs.json", executed)
    results = {}
    for entry in sources["models"]:
        result = render_one(entry, spec, args, attempt)
        results[entry["id"]] = result
        print(json.dumps({"model": entry["id"], "success": result["success"], "output": str(attempt / entry["id"])}), flush=True)
        if not result["success"]:
            break
    after = protected_snapshot(sources)
    execution_unchanged = execution_sources() == executed
    final = {"schema": "secca-supplemental-attempt-v1", "attempt": str(attempt),
             "success": len(results) == 4 and all(item["success"] for item in results.values()) and before == after and execution_unchanged,
             "executed_sources_sha256": executed, "execution_sources_unchanged": execution_unchanged,
             "git_canonical_checks": canonical,
             "protected_before": before, "protected_after": after, "historical_evidence_unchanged": before == after,
             "models": list(results)}
    write_json(attempt / "result.json", final)
    write_json(Path(args.output) / "latest.json", final)
    return 0 if final["success"] else 1


def export(args):
    final = read_json(Path(args.output) / "latest.json")
    if final["success"] is not True:
        raise ValueError("Cannot export an incomplete attempt")
    if final.get("executed_sources_sha256") != execution_sources() or final.get("execution_sources_unchanged") is not True:
        raise ValueError("Publication sources differ from the frozen executed sources")
    attempt = Path(final["attempt"])
    public = HERE / "artifacts"
    public.mkdir(exist_ok=True)
    renders = HERE / "renders"
    renders.mkdir(exist_ok=True)
    records = []
    for name in final["models"]:
        raw_path = attempt / name / "result.json"
        raw = read_json(raw_path)
        worker = dict(raw["worker"])
        for key in ("source_before", "source_after"):
            worker[key] = dict(worker[key], path="source.FCStd")
        sandbox = raw["sandbox"]
        inspection = sandbox["container_inspection"]
        cleanup_query = bounded_capture(["podman", "--connection", args.connection, "ps", "--all", "--filter",
                                         "id=" + inspection["Id"], "--format", "{{.ID}}"], timeout=30)
        cleanup_check = {"container_id": inspection["Id"], "returncode": cleanup_query.returncode,
                         "remaining_ids": cleanup_query.stdout.decode().split(),
                         "capture_stopped_reason": cleanup_query.stopped_reason}
        write_json(attempt / name / "cleanup-query.json", cleanup_check)
        if cleanup_query.returncode or cleanup_query.stdout.strip() or cleanup_query.stopped_reason is not None:
            raise ValueError("Own rendering container absence check failed")
        evidence = {"schema": "secca-supplemental-public-v1", "success": raw["success"],
                    "request": raw["request"], "worker": worker, "image_checks": raw["image_checks"],
                    "source_host_unchanged": raw["source_host_unchanged"],
                    "cleanup": {"success": raw["cleanup_error"] is None and sandbox["remaining_container_id"] is None,
                                "independent_query": cleanup_check},
                    "runtime": {"image_id": sandbox["image_id"], "container_id": inspection["Id"],
                                "network": inspection["HostConfig"]["NetworkMode"],
                                "user": inspection["Config"]["User"], "root_readonly": inspection["HostConfig"]["ReadonlyRootfs"],
                                "bind_mounts": [], "process_isolation": sandbox["process_isolation"]},
                    "original_evidence_sha256": digest(raw_path),
                    "transformation": "Allowlist export. Omit host command logs, named connection and host paths. Normalize worker CAD path."}
        target = public / name
        target.mkdir(exist_ok=True)
        write_json(target / "evidence.json", evidence)
        for image in raw["image_checks"]:
            shutil.copyfile(attempt / name / (image + ".png"), target / (image + ".png"))
            shutil.copyfile(target / (image + ".png"), renders / (name + "-" + image + ".png"))
        records.append({"model": name, "original_evidence_sha256": digest(raw_path),
                        "public_evidence_sha256": digest(target / "evidence.json"),
                        "images": raw["image_checks"]})
    visual_path = Path(args.visual_qa)
    visual = read_json(visual_path)
    if visual.get("overall_verdict") != "pass" or len(visual.get("models", [])) != 4:
        raise ValueError("Four-model visual QA must pass before publication")
    for model in visual["models"]:
        for image in model["images"]:
            name = Path(image["path"]).name
            target = public / model["model"] / name
            if digest(target) != image["sha256"]:
                raise ValueError("Visual QA is bound to a different image")
            image["path"] = target.relative_to(HERE).as_posix()
    visual["original_evidence_sha256"] = digest(visual_path)
    visual["transformation"] = "Image paths changed to public experiment-relative artifacts; observations and image hashes preserved."
    write_json(HERE / "visual-qa.json", visual)
    write_json(HERE / "manifest.json", {"schema": "secca-supplemental-package-v1", "success": True,
               "scope": "Estimated near-reference presentation only. No new generation or scoring.",
               "historical_evidence_unchanged": final["historical_evidence_unchanged"],
               "executed_sources_sha256": final["executed_sources_sha256"],
               "execution_sources_unchanged": final["execution_sources_unchanged"],
               "git_canonical_checks": final["git_canonical_checks"],
               "presentation_attempts": [{"attempt_id": path.parent.name, "success": read_json(path)["success"],
                                           "publication_portable": bool(read_json(path).get("git_canonical_checks")),
                                           "source_binding": ("execution-bound Git-canonical source bytes" if "git_canonical_checks" in read_json(path)
                                                              else "execution-bound but unportable; CRLF helper differed from published LF blob" if "executed_sources_sha256" in read_json(path)
                                                              else "prototype, no executed-host-source snapshot")}
                                          for path in sorted((Path(args.output) / "attempts").glob("*/result.json"), key=lambda path:path.stat().st_mtime_ns)],
               "accepted_attempt_id": attempt.name,
               "protected_historical_and_helper_files": len(final["protected_before"]),
               "spec_sha256": digest(HERE / "spec.json"), "sources_sha256": digest(HERE / "sources.json"),
               "renderer_sha256": digest(HERE / "renderer.py"), "worker_sha256": digest(HERE / "worker.py"),
               "visual_qa_sha256": digest(HERE / "visual-qa.json"),
               "models": records})
    return verify(args)


def verify(_args):
    manifest = read_json(HERE / "manifest.json")
    if manifest["executed_sources_sha256"] != execution_sources() or manifest["execution_sources_unchanged"] is not True:
        raise ValueError("Package differs from executed source snapshot")
    if not manifest["git_canonical_checks"] or any(item["raw_git_blob"] != item["canonical_git_blob"] for item in manifest["git_canonical_checks"].values()):
        raise ValueError("Executed sources did not pass Git byte-preservation checks")
    verify_inputs(read_json(HERE / "sources.json"))
    for filename, key in (("spec.json", "spec_sha256"), ("sources.json", "sources_sha256"), ("renderer.py", "renderer_sha256"), ("worker.py", "worker_sha256"), ("visual-qa.json", "visual_qa_sha256")):
        if digest(HERE / filename) != manifest[key]:
            raise ValueError("Package source hash mismatch: " + filename)
    for model in manifest["models"]:
        folder = HERE / "artifacts" / model["model"]
        if digest(folder / "evidence.json") != model["public_evidence_sha256"]:
            raise ValueError("Evidence hash mismatch")
        evidence = read_json(folder / "evidence.json")
        if not evidence["success"] or not evidence["cleanup"]["success"] or not evidence["source_host_unchanged"]:
            raise ValueError("Evidence reports failure")
        for name, expected in model["images"].items():
            actual = image_check(folder / (name + ".png"), [expected["width"], expected["height"]])
            if actual != expected:
                raise ValueError("Public image differs")
            if digest(HERE / "renders" / (model["model"] + "-" + name + ".png")) != actual["sha256"]:
                raise ValueError("Comparison gallery image differs")
    print("Verified four supplemental renders and preserved historical evidence.")
    return 0


def selftest(_args):
    sources, spec = read_json(HERE / "sources.json"), read_json(HERE / "spec.json")
    analysis = read_json(HERE / "camera-analysis.json")
    if spec["images"] != {"reference-view": [1600,900], "preview": [960,540]}:
        raise ValueError("Unexpected image output contract")
    for source, expected in zip(sources["models"], analysis["models"]):
        actual = quaternion(spec["base_quaternion_xyzw"], source["yaw_degrees"])
        if max(abs(a-b) for a,b in zip(actual, expected["supplemental_quaternion_xyzw"])) > 1e-8:
            raise AssertionError("Rotation differs from independent camera analysis")
    for invalid in (float("nan"), float("inf")):
        try:
            quaternion(spec["base_quaternion_xyzw"], invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Nonfinite camera accepted")
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "test.png"
        image = Image.new("RGB", (200,100), "white")
        image.save(path)
        try:
            image_check(path, [200,100])
        except ValueError:
            pass
        else:
            raise AssertionError("Blank image accepted")
        ImageDraw.Draw(image).rectangle((20,20,180,80), fill="blue")
        image.save(path)
        image_check(path, [200,100])
        ImageDraw.Draw(image).rectangle((0,20,180,80), fill="blue")
        image.save(path)
        try:
            image_check(path, [200,100])
        except ValueError:
            pass
        else:
            raise AssertionError("Edge-clipped image accepted")
    print("Camera composition and image boundary checks passed.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("render")
    command.add_argument("--connection", required=True)
    command.add_argument("--image-id", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(handler=run)
    command = sub.add_parser("export")
    command.add_argument("--output", required=True)
    command.add_argument("--connection", required=True)
    command.add_argument("--visual-qa", required=True)
    command.set_defaults(handler=export)
    sub.add_parser("verify").set_defaults(handler=verify)
    sub.add_parser("selftest").set_defaults(handler=selftest)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
