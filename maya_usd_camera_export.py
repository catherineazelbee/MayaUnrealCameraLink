"""
Export a Maya camera to .usdc with baked animation.
Tested in Maya 2025.3 (Python 3).

USAGE
-----
1) Paste this file into:  maya_usd_camera_export.py
2) In Maya, open Script Editor (Python), paste:
       import maya_usd_camera_export as m
       m.exportCameraUSDC_ui()
   …or just run this file directly to auto-open the UI.

NOTES
-----
• Aperture/offset attributes in Maya are in INCHES. USD expects MILLIMETERS.
  We convert only those optical attributes to mm (industry standard in USD).
• We do not set stage up-axis or linear units; Unreal’s USD importer handles
  its own axis/unit interpretation. This matches your “manual import” path.
• TimeCodesPerSecond is set from Maya’s current time unit to keep frames aligned
  1:1 with your timeline (e.g., 24fps, 30fps, etc.).
"""

import os
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om
from pxr import Usd, UsdGeom, Sdf, Gf

# -------------------------
# Utilities
# -------------------------

<<<<<<< Updated upstream
# TODO: this is wrong I think
def _inches_to_mm(x):  # Maya film gate units are inches
=======
def _inches_to_mm(x):
    """
    Convert inches to millimeters.

    Maya camera film gate + offsets are authored in inches.
    USD (UsdGeom.Camera) expects millimeters for aperture-related fields.
    """
>>>>>>> Stashed changes
    return float(x) * 25.4

def _maya_fps():
    """
    Return the numeric FPS for the current Maya time unit.

    Maya time unit can be symbolic (e.g. "film", "pal", "ntsc", "show", etc.)
    or explicit strings like "23.976fps". We normalize both to float FPS.

    Returns
    -------
    float
        Frames per second (e.g. 24.0, 30.0, 23.976).
    """
    unit = cmds.currentUnit(q=True, time=True)
    table = {
        "film": 24.0, "pal": 25.0, "ntsc": 30.0, "show": 48.0,
        "palf": 50.0, "ntscf": 60.0,
        "23.976fps": 23.976, "29.97fps": 29.97, "47.952fps": 47.952, "59.94fps": 59.94
    }
    if unit in table:
        return table[unit]
    if unit.endswith("fps"):
        try:
            return float(unit[:-3])
        except Exception:
            pass
    return 24.0

def _resolve_camera(name):
    """
    Resolve a camera selection to (transform, shape) long DAG paths.

    Parameters
    ----------
    name : str
        Camera transform OR camera shape path/name.

    Returns
    -------
    (str, str)
        Tuple of (camera_transform_long_path, camera_shape_long_path)

    Raises
    ------
    RuntimeError
        If the node doesn't exist or isn't a valid camera selection.
    """
    if not name or not cmds.objExists(name):
        raise RuntimeError("Camera does not exist: %s" % name)
    if cmds.nodeType(name) == "camera":
        shape = name
        parents = cmds.listRelatives(shape, p=True, fullPath=True) or []
        if not parents:
            raise RuntimeError("Camera shape has no parent transform: %s" % shape)
        xform = parents[0]
    else:
        shapes = cmds.listRelatives(name, s=True, type="camera", fullPath=True) or []
        if not shapes:
            raise RuntimeError("Selected node is not a camera transform: %s" % name)
        xform = cmds.ls(name, long=True)[0]
        shape = shapes[0]
    return xform, shape

def _cam_attrs_mm(shape):
    """Collect camera optical attributes; apertures/offsets in mm."""
    ga = cmds.getAttr
    return {
        "focalLength": float(ga(shape + ".focalLength")),
        "near": float(ga(shape + ".nearClipPlane")),
        "far": float(ga(shape + ".farClipPlane")),
        "hA": _inches_to_mm(ga(shape + ".horizontalFilmAperture")),
        "vA": _inches_to_mm(ga(shape + ".verticalFilmAperture")),
        "hOff": _inches_to_mm(ga(shape + ".horizontalFilmOffset")),
        "vOff": _inches_to_mm(ga(shape + ".verticalFilmOffset")),
    }

# -------------------------
# Core export 
# -------------------------

def export_camera_usdc(path, start, end, step, camera):
    """
    Bake the selected Maya camera into a binary .usdc file.

    We author the camera's world transform verbatim per frame (no flips or conversions),
    and set optical attributes (aperture/offsets in mm). This mirrors the behavior you
    expect when manually importing into Unreal via the USD importer.

    Parameters
    ----------
    path : str
        Output file path. Must end with ".usdc".
    start : int
        Start frame (inclusive).
    end : int
        End frame (inclusive).
    step : int
        Frame step (e.g., 1 to key every frame, 2 to key every other frame).
    camera : str
        Camera transform or shape to export.

    Returns
    -------
    str
        The output .usdc path.

    Raises
    ------
    RuntimeError
        If validation fails (bad frame range, missing camera, wrong extension, etc.).
    """
    if not path or not path.lower().endswith(".usdc"):
        raise RuntimeError("Export file must end with .usdc")

    # Ensure directory exists
    out_dir = os.path.dirname(os.path.abspath(path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if end < start:
        raise RuntimeError("End frame must be >= start frame.")
    if step <= 0:
        raise RuntimeError("Step must be > 0.")

    cam_x, cam_s = _resolve_camera(camera)
    fps = _maya_fps()

    # Create USD stage (leave up-axis and units untouched)
    stage = Usd.Stage.CreateNew(path)
    stage.SetTimeCodesPerSecond(fps)
    stage.SetStartTimeCode(start)
    stage.SetEndTimeCode(end)

    # Name prim after the Maya transform
    cam_name = os.path.basename(cam_x).split("|")[-1]
    usd_cam = UsdGeom.Camera.Define(stage, Sdf.Path(f"/{cam_name}"))
    prim = usd_cam.GetPrim()

    # Static optical params
    attrs0 = _cam_attrs_mm(cam_s)
    usd_cam.CreateHorizontalApertureAttr().Set(attrs0["hA"])
    usd_cam.CreateVerticalApertureAttr().Set(attrs0["vA"])
    usd_cam.CreateHorizontalApertureOffsetAttr().Set(attrs0["hOff"])
    usd_cam.CreateVerticalApertureOffsetAttr().Set(attrs0["vOff"])

    # Transform op
    xformable = UsdGeom.Xformable(prim)
    xop = xformable.AddTransformOp()

    # Bake per-frame: worldMatrix verbatim, plus focal length & clipping
    current = cmds.currentTime(q=True)
    try:
        num_steps = int(math.floor(((end - start) / step) + 0.5)) + 1
        for i in range(num_steps):
            t = start + i * step
            cmds.currentTime(t, e=True)

            # VERBATIM world matrix from Maya
            m = cmds.xform(cam_x, q=True, ws=True, m=True)  # 16 row-major
            M = Gf.Matrix4d(*m)
            xop.Set(M, Usd.TimeCode(t))

            at = _cam_attrs_mm(cam_s)
            usd_cam.CreateFocalLengthAttr().Set(at["focalLength"], Usd.TimeCode(t))
            usd_cam.CreateClippingRangeAttr().Set(Gf.Vec2f(at["near"], at["far"]), Usd.TimeCode(t))
    finally:
        try:
            cmds.currentTime(current, e=True)
        except Exception:
            pass

    stage.GetRootLayer().Save()
    om.MGlobal.displayInfo("Camera exported to: %s" % path)
    return path

# -------------------------
# UI 
# -------------------------

def exportCameraUSDC_ui():
    """Open a simple, resizable window to export a camera to USDC."""
    win = "ExportCamUSDC_UI"
    if cmds.window(win, ex=True):
        cmds.deleteUI(win)

    cmds.window(
        win,
        title="Export Camera to USDC",
        sizeable=True,
        resizeToFitChildren=False,
        widthHeight=(500, 300),
    )
    main = cmds.columnLayout(adj=True, rs=10, cat=("both", 10))

    # Camera selection
    cmds.frameLayout(label="Camera", collapsable=False, marginHeight=8, marginWidth=8)
    cmds.rowLayout(nc=2, adj=2, cw2=(120, 340))
    cmds.text(l="Select Camera:")
    cam_menu = cmds.optionMenu(w=340)
    cams = cmds.ls(type="camera") or []
    cam_trans = [cmds.listRelatives(c, p=True, f=True)[0] for c in cams]
    for c in cam_trans:
        cmds.menuItem(l=c)
    # Preselect current camera if selected
    preselect = None
    sel = cmds.ls(sl=True) or []
    if sel:
        s0 = sel[0]
        if cmds.nodeType(s0) == "camera":
            parent = cmds.listRelatives(s0, p=True, f=True) or []
            if parent:
                preselect = parent[0]
        else:
            if cmds.listRelatives(s0, s=True, type="camera"):
                preselect = cmds.ls(s0, long=True)[0]
    if preselect and preselect in cam_trans:
        cmds.optionMenu(cam_menu, e=True, v=preselect)
    cmds.setParent(".."); cmds.setParent("..")

    # File selection
    cmds.frameLayout(label="Export File", collapsable=False, marginHeight=8, marginWidth=8)
    cmds.rowLayout(nc=3, adj=2, cw3=(120, 300, 80))
    cmds.text(l="Save As (.usdc):")
    default_path = os.path.join(cmds.workspace(q=True, rd=True), "camera.usdc")
    file_field = cmds.textField(tx=default_path)
    def _browse(*_):
        sel = cmds.fileDialog2(fileMode=0, caption="Choose .usdc", fileFilter="USDC Files (*.usdc)")
        if sel:
            path = sel[0]
            if not path.lower().endswith(".usdc"):
                path += ".usdc"
            cmds.textField(file_field, e=True, tx=path)
    cmds.button(l="Browse…", c=_browse)
    cmds.setParent(".."); cmds.setParent("..")

    # Frame range
    cmds.frameLayout(label="Frame Range", collapsable=False, marginHeight=8, marginWidth=8)
    minf = cmds.playbackOptions(q=True, min=True)
    maxf = cmds.playbackOptions(q=True, max=True)
    cmds.rowLayout(nc=6, adj=2, cw6=(60, 120, 50, 120, 50, 120))
    cmds.text(l="Start:"); start_f = cmds.intField(v=int(minf))
    cmds.text(l="End:");   end_f   = cmds.intField(v=int(maxf))
    cmds.text(l="Step:");  step_f  = cmds.intField(v=1)
    cmds.setParent(".."); cmds.setParent("..")

    # Export button
    cmds.separator(h=10, style="in")
    def _do_export(*_):
        try:
            cam = cmds.optionMenu(cam_menu, q=True, v=True)
            path = cmds.textField(file_field, q=True, tx=True)
            if not path.lower().endswith(".usdc"):
                path += ".usdc"
            s  = cmds.intField(start_f, q=True, v=True)
            e  = cmds.intField(end_f, q=True, v=True)
            st = cmds.intField(step_f, q=True, v=True)
            export_camera_usdc(path, s, e, st, cam)
            cmds.inViewMessage(amg='Camera <hl>exported</hl> to: <hl>%s</hl>' % path,
                               pos='topCenter', fade=True, bkc=0x303030)
        except Exception as ex:
            om.MGlobal.displayError(str(ex))
    cmds.button(l="Export Camera to USDC", h=44, bgc=(0.35, 0.65, 0.35), c=_do_export)

    cmds.showWindow(win)

# Launch UI
exportCameraUSDC_ui()
