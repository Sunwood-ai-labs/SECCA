"""Run one fixed OpenCode request inside the candidate container."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


MODEL_CONFIG_KEYS = {"id", "name", "family", "attachment", "reasoning", "tool_call", "temperature",
                     "modalities", "limit", "interleaved", "cost", "structured_output"}


def model_configuration(metadata, model_id, api_model_id):
    provider, route = model_id.split("/", 1)
    if not isinstance(metadata, dict):
        raise ValueError("Model metadata must be an object")
    model = metadata.get("model")
    if (metadata.get("provider_id") != provider or not isinstance(model, dict)
            or model.get("id") != route or model.get("id") != api_model_id):
        raise ValueError("Model metadata provider/model identity differs")
    return {key: value for key, value in model.items() if key in MODEL_CONFIG_KEYS}


def validate_process_security(status_text):
    status = dict(line.split(":", 1) for line in status_text.splitlines() if ":" in line)
    if any(key not in status for key in ("CapEff", "CapPrm", "CapBnd", "NoNewPrivs")):
        raise ValueError("Candidate process security fields are missing")
    if any(int(status[key].strip(), 16) != 0 for key in ("CapEff", "CapPrm", "CapBnd")) or status["NoNewPrivs"].strip() != "1":
        raise ValueError("Candidate requires zero effective, permitted and bounding capabilities and no-new-privileges")
    return {key: status[key].strip() for key in ("CapEff", "CapPrm", "CapBnd", "NoNewPrivs")}


def main():
    root = Path("/workspace")
    inputs = root / ".runtime-input"
    spec = json.loads((inputs / "runtime.json").read_text(encoding="utf-8"))
    image = inputs / "reference.jpg"
    if hashlib.sha256(image.read_bytes()).hexdigest() != spec["reference_sha256"]:
        raise ValueError("Reference hash differs from prepared input")
    if hashlib.sha256(spec["prompt_text"].encode()).hexdigest() != spec["prompt_sha256"]:
        raise ValueError("Prompt hash differs from prepared input")
    if os.getuid() != 10000 or set(path.name for path in root.iterdir()) - {".runtime-input", ".runtime"}:
        raise ValueError("Candidate requires a fresh workspace and UID 10000")
    process_security = validate_process_security(Path("/proc/self/status").read_text())
    version = subprocess.check_output(["opencode", "--version"], text=True, timeout=30).strip()
    if version != "1.19.3":
        raise ValueError("Candidate requires OpenCode 1.19.3")
    identity = {"type": "sandbox_runtime_identity", "opencode_version": version, "process_security": process_security,
                "locks_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in (Path("/opt/debian-packages.lock"), Path("/opt/mcp-source-manifest.json"), Path("/opt/opencode-version.txt"))}}
    freecad = root / ".runtime/freecad.json"
    if freecad.is_file():
        identity["freecad"] = json.loads(freecad.read_text())
    print(json.dumps(identity), flush=True)
    shutil.copyfile(image, root / "reference.jpg")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    provider = spec["model_id"].split("/", 1)[0]
    config = {
        "model": spec["model_id"], "small_model": spec["model_id"],
        "enabled_providers": [provider], "share": "disabled", "permission": {"*": "allow"},
        "provider": {provider: {"options": {"baseURL": spec["api_base_url"], "apiKey": "trial-local"}}},
        "mcp": {"freecad": {"type": "local", "command": ["/opt/freecad-mcp/.venv/bin/freecad-mcp", "--host", "127.0.0.1", "--freecadcmd", "/usr/bin/freecadcmd"], "enabled": True, "timeout": 120000}},
        "agent": {"build": {"prompt": "Create the requested artifact using the available tools. Work only inside the current workspace. Do not read or modify management documents outside this workspace."}},
    }
    metadata_path = inputs / "model-metadata.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        config["provider"][provider]["models"] = {
            spec["model_id"].split("/", 1)[1]: model_configuration(metadata, spec["model_id"], spec["api_model_id"])}
    env = {key: value for key, value in os.environ.items() if key in {
        "PATH", "HOME", "LANG", "LC_ALL", "DISPLAY", "QT_X11_NO_MITSHM", "LIBGL_ALWAYS_SOFTWARE",
        "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"}}
    env.update({"OPENCODE_CONFIG_CONTENT": json.dumps(config), "OPENCODE_CONFIG_DIR": "/home/candidate/.config/opencode"})
    for suffix in ("AUTOUPDATE", "DEFAULT_PLUGINS", "CLAUDE_CODE", "CLAUDE_CODE_PROMPT", "CLAUDE_CODE_SKILLS", "CLAUDE_CODE_MCP", "LSP_DOWNLOAD", "PROJECT_CONFIG"):
        env["OPENCODE_DISABLE_" + suffix] = "true"
    adapter = subprocess.Popen([sys.executable, "/opt/runtime/loopback_adapter.py", "--socket", "/run/model-link/api.sock"], env=env)
    try:
        import socket
        import time
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", 18080), timeout=.1):
                    break
            except OSError:
                if adapter.poll() is not None:
                    raise RuntimeError("Model channel adapter exited")
                time.sleep(.05)
        else:
            raise RuntimeError("Model channel adapter did not become ready")
        print(json.dumps({"type": "sandbox_generation_start"}), flush=True)
        command = ["opencode", "run", "--pure", "-m", spec["model_id"], "--format", "json", "-f", str(root / "reference.jpg"), "--", spec["prompt_text"]]
        return subprocess.call(command, cwd=root, env=env)
    finally:
        adapter.terminate()
        try:
            adapter.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter.kill()
            adapter.wait()


if __name__ == "__main__":
    sys.exit(main())
