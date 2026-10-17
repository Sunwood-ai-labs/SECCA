import hashlib
import json
import os
from pathlib import Path
import subprocess

CLIENT = ["/opt/freecad-mcp/.venv/bin/python3", "/opt/runtime/mcp_client.py"]
WORK = Path("/workspace")


def call(tool, arguments):
    result = subprocess.run(CLIENT + ["call", tool, "--arguments", json.dumps(arguments)], check=True, capture_output=True, text=True, timeout=90)
    return json.loads(result.stdout)


def main():
    tools = json.loads(subprocess.run(CLIENT + ["list"], check=True, capture_output=True, text=True, timeout=30).stdout)
    names = [tool["name"] for tool in tools["tools"]]
    assert "execute_code" in names and "get_rpc_status" in names
    code = """
import json
import FreeCAD as App
import FreeCADGui as Gui
import Part
import Import
doc = App.newDocument("SandboxSmoke")
obj = doc.addObject("PartDesign::Body", "Body")
feature = doc.addObject("PartDesign::AdditiveBox", "Box")
obj.addObject(feature)
feature.Length = 2
feature.Width = 3
feature.Height = 4
doc.recompute()
Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
Gui.updateGui()
doc.saveAs("/workspace/smoke.FCStd")
Import.export([obj], "/workspace/smoke.step")
Gui.activeDocument().activeView().saveImage("/workspace/smoke.png", 640, 480, "White")
with open("/workspace/smoke-geometry.json", "w") as stream:
    json.dump({"valid": obj.Shape.isValid(), "volume": obj.Shape.Volume, "solids": len(obj.Shape.Solids)}, stream)
"""
    response = call("execute_code", {"code": code, "include_screenshot": False})
    texts = [item.get("text", "") for item in response["content"] if item["type"] == "text"]
    assert any("Code executed successfully" in text for text in texts), texts
    geometry = json.loads((WORK / "smoke-geometry.json").read_text())
    assert geometry["valid"] and geometry["solids"] == 1 and abs(geometry["volume"] - 24) < 1e-8
    reopen = """
import json
import FreeCAD as App
import Import
native = App.openDocument("/workspace/smoke.FCStd")
assert native.getObject("Body").Shape.isValid()
assert abs(native.getObject("Body").Shape.Volume - 24) < 1e-8
App.closeDocument(native.Name)
step = App.newDocument("StepReopen")
Import.insert("/workspace/smoke.step", step.Name)
shapes = [obj.Shape for obj in step.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
assert shapes
assert all(shape.isValid() for shape in shapes)
assert abs(sum(shape.Volume for shape in shapes) - 24) < 1e-8
with open("/workspace/reopen.json", "w") as stream:
    json.dump({"native_valid": True, "step_valid": True, "step_volume": sum(shape.Volume for shape in shapes)}, stream)
"""
    result = call("execute_code_headless", {"code": reopen, "timeout": 60})
    assert (WORK / "reopen.json").is_file(), result
    files = {}
    for name in ["smoke.FCStd", "smoke.step", "smoke.png"]:
        payload = (WORK / name).read_bytes()
        assert len(payload) > 100, name
        files[name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    report = {
        "success": True,
        "uid": os.getuid(),
        "tools": names,
        "geometry": geometry,
        "reopen": json.loads((WORK / "reopen.json").read_text()),
        "runtime": json.loads((WORK / ".runtime/freecad.json").read_text()),
        "files": files,
        "opencode_version": subprocess.check_output(["opencode", "--version"], text=True).strip(),
        "model_inference_performed": False,
    }
    (WORK / "smoke-result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()

