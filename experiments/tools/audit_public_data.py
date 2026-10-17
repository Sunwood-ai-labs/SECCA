"""Read-only, value-suppressing audit for a public repository. Standard library only."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import zipfile
from pathlib import Path

SECRET_RULES = {
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "github_token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b",
    "provider_token": rb"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|hf_[A-Za-z0-9]{24,})\b",
    "aws_access_key": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "jwt": rb"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b",
    "credential_url": rb"https?://[^\s/:@]{2,}:[^\s/@]{3,}@",
}
INFO_RULES = {
    "windows_path": rb"(?<![A-Za-z])[A-Za-z]:[\\/](?:[^\r\n\"<>]+)",
    "user_home_path": rb"(?:/home/|/Users/|[A-Za-z]:\\+Users\\+)[^/\\\s\"']+",
    "email_like": rb"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "machine_connection_field": rb'"connection"\s*:',
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan(root: Path) -> dict:
    findings = []
    files = 0
    members = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in (".git", ".venv", "__pycache__", "node_modules") for part in path.relative_to(root).parts):
            continue
        files += 1
        payloads = [("", path.read_bytes())]
        if path.suffix.lower() == ".fcstd":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith((".xml", ".json", ".txt")):
                        payloads.append(("!" + name, archive.read(name)))
                        members += 1
        for member, data in payloads:
            counts = {}
            for level, rules in (("credential_candidate", SECRET_RULES), ("metadata", INFO_RULES)):
                for category, pattern in rules.items():
                    count = len(re.findall(pattern, data))
                    if count:
                        counts[f"{level}:{category}"] = count
            if counts:
                findings.append({"file": path.relative_to(root).as_posix() + member,
                                 "sha256": sha(path), "counts": counts})
    totals = collections.Counter()
    for item in findings:
        totals.update(item["counts"])
    return {"schema_version": 1, "scope": "Repository files and XML/JSON/text members of FCStd archives; no account or credential-store reads.",
            "files_scanned": files, "fcstd_text_members_scanned": members,
            "matched_values_included": False, "totals": dict(totals), "findings": findings,
            "limitations": ["Pattern matching is not proof of the absence of secrets or personal data.",
                            "Source-code regex literals, fixtures and public attribution may match; inspect candidates before publication.",
                            "Filesystem paths, sandbox session IDs, container IDs and connection names are archival metadata, not credentials.",
                            "No inferred copyright or redistribution permission is granted by this audit."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files_scanned": result["files_scanned"], "totals": result["totals"]}))


if __name__ == "__main__":
    main()
