"""Verify the actual offline FreeCAD runtime without calling any model API."""

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import uuid

from PIL import Image

from sandbox_postprocess import OfflineContainer
from sandbox_runner import Podman, canonical_image_id

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "container"))
from build_context import RUNTIME_NAMES, verified_vendor_files


@dataclass(frozen=True)
class SmokeJob:
    connection: str
    image_id: str
    timeout: int
    request_id: str
    operation: str = "render"


def embedded_sources():
    manifest = json.loads((ROOT / "container/vendor/source-manifest.json").read_text(encoding="utf-8"))
    records = {"/opt/runtime/" + name: hashlib.sha256((ROOT / "container" / name).read_bytes()).hexdigest()
               for name in RUNTIME_NAMES}
    records.update({"/opt/freecad-mcp/" + name: hashlib.sha256(payload).hexdigest()
                    for name, payload in verified_vendor_files(ROOT / "container/vendor/freecad-mcp", manifest)})
    return records, manifest


def compare_sources(expected, actual, expected_manifest, actual_manifest):
    if expected != actual or expected_manifest != actual_manifest:
        changed = sorted(name for name in set(expected) | set(actual) if expected.get(name) != actual.get(name))
        raise ValueError("Runtime differs from the checkout; rebuild before verification. Files: " + ", ".join(changed))


def verify_png(path):
    with Image.open(path) as image:
        if image.format != "PNG" or image.size != (640, 480):
            raise ValueError("Runtime did not produce the expected 640 by 480 PNG")
        pixels = image.convert("RGB")
        corners = [pixels.getpixel(point) for point in ((0, 0), (639, 0), (0, 479), (639, 479))]
        if any(pixel != (255, 255, 255) for pixel in corners):
            raise ValueError("Runtime PNG background corners are not white")
        extrema = pixels.getextrema()
        if all(low == high == 255 for low, high in extrema):
            raise ValueError("Runtime PNG is empty")
        return {"width": image.width, "height": image.height, "white_corners": True, "nonempty": True}


def verify(connection, image, output, timeout):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "success": False, "model_inference_performed": False}
    box = None
    try:
        client = Podman(connection)
        image_id = canonical_image_id(client.document(["image", "inspect", image])[0]["Id"])
        report["image_id"] = image_id
        job = SmokeJob(connection, image_id, timeout, uuid.uuid4().hex)
        expected, manifest = embedded_sources()
        box = OfflineContainer(job)
        with box:
            source_check = """
import hashlib, json, sys
from pathlib import Path
print(json.dumps({"files": {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in json.loads(sys.argv[1])},
                  "manifest": json.loads(Path('/opt/mcp-source-manifest.json').read_text())}))
"""
            actual = json.loads(box.exec("/usr/local/bin/python3", "-c", source_check, json.dumps(list(expected))).stdout)
            compare_sources(expected, actual["files"], manifest, actual["manifest"])
            report["embedded_sources"] = {"matched": True, "files": expected, "vendor_source_head": manifest["source_head"]}
            box.exec("/usr/local/bin/python3", "/opt/runtime/smoke_test.py")
            for name in ("smoke.FCStd", "smoke.step", "smoke.png", "smoke-result.json"):
                box.download("/workspace/" + name, output / name, 16 * 1024 * 1024)
            smoke = json.loads((output / "smoke-result.json").read_text(encoding="utf-8"))
            if smoke.get("success") is not True or smoke.get("model_inference_performed") is not False:
                raise ValueError("Runtime smoke did not report success without inference")
            for name, record in smoke["files"].items():
                payload = (output / name).read_bytes()
                if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
                    raise ValueError("Downloaded smoke artifact hash mismatch: " + name)
            report["png"] = verify_png(output / "smoke.png")
            report["smoke"] = smoke
            box.upload(ROOT / "scripts/test_gateway.py", "/job/test_gateway.py")
            gateway_check = """
import contextlib, json, runpy, sys, types, unittest
module = types.ModuleType('secca_gateway_tests')
module.__dict__.update(runpy.run_path('/job/test_gateway.py'))
with contextlib.redirect_stdout(sys.stderr):
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
print(json.dumps({'ran': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}))
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
"""
            gateway_result = box.podman("exec", "--env", "PYTHONPATH=/opt/runtime", box.container_id,
                                        "/usr/local/bin/python3", "-c", gateway_check)
            (output / "gateway-tests.txt").write_bytes(gateway_result.stderr)
            report["gateway_tests"] = json.loads(gateway_result.stdout)
            report["isolation"] = box.runtime_isolation
            report["container_isolation_verified"] = True
        if box.cleanup_error:
            raise RuntimeError(box.cleanup_error)
        report["success"] = True
    except Exception as error:
        report["error"] = str(error)
    finally:
        if box is not None:
            report["cleanup_error"] = box.cleanup_error
            (output / "podman-commands.json").write_text(json.dumps(box.log, indent=2), encoding="utf-8")
        (output / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", required=True, help="Explicit named Podman connection")
    parser.add_argument("--image", required=True, help="Runtime tag or immutable image ID; resolved and recorded")
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory outside a model trial")
    parser.add_argument("--timeout", type=int, default=240, help="Per-operation timeout in seconds")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    try:
        report = verify(args.connection, args.image, args.output, args.timeout)
    except OSError as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({key: report[key] for key in ("success", "model_inference_performed")}
                     | {"evidence": str(args.output)}))
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
