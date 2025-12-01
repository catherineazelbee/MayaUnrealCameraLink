"""
Export a Maya camera to .usda with baked animation.
Tested in Maya 2025.3 (Python 3).

USAGE
-----
1) Place this file in your Maya scripts folder
2) In Maya Script Editor (Python):
       import maya_usd_camera_export
       maya_usd_camera_export.export_camera_ui()
"""

import os
import maya.cmds as cmds
import maya.api.OpenMaya as om
from pxr import Usd, UsdGeom, Sdf, Gf


# =============================================================================
# Utilities
# =============================================================================

def _inches_to_mm(val):
    """Convert inches to millimeters (USD expects mm for aperture)."""
    return float(val) * 25.4


def _get_maya_fps():
    """Get Maya's current FPS as a float."""
    time_unit = cmds.currentUnit(query=True, time=True)
    
    fps_map = {
        "game": 15.0,
        "film": 24.0,
        "pal": 25.0,
        "ntsc": 30.0,
        "show": 48.0,
        "palf": 50.0,
        "ntscf": 60.0,
        "23.976fps": 23.976,
        "29.97fps": 29.97,
        "29.97df": 29.97,
        "47.952fps": 47.952,
        "59.94fps": 59.94,
    }
    
    if time_unit in fps_map:
        return fps_map[time_unit]
    
    # Try parsing "XXfps" format
    if time_unit.endswith("fps"):
        try:
            return float(time_unit[:-3])
        except ValueError:
            pass
    
    return 24.0  # Default


def _resolve_camera(name):
    """
    Resolve camera name to (transform_path, shape_path).
    
    Args:
        name: Camera transform or shape name
        
    Returns:
        Tuple of (transform_long_path, shape_long_path)
    """
    if not name or not cmds.objExists(name):
        raise RuntimeError(f"Camera does not exist: {name}")
    
    node_type = cmds.nodeType(name)
    
    if node_type == "camera":
        # User selected the shape
        shape = cmds.ls(name, long=True)[0]
        parents = cmds.listRelatives(shape, parent=True, fullPath=True)
        if not parents:
            raise RuntimeError(f"Camera shape has no parent: {shape}")
        xform = parents[0]
    else:
        # User selected the transform
        xform = cmds.ls(name, long=True)[0]
        shapes = cmds.listRelatives(xform, shapes=True, type="camera", fullPath=True)
        if not shapes:
            raise RuntimeError(f"No camera shape found under: {name}")
        shape = shapes[0]
    
    return xform, shape


def _sanitize_name(name):
    """Clean up name for USD prim path."""
    # Get short name without namespace or path
    clean = name.split("|")[-1].split(":")[-1]
    # Replace invalid characters
    for char in '<>:"/\\|?*. ':
        clean = clean.replace(char, "_")
    return clean


def _is_animated(obj):
    """Check if object has animation (keyframes or constraints)."""
    # Check for keyframes on transform attributes
    animatable_attrs = [
        "translateX", "translateY", "translateZ",
        "rotateX", "rotateY", "rotateZ",
        "scaleX", "scaleY", "scaleZ"
    ]
    
    for attr in animatable_attrs:
        full_attr = f"{obj}.{attr}"
        if cmds.objExists(full_attr):
            # Check for animation curves
            connections = cmds.listConnections(full_attr, type="animCurve") or []
            if connections:
                return True
            # Check for constraints
            constraints = cmds.listConnections(full_attr, type="constraint") or []
            if constraints:
                return True
    
    return False


def _is_camera_animated(shape):
    """Check if camera optical attributes are animated."""
    camera_attrs = ["focalLength", "horizontalFilmAperture", "verticalFilmAperture",
                    "horizontalFilmOffset", "verticalFilmOffset", 
                    "nearClipPlane", "farClipPlane"]
    
    for attr in camera_attrs:
        full_attr = f"{shape}.{attr}"
        if cmds.objExists(full_attr):
            connections = cmds.listConnections(full_attr, type="animCurve") or []
            if connections:
                return True
    
    return False


# =============================================================================
# Core Export
# =============================================================================

def export_camera_usda(file_path, start_frame, end_frame, step, camera):
    """
    Export Maya camera to USD with baked animation.
    
    Args:
        file_path: Output .usda file path
        start_frame: Start frame
        end_frame: End frame  
        step: Frame step (usually 1)
        camera: Camera transform or shape name
        
    Returns:
        Output file path
    """
    # Validate extension
    if not file_path.lower().endswith((".usda", ".usd")):
        raise RuntimeError("Export file must have .usda or .usd extension")
    
    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(file_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    # Validate frame range
    if end_frame < start_frame:
        raise RuntimeError("End frame must be >= start frame")
    if step <= 0:
        raise RuntimeError("Step must be > 0")
    
    # Resolve camera
    cam_xform, cam_shape = _resolve_camera(camera)
    cam_name = _sanitize_name(cam_xform)
    
    fps = _get_maya_fps()
    
    print(f"Exporting camera: {cam_xform}")
    print(f"  Frame range: {start_frame} - {end_frame} (step {step})")
    print(f"  FPS: {fps}")
    
    # Check if animated
    xform_animated = _is_animated(cam_xform)
    optics_animated = _is_camera_animated(cam_shape)
    
    print(f"  Transform animated: {xform_animated}")
    print(f"  Optics animated: {optics_animated}")
    
    # Remove existing file
    abs_path = os.path.abspath(file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
    
    # Create USD stage
    stage = Usd.Stage.CreateNew(abs_path)
    
    # Set stage metadata
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)  # Maya uses cm
    stage.SetTimeCodesPerSecond(fps)
    stage.SetStartTimeCode(start_frame)
    stage.SetEndTimeCode(end_frame)
    
    # Create camera prim at root level
    prim_path = f"/{cam_name}"
    usd_camera = UsdGeom.Camera.Define(stage, prim_path)
    camera_prim = usd_camera.GetPrim()
    
    # Set as default prim
    stage.SetDefaultPrim(camera_prim)
    
    # Get xformable interface for transform ops
    xformable = UsdGeom.Xformable(usd_camera)
    xformable.ClearXformOpOrder()
    
    # Add transform operations (matching your working plugin's pattern)
    translate_op = xformable.AddTranslateOp()
    rotate_op = xformable.AddRotateXYZOp()
    scale_op = xformable.AddScaleOp()
    
    # Store current time to restore later
    original_time = cmds.currentTime(query=True)
    
    try:
        # Calculate frame count
        frame_count = int((end_frame - start_frame) / step) + 1
        
        for i in range(frame_count):
            frame = start_frame + (i * step)
            time_code = Usd.TimeCode(frame)
            
            # Set Maya time
            cmds.currentTime(frame, edit=True)
            
            # Get world-space transform components
            translation = cmds.xform(cam_xform, query=True, worldSpace=True, translation=True)
            rotation = cmds.xform(cam_xform, query=True, worldSpace=True, rotation=True)
            scale = cmds.xform(cam_xform, query=True, worldSpace=True, scale=True)
            
            # Write transform time samples
            translate_op.Set(Gf.Vec3d(translation[0], translation[1], translation[2]), time_code)
            rotate_op.Set(Gf.Vec3f(rotation[0], rotation[1], rotation[2]), time_code)
            scale_op.Set(Gf.Vec3d(scale[0], scale[1], scale[2]), time_code)
            
            # Get camera optical attributes
            focal_length = cmds.getAttr(f"{cam_shape}.focalLength")
            h_aperture = cmds.getAttr(f"{cam_shape}.horizontalFilmAperture")
            v_aperture = cmds.getAttr(f"{cam_shape}.verticalFilmAperture")
            h_offset = cmds.getAttr(f"{cam_shape}.horizontalFilmOffset")
            v_offset = cmds.getAttr(f"{cam_shape}.verticalFilmOffset")
            near_clip = cmds.getAttr(f"{cam_shape}.nearClipPlane")
            far_clip = cmds.getAttr(f"{cam_shape}.farClipPlane")
            
            # Write camera attributes (convert aperture from inches to mm)
            usd_camera.GetFocalLengthAttr().Set(float(focal_length), time_code)
            usd_camera.GetHorizontalApertureAttr().Set(_inches_to_mm(h_aperture), time_code)
            usd_camera.GetVerticalApertureAttr().Set(_inches_to_mm(v_aperture), time_code)
            usd_camera.GetHorizontalApertureOffsetAttr().Set(_inches_to_mm(h_offset), time_code)
            usd_camera.GetVerticalApertureOffsetAttr().Set(_inches_to_mm(v_offset), time_code)
            usd_camera.GetClippingRangeAttr().Set(Gf.Vec2f(near_clip, far_clip), time_code)
        
        print(f"  Wrote {frame_count} time samples")
        
    finally:
        # Restore original time
        cmds.currentTime(original_time, edit=True)
    
    # Add custom metadata for Unreal import
    root_layer = stage.GetRootLayer()
    custom_data = dict(root_layer.customLayerData or {})
    custom_data["layoutlink_has_animation"] = True
    custom_data["layoutlink_start_frame"] = int(start_frame)
    custom_data["layoutlink_end_frame"] = int(end_frame)
    custom_data["layoutlink_fps"] = fps
    custom_data["layoutlink_animated_objects"] = 1
    custom_data["layoutlink_source"] = "maya_camera_export"
    root_layer.customLayerData = custom_data
    
    # Save stage
    stage.Save()
    
    # Verify file size
    file_size = os.path.getsize(abs_path)
    print(f"  File size: {file_size} bytes")
    
    if file_size < 1000:
        om.MGlobal.displayWarning(f"File seems small ({file_size} bytes) - animation may not have exported correctly")
    
    om.MGlobal.displayInfo(f"Camera exported to: {abs_path}")
    
    return abs_path


# =============================================================================
# UI
# =============================================================================

def export_camera_ui():
    """Open the camera export UI window."""
    
    win_name = "CameraExportUSDA_Win"
    
    # Delete existing window
    if cmds.window(win_name, exists=True):
        cmds.deleteUI(win_name)
    
    # Create window
    cmds.window(
        win_name,
        title="Export Camera to USDA",
        sizeable=True,
        widthHeight=(500, 280)
    )
    
    main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))
    
    cmds.separator(height=10, style="none")
    
    # === Camera Selection ===
    cmds.frameLayout(label="Camera", collapsable=False, marginHeight=6, marginWidth=6)
    cam_row = cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(80, 280, 80))
    cmds.text(label="Camera:")
    camera_menu = cmds.optionMenu(width=280)
    
    def populate_cameras():
        """Populate camera dropdown."""
        # Clear existing items
        existing = cmds.optionMenu(camera_menu, query=True, itemListLong=True) or []
        for item in existing:
            try:
                cmds.deleteUI(item)
            except:
                pass
        
        # Get all cameras
        cam_shapes = cmds.ls(type="camera") or []
        cam_transforms = []
        
        for shape in cam_shapes:
            parents = cmds.listRelatives(shape, parent=True, fullPath=True)
            if parents:
                cam_transforms.append(parents[0])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_cams = []
        for cam in cam_transforms:
            if cam not in seen:
                unique_cams.append(cam)
                seen.add(cam)
        
        if not unique_cams:
            cmds.menuItem(parent=camera_menu, label="(no cameras)")
            return
        
        for cam in unique_cams:
            cmds.menuItem(parent=camera_menu, label=cam)
        
        # Try to select the currently selected camera
        selection = cmds.ls(selection=True) or []
        if selection:
            sel = selection[0]
            if cmds.nodeType(sel) == "camera":
                parents = cmds.listRelatives(sel, parent=True, fullPath=True)
                if parents:
                    sel = parents[0]
            if sel in unique_cams:
                try:
                    cmds.optionMenu(camera_menu, edit=True, value=sel)
                except:
                    pass
    
    cmds.button(label="Refresh", command=lambda x: populate_cameras(), width=80)
    cmds.setParent("..")
    cmds.setParent("..")
    
    # === File Path ===
    cmds.frameLayout(label="Output File", collapsable=False, marginHeight=6, marginWidth=6)
    file_row = cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(80, 320, 80))
    cmds.text(label="Save As:")
    
    default_path = os.path.join(cmds.workspace(query=True, rootDirectory=True), "camera.usda")
    file_field = cmds.textField(text=default_path, width=320)
    
    def browse_file(*args):
        result = cmds.fileDialog2(
            fileMode=0,
            caption="Save Camera USD",
            fileFilter="USD ASCII (*.usda);;USD (*.usd)"
        )
        if result:
            path = result[0]
            if not path.lower().endswith((".usda", ".usd")):
                path += ".usda"
            cmds.textField(file_field, edit=True, text=path)
    
    cmds.button(label="Browse...", command=browse_file, width=80)
    cmds.setParent("..")
    cmds.setParent("..")
    
    # === Frame Range ===
    cmds.frameLayout(label="Frame Range", collapsable=False, marginHeight=6, marginWidth=6)
    range_row = cmds.rowLayout(numberOfColumns=6, columnWidth6=(50, 80, 50, 80, 50, 80))
    
    min_time = cmds.playbackOptions(query=True, minTime=True)
    max_time = cmds.playbackOptions(query=True, maxTime=True)
    
    cmds.text(label="Start:")
    start_field = cmds.intField(value=int(min_time), width=80)
    cmds.text(label="End:")
    end_field = cmds.intField(value=int(max_time), width=80)
    cmds.text(label="Step:")
    step_field = cmds.intField(value=1, minValue=1, width=80)
    cmds.setParent("..")
    cmds.setParent("..")
    
    cmds.separator(height=15, style="in")
    
    # === Export Button ===
    def do_export(*args):
        try:
            cam = cmds.optionMenu(camera_menu, query=True, value=True)
            path = cmds.textField(file_field, query=True, text=True)
            start = cmds.intField(start_field, query=True, value=True)
            end = cmds.intField(end_field, query=True, value=True)
            step = cmds.intField(step_field, query=True, value=True)
            
            if not path.lower().endswith((".usda", ".usd")):
                path += ".usda"
            
            result = export_camera_usda(path, start, end, step, cam)
            
            cmds.inViewMessage(
                assistMessage=f"Camera exported to:\n{result}",
                position="topCenter",
                fade=True
            )
            
        except Exception as e:
            om.MGlobal.displayError(str(e))
            import traceback
            traceback.print_exc()
    
    cmds.button(
        label="Export Camera to USDA",
        height=40,
        backgroundColor=(0.3, 0.6, 0.3),
        command=do_export
    )
    
    cmds.separator(height=10, style="none")
    
    # Populate cameras on window open
    populate_cameras()
    
    # Show window
    cmds.showWindow(win_name)


# Auto-launch UI when run directly
if __name__ == "__main__":
    export_camera_ui()