import maya.cmds as mc
import maya.mel as mel
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance
import maya.OpenMayaUI as omui
import os

try:
    from pxr import Usd, UsdGeom, Sdf, Gf
except ImportError:
    mc.error("USD Python libraries not found. Make sure Maya USD plugin is loaded.")

def get_maya_main_window():
    """Get Maya main window as a Qt widget."""
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

def export_camera_to_usd(camera_name, output_path, frame_range):
    """Export camera animation to USD with proper time metadata."""
    start_frame, end_frame = frame_range
    
    # Get Maya's current frame rate
    time_unit = mc.currentUnit(query=True, time=True)
    fps_map = {
        'game': 15.0, 'film': 24.0, 'pal': 25.0, 'ntsc': 30.0,
        'show': 48.0, 'palf': 50.0, 'ntscf': 60.0,
        '23.976fps': 23.976, '29.97fps': 29.97, '29.97df': 29.97,
        '47.952fps': 47.952, '59.94fps': 59.94, '44100fps': 44100.0,
        '48000fps': 48000.0
    }
    maya_fps = fps_map.get(time_unit, 24.0)
    
    # Ensure .usda extension (ASCII format)
    if not output_path.endswith('.usda'):
        output_path = output_path.rsplit('.', 1)[0] + '.usda'
    
    # Create USD stage in ASCII format
    stage = Usd.Stage.CreateNew(output_path)
    
    # CRITICAL: Set time/FPS metadata for proper Unreal import
    stage.SetTimeCodesPerSecond(maya_fps)
    stage.SetFramesPerSecond(maya_fps)
    stage.SetStartTimeCode(start_frame)
    stage.SetEndTimeCode(end_frame)
    
    # Set scene metadata
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    
    # Create camera prim
    camera_path = f"/cameras/{camera_name}"
    camera_prim = UsdGeom.Camera.Define(stage, camera_path)
    
    # Store transform samples and attribute samples
    xform_samples = {}
    attr_samples = {
        'focalLength': {},
        'horizontalAperture': {},
        'verticalAperture': {},
        'focusDistance': {},
        'fStop': {}
    }
    
    # Sample at every frame
    for frame in range(int(start_frame), int(end_frame) + 1):
        mc.currentTime(frame)
        time_code = Usd.TimeCode(frame)
        
        # Get transform
        world_matrix = mc.xform(camera_name, query=True, matrix=True, worldSpace=True)
        gf_matrix = Gf.Matrix4d(
            world_matrix[0], world_matrix[1], world_matrix[2], world_matrix[3],
            world_matrix[4], world_matrix[5], world_matrix[6], world_matrix[7],
            world_matrix[8], world_matrix[9], world_matrix[10], world_matrix[11],
            world_matrix[12], world_matrix[13], world_matrix[14], world_matrix[15]
        )
        xform_samples[frame] = gf_matrix
        
        # Get camera attributes
        shape = mc.listRelatives(camera_name, shapes=True)[0]
        attr_samples['focalLength'][frame] = mc.getAttr(f"{shape}.focalLength")
        attr_samples['horizontalAperture'][frame] = mc.getAttr(f"{shape}.horizontalFilmAperture") * 25.4
        attr_samples['verticalAperture'][frame] = mc.getAttr(f"{shape}.verticalFilmAperture") * 25.4
        attr_samples['focusDistance'][frame] = mc.getAttr(f"{shape}.focusDistance")
        attr_samples['fStop'][frame] = mc.getAttr(f"{shape}.fStop")
    
    # Write transform samples
    xformable = UsdGeom.Xformable(camera_prim)
    xform_op = xformable.AddTransformOp()
    for frame, matrix in xform_samples.items():
        xform_op.Set(matrix, Usd.TimeCode(frame))
    
    # Write attribute samples
    for attr_name, samples in attr_samples.items():
        attr = camera_prim.GetPrim().GetAttribute(attr_name)
        for frame, value in samples.items():
            attr.Set(value, Usd.TimeCode(frame))
    
    stage.Save()
    
    # Print metadata info for verification
    print(f"✓ Exported camera with FPS metadata:")
    print(f"  - Maya FPS: {maya_fps}")
    print(f"  - timeCodesPerSecond: {stage.GetTimeCodesPerSecond()}")
    print(f"  - framesPerSecond: {stage.GetFramesPerSecond()}")
    print(f"  - Frame range: {start_frame} to {end_frame}")
    
    return output_path

class CameraLinkUI(QtWidgets.QWidget):
    """Main UI for CameraLink Maya plugin."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CameraLinkWidget")
        self.setWindowTitle("CameraLink - Export Camera")
        self.selected_camera = None
        self.setup_ui()
        self.load_timeline_range()
    
    def setup_ui(self):
        """Create the user interface."""
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 5px;
                border-radius: 3px;
            }
        """)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Title
        title = QtWidgets.QLabel("📹 CameraLink - Export Camera")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title_font = QtGui.QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # Camera Selection Group
        camera_group = QtWidgets.QGroupBox("📷 Camera Selection")
        camera_layout = QtWidgets.QVBoxLayout()
        
        select_layout = QtWidgets.QHBoxLayout()
        self.select_camera_btn = QtWidgets.QPushButton("Select Camera")
        self.select_camera_btn.setStyleSheet("background-color: rgb(179, 138, 188); color: black;")
        self.select_camera_btn.clicked.connect(self.select_camera)
        select_layout.addWidget(self.select_camera_btn)
        
        self.camera_label = QtWidgets.QLabel("No camera selected")
        select_layout.addWidget(self.camera_label)
        camera_layout.addLayout(select_layout)
        
        camera_group.setLayout(camera_layout)
        main_layout.addWidget(camera_group)
        
        # Frame Range Group
        range_group = QtWidgets.QGroupBox("🎬 Frame Range")
        range_layout = QtWidgets.QVBoxLayout()
        
        # FPS info display
        fps_label = QtWidgets.QLabel()
        time_unit = mc.currentUnit(query=True, time=True)
        fps_label.setText(f"Current Maya FPS: {time_unit}")
        fps_label.setStyleSheet("color: #888; font-style: italic;")
        range_layout.addWidget(fps_label)
        
        # Start frame
        start_layout = QtWidgets.QHBoxLayout()
        start_layout.addWidget(QtWidgets.QLabel("Start Frame:"))
        self.start_frame = QtWidgets.QSpinBox()
        self.start_frame.setRange(-999999, 999999)
        self.start_frame.setValue(1)
        start_layout.addWidget(self.start_frame)
        range_layout.addLayout(start_layout)
        
        # End frame
        end_layout = QtWidgets.QHBoxLayout()
        end_layout.addWidget(QtWidgets.QLabel("End Frame:"))
        self.end_frame = QtWidgets.QSpinBox()
        self.end_frame.setRange(-999999, 999999)
        self.end_frame.setValue(100)
        end_layout.addWidget(self.end_frame)
        range_layout.addLayout(end_layout)
        
        # Get from timeline button
        timeline_btn = QtWidgets.QPushButton("⏱️ Get from Timeline")
        timeline_btn.setStyleSheet("background-color: rgb(179, 138, 188); color: black;")
        timeline_btn.clicked.connect(self.load_timeline_range)
        range_layout.addWidget(timeline_btn)
        
        range_group.setLayout(range_layout)
        main_layout.addWidget(range_group)
        
        # Output File Group
        output_group = QtWidgets.QGroupBox("💾 Output File")
        output_layout = QtWidgets.QVBoxLayout()
        
        file_layout = QtWidgets.QHBoxLayout()
        self.output_path = QtWidgets.QLineEdit()
        self.output_path.setPlaceholderText("Select output path...")
        file_layout.addWidget(self.output_path)
        
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.setStyleSheet("background-color: rgb(179, 138, 188); color: black;")
        browse_btn.clicked.connect(self.browse_output)
        file_layout.addWidget(browse_btn)
        output_layout.addLayout(file_layout)
        
        # Info label
        info_label = QtWidgets.QLabel("⚡ Will export as .usda (ASCII) with correct FPS metadata")
        info_label.setStyleSheet("color: #888; font-size: 9pt;")
        output_layout.addWidget(info_label)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # Export Button
        export_btn = QtWidgets.QPushButton("🚀 Export Camera to USDA")
        export_btn.setMinimumHeight(40)
        export_btn.setStyleSheet("background-color: rgb(96, 201, 80); color: black; font-weight: bold;")
        export_btn.clicked.connect(self.export_camera)
        main_layout.addWidget(export_btn)
        
        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)
        
        # Add stretch at bottom
        main_layout.addStretch()
    
    def select_camera(self):
        """Select camera from scene selection."""
        selection = mc.ls(selection=True, cameras=False, transforms=True)
        
        if not selection:
            self.status_label.setText("❌ Please select a camera in the scene")
            self.status_label.setStyleSheet("color: red;")
            return
        
        # Check if selected object has a camera shape
        shapes = mc.listRelatives(selection[0], shapes=True, type='camera')
        if not shapes:
            self.status_label.setText("❌ Selected object is not a camera")
            self.status_label.setStyleSheet("color: red;")
            return
        
        self.selected_camera = selection[0]
        self.camera_label.setText(f"Camera: {self.selected_camera}")
        self.status_label.setText("✓ Camera selected")
        self.status_label.setStyleSheet("color: green;")
        
        mc.inViewMessage(amg=f"Camera set: {self.selected_camera}", pos='topCenter', fade=True)
    
    def load_timeline_range(self):
        """Load frame range from Maya timeline."""
        start = int(mc.playbackOptions(query=True, minTime=True))
        end = int(mc.playbackOptions(query=True, maxTime=True))
        self.start_frame.setValue(start)
        self.end_frame.setValue(end)
        
        mc.inViewMessage(amg=f"Timeline range loaded: {start}-{end}", pos='topCenter', fade=True)
    
    def browse_output(self):
        """Browse for output file location."""
        file_path = mc.fileDialog2(
            fileMode=0,
            caption="Save Camera USD",
            fileFilter="USD ASCII (*.usda);;All Files (*.*)",
            dialogStyle=2
        )
        
        if file_path:
            self.output_path.setText(file_path[0])
    
    def export_camera(self):
        """Export the selected camera to USD."""
        if not self.selected_camera:
            self.status_label.setText("❌ Please select a camera first")
            self.status_label.setStyleSheet("color: red;")
            return
        
        output = self.output_path.text()
        if not output:
            self.status_label.setText("❌ Please specify an output path")
            self.status_label.setStyleSheet("color: red;")
            return
        
        try:
            # Export camera
            frame_range = (self.start_frame.value(), self.end_frame.value())
            result_path = export_camera_to_usd(self.selected_camera, output, frame_range)
            
            # Success
            self.status_label.setText(f"✓ Camera exported successfully!\n{result_path}")
            self.status_label.setStyleSheet("color: green;")
            
            mc.inViewMessage(
                amg=f"Camera exported with FPS metadata: {result_path}",
                pos='topCenter',
                fade=True
            )
            
        except Exception as e:
            self.status_label.setText(f"❌ Export failed: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            mc.warning(f"CameraLink export error: {str(e)}")

def show_ui():
    """Launch CameraLink UI as a dockable workspace control."""
    # Delete existing workspace control
    if mc.workspaceControl("CameraLinkWC", exists=True):
        mc.deleteUI("CameraLinkWC", control=True)
    
    # Create dockable workspace control
    workspace = mc.workspaceControl(
        "CameraLinkWC",
        label="CameraLink",
        dockToMainWindow=("right", 1),
        initialWidth=400,
        initialHeight=650,
        retain=False,
        widthProperty="preferred"
    )
    
    # Get workspace control's Qt widget pointer
    workspace_ptr = omui.MQtUtil.findControl(workspace)
    workspace_widget = wrapInstance(int(workspace_ptr), QtWidgets.QWidget)
    
    # Create and add our UI
    ui = CameraLinkUI(parent=workspace_widget)
    workspace_widget.layout().addWidget(ui)
    
    return ui

# Launch the UI
show_ui()