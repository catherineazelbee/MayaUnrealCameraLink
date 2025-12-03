"""
Export a Maya camera to .usda with baked animation.
Tested in Maya 2025.3 (Python 3).

USAGE
-----
1) Place this file in your Maya scripts folder
2) In Maya Script Editor (Python):
       import maya_usd_camera_export
       maya_usd_camera_export.show_ui()
"""

import os
import maya.cmds as cmds
import maya.api.OpenMaya as om
from pxr import Usd, UsdGeom, Sdf, Gf

# Qt imports with fallback
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin


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
    
    if time_unit.endswith("fps"):
        try:
            return float(time_unit[:-3])
        except ValueError:
            pass
    
    return 24.0


def _resolve_camera(name):
    """Resolve camera name to (transform_path, shape_path)."""
    if not name or not cmds.objExists(name):
        raise RuntimeError(f"Camera does not exist: {name}")
    
    node_type = cmds.nodeType(name)
    
    if node_type == "camera":
        shape = cmds.ls(name, long=True)[0]
        parents = cmds.listRelatives(shape, parent=True, fullPath=True)
        if not parents:
            raise RuntimeError(f"Camera shape has no parent: {shape}")
        xform = parents[0]
    else:
        xform = cmds.ls(name, long=True)[0]
        shapes = cmds.listRelatives(xform, shapes=True, type="camera", fullPath=True)
        if not shapes:
            raise RuntimeError(f"No camera shape found under: {name}")
        shape = shapes[0]
    
    return xform, shape


def _sanitize_name(name):
    """Clean up name for USD prim path."""
    clean = name.split("|")[-1].split(":")[-1]
    for char in '<>:"/\\|?*. ':
        clean = clean.replace(char, "_")
    return clean


def _is_animated(obj):
    """Check if object has animation (keyframes or constraints)."""
    animatable_attrs = [
        "translateX", "translateY", "translateZ",
        "rotateX", "rotateY", "rotateZ",
        "scaleX", "scaleY", "scaleZ"
    ]
    
    for attr in animatable_attrs:
        full_attr = f"{obj}.{attr}"
        if cmds.objExists(full_attr):
            connections = cmds.listConnections(full_attr, type="animCurve") or []
            if connections:
                return True
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
    """Export Maya camera to USD with baked animation."""
    
    if not file_path.lower().endswith((".usda", ".usd")):
        raise RuntimeError("Export file must have .usda or .usd extension")
    
    out_dir = os.path.dirname(os.path.abspath(file_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    if end_frame < start_frame:
        raise RuntimeError("End frame must be >= start frame")
    if step <= 0:
        raise RuntimeError("Step must be > 0")
    
    cam_xform, cam_shape = _resolve_camera(camera)
    cam_name = _sanitize_name(cam_xform)
    fps = _get_maya_fps()
    
    print(f"Exporting camera: {cam_xform}")
    print(f"  Frame range: {start_frame} - {end_frame} (step {step})")
    print(f"  FPS: {fps}")
    
    xform_animated = _is_animated(cam_xform)
    optics_animated = _is_camera_animated(cam_shape)
    
    print(f"  Transform animated: {xform_animated}")
    print(f"  Optics animated: {optics_animated}")
    
    abs_path = os.path.abspath(file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
    
    stage = Usd.Stage.CreateNew(abs_path)
    
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    stage.SetTimeCodesPerSecond(fps)
    stage.SetStartTimeCode(start_frame)
    stage.SetEndTimeCode(end_frame)
    
    prim_path = f"/{cam_name}"
    usd_camera = UsdGeom.Camera.Define(stage, prim_path)
    camera_prim = usd_camera.GetPrim()
    stage.SetDefaultPrim(camera_prim)
    
    xformable = UsdGeom.Xformable(usd_camera)
    xformable.ClearXformOpOrder()
    
    translate_op = xformable.AddTranslateOp()
    rotate_op = xformable.AddRotateXYZOp()
    scale_op = xformable.AddScaleOp()
    
    original_time = cmds.currentTime(query=True)
    
    try:
        frame_count = int((end_frame - start_frame) / step) + 1
        
        for i in range(frame_count):
            frame = start_frame + (i * step)
            time_code = Usd.TimeCode(frame)
            
            cmds.currentTime(frame, edit=True)
            
            translation = cmds.xform(cam_xform, query=True, worldSpace=True, translation=True)
            rotation = cmds.xform(cam_xform, query=True, worldSpace=True, rotation=True)
            scale = cmds.xform(cam_xform, query=True, worldSpace=True, scale=True)
            
            translate_op.Set(Gf.Vec3d(translation[0], translation[1], translation[2]), time_code)
            rotate_op.Set(Gf.Vec3f(rotation[0], rotation[1], rotation[2]), time_code)
            scale_op.Set(Gf.Vec3d(scale[0], scale[1], scale[2]), time_code)
            
            focal_length = cmds.getAttr(f"{cam_shape}.focalLength")
            h_aperture = cmds.getAttr(f"{cam_shape}.horizontalFilmAperture")
            v_aperture = cmds.getAttr(f"{cam_shape}.verticalFilmAperture")
            h_offset = cmds.getAttr(f"{cam_shape}.horizontalFilmOffset")
            v_offset = cmds.getAttr(f"{cam_shape}.verticalFilmOffset")
            near_clip = cmds.getAttr(f"{cam_shape}.nearClipPlane")
            far_clip = cmds.getAttr(f"{cam_shape}.farClipPlane")
            
            usd_camera.GetFocalLengthAttr().Set(float(focal_length), time_code)
            usd_camera.GetHorizontalApertureAttr().Set(_inches_to_mm(h_aperture), time_code)
            usd_camera.GetVerticalApertureAttr().Set(_inches_to_mm(v_aperture), time_code)
            usd_camera.GetHorizontalApertureOffsetAttr().Set(_inches_to_mm(h_offset), time_code)
            usd_camera.GetVerticalApertureOffsetAttr().Set(_inches_to_mm(v_offset), time_code)
            usd_camera.GetClippingRangeAttr().Set(Gf.Vec2f(near_clip, far_clip), time_code)
        
        print(f"  Wrote {frame_count} time samples")
        
    finally:
        cmds.currentTime(original_time, edit=True)
    
    root_layer = stage.GetRootLayer()
    custom_data = dict(root_layer.customLayerData or {})
    custom_data["layoutlink_has_animation"] = True
    custom_data["layoutlink_start_frame"] = int(start_frame)
    custom_data["layoutlink_end_frame"] = int(end_frame)
    custom_data["layoutlink_fps"] = fps
    custom_data["layoutlink_animated_objects"] = 1
    custom_data["layoutlink_source"] = "maya_camera_export"
    root_layer.customLayerData = custom_data
    
    stage.Save()
    
    file_size = os.path.getsize(abs_path)
    print(f"  File size: {file_size} bytes")
    
    if file_size < 1000:
        om.MGlobal.displayWarning(f"File seems small ({file_size} bytes) - animation may not have exported correctly")
    
    om.MGlobal.displayInfo(f"Camera exported to: {abs_path}")
    
    return abs_path


# =============================================================================
# Qt UI
# =============================================================================

class CameraExportUI(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    """Professional USD Camera Export UI"""
    
    WINDOW_TITLE = "CameraLink - Export Camera"
    WINDOW_OBJECT = "CameraLinkExportWindow"
    
    def __init__(self, parent=None):
        super(CameraExportUI, self).__init__(parent=parent)
        
        self.setObjectName(self.WINDOW_OBJECT)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(450)
        
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header
        header = QtWidgets.QLabel("USD Camera Export")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        header.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(header)
        
        # ============================================================
        # CAMERA SELECTION
        # ============================================================
        camera_group = QtWidgets.QGroupBox("Camera")
        camera_layout = QtWidgets.QHBoxLayout()
        
        self.camera_combo = QtWidgets.QComboBox()
        self.camera_combo.setMinimumWidth(250)
        camera_layout.addWidget(self.camera_combo)
        
        refresh_btn = QtWidgets.QPushButton("↻ Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.populate_cameras)
        camera_layout.addWidget(refresh_btn)
        
        camera_group.setLayout(camera_layout)
        main_layout.addWidget(camera_group)
        
        # ============================================================
        # OUTPUT FILE
        # ============================================================
        output_group = QtWidgets.QGroupBox("Output File")
        output_layout = QtWidgets.QHBoxLayout()
        
        self.file_path_input = QtWidgets.QLineEdit()
        default_path = os.path.join(cmds.workspace(query=True, rootDirectory=True), "camera.usda")
        self.file_path_input.setText(default_path)
        output_layout.addWidget(self.file_path_input)
        
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self.browse_file)
        output_layout.addWidget(browse_btn)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # ============================================================
        # FRAME RANGE
        # ============================================================
        frame_group = QtWidgets.QGroupBox("Frame Range")
        frame_layout = QtWidgets.QHBoxLayout()
        
        # Start
        frame_layout.addWidget(QtWidgets.QLabel("Start:"))
        self.start_spin = QtWidgets.QSpinBox()
        self.start_spin.setRange(-100000, 100000)
        self.start_spin.setMinimumWidth(70)
        frame_layout.addWidget(self.start_spin)
        
        frame_layout.addSpacing(10)
        
        # End
        frame_layout.addWidget(QtWidgets.QLabel("End:"))
        self.end_spin = QtWidgets.QSpinBox()
        self.end_spin.setRange(-100000, 100000)
        self.end_spin.setMinimumWidth(70)
        frame_layout.addWidget(self.end_spin)
        
        frame_layout.addSpacing(10)
        
        # Step
        frame_layout.addWidget(QtWidgets.QLabel("Step:"))
        self.step_spin = QtWidgets.QSpinBox()
        self.step_spin.setRange(1, 100)
        self.step_spin.setValue(1)
        self.step_spin.setMinimumWidth(50)
        frame_layout.addWidget(self.step_spin)
        
        frame_layout.addSpacing(15)
        
        # Get from Timeline button (same row)
        timeline_btn = QtWidgets.QPushButton("↻ Get from Timeline")
        timeline_btn.clicked.connect(self.sync_from_timeline)
        frame_layout.addWidget(timeline_btn)
        
        frame_layout.addStretch()
        
        frame_group.setLayout(frame_layout)
        main_layout.addWidget(frame_group)
        
        # ============================================================
        # EXPORT BUTTON
        # ============================================================
        main_layout.addSpacing(5)
        
        self.export_btn = QtWidgets.QPushButton("📷 Export Camera to USDA")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.export_btn.clicked.connect(self.do_export)
        main_layout.addWidget(self.export_btn)
        
        main_layout.addStretch()
        
        # Initialize
        self.populate_cameras()
        self.sync_from_timeline()
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def populate_cameras(self):
        """Populate camera dropdown with scene cameras."""
        self.camera_combo.clear()
        
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
            self.camera_combo.addItem("(no cameras in scene)")
            return
        
        for cam in unique_cams:
            self.camera_combo.addItem(cam)
        
        # Try to select currently selected camera
        selection = cmds.ls(selection=True) or []
        if selection:
            sel = selection[0]
            if cmds.nodeType(sel) == "camera":
                parents = cmds.listRelatives(sel, parent=True, fullPath=True)
                if parents:
                    sel = parents[0]
            
            idx = self.camera_combo.findText(sel)
            if idx >= 0:
                self.camera_combo.setCurrentIndex(idx)
    
    def browse_file(self):
        """Open file browser for output path."""
        result = cmds.fileDialog2(
            fileMode=0,
            caption="Save Camera USD",
            fileFilter="USD ASCII (*.usda);;USD (*.usd)",
            startingDirectory=os.path.dirname(self.file_path_input.text())
        )
        if result:
            path = result[0]
            if not path.lower().endswith((".usda", ".usd")):
                path += ".usda"
            self.file_path_input.setText(path)
    
    def sync_from_timeline(self):
        """Sync frame range from Maya timeline."""
        start = int(cmds.playbackOptions(query=True, minTime=True))
        end = int(cmds.playbackOptions(query=True, maxTime=True))
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)
    
    def do_export(self):
        """Execute the export."""
        try:
            camera = self.camera_combo.currentText()
            if camera == "(no cameras in scene)":
                QtWidgets.QMessageBox.warning(
                    self, "No Camera",
                    "No cameras found in scene.\nPlease create a camera first."
                )
                return
            
            file_path = self.file_path_input.text()
            if not file_path:
                QtWidgets.QMessageBox.warning(
                    self, "No File Path",
                    "Please specify an output file path."
                )
                return
            
            if not file_path.lower().endswith((".usda", ".usd")):
                file_path += ".usda"
            
            start = self.start_spin.value()
            end = self.end_spin.value()
            step = self.step_spin.value()
            
            result = export_camera_usda(file_path, start, end, step, camera)
            
            QtWidgets.QMessageBox.information(
                self, "Export Complete",
                f"Camera exported successfully!\n\n{result}"
            )
            
        except Exception as e:
            om.MGlobal.displayError(str(e))
            QtWidgets.QMessageBox.critical(
                self, "Export Failed",
                f"An error occurred:\n\n{e}"
            )
            import traceback
            traceback.print_exc()


# =============================================================================
# PUBLIC API
# =============================================================================

def show_ui():
    """Show the Camera Export UI as a dockable window."""
    
    workspace_control_name = CameraExportUI.WINDOW_OBJECT + "WorkspaceControl"
    if cmds.workspaceControl(workspace_control_name, exists=True):
        cmds.deleteUI(workspace_control_name)
    
    ui = CameraExportUI()
    ui.show(dockable=True)
    
    return ui


# Backwards compatibility alias
def export_camera_ui():
    """Alias for show_ui() for backwards compatibility."""
    return show_ui()


# =============================================================================
# AUTO-LAUNCH
# =============================================================================

if __name__ == "__main__":
    show_ui()