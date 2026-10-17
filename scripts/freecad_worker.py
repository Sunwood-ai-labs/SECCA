"""Read saved CAD and render a separate review copy in FreeCAD runtimes."""

import hashlib
import json
import math
from pathlib import Path
import traceback
import xml.etree.ElementTree as ET
import zipfile




def file_record(path):
    record = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        record["bytes"] = path.stat().st_size
        with path.open("rb") as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        record["sha256"] = digest.hexdigest()
    return record


def stored_visibility(path):
    visibility = {}
    with zipfile.ZipFile(path) as archive:
        if "GuiDocument.xml" not in archive.namelist():
            return visibility
        root = ET.fromstring(archive.read("GuiDocument.xml"))
    for provider in root.iter("ViewProvider"):
        for prop in provider.iter("Property"):
            if prop.get("name") == "Visibility":
                value = prop.find("Bool")
                if value is not None:
                    visibility[provider.get("name")] = value.get("value") in ("true", "1")
    return visibility


def bounds(box):
    values = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    if not all(math.isfinite(value) for value in values):
        return None
    return {"min": values[:3], "max": values[3:],
            "size": [box.XLength, box.YLength, box.ZLength]}


def combined_bounds(records):
    boxes = [record["shape"]["bounds_mm"] for record in records
             if record.get("shape", {}).get("bounds_mm")]
    if not boxes:
        return None
    low = [min(box["min"][axis] for box in boxes) for axis in range(3)]
    high = [max(box["max"][axis] for box in boxes) for axis in range(3)]
    return {"min": low, "max": high,
            "size": [high[axis] - low[axis] for axis in range(3)]}


def inspect_object(obj, visibility, assume_visible):
    record = {"name": obj.Name, "label": obj.Label, "type": obj.TypeId,
              "parents": [parent.Name for parent in obj.InList],
              "children": [child.Name for child in obj.OutList]}
    view = getattr(obj, "ViewObject", None)
    if view is not None and hasattr(view, "Visibility"):
        record.update(visible=bool(view.Visibility), visibility_source="ViewObject")
    elif obj.Name in visibility:
        record.update(visible=visibility[obj.Name], visibility_source="saved_GuiDocument.xml")
    elif "Visibility" in obj.PropertiesList:
        record.update(visible=bool(obj.Visibility), visibility_source="object_property")
    else:
        record.update(visible=True if assume_visible else None,
                      visibility_source="STEP_import_default" if assume_visible else "unavailable")
    if not hasattr(obj, "Shape"):
        return record
    try:
        shape = obj.Shape
        null = shape.isNull()
        record["shape"] = {"null": null}
        if null:
            return record
        world = shape.copy()
        if hasattr(obj, "getGlobalPlacement") and hasattr(obj, "Placement"):
            world.Placement = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).multiply(shape.Placement)
        record["shape"].update(valid=bool(shape.isValid()),
                               volume_mm3=float(shape.Volume), solids=len(shape.Solids),
                               faces=len(shape.Faces), bounds_mm=bounds(world.BoundBox))
        if not math.isfinite(record["shape"]["volume_mm3"]):
            record["shape"]["volume_mm3"] = None
            raise ValueError("Shape volume is not finite")
    except Exception:
        record["shape_exception"] = traceback.format_exc()
    return record


def render_records(doc, records):
    by_name = {record["name"]: record for record in records}
    selected = []
    excluded = []
    for obj in doc.Objects:
        record = by_name[obj.Name]
        reason = None
        if obj.TypeId in ("App::Part", "App::DocumentObjectGroup"):
            reason = "aggregate_container"
        elif obj.TypeId in ("App::Origin", "App::Line", "App::Plane", "App::Point"):
            reason = "origin_or_datum"
        elif obj.TypeId != "PartDesign::Body" and not obj.isDerivedFrom("Part::Feature"):
            reason = "not_physical_shape_object"
        elif "shape" not in record and "shape_exception" not in record:
            reason = "no_shape"
        elif record["visible"] is False:
            reason = "hidden"
        ancestors = list(obj.InList)
        seen = set()
        while ancestors and reason is None:
            parent = ancestors.pop()
            if parent.Name in seen:
                continue
            seen.add(parent.Name)
            if parent.TypeId == "PartDesign::Body" and obj in getattr(parent, "Group", []):
                reason = "represented_by_PartDesign_Body"
                break
            if parent.TypeId in ("App::Part", "App::DocumentObjectGroup", "PartDesign::Body"):
                if by_name.get(parent.Name, {}).get("visible") is False:
                    reason = "hidden_container"
                    break
                ancestors.extend(parent.InList)
        if reason:
            excluded.append({"name": obj.Name, "reason": reason})
        else:
            selected.append(record)
    return selected, excluded


def inspect_document(doc, visibility, assume_visible=False):
    records = [inspect_object(obj, visibility, assume_visible) for obj in doc.Objects]
    selected, excluded = render_records(doc, records)
    failures = []
    shape_records = [record for record in records if "shape" in record]
    for record in records:
        if record.get("shape_exception"):
            failures.append(record["name"] + ":shape_inspection_exception")
        elif record.get("shape", {}).get("valid") is False:
            failures.append(record["name"] + ":invalid_shape_in_document")
    if not selected:
        failures.append("no_render_shape_objects")
    for record in selected:
        shape = record.get("shape", {})
        if record.get("shape_exception"):
            failures.append(record["name"] + ":shape_exception")
        elif shape.get("null", True):
            failures.append(record["name"] + ":null_shape")
        elif not shape.get("valid", False):
            failures.append(record["name"] + ":invalid_shape")
        elif not shape.get("solids", 0) or shape.get("volume_mm3", 0) <= 0:
            failures.append(record["name"] + ":no_positive_volume_solid")
        elif shape.get("bounds_mm") is None:
            failures.append(record["name"] + ":nonfinite_bounds")
    if any(record["visible"] is None for record in selected):
        failures.append("render_visibility_unknown")
    return {"document_name": doc.Name, "object_count": len(records),
            "all_shape_object_counts": {"total": len(shape_records),
                                        "null": sum(record["shape"]["null"] for record in shape_records),
                                        "invalid": sum(record["shape"].get("valid") is False for record in shape_records),
                                        "inspection_exceptions": sum("shape_exception" in record for record in records)},
            "objects": records,
            "render_selection": {"names": [record["name"] for record in selected],
                                 "object_count": len(selected),
                                 "solid_count": sum(record.get("shape", {}).get("solids", 0) for record in selected),
                                 "bounds_mm": combined_bounds(selected),
                                 "excluded": excluded},
            "geometry_valid": not failures, "failures": failures}


def inspect_artifact(app, path, kind):
    result = {"file_before": file_record(path)}
    doc = None
    try:
        if not result["file_before"]["exists"] or not result["file_before"].get("bytes"):
            raise ValueError("Input file is missing or empty")
        if kind == "native":
            visibility = stored_visibility(path)
            doc = app.openDocument(str(path))
        else:
            import Import
            visibility = {}
            doc = app.newDocument("Independent_STEP_validation")
            Import.insert(str(path), doc.Name)
        result.update(inspect_document(doc, visibility, assume_visible=kind == "step"))
    except Exception:
        result.update(geometry_valid=False, exception=traceback.format_exc())
    finally:
        if doc is not None:
            app.closeDocument(doc.Name)
        result["file_after"] = file_record(path)
        result["source_unchanged"] = result["file_before"] == result["file_after"]
    return result


def compare(native, step):
    first = native.get("render_selection", {})
    second = step.get("render_selection", {})
    a, b = first.get("bounds_mm"), second.get("bounds_mm")
    result = {"bounds_tolerance_mm": 0.01,
              "native_render_solid_count": first.get("solid_count"),
              "step_import_solid_count": second.get("solid_count"),
              "step_import_render_object_count": second.get("object_count"),
              "solid_counts_equal": first.get("solid_count") == second.get("solid_count")
                                    if first and second else None,
              "bounds_match": None}
    if a and b:
        delta = [abs(a[side][axis] - b[side][axis]) for side in ("min", "max") for axis in range(3)]
        result.update(max_bounds_delta_mm=max(delta), bounds_match=max(delta) <= 0.01)
    return result



TERMINAL_STATUSES = {"completed", "failed", "timeout", "runner_error", "timed_out", "interrupted", "error", "cancelled", "succeeded", "success"}


def load_request(request):
    if isinstance(request, (str, Path)):
        request = json.loads(Path(request).read_text(encoding="utf-8"))
    root = Path(request["trial"]).resolve()
    if not (root / "trial.json").is_file():
        raise ValueError("Missing trial.json")
    manifest = json.loads((root / "trial.json").read_text(encoding="utf-8"))
    protocol_path = Path(request["protocol"])
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["id"] != manifest["protocol_id"] or file_record(protocol_path)["sha256"] != manifest["protocol_sha256"]:
        raise ValueError("Trial protocol mismatch")
    require_terminal(root)
    return request, root


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def inspect_saved(request):
    request, root = load_request(request)
    result = {"schema_version": 1, "request_id": request["request_id"], "scope": "Independent disk reopen and STEP import; no recompute, save, grading, or structural safety assessment.",
              "selection_note": "Visible physical Part::Feature and Body shapes; exclude containers, datum objects and Body internals. STEP object count is an import representation, not a manufactured part count.",
              "success": False}
    try:
        import FreeCAD as App
        result["freecad_version"] = list(App.Version())
        result["native"] = inspect_artifact(App, root / "workspace" / "racing-kart.FCStd", "native")
        result["step"] = inspect_artifact(App, root / "workspace" / "racing-kart.step", "step")
        result["comparison"] = compare(result["native"], result["step"])
        result["success"] = all(result[kind]["geometry_valid"] and result[kind]["source_unchanged"] for kind in ("native", "step"))
        result["success"] = result["success"] and result["comparison"]["bounds_match"] is True and result["comparison"]["solid_counts_equal"] is True
    except Exception:
        result["exception"] = traceback.format_exc()
    write_json(root / "evidence" / "validation.json", result)
    return result


def require_terminal(root):
    run = json.loads((root / "evidence" / "run.json").read_text(encoding="utf-8"))
    if run.get("status") not in TERMINAL_STATUSES:
        raise ValueError("Candidate run is not terminal; artifact review refused")


def png_record(path):
    import struct
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Renderer did not write a PNG: " + str(path))
    width, height = struct.unpack(">II", header[16:24])
    return dict(file_record(path), width=width, height=height)


def render_saved(request):
    import shutil
    import sys
    import uuid
    request, root = load_request(request)
    require_terminal(root)
    scripts = str(Path(__file__).resolve().parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from gui_lease import GuiLease
    import FreeCAD as App
    import FreeCADGui as Gui
    spec_path = Path(request["render_spec"])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    protocol_path = Path(request["protocol"])
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if file_record(spec_path)["sha256"] != protocol["render_spec_sha256"]:
        raise ValueError("Render specification hash differs from protocol")
    sources = {name: root / "workspace" / name for name in protocol["outputs"]}
    before = {name: file_record(path) for name, path in sources.items()}
    if not all(record.get("bytes", 0) > 0 for record in before.values()):
        raise ValueError("CAD source missing or empty")
    result = {"schema_version": 1, "request_id": request["request_id"], "success": False, "source_before": before,
              "render_spec": file_record(spec_path), "freecad_version": list(App.Version()), "images": {},
              "presentation": {"background": "White", "projection": "Orthographic", "animation_enabled": False, "display_mode": "Flat Lines", "preserve_model_colors": True, "preserve_model_visibility": True}}
    with GuiLease("render:" + str(root), resource="freecad-local"):
        require_terminal(root)
        review = root / "evidence" / "review" / ("review-" + uuid.uuid4().hex + ".FCStd")
        review.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sources["racing-kart.FCStd"], review)
        result["review_copy"] = file_record(review)
        previous = App.ActiveDocument
        doc = None
        preferences = App.ParamGet("User parameter:BaseApp/Preferences/View")
        animation = preferences.GetBool("EnableAnimation", True)
        preferences.SetBool("EnableAnimation", False)
        try:
            doc = App.openDocument(str(review))
            App.setActiveDocument(doc.Name)
            view = Gui.activeDocument().activeView()
            if hasattr(view, "setAnimationEnabled"):
                view.setAnimationEnabled(False)
            view.setCameraType("Orthographic")
            changed = []
            for obj in doc.Objects:
                provider = getattr(obj, "ViewObject", None)
                if provider is not None and hasattr(provider, "listDisplayModes") and "Flat Lines" in provider.listDisplayModes():
                    provider.DisplayMode = "Flat Lines"
                    changed.append(obj.Name)
            result["display_mode_objects"] = changed
            render_dir = root / "renders"
            render_dir.mkdir(parents=True, exist_ok=True)
            views = list(spec["views"])
            preview_source = next(item for item in views if item["id"] == spec["preview"]["from_view"])
            views.append(dict(spec["preview"], id="preview", quaternion_xyzw=preview_source["quaternion_xyzw"]))
            for item in views:
                quaternion = item["quaternion_xyzw"]
                view.setCameraOrientation(App.Rotation(*quaternion).Q)
                view.fitAll()
                Gui.updateGui()
                view.redraw()
                Gui.updateGui()
                path = render_dir / item["filename"]
                view.saveImage(str(path), item["width"], item["height"], "White")
                record = png_record(path)
                record.update(requested_quaternion_xyzw=quaternion,
                              actual_quaternion_xyzw=list(view.getCameraOrientation().Q),
                              camera_type=view.getCameraType())
                actual = record["actual_quaternion_xyzw"]
                orientation_delta = min(max(abs(a - b) for a, b in zip(actual, quaternion)),
                                        max(abs(a + b) for a, b in zip(actual, quaternion)))
                record["quaternion_max_delta"] = orientation_delta
                if orientation_delta > 1e-6 or record["camera_type"] != "Orthographic":
                    raise ValueError("Actual camera differs from render specification")
                if [record["width"], record["height"]] != [item["width"], item["height"]]:
                    raise ValueError("Rendered image dimensions differ from render specification")
                record["path"] = path.relative_to(root).as_posix()
                result["images"][item["id"]] = record
            result["success"] = True
        except Exception:
            result["exception"] = traceback.format_exc()
        finally:
            if doc is not None:
                App.closeDocument(doc.Name)
            if previous is not None and previous.Name in App.listDocuments():
                App.setActiveDocument(previous.Name)
            preferences.SetBool("EnableAnimation", animation)
            result["source_after"] = {name: file_record(path) for name, path in sources.items()}
            result["source_unchanged"] = before == result["source_after"]
            result["review_copy_after"] = file_record(review)
            result["review_copy_unchanged"] = result["review_copy"] == result["review_copy_after"]
            result["success"] = result["success"] and result["source_unchanged"] and result["review_copy_unchanged"]
            write_json(root / "evidence" / "render.json", result)
    return result
