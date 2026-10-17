"""Prepare and execute one immutable, isolated OpenCode CAD trial."""

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time


PACKAGE = Path(__file__).resolve().parent.parent
ENV_ALLOWLIST = {
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
    "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS",
    "LANG", "LC_ALL", "SYSTEMDRIVE",
}
RESERVED_ENV = ENV_ALLOWLIST | {"CODEX_HOME"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes its root: {relative}")
    return path


def verify_assets():
    document = read_json(PACKAGE / "assets/manifest.json")
    if document.get("schema_version") != 1 or document.get("algorithm") != "sha256":
        raise ValueError("Unsupported asset manifest schema or algorithm")
    manifest = document.get("files")
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Asset manifest files must map relative paths to SHA-256 values")
    actual = {path.relative_to(PACKAGE).as_posix() for path in (PACKAGE / "assets").rglob("*")
              if path.is_file() and path != PACKAGE / "assets/manifest.json"}
    if set(manifest) != actual:
        raise ValueError("Asset manifest has unexpected or missing files")
    for relative, expected in manifest.items():
        path = inside(PACKAGE, relative)
        if not isinstance(expected, str) or sha256(path) != expected:
            raise ValueError(f"Asset integrity mismatch: {relative}")
    return {"status": "verified", "files": len(manifest)}


def credential_names(names):
    result = []
    for name in names:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid credential environment variable name: {name}")
        if name.upper() in RESERVED_ENV or name.upper().startswith(("OPENCODE_", "XDG_")):
            raise ValueError(f"Reserved environment variable cannot be a credential: {name}")
        if name not in result:
            result.append(name)
    return result


@dataclass
class RunMetrics:
    event_types: Counter = field(default_factory=Counter)
    tool_calls: Counter = field(default_factory=Counter)
    tokens: Counter = field(default_factory=Counter)
    cost: float = 0.0
    errors: list = field(default_factory=list)
    session_ids: set = field(default_factory=set)
    non_json_lines: int = 0

    def observe(self, line):
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.non_json_lines += 1
            return
        if not isinstance(event, dict):
            self.non_json_lines += 1
            return
        kind = str(event.get("type", "unknown"))
        self.event_types[kind] += 1
        if event.get("sessionID"):
            self.session_ids.add(str(event["sessionID"]))
        part = event.get("part")
        part = part if isinstance(part, dict) else {}
        if kind == "tool_use":
            tool = str(part.get("tool", "unknown"))
            self.tool_calls[tool] += 1
            state = part.get("state")
            state = state if isinstance(state, dict) else {}
            if state.get("status") == "error":
                self.errors.append({"type": "tool_error", "tool": tool, "message": str(state.get("error", "tool error"))})
            output = state.get("output", "")
            output_text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
            if "Failed to execute code:" in output_text:
                self.errors.append({"type": "tool_output_error", "tool": tool, "message": output_text})
        elif kind == "step_finish":
            self.cost += float(part.get("cost") or 0)
            for key, value in (part.get("tokens") or {}).items():
                if isinstance(value, (int, float)):
                    self.tokens[key] += value
                elif isinstance(value, dict):
                    for nested, number in value.items():
                        if isinstance(number, (int, float)):
                            self.tokens[f"{key}.{nested}"] += number
        elif kind == "error":
            self.errors.append({"type": "error", "message": str(event.get("error", part))})

    def as_dict(self):
        return {"event_types": dict(self.event_types), "tool_calls": dict(self.tool_calls),
                "tokens": dict(self.tokens), "recorded_cost_usd": self.cost,
                "errors": self.errors, "session_ids": sorted(self.session_ids),
                "non_json_stdout_lines": self.non_json_lines}


def saved_files(workspace):
    return [{"path": str(path.relative_to(workspace)).replace("\\", "/"),
             "bytes": path.stat().st_size, "sha256": sha256(path),
             "modified_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
            for path in sorted(workspace.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(workspace).parts]


def terminate_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=30, check=False)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()


def stream_reader(name, stream, events):
    try:
        for line in stream:
            events.put((name, line))
    finally:
        stream.close()
        events.put((name, None))


def prepare(args):
    from sandbox_runner import prepare as isolated_prepare
    return isolated_prepare(args)


def load_trial(trial):
    from sandbox_runner import load_trial as isolated_load
    return isolated_load(trial)


def run(args):
    from sandbox_runner import run as isolated_run
    return isolated_run(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build the isolated runtime image without invoking a model")
    build.add_argument("--connection", required=True)
    build.add_argument("--mcp-source", type=Path)
    build.add_argument("--tag", required=True)
    prep = commands.add_parser("prepare", help="Prepare one fresh OS-isolated trial without invoking a model")
    prep.add_argument("--trial", type=Path, required=True)
    prep.add_argument("--model", required=True)
    prep.add_argument("--connection", required=True)
    prep.add_argument("--image", required=True)
    prep.add_argument("--api-base-url", required=True)
    prep.add_argument("--api-model")
    prep.add_argument("--model-metadata", type=Path)
    prep.add_argument("--credential-env")
    prep.add_argument("--timeout", type=int, default=1800)
    execute = commands.add_parser("run", help="Run one prepared Podman trial exactly once")
    execute.add_argument("--trial", type=Path, required=True)
    commands.add_parser("verify-assets", help="Verify installed package asset hashes")
    args = parser.parse_args()
    try:
        if args.command == "build":
            command = [sys.executable, str(PACKAGE / "container/build_context.py"), "--connection", args.connection, "--tag", args.tag]
            if args.mcp_source is not None:
                command += ["--mcp-source", str(args.mcp_source)]
            return subprocess.call(command)
        if args.command == "run":
            return run(args)
        result = prepare(args) if args.command == "prepare" else verify_assets()
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"candidate: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
