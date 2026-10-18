import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freecad_worker import file_record, inspect_document, png_record, stored_visibility, write_json
from gui_lease import GuiLease


def render_reference_view(request_path):
    import FreeCAD as App
    import FreeCADGui as Gui

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    source = Path("/job/workspace/source.FCStd")
    before = file_record(source)
    if before["sha256"] != request["source_sha256"]:
        raise ValueError("Source CAD hash mismatch")
    result = {"request_id": request["request_id"], "model": request["model"],
              "source_before": before, "freecad_version": list(App.Version()),
              "requested_quaternion_xyzw": request["quaternion_xyzw"], "images": {}}
    result["runtime_files_sha256"] = {name: file_record(Path(__file__).parent / name)["sha256"]
                                      for name in request["runtime_files_sha256"]}
    if result["runtime_files_sha256"] != request["runtime_files_sha256"]:
        raise ValueError("Runtime worker/helper source mismatch")
    with GuiLease("supplemental:" + request["request_id"], resource="freecad-local"):
        doc = None
        preferences = App.ParamGet("User parameter:BaseApp/Preferences/View")
        animation = preferences.GetBool("EnableAnimation", True)
        preferences.SetBool("EnableAnimation", False)
        try:
            doc = App.openDocument(str(source))
            App.setActiveDocument(doc.Name)
            view = Gui.activeDocument().activeView()
            if hasattr(view, "setAnimationEnabled"):
                view.setAnimationEnabled(False)
            view.setCameraType("Orthographic")
            for obj in doc.Objects:
                provider = getattr(obj, "ViewObject", None)
                if provider is not None and hasattr(provider, "listDisplayModes") and "Flat Lines" in provider.listDisplayModes():
                    provider.DisplayMode = "Flat Lines"
            result["render_selection"] = inspect_document(doc, stored_visibility(source))["render_selection"]
            quaternion = request["quaternion_xyzw"]
            view.setCameraOrientation(App.Rotation(*quaternion).Q)
            view.fitAll()
            Gui.updateGui()
            view.redraw()
            Gui.updateGui()
            actual = list(view.getCameraOrientation().Q)
            delta = min(max(abs(a - b) for a, b in zip(actual, quaternion)),
                        max(abs(a + b) for a, b in zip(actual, quaternion)))
            result.update(actual_quaternion_xyzw=actual, quaternion_max_delta=delta,
                          camera_type=view.getCameraType(), camera=view.getCamera())
            if delta > 1e-6 or view.getCameraType() != "Orthographic":
                raise ValueError("Camera did not match supplemental request")
            for name, dimensions in request["images"].items():
                path = Path("/job/renders") / (name + ".png")
                view.saveImage(str(path), *dimensions, "White")
                record = png_record(path)
                if [record["width"], record["height"]] != dimensions:
                    raise ValueError("Image dimensions mismatch")
                record["path"] = path.name
                result["images"][name] = record
            result["success"] = True
        finally:
            if doc is not None:
                App.closeDocument(doc.Name)
            preferences.SetBool("EnableAnimation", animation)
            result["source_after"] = file_record(source)
            result["source_unchanged"] = result["source_before"] == result["source_after"]
            result["success"] = result.get("success", False) and result["source_unchanged"]
            write_json(Path("/job/evidence/supplemental.json"), result)
    return result
