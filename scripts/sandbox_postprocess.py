"""Run CAD inspection and rendering in a fresh offline Podman container."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
ASSETS = SCRIPTS.parent / "assets"
OUTPUTS = ("racing-kart.FCStd", "racing-kart.step")
TERMINAL = {"completed", "failed", "timeout", "runner_error", "interrupted",
            "timed_out", "error", "cancelled", "succeeded", "success"}
MAX_CAD_BYTES = 1024 ** 3
MAX_JSON_BYTES = 32 * 1024 ** 2
MAX_PNG_BYTES = 64 * 1024 ** 2
MAX_CAPTURE_BYTES = 32 * 1024 ** 2


@dataclass(frozen=True)
class CommandOutput:
    returncode: int
    stdout: bytes
    stderr: bytes
    stopped_reason: str | None = None


def bounded_capture(command, timeout, budget=MAX_CAPTURE_BYTES):
    if timeout <= 0 or budget <= 0:
        raise ValueError("Command timeout and output budget must be positive")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    lock = threading.Lock()
    limit_hit = threading.Event()
    read_failed = threading.Event()
    retained = 0

    def drain(name, stream):
        nonlocal retained
        try:
            while chunk := stream.read1(65536):
                with lock:
                    size = min(len(chunk), budget - retained)
                    buffers[name].extend(chunk[:size])
                    retained += size
                    if size < len(chunk):
                        limit_hit.set()
        except (OSError, ValueError):
            read_failed.set()
        finally:
            stream.close()

    readers = [threading.Thread(target=drain, args=(name, getattr(process, name)), daemon=True)
               for name in buffers]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    reason = None
    try:
        while process.poll() is None:
            if limit_hit.is_set() or read_failed.is_set():
                reason = "output_limit" if limit_hit.is_set() else "capture_error"
                break
            if time.monotonic() >= deadline:
                reason = "timeout"
                break
            limit_hit.wait(min(0.02, max(0, deadline - time.monotonic())))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=1)
        if any(reader.is_alive() for reader in readers):
            reason = reason or "capture_error"
    reason = reason or ("output_limit" if limit_hit.is_set() else None)
    reason = reason or ("capture_error" if read_failed.is_set() else None)
    with lock:
        return CommandOutput(process.returncode, bytes(buffers["stdout"]),
                             bytes(buffers["stderr"]), reason)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def regular_file(root, relative, limit=MAX_CAD_BYTES):
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink() or current.is_junction():
            raise ValueError("Linked artifact path refused: " + relative)
        current = current.parent
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("Artifact escapes trial: " + relative)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Artifact must be a regular unlinked file: " + relative)
    if not 0 < info.st_size <= limit:
        raise ValueError("Artifact is empty or exceeds its size limit: " + relative)
    return path


def source_records(root):
    return {name: {"path": "workspace/" + name, "exists": True,
                   "bytes": (path := regular_file(root, "workspace/" + name)).stat().st_size,
                   "sha256": digest(path)}
            for name in OUTPUTS}


@dataclass(frozen=True)
class PostprocessJob:
    root: Path
    operation: str
    request_id: str
    connection: str
    image_id: str
    protocol: dict
    spec: dict
    spec_path: Path
    manifest: dict
    sources: dict
    timeout: int

    @classmethod
    def load(cls, trial, operation, timeout=180):
        if operation not in {"inspect", "render"} or type(timeout) is not int or timeout <= 0:
            raise ValueError("Invalid postprocess operation or timeout")
        root = Path(trial).expanduser().resolve(strict=True)
        manifest = read_json(regular_file(root, "trial.json", MAX_JSON_BYTES))
        protocol_path = regular_file(root, "protocol.json", MAX_JSON_BYTES)
        protocol = read_json(protocol_path)
        canonical = read_json(ASSETS / "protocol.json")
        if (digest(protocol_path) != digest(ASSETS / "protocol.json")
                or manifest.get("protocol_id") != canonical["id"]
                or manifest.get("protocol_sha256") != digest(protocol_path)
                or protocol.get("outputs") != list(OUTPUTS)):
            raise ValueError("Trial must use the installed canonical protocol")
        run = read_json(regular_file(root, "evidence/run.json", MAX_JSON_BYTES))
        if run.get("status") not in TERMINAL or run.get("candidate_stopped") is not True:
            raise ValueError("Candidate run is not terminal; postprocessing refused")
        sandbox = manifest.get("sandbox", {})
        if sandbox.get("backend") != "podman-network-none-uds":
            raise ValueError("Postprocessing requires a Podman sandbox trial; host FreeCAD is forbidden")
        connection, image_id = sandbox.get("connection"), sandbox.get("image_id")
        if not isinstance(connection, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", connection):
            raise ValueError("Trial requires a named Podman connection")
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("Trial requires an immutable runtime image ID")
        spec_path = root / "render-spec.json"
        if spec_path.exists() or spec_path.is_symlink():
            spec_path = regular_file(root, "render-spec.json", MAX_JSON_BYTES)
        else:
            spec_path = ASSETS / "render-spec.json"
        if digest(spec_path) != protocol["render_spec_sha256"]:
            raise ValueError("Render specification differs from the fixed protocol")
        spec = read_json(spec_path)
        for view in [*spec["views"], spec["preview"]]:
            if not re.fullmatch(r"[a-z][a-z0-9_-]*\.png", view["filename"]):
                raise ValueError("Render filename is not a fixed PNG basename")
        return cls(root, operation, uuid.uuid4().hex, connection, image_id, protocol,
                   spec, spec_path, manifest, source_records(root), timeout)

    @property
    def result_name(self):
        return "validation.json" if self.operation == "inspect" else "render.json"

    def request(self):
        return {"schema_version": 1, "request_id": self.request_id,
                "operation": self.operation, "trial": "/job",
                "protocol": "/job/protocol.json", "render_spec": "/job/render-spec.json"}


def normalize_paths(value):
    if isinstance(value, dict):
        return {key: normalize_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_paths(item) for item in value]
    if isinstance(value, str) and value.startswith("/job/"):
        relative = PurePosixPath(value).relative_to("/job")
        if ".." in relative.parts:
            raise ValueError("Container evidence path escapes /job")
        return relative.as_posix()
    if value == "/job":
        return "."
    return value


def verify_container(info, image_id):
    config, host = info.get("Config", {}), info.get("HostConfig", {})
    actual_image = str(info.get("Image", "")).removeprefix("sha256:")
    if (actual_image != image_id.removeprefix("sha256:")
            or config.get("User") != "10000:10000"
            or host.get("NetworkMode") != "none"
            or host.get("ReadonlyRootfs") is not True
            or host.get("Privileged") is not False
            or host.get("CapAdd")
            or not any(str(item).split("=")[0] == "no-new-privileges"
                       for item in host.get("SecurityOpt", []))
            or any("unconfined" in str(item) for item in host.get("SecurityOpt", []))
            or host.get("PidMode") == "host" or host.get("IpcMode") == "host"
            or host.get("Devices") or host.get("PortBindings")
            or info.get("NetworkSettings", {}).get("Ports")
            or any(mount.get("Type") != "tmpfs" for mount in info.get("Mounts", []))):
        raise ValueError("Postprocess container isolation inspection failed")
    networks = info.get("NetworkSettings", {}).get("Networks", {})
    if networks and set(networks) != {"none"}:
        raise ValueError("Postprocess container has an external network")


class OfflineContainer:
    def __init__(self, job):
        self.job = job
        self.name = "cad-review-" + job.request_id
        self.container_id = None
        self.inspection = None
        self.runtime_isolation = None
        self.cleanup_error = None
        self.log = []

    def podman(self, *args, timeout=None, check=True):
        command = ["podman", "--connection", self.job.connection, *args]
        result = bounded_capture(command, timeout=timeout or self.job.timeout)
        self.log.append({"command": list(args[:2]), "returncode": result.returncode,
                         "stdout": result.stdout[-32768:].decode("utf-8", errors="replace"),
                         "stderr": result.stderr[-32768:].decode("utf-8", errors="replace"),
                         "capture_budget_bytes": MAX_CAPTURE_BYTES,
                         "captured_bytes": len(result.stdout) + len(result.stderr),
                         "stopped_reason": result.stopped_reason,
                         "raw_log_truncated": result.stopped_reason is not None,
                         "log_tails_truncated": len(result.stdout) > 32768 or len(result.stderr) > 32768})
        if result.stopped_reason is not None:
            raise RuntimeError("Podman postprocess stopped: " + result.stopped_reason +
                               "; raw log truncated; see command evidence")
        if check and result.returncode:
            raise RuntimeError("Podman postprocess failed: " + str(args[0]) + " " +
                               result.stderr.decode("utf-8", errors="replace")[-2000:])
        return result

    def __enter__(self):
        launcher = (["/opt/runtime/runtime_boot.py", "/usr/bin/python3", "-c",
                     "import time; time.sleep(86400)"]
                    if self.job.operation == "render"
                    else ["-c", "import time; time.sleep(86400)"])
        command = ["create", "--name", self.name, "--network", "none",
                   "--http-proxy=false", "--no-hosts",
                   "--user", "10000:10000", "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--pids-limit", "512",
                   "--memory", "4g", "--cpus", "2", "--ipc", "private",
                   "--tmpfs", "/job:rw,nosuid,nodev,size=1536m,mode=1777",
                   "--tmpfs", "/workspace:rw,nosuid,nodev,size=256m,mode=1777",
                   "--tmpfs", "/home/candidate:rw,nosuid,nodev,size=256m,mode=1777",
                   "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m,mode=1777",
                   "--entrypoint", "/usr/bin/python3", self.job.image_id, *launcher]
        try:
            response = self.podman(*command)
            identifier = response.stdout.decode("ascii").strip()
            if not re.fullmatch(r"[0-9a-f]{64}", identifier):
                raise RuntimeError("Podman did not return a container ID")
            self.container_id = identifier
            self.inspection = json.loads(self.podman("inspect", identifier).stdout)[0]
            verify_container(self.inspection, self.job.image_id)
            self.podman("start", identifier)
            isolation = self.exec("/usr/bin/python3", "-c", PROCESS_ISOLATION)
            self.runtime_isolation = json.loads(isolation.stdout)
            self.exec("/usr/bin/python3", "-c",
                      "from pathlib import Path; "
                      "[Path('/job/'+p).mkdir(parents=True,exist_ok=True) "
                      "for p in ['workspace','evidence','evidence/review','renders','runtime']]")
            if self.job.operation == "render":
                self.exec("/usr/bin/python3", "-c", GUI_READY)
            return self
        except BaseException:
            self.cleanup()
            raise

    def exec(self, *command):
        return self.podman("exec", self.container_id, *command)

    def upload(self, path, remote):
        self.podman("cp", str(path), self.container_id + ":" + remote)

    def download(self, remote, path, limit):
        self.podman("cp", self.container_id + ":" + remote, str(path))
        return regular_file(path.parent, path.name, limit)

    def cleanup(self):
        if self.container_id is not None:
            try:
                result = self.podman("rm", "--force", self.container_id, timeout=30, check=False)
                if result.returncode:
                    self.cleanup_error = "Failed to remove own postprocess container: " + self.container_id
                else:
                    self.container_id = None
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                self.cleanup_error = str(error)

    def __exit__(self, *_):
        self.cleanup()


GUI_READY = """
import time
from xmlrpc.client import ServerProxy
for attempt in range(120):
    try:
        result = ServerProxy('http://127.0.0.1:9875').get_rpc_status()
        if result:
            break
    except Exception:
        pass
    time.sleep(0.5)
else:
    raise RuntimeError('Private FreeCAD GUI RPC did not become ready')
"""

PROCESS_ISOLATION = """
import json
from pathlib import Path
values = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
record = {name: int(values[name].strip(), 16) for name in ('CapEff', 'CapPrm', 'CapBnd')}
record['NoNewPrivs'] = int(values['NoNewPrivs'].strip())
if any(record[name] != 0 for name in ('CapEff', 'CapPrm', 'CapBnd')) or record['NoNewPrivs'] != 1:
    raise RuntimeError('Container capabilities or no-new-privileges failed')
print(json.dumps(record))
"""

GUI_RENDER = r"""
from xmlrpc.client import ServerProxy
code = "import runpy\nresult = runpy.run_path('/job/runtime/freecad_worker.py')['render_saved']('/job/request.json')\nprint(result)\n"
result = ServerProxy('http://127.0.0.1:9875').execute_code(code)
if not isinstance(result, dict) or result.get('success') is not True:
    raise RuntimeError('Private FreeCAD GUI execution failed: ' + repr(result))
"""


def prepare_inputs(job, folder):
    for part in ("workspace", "evidence", "runtime"):
        (folder / part).mkdir()
    shutil.copyfile(job.root / "protocol.json", folder / "protocol.json")
    write_json(folder / "trial.json", {"protocol_id": job.manifest["protocol_id"],
                                     "protocol_sha256": job.manifest["protocol_sha256"]})
    shutil.copyfile(job.spec_path, folder / "render-spec.json")
    write_json(folder / "evidence/run.json", {"status": "completed"})
    write_json(folder / "request.json", job.request())
    for name in OUTPUTS:
        shutil.copyfile(regular_file(job.root, "workspace/" + name), folder / "workspace" / name)
        if digest(folder / "workspace" / name) != job.sources[name]["sha256"]:
            raise ValueError("CAD changed while copying input: " + name)
    for name in ("freecad_worker.py", "gui_lease.py"):
        shutil.copyfile(SCRIPTS / name, folder / "runtime" / name)
    (folder / "inspect.py").write_text(
        "import runpy\n"
        "result = runpy.run_path('/job/runtime/freecad_worker.py')['inspect_saved']('/job/request.json')\n"
        "print(result)\n", encoding="utf-8")
    for path in folder.rglob("*"):
        if path.is_file():
            path.chmod(0o644)
    return [path for path in folder.rglob("*") if path.is_file()]


def validate_result(job, result):
    if result.get("request_id") != job.request_id:
        raise ValueError("Postprocess result has a stale or absent request ID")
    if job.operation == "inspect":
        pairs = [(result.get(kind, {}).get(key), name)
                 for kind, name in (("native", OUTPUTS[0]), ("step", OUTPUTS[1]))
                 for key in ("file_before", "file_after")]
    else:
        pairs = [(result.get(key, {}).get(name), name)
                 for key in ("source_before", "source_after") for name in OUTPUTS]
    for record, name in pairs:
        if not isinstance(record, dict) or record != job.sources[name]:
            raise ValueError("Container CAD copy hash/bytes/path differs from host source: " + name)
    if job.operation == "render":
        if result.get("render_spec", {}).get("sha256") != job.protocol["render_spec_sha256"]:
            raise ValueError("Container rendered with a different specification")


def output_files(job, result):
    if job.operation != "render" or result.get("success") is not True:
        return []
    paths = []
    expected = {item["id"]: item for item in job.spec["views"]}
    expected["preview"] = job.spec["preview"]
    for view_id, spec in expected.items():
        record = result.get("images", {}).get(view_id, {})
        path = "renders/" + spec["filename"]
        if (record.get("path") != path
                or [record.get("width"), record.get("height")] != [spec["width"], spec["height"]]):
            raise ValueError("Rendered image differs from the fixed output specification")
        paths.append((path, record, MAX_PNG_BYTES))
    review = result.get("review_copy", {})
    if not re.fullmatch(r"evidence/review/review-[0-9a-f]{32}\.FCStd", review.get("path", "")):
        raise ValueError("Renderer review copy is not a fixed trial-relative artifact")
    if review.get("sha256") != job.sources[OUTPUTS[0]]["sha256"]:
        raise ValueError("Renderer review copy differs from the source CAD")
    paths.append((review["path"], review, MAX_CAD_BYTES))
    return paths


def run_postprocess(job):
    evidence = job.root / "evidence"
    if evidence.is_symlink() or evidence.is_junction():
        raise ValueError("Linked evidence directory refused")
    archive = evidence / "postprocess" / job.request_id
    archive.mkdir(parents=True, exist_ok=False)
    container = OfflineContainer(job)
    result = {"schema_version": 1, "request_id": job.request_id, "success": False,
              "status": "runner_error"}
    failure = None
    try:
        with tempfile.TemporaryDirectory(prefix="cad-postprocess-") as temporary:
            stage = Path(temporary)
            incoming = stage / "input"
            incoming.mkdir()
            inputs = prepare_inputs(job, incoming)
            with container:
                for path in inputs:
                    container.upload(path, "/job/" + path.relative_to(incoming).as_posix())
                if job.operation == "inspect":
                    execution = container.exec("/usr/bin/freecadcmd", "-c",
                                               "exec(open('/job/inspect.py').read())")
                else:
                    execution = container.exec("/usr/bin/python3", "-c", GUI_RENDER)
                raw = stage / job.result_name
                container.download("/job/evidence/" + job.result_name, raw, MAX_JSON_BYTES)
                shutil.copyfile(raw, archive / ("container-" + job.result_name))
                result = normalize_paths(read_json(raw))
                validate_result(job, result)
                for relative, record, limit in output_files(job, result):
                    copied = stage / Path(relative).name
                    container.download("/job/" + relative, copied, limit)
                    if digest(copied) != record.get("sha256") or copied.stat().st_size != record.get("bytes"):
                        raise ValueError("Downloaded artifact differs from container evidence")
                    target = job.root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.parent.resolve() != (job.root / Path(relative).parent).absolute() or target.is_symlink():
                        raise ValueError("Output target is linked")
                    shutil.copyfile(copied, target)
                result["postprocess_exit_code"] = execution.returncode
    except Exception as error:
        failure = error
        result.update(success=False, status="runner_error", exception=f"{type(error).__name__}: {error}")
    finally:
        if container.cleanup_error is not None:
            result.update(success=False, cleanup_error=container.cleanup_error)
            if failure is None:
                failure = RuntimeError(container.cleanup_error)
        try:
            unchanged = source_records(job.root) == job.sources
        except (OSError, ValueError):
            unchanged = False
        result["host_source_unchanged"] = unchanged
        if not unchanged:
            result["success"] = False
        result["sandbox"] = {"backend": "podman-offline-postprocess",
                             "connection": job.connection, "image_id": job.image_id,
                             "network": "none", "user": "10000:10000",
                             "api_channel": False, "bind_mounts": [],
                             "request_id": job.request_id,
                             "inspection": "evidence/postprocess/" + job.request_id + "/container-inspect.json"}
        if container.inspection is not None:
            write_json(archive / "container-inspect.json", container.inspection)
        if container.runtime_isolation is not None:
            write_json(archive / "process-isolation.json", container.runtime_isolation)
        write_json(archive / "commands.json", container.log)
        write_json(archive / job.result_name, result)
        target = evidence / job.result_name
        if target.is_symlink() or target.is_junction():
            raise ValueError("Linked evidence target refused")
        write_json(target, result)
    if failure is not None:
        raise RuntimeError("Offline postprocessing failed; see " + str(archive / job.result_name)) from failure
    return result

