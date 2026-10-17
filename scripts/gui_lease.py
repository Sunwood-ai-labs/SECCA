"""Serialize cooperating writers to one FreeCAD GUI."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import uuid


class GuiLease:
    def __init__(self, owner, resource="freecad-local"):
        self.owner = str(owner)
        self.resource = str(resource)
        key = hashlib.sha256(self.resource.encode("utf-8")).hexdigest()[:16]
        self.path = Path(tempfile.gettempdir()) / ("freecad-cad-benchmark-" + key + ".lock")
        self.token = uuid.uuid4().hex
        self.acquired = False

    def __enter__(self):
        record = {"owner": self.owner, "resource": self.resource, "pid": os.getpid(),
                  "token": self.token, "created_unix": time.time()}
        try:
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                existing = self.path.read_text(encoding="utf-8")
            except OSError:
                existing = "unreadable lock"
            raise RuntimeError("FreeCAD writer lease is busy: " + str(self.path) + " " + existing) from None
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            self.acquired = True
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.acquired:
            return False
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if current.get("token") != self.token:
                raise RuntimeError("FreeCAD writer lease ownership changed; lock retained")
            self.path.unlink()
        except (OSError, ValueError, RuntimeError):
            if exc_type is None:
                raise
        finally:
            self.acquired = False
        return False
