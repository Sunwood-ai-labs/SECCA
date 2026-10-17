import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xmlrpc.client


class RPCTransport(xmlrpc.client.Transport):
    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = 2
        return connection


def main():
    output = Path("/workspace/.runtime")
    output.mkdir(parents=True, exist_ok=True)
    children = []
    handles = []

    def stop(signum=None, frame=None):
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
        for process in reversed(children):
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))
    try:
        for name, command in (
            ("xvfb", ["Xvfb", ":99", "-screen", "0", "1440x1080x24", "-nolisten", "tcp", "-noreset"]),
            ("freecad", ["/usr/bin/freecad", "/opt/runtime/start_freecad.FCMacro"]),
        ):
            log = open(output / (name + ".log"), "wb")
            handles.append(log)
            children.append(subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT))
            if name == "xvfb":
                deadline = time.monotonic() + 15
                while not Path("/tmp/.X11-unix/X99").exists():
                    if children[-1].poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Xvfb did not become ready")
                    time.sleep(0.1)

        deadline = time.monotonic() + 90
        last_error = ""
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in children):
                raise RuntimeError("FreeCAD or Xvfb exited before RPC readiness")
            try:
                with xmlrpc.client.ServerProxy("http://127.0.0.1:9875", transport=RPCTransport(), allow_none=True) as rpc:
                    status = rpc.get_rpc_status()
                    if status.get("success") and status.get("rpc_server") == "running":
                        (output / "rpc-ready.json").write_text(json.dumps(status, indent=2))
                        break
            except (OSError, xmlrpc.client.Error) as error:
                last_error = str(error)
            time.sleep(0.25)
        else:
            raise RuntimeError("FreeCAD RPC readiness timed out: " + last_error)

        command = sys.argv[1:] or ["/bin/sh"]
        child = subprocess.Popen(command)
        children.append(child)
        while child.poll() is None:
            if any(process.poll() is not None for process in children[:-1]):
                raise RuntimeError("FreeCAD or Xvfb exited while command was running")
            time.sleep(0.2)
        return child.returncode
    except Exception as error:
        print(str(error), file=sys.stderr)
        for name in ("freecad.log", "xvfb.log"):
            log = output / name
            if log.exists():
                print(log.read_text(errors="replace")[-12000:], file=sys.stderr)
        return 1
    finally:
        stop()
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())

