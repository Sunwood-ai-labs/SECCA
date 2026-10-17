import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile

RUNTIME_NAMES = [
    "runtime_boot.py", "start_freecad.FCMacro", "mcp_client.py", "smoke_test.py",
    "candidate_entry.py", "gateway.py", "loopback_adapter.py",
]
ROOT_FILES = ["pyproject.toml", "uv.lock", "README.md", "LICENSE"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_vendor(source, vendor):
    source = Path(source).resolve(strict=True)
    vendor = Path(vendor)
    vendor.mkdir(parents=True, exist_ok=True)
    files = [source / name for name in ROOT_FILES]
    files += sorted((source / "src/freecad_mcp").rglob("*.py"))
    files += sorted((source / "addon/FreeCADMCP").rglob("*.py"))
    records = []
    for path in files:
        if path.is_symlink():
            raise ValueError("MCP source symlinks are not allowed: " + str(path))
        relative = path.relative_to(source)
        destination = vendor / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        records.append({"path": relative.as_posix(), "sha256": sha256(destination), "bytes": destination.stat().st_size})
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    manifest = {"schema_version": 1, "source_head": head, "files": records, "local_working_tree_files_included_by_hash": True}
    (vendor.parent / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verified_vendor_files(vendor, manifest):
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("Unsupported bundled MCP source manifest")
    files = []
    seen = set()
    root = vendor.resolve(strict=True)
    for record in manifest["files"]:
        name = record.get("path") if isinstance(record, dict) else None
        if not isinstance(name, str) or "\\" in name or ":" in name:
            raise ValueError("Invalid MCP source manifest path")
        relative = PurePosixPath(name)
        allowed = name in ROOT_FILES or (
            relative.parts[:2] in (("src", "freecad_mcp"), ("addon", "FreeCADMCP"))
            and relative.suffix == ".py"
        )
        if not allowed or relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name:
            raise ValueError("MCP source path is outside the staging allowlist: " + name)
        if name.casefold() in seen:
            raise ValueError("Duplicate MCP source manifest path: " + name)
        seen.add(name.casefold())
        original = vendor / name
        if original.is_symlink() or not original.resolve(strict=True).is_relative_to(root):
            raise ValueError("Bundled MCP source cannot escape its vendor directory: " + name)
        payload = original.read_bytes()
        if hashlib.sha256(payload).hexdigest() != record.get("sha256") or len(payload) != record.get("bytes"):
            raise ValueError("Bundled MCP source does not match its manifest: " + name)
        files.append((name, payload))
    if not {name.casefold() for name in ROOT_FILES}.issubset(seen):
        raise ValueError("Bundled MCP source manifest is missing required root files")
    return files


def stage_context(source, destination):
    here = Path(__file__).resolve().parent
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    vendor = here / "vendor/freecad-mcp"
    manifest = (
        refresh_vendor(source, vendor)
        if source is not None
        else json.loads((here / "vendor/source-manifest.json").read_text(encoding="utf-8"))
    )
    files = verified_vendor_files(vendor, manifest)
    shutil.copyfile(here / "Containerfile", destination / "Containerfile")
    runtime = destination / "runtime"
    runtime.mkdir()
    for name in RUNTIME_NAMES:
        path = here / name
        if path.is_file():
            shutil.copyfile(path, runtime / name)
    staged_vendor = destination / "vendor/freecad-mcp"
    for name, payload in files:
        target = staged_vendor / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (destination / "vendor/source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination


def build_image(connection, mcp_source, tag):
    if not connection or not tag.startswith("localhost/kart-sbx-"):
        raise ValueError("named connection and localhost/kart-sbx- tag are required")
    with tempfile.TemporaryDirectory(prefix="kart-sbx-build-") as temporary:
        context = stage_context(mcp_source, temporary)
        result = subprocess.run(["podman", "--connection", connection, "build", "--tag", tag, "--file", str(context / "Containerfile"), str(context)], check=False)
        if result.returncode:
            raise RuntimeError("Podman image build failed")
    inspected = subprocess.check_output(["podman", "--connection", connection, "image", "inspect", tag, "--format", "{{.Id}}"], text=True).strip()
    return {"tag": tag, "image_id": inspected, "connection": connection}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", required=True)
    parser.add_argument("--mcp-source", help="Optional MCP checkout for refreshing the bundled source")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    print(json.dumps(build_image(args.connection, args.mcp_source, args.tag)))


if __name__ == "__main__":
    main()

