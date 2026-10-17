"""Host-owned runner for fail-closed per-trial Podman CAD execution."""

import hashlib
import io
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import tarfile
import threading
import time
import uuid
from urllib.parse import urlsplit

import candidate

PACKAGE = Path(__file__).resolve().parent.parent
MAX_ARTIFACT = 128 * 1024 * 1024
PODMAN_DEFAULT_CAPS = {"CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID", "KILL", "NET_BIND_SERVICE", "SETFCAP", "SETGID", "SETPCAP", "SETUID", "SYS_CHROOT"}


def canonical_image_id(value):
    bare = value.removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", bare):
        raise ValueError("Podman did not return an immutable image ID")
    return "sha256:" + bare


class Podman:
    def __init__(self, connection):
        if not isinstance(connection, str) or not connection.strip() or connection.startswith("-"):
            raise ValueError("An explicit named Podman connection is required")
        self.prefix = ["podman", "--connection", connection]

    def call(self, args, *, data=None, timeout=60, check=True):
        result = subprocess.run(self.prefix + args, input=data, capture_output=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError("Podman operation failed: " + args[0] + " (exit " + str(result.returncode) + ")")
        return result

    def document(self, args):
        return json.loads(self.call(args).stdout)


def api_base(value):
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("benchmark_gateway", PACKAGE / "container/gateway.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_base_url(value)
    return value.rstrip("/")


def validate_model_metadata(metadata, model_id, api_model_id, base):
    provider, route = model_id.split("/", 1)
    if not isinstance(metadata, dict):
        raise ValueError("Model metadata must be an object")
    model = metadata.get("model")
    if (metadata.get("provider_id") != provider or not isinstance(model, dict)
            or model.get("id") != route or model.get("id") != api_model_id):
        raise ValueError("Model metadata provider/model identity differs")
    if metadata.get("provider_api") != base or not isinstance(metadata.get("provider_npm"), str):
        raise ValueError("Model metadata provider endpoint differs or package is missing")
    if (not isinstance(metadata.get("source_url"), str) or not metadata["source_url"].startswith("https://")
            or not re.fullmatch(r"[0-9a-f]{64}", metadata.get("source_sha256", ""))):
        raise ValueError("Model metadata source provenance is missing")
    return metadata


def prepare(args):
    candidate.verify_assets()
    if not re.fullmatch(r"[^/\s]+/.+", args.model) or any(char.isspace() for char in args.model):
        raise ValueError("Model must be the exact provider/model identifier")
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    names = candidate.credential_names([args.credential_env] if args.credential_env else [])
    if names and names[0] not in os.environ:
        raise ValueError("Requested credential environment variable is unset")
    base = api_base(args.api_base_url)
    wire_model = args.api_model or args.model.split("/", 1)[1]
    if not wire_model or any(char.isspace() for char in wire_model):
        raise ValueError("API model must be an exact nonempty identifier")
    metadata_path = getattr(args, "model_metadata", None)
    metadata = (validate_model_metadata(candidate.read_json(metadata_path), args.model, wire_model, base)
                if metadata_path is not None else None)
    client = Podman(args.connection)
    images = client.document(["image", "inspect", args.image])
    image_id = canonical_image_id(images[0]["Id"])
    protocol = candidate.read_json(candidate.PACKAGE / "assets/protocol.json")
    prompt = protocol["prompt_text"]
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    if prompt_hash != protocol["prompt_sent_utf8_sha256"]:
        raise ValueError("Fixed prompt hash mismatch")
    reference = candidate.inside(candidate.PACKAGE, protocol["reference_image_file"])
    if candidate.sha256(reference) != protocol["reference_image_sha256"]:
        raise ValueError("Fixed reference hash mismatch")
    trial = args.trial.resolve()
    trial.mkdir(parents=True, exist_ok=False, mode=0o700)
    workspace = trial / "workspace"
    inputs = trial / "runtime-input"
    workspace.mkdir()
    inputs.mkdir()
    import shutil
    shutil.copyfile(reference, workspace / "reference.jpg")
    shutil.copyfile(reference, inputs / "reference.jpg")
    shutil.copyfile(candidate.PACKAGE / "assets/protocol.json", trial / "protocol.json")
    runtime = {"schema_version": 1, "model_id": args.model, "api_model_id": wire_model,
               "prompt_text": prompt, "prompt_sha256": prompt_hash, "reference_sha256": candidate.sha256(reference),
               "api_base_url": "http://127.0.0.1:18080" + urlsplit(base).path}
    candidate.write_json_new(inputs / "runtime.json", runtime)
    files = ["protocol.json", "workspace/reference.jpg", "runtime-input/runtime.json", "runtime-input/reference.jpg"]
    if metadata is not None:
        shutil.copyfile(metadata_path, inputs / "model-metadata.json")
        files.append("runtime-input/model-metadata.json")
    manifest = {"schema_version": 2, "created_utc": candidate.utc_now(), "model_id": args.model,
                "protocol_id": protocol["id"], "protocol_sha256": candidate.sha256(trial / "protocol.json"),
                "credential_env_names": names, "timeout_seconds": args.timeout,
                "input": {"prompt_text": prompt, "prompt_sent_utf8_sha256": prompt_hash, "reference_sha256": candidate.sha256(reference)},
                "sandbox": {"backend": "podman-network-none-uds", "connection": args.connection,
                            "image_id": image_id, "api_base_url": base, "api_model_id": wire_model,
                            "limits": {"timeout_seconds": args.timeout, "memory": "4g", "cpus": 2, "pids": 512}},
                "harness": {"name": "OpenCode", "version": "1.19.3", "image_id": image_id},
                "protocol_deviations": ["Podman Linux, container-local FreeCAD/Xvfb and Unix-socket API gateway"],
                "file_hashes": {name: candidate.sha256(trial / name) for name in files}}
    if metadata is not None:
        manifest["model_metadata"] = {"file": "runtime-input/model-metadata.json", "source_url": metadata["source_url"],
                                      "source_sha256": metadata["source_sha256"]}
        manifest["protocol_deviations"].append("Explicit source-bound model catalog metadata supplements the bundled OpenCode registry")
    candidate.write_json_new(trial / "trial.json", manifest)
    return {"status": "prepared", "trial": str(trial), "model": args.model, "image_id": image_id}


def load_trial(trial):
    manifest = candidate.read_json(trial / "trial.json")
    if manifest.get("schema_version") != 2 or manifest.get("sandbox", {}).get("backend") != "podman-network-none-uds":
        raise ValueError("Only OS-isolated Podman trials may execute; prepare a new trial")
    if len(manifest.get("credential_env_names", [])) > 1:
        raise ValueError("Only one explicit provider credential is allowed")
    candidate.credential_names(manifest.get("credential_env_names", []))
    if canonical_image_id(manifest["sandbox"]["image_id"]) != manifest["sandbox"]["image_id"]:
        raise ValueError("Prepared image identity is not canonical")
    required = {"protocol.json", "workspace/reference.jpg", "runtime-input/runtime.json", "runtime-input/reference.jpg"}
    metadata_record = manifest.get("model_metadata")
    if metadata_record is not None:
        if metadata_record.get("file") != "runtime-input/model-metadata.json":
            raise ValueError("Prepared model metadata file differs")
        required.add(metadata_record["file"])
    elif (trial / "runtime-input/model-metadata.json").exists():
        raise ValueError("Unmanifested model metadata file")
    if set(manifest["file_hashes"]) != required:
        raise ValueError("Prepared file manifest differs")
    for relative, expected in manifest["file_hashes"].items():
        if candidate.sha256(candidate.inside(trial, relative)) != expected:
            raise ValueError("Prepared input/config changed: " + relative)
    protocol = candidate.read_json(trial / "protocol.json")
    runtime = candidate.read_json(trial / "runtime-input/runtime.json")
    if manifest["protocol_sha256"] != candidate.sha256(trial / "protocol.json"):
        raise ValueError("Prepared protocol changed")
    if (runtime["model_id"] != manifest["model_id"] or runtime["api_model_id"] != manifest["sandbox"]["api_model_id"]
            or runtime["prompt_text"] != protocol["prompt_text"] or runtime["prompt_text"] != manifest["input"]["prompt_text"]
            or hashlib.sha256(runtime["prompt_text"].encode()).hexdigest() != manifest["input"]["prompt_sent_utf8_sha256"]
            or runtime["reference_sha256"] != manifest["input"]["reference_sha256"]
            or candidate.sha256(trial / "runtime-input/reference.jpg") != runtime["reference_sha256"]
            or runtime["api_base_url"] != "http://127.0.0.1:18080" + urlsplit(manifest["sandbox"]["api_base_url"]).path):
        raise ValueError("Prepared model or input differs")
    api_base(manifest["sandbox"]["api_base_url"])
    if metadata_record is not None:
        metadata = validate_model_metadata(candidate.read_json(trial / metadata_record["file"]), manifest["model_id"],
                                           manifest["sandbox"]["api_model_id"], manifest["sandbox"]["api_base_url"])
        if any(metadata_record.get(key) != metadata[key] for key in ("source_url", "source_sha256")):
            raise ValueError("Prepared model metadata provenance differs")
    return manifest, protocol, runtime


def sanitized_inspect(record):
    config = record.get("Config", {})
    host = record.get("HostConfig", {})
    return {"Id": record.get("Id"), "Image": record.get("Image"), "State": record.get("State"),
            "Config": {"User": config.get("User"), "Image": config.get("Image")},
            "HostConfig": {key: host.get(key) for key in ("NetworkMode", "ReadonlyRootfs", "Privileged", "CapAdd", "CapDrop", "SecurityOpt", "PortBindings", "PidMode", "IpcMode")},
            "Mounts": [{key: mount.get(key) for key in ("Type", "Name", "Destination", "RW")} for mount in record.get("Mounts", [])]}


def validate_candidate(record, volumes):
    host = record["HostConfig"]
    if (host.get("NetworkMode") != "none" or not host.get("ReadonlyRootfs") or host.get("Privileged")
            or host.get("CapAdd") or host.get("PortBindings") or host.get("PidMode") == "host"
            or host.get("IpcMode") == "host" or record["Config"].get("User") != "10000:10000"
            or not any("no-new-privileges" in value for value in host.get("SecurityOpt", []))):
        raise ValueError("Container isolation settings differ from required policy")
    capdrop = {str(value).upper().removeprefix("CAP_") for value in host.get("CapDrop", [])}
    if "ALL" not in capdrop and not PODMAN_DEFAULT_CAPS.issubset(capdrop):
        raise ValueError("Container capabilities must be dropped")
    if any(record.get(key) not in (None, []) for key in ("EffectiveCaps", "BoundingCaps", "PermittedCaps")):
        raise ValueError("Container inspect reports remaining capabilities")
    expected = {"/workspace": (volumes["work"], True), "/home/candidate": (volumes["home"], True), "/run/model-link": (volumes["channel"], False)}
    seen = set()
    for mount in record.get("Mounts", []):
        if mount.get("Type") == "tmpfs":
            if mount.get("Destination") not in {"/tmp", "/run"}:
                raise ValueError("Unexpected tmpfs")
            continue
        dest = mount.get("Destination")
        if mount.get("Type") != "volume" or dest not in expected or (mount.get("Name"), mount.get("RW")) != expected[dest]:
            raise ValueError("Unexpected container mount")
        seen.add(dest)
    if seen != set(expected):
        raise ValueError("Required private volume is missing")


def artifact_from_tar(data, filename):
    if len(data) > MAX_ARTIFACT + 1024 * 1024:
        raise ValueError("CAD archive exceeds byte limit")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        members = archive.getmembers()
        if len(members) != 1 or not members[0].isfile() or members[0].name not in {filename, "./" + filename} or not 0 < members[0].size <= MAX_ARTIFACT:
            raise ValueError("CAD output must be one bounded regular file, without links")
        return archive.extractfile(members[0]).read()


def collect_artifact(client, sandbox, volume, filename, target, owned_containers):
    code = """import io,os,stat,sys,tarfile
name=sys.argv[1]
if name not in ('racing-kart.FCStd','racing-kart.step'): raise ValueError('Unexpected export')
try: fd=os.open('/workspace/'+name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
except FileNotFoundError: sys.exit(3)
with os.fdopen(fd,'rb') as source:
 info=os.fstat(source.fileno())
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=134217728: raise ValueError('Unsafe artifact type or size')
 data=source.read(134217729)
 if len(data)!=info.st_size: raise ValueError('Artifact size changed')
 with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
  member=tarfile.TarInfo(name); member.size=len(data); archive.addfile(member,io.BytesIO(data))
"""
    argv = ["create", "--network", "none", "--http-proxy=false", "--no-hosts", "--read-only", "--user", "10000:10000", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "32", "--memory", "512m",
            "--mount", "type=volume,source=" + volume + ",target=/workspace,ro=true",
            "--entrypoint", "/usr/local/bin/python3", sandbox["image_id"], "-c", code, filename]
    helper_id = client.call(argv).stdout.decode().strip()
    owned_containers.append(helper_id)
    process = subprocess.Popen(client.prefix + ["start", "--attach", helper_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = bytearray()
    try:
        while chunk := process.stdout.read(65536):
            data.extend(chunk)
            if len(data) > MAX_ARTIFACT + 1024 * 1024:
                raise ValueError("CAD export exceeds byte limit")
        process.stderr.read()
        returncode = process.wait(timeout=30)
        if returncode == 3:
            return False
        if returncode:
            raise ValueError("Artifact export helper rejected output")
        raw = artifact_from_tar(bytes(data), filename)
        with target.open("xb") as output:
            output.write(raw)
        return True
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()


def run(args):
    trial = args.trial.resolve()
    manifest, _, _ = load_trial(trial)
    evidence = trial / "evidence"
    evidence.mkdir(exist_ok=True)
    with (evidence / "run.claim").open("x") as claim:
        claim.write(candidate.utc_now())
    sandbox = manifest["sandbox"]
    client = Podman(sandbox["connection"])
    key = "cad-" + uuid.uuid4().hex
    volumes = {name: key + "-" + name for name in ("work", "home", "channel")}
    created_volumes, containers, secrets = [], [], []
    candidate_id = gateway_id = None
    metrics = candidate.RunMetrics()
    meta = {"schema_version": 2, "status": "running", "started_utc": candidate.utc_now(), "model_id": manifest["model_id"],
            "sandbox": sandbox, "trial_sha256": candidate.sha256(trial / "trial.json"), "returncode": None,
            "credential_env_names": manifest["credential_env_names"], "cleanup_errors": [], "outputs": [],
            "measurement_scope": "generation event to OpenCode exit, including model waits, retries and MCP work; startup recorded separately"}
    started = time.monotonic()
    generation_start = None
    try:
        images = client.document(["image", "inspect", sandbox["image_id"]])
        if canonical_image_id(images[0]["Id"]) != sandbox["image_id"]:
            raise ValueError("Prepared immutable image is unavailable")
        for volume in volumes.values():
            client.call(["volume", "create", "--label", "cad.trial=" + key, volume])
            created_volumes.append(volume)
        common = ["--http-proxy=false", "--no-hosts", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "512", "--memory", "4g", "--cpus", "2", "--label", "cad.trial=" + key]
        init = ["run", "--rm", "--network", "none", "--user", "0:0", "--cap-add", "CHOWN", *common,
                "--entrypoint", "/usr/local/bin/python3"]
        for name, dest in (("work", "/workspace"), ("home", "/home/candidate"), ("channel", "/run/model-link")):
            init += ["--mount", "type=volume,source=" + volumes[name] + ",target=" + dest]
        client.call(init + [sandbox["image_id"], "-c", "import os; [os.chown(p,10000,10000) for p in ['/workspace','/home/candidate','/run/model-link']]"], timeout=120)
        secret_args = []
        if manifest["credential_env_names"]:
            name = manifest["credential_env_names"][0]
            value = os.environ.get(name)
            if not value or "\n" in value or "\r" in value:
                raise ValueError("Credential is absent or malformed")
            secret_id = client.call(["secret", "create", key + "-key", "-"], data=value.encode()).stdout.decode().strip()
            secrets.append(secret_id)
            secret_args = ["--secret", "source=" + secret_id + ",target=provider-key,uid=10000,gid=10000,mode=0400"]
        gateway = ["create", "--name", key + "-gateway", "--user", "10000:10000", *common, *secret_args,
                   "--mount", "type=volume,source=" + volumes["channel"] + ",target=/run/model-link",
                   "--entrypoint", "/usr/local/bin/python3", sandbox["image_id"], "/opt/runtime/gateway.py",
                   "--socket", "/run/model-link/api.sock", "--base-url", sandbox["api_base_url"], "--model", sandbox["api_model_id"]]
        if secret_args:
            gateway += ["--credential-file", "/run/secrets/provider-key"]
        gateway_id = client.call(gateway).stdout.decode().strip()
        containers.append(gateway_id)
        client.call(["start", gateway_id])
        for _ in range(100):
            if client.call(["exec", gateway_id, "/usr/local/bin/python3", "-c", "import socket; s=socket.socket(socket.AF_UNIX); s.connect('/run/model-link/api.sock'); s.close()"], check=False).returncode == 0:
                break
            if not client.document(["inspect", gateway_id])[0]["State"]["Running"]:
                raise RuntimeError("API gateway failed before readiness")
            time.sleep(.1)
        else:
            raise RuntimeError("API gateway readiness timeout")
        command = ["create", "--name", key + "-candidate", "--network", "none", "--user", "10000:10000", *common,
                   "--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777", "--tmpfs", "/run:rw,nosuid,nodev,mode=1777",
                   "--mount", "type=volume,source=" + volumes["work"] + ",target=/workspace",
                   "--mount", "type=volume,source=" + volumes["home"] + ",target=/home/candidate",
                   "--mount", "type=volume,source=" + volumes["channel"] + ",target=/run/model-link,ro=true",
                   "--workdir", "/workspace", sandbox["image_id"], "/usr/local/bin/python3", "/opt/runtime/candidate_entry.py"]
        candidate_id = client.call(command).stdout.decode().strip()
        containers.append(candidate_id)
        record = client.document(["inspect", candidate_id])[0]
        validate_candidate(record, volumes)
        candidate.write_json_new(evidence / "candidate-inspect-before.json", sanitized_inspect(record))
        client.call(["cp", str(trial / "runtime-input"), candidate_id + ":/workspace/.runtime-input"])
        events = queue.Queue()
        process = subprocess.Popen(client.prefix + ["start", "--attach", candidate_id], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=os.name != "nt")
        threads = [threading.Thread(target=candidate.stream_reader, args=(name, stream, events), daemon=True)
                   for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
        for thread in threads:
            thread.start()
        finished = set()
        attach_start = time.monotonic()
        with (evidence / "run.events.jsonl").open("xb") as stdout, (evidence / "stderr.log").open("xb") as stderr:
            while len(finished) < 2:
                now = time.monotonic()
                if ((generation_start is None and now - attach_start > 120)
                        or (generation_start is not None and now - generation_start > sandbox["limits"]["timeout_seconds"])):
                    meta["status"] = "timeout"
                    client.call(["kill", candidate_id], check=False)
                    candidate.terminate_tree(process)
                try:
                    name, line = events.get(timeout=.2)
                except queue.Empty:
                    if process.poll() is not None and not any(thread.is_alive() for thread in threads):
                        break
                    continue
                if line is None:
                    finished.add(name)
                    continue
                (stdout if name == "stdout" else stderr).write(line)
                if name == "stdout":
                    metrics.observe(line)
                    try:
                        if json.loads(line).get("type") == "sandbox_generation_start" and generation_start is None:
                            generation_start = time.monotonic()
                            meta["startup_seconds"] = round(generation_start - attach_start, 3)
                    except (ValueError, AttributeError):
                        pass
            meta["returncode"] = process.wait(timeout=30)
        client.call(["stop", "--time", "1", candidate_id], check=False)
        after = client.document(["inspect", candidate_id])[0]
        candidate.write_json_new(evidence / "candidate-inspect-after.json", sanitized_inspect(after))
        meta["candidate_stopped"] = not after["State"]["Running"]
        if not meta["candidate_stopped"]:
            raise RuntimeError("Candidate did not stop before artifact collection")
        meta["candidate_container_id"] = candidate_id
        meta["duration_seconds"] = round(time.monotonic() - generation_start, 3) if generation_start else None
        if meta["status"] == "running":
            meta["status"] = "completed" if meta["returncode"] == 0 and generation_start else "failed"
        for filename in ("racing-kart.FCStd", "racing-kart.step"):
            if collect_artifact(client, sandbox, volumes["work"], filename, trial / "workspace" / filename, containers):
                meta["outputs"].append(filename)
        missing = sorted({"racing-kart.FCStd", "racing-kart.step"} - set(meta["outputs"]))
        if missing:
            meta["missing_outputs"] = missing
            if meta["status"] == "completed":
                meta["status"] = "failed"
    except BaseException as error:
        meta["status"] = "runner_error"
        meta["runner_error"] = type(error).__name__ + ": " + str(error)
    finally:
        for container in reversed(containers):
            try:
                client.call(["stop", "--time", "1", container], check=False)
                if container == gateway_id:
                    log = client.call(["logs", container], check=False)
                    (evidence / "gateway.log").write_bytes(log.stdout + log.stderr)
                result = client.call(["rm", "--force", container], check=False)
                if result.returncode:
                    meta["cleanup_errors"].append("container " + container)
            except Exception as error:
                meta["cleanup_errors"].append("container cleanup: " + type(error).__name__)
        for secret in secrets:
            try:
                if client.call(["secret", "rm", secret], check=False).returncode:
                    meta["cleanup_errors"].append("secret cleanup failed")
            except Exception as error:
                meta["cleanup_errors"].append("secret cleanup: " + type(error).__name__)
        for volume in reversed(created_volumes):
            try:
                if client.call(["volume", "rm", volume], check=False).returncode:
                    meta["cleanup_errors"].append("volume " + volume)
            except Exception as error:
                meta["cleanup_errors"].append("volume cleanup: " + type(error).__name__)
        meta.update({"finished_utc": candidate.utc_now(), "wall_seconds": round(time.monotonic() - started, 3), "metrics": metrics.as_dict(),
                     "tool_failure_count": sum(error["type"] in {"tool_error", "tool_output_error"} for error in metrics.errors)})
        candidate.write_json_new(evidence / "run.json", meta)
    print(json.dumps({"status": meta["status"], "metadata": str(evidence / "run.json")}))
    return 0 if meta["status"] == "completed" and not meta["cleanup_errors"] else 1
