"""Export historical verification records with host identifiers replaced."""

import argparse
import hashlib
import json
from pathlib import Path
import re

MARKER = {
    "record_type": "historical_public_transformed_export",
    "raw_record": False,
    "provenance_manifest": "references/public-export-manifest.json",
    "new_model_generation": False,
}
HOME_PATTERN = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+", re.IGNORECASE)
LINUX_HOME_PATTERN = re.compile("/" + r"home/(?!candidate(?:/|$))[^/\s\"']+(?=/)")


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def export(source_root, output_root):
    source_root, output_root = Path(source_root).resolve(strict=True), Path(output_root).resolve(strict=True)
    if source_root == output_root or source_root.is_relative_to(output_root) or output_root.is_relative_to(source_root):
        raise ValueError("Source originals and public output must be separate directories")
    source_files = sorted((source_root / "references/verification").rglob("*"))
    source_files = [path for path in source_files if path.is_file()]
    source_files.append(source_root / "references/verified-runtime.json")
    if len(source_files) < 2:
        raise ValueError("Historical verification records are missing")
    inputs = {path.relative_to(source_root).as_posix(): path.read_bytes() for path in source_files}
    connections = set()

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "connection" and isinstance(child, str) and child:
                    connections.add(child)
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for name, payload in inputs.items():
        if name.endswith(".json"):
            collect(json.loads(payload))

    def text_export(value):
        value = HOME_PATTERN.sub("<HOST_HOME>", value)
        value = LINUX_HOME_PATTERN.sub("<HOST_HOME>", value)
        for connection in sorted(connections, key=len, reverse=True):
            value = value.replace(connection, "<PODMAN_CONNECTION>")
        return value

    def value_export(value):
        if isinstance(value, dict):
            return {text_export(key): value_export(child) for key, child in value.items()}
        if isinstance(value, list):
            return [value_export(child) for child in value]
        return text_export(value) if isinstance(value, str) else value

    outputs = {}
    for name, payload in inputs.items():
        text = payload.decode("utf-8-sig")
        if name.endswith(".json"):
            value = value_export(json.loads(text))
            value["public_export"] = MARKER
            text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        elif name.endswith(".jsonl"):
            rows = []
            for line in text.splitlines():
                if line.strip():
                    value = value_export(json.loads(line))
                    value["public_export"] = MARKER
                    rows.append(json.dumps(value, ensure_ascii=False))
            text = "\n".join(rows) + ("\n" if rows else "")
        else:
            text = ("Historical public transformed export; not a raw record. "
                    "See references/public-export-manifest.json for source and export hashes.\n"
                    + text_export(text).replace("\r\n", "\n"))
        outputs[name] = text.encode("utf-8")

    source_by_hash = {digest(payload): name for name, payload in inputs.items()}
    dependencies = {}
    finished = {}

    def finish(name, active=()):
        if name in finished:
            return finished[name]
        if name in active:
            raise ValueError("Historical record hash references contain a cycle")
        text = outputs[name].decode("utf-8")
        dependencies[name] = []
        for original_hash, target in source_by_hash.items():
            if original_hash in text:
                exported_hash = digest(finish(target, (*active, name)))
                text = text.replace(original_hash, exported_hash)
                dependencies[name].append(target)
        finished[name] = text.encode("utf-8")
        return finished[name]

    for name in outputs:
        finish(name)
    records = []
    for name, payload in finished.items():
        target = output_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        records.append({"path": name, "source_path": name, "source_sha256": digest(inputs[name]),
                        "export_sha256": digest(payload), "source_bytes": len(inputs[name]),
                        "export_bytes": len(payload), "dependent_hash_exports": dependencies[name],
                        "transforms": ["replace host homes with <HOST_HOME>",
                                       "replace Podman connection labels with <PODMAN_CONNECTION>",
                                       "mark as historical public transformed export, not raw",
                                       "serialize UTF-8 with LF line endings"]})
    manifest = {"schema_version": 1, **MARKER, "fixed_assets_modified": False,
                "source_originals_included": False, "files": sorted(records, key=lambda record: record["path"])}
    target = output_root / "references/public-export-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_public_export(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads((root / "references/public-export-manifest.json").read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in MARKER.items()):
        raise ValueError("Public historical export provenance marker is missing")
    seen = set()
    for record in manifest["files"]:
        name = record["path"]
        path = (root / name).resolve(strict=True)
        if (name in seen or not path.is_relative_to(root)
                or not (name.startswith("references/verification/") or name == "references/verified-runtime.json")
                or record["source_path"] != name
                or not re.fullmatch(r"[0-9a-f]{64}", record["source_sha256"])):
            raise ValueError("Invalid public historical export manifest entry")
        seen.add(name)
        payload = path.read_bytes()
        if digest(payload) != record["export_sha256"] or len(payload) != record["export_bytes"]:
            raise ValueError("Public historical export hash mismatch: " + name)
        if path.suffix in (".json", ".jsonl"):
            values = [json.loads(payload)] if path.suffix == ".json" else [json.loads(line) for line in payload.splitlines() if line.strip()]
            if any(value.get("public_export") != MARKER for value in values):
                raise ValueError("Historical record lacks its public transformation marker: " + name)
        elif not payload.startswith(b"Historical public transformed export; not a raw record."):
            raise ValueError("Historical text record lacks its public transformation marker: " + name)
    expected = {path.relative_to(root).as_posix() for path in (root / "references/verification").rglob("*") if path.is_file()}
    expected.add("references/verified-runtime.json")
    if seen != expected:
        raise ValueError("Public historical export manifest does not cover every record")
    return {"status": "verified", "files": len(seen), "new_model_generation": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Separate skill root containing private originals")
    parser.add_argument("--output", type=Path, required=True, help="Public repository root")
    parser.add_argument("--verify", action="store_true", help="Verify exported hashes and markers without private originals")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_public_export(args.output)))
        return
    if args.source is None:
        parser.error("--source is required unless --verify is used")
    result = export(args.source, args.output)
    print(json.dumps({"status": "exported", "files": len(result["files"]), "new_model_generation": False}))


if __name__ == "__main__":
    main()
