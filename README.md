# Maya → Unreal USD Camera Pipeline

A streamlined pipeline for transferring animated cameras from Maya to Unreal Engine using USD format.

---

## Features

- Export Maya cameras with full animation to `.usda` format
- One-click import into Unreal via toolbar button
- Import creates a Level Sequence with animated CineCameraActor
- Live reload support for iterative workflows
- Preserves transform animation, focal length, aperture, and clipping planes

---

## Requirements

### Maya
- Maya 2025.3+ (tested on 2025.3 and 2026)
- USD Python bindings (`pxr`) available inside Maya
- Access to `maya.cmds` and `maya.api.OpenMaya`

### Unreal Engine
- Unreal Engine 5.3+
- Enabled plugins:
  - **USD Importer**
  - **Python Editor Script Plugin**
  - **Editor Scripting Utilities**

---

## Installation

### Maya Setup
1. Copy `maya_usd_camera_export.py` to your Maya scripts folder:
   - Windows: `Documents/maya/scripts/`
   - Mac: `~/Library/Preferences/Autodesk/maya/scripts/`

### Unreal Setup
1. Copy the `CameraLink` plugin folder to your project's `Plugins/` directory:
   ```
   YourProject/
   └── Plugins/
       └── CameraLink/
   ```
2. Restart Unreal Engine
3. Enable the **CameraLink** plugin in Edit → Plugins if not already enabled
4. A camera icon button will appear in the toolbar

---

## Workflow

### Step 1: Export from Maya

1. Open Maya and load your scene with an animated camera.

2. In the Script Editor (Python tab), run:
   ```python
   import maya_usd_camera_export
   maya_usd_camera_export.export_camera_ui()
   ```

3. In the export UI:
   - Select your **camera** from the dropdown
   - Choose a **.usda output path** (e.g., `C:/Projects/camera.usda`)
   - Set the **frame range** (defaults to timeline range)
   - Click **Export Camera to USDA**

4. You'll see a confirmation message with the file path.

**What gets exported:**
- Camera transform animation (translate, rotate, scale) per frame
- Focal length (with animation if keyed)
- Film aperture (horizontal/vertical) converted from inches to mm
- Clipping planes (near/far)
- Custom metadata for Unreal import

---

### Step 2: Import into Unreal

1. Click the **CameraLink** button in the toolbar (camera icon)

2. A file browser opens — select your `.usda` camera file

3. The camera imports and the Level Sequence opens in Sequencer automatically

**What gets created:**
- A `UsdStageActor` that references your USD file
- A Level Sequence with the animated camera
- Proper frame range and FPS settings

---

## Updating Camera Animation (Live Reload)

One of the best features of this USD workflow is **live reloading**. You don't need to re-import when you make changes in Maya.

### To update your camera animation:

1. **In Maya:** Make your animation changes and re-export to the **same file path** with the export button.

2. **In Unreal:** 
   - Open the **USD Stage Editor** (Window → USD Stage)
   - Select your `UsdStageActor` in the level
   - Click **Reload** (or right-click → Reload Stage)

3. Your camera animation updates instantly in Sequencer!

### Tips for iterative workflow:
- Keep Maya and Unreal open side-by-side
- Always export to the same `.usda` file location
- Use Reload instead of re-importing to preserve your Unreal scene setup
- The Level Sequence frame range updates automatically with the new animation

---

## Debugging

### Verify USD file has animation data

In Unreal's Python console:
```python
import unreal_usd_camera_import
unreal_usd_camera_import.print_usd_debug(r"C:/path/to/camera.usda")
```

This prints:
- Time codes per second (FPS)
- Start/end frame range
- All prims and their animation data
- Number of time samples per transform

### Common issues:

| Problem | Solution |
|---------|----------|
| Working with USD Stage setup | Add the imported camera root as an actor to the main sequence, set the Time to the start and end of your desired frame range|

---

## File Structure

```
YourProject/
└── Plugins/
    └── CameraLink/
        ├── CameraLink.uplugin
        ├── Content/
        │   └── Python/
        │       └── unreal_usd_camera_import.py
        ├── Resources/
        │   └── ...
        └── Source/
            └── CameraLink/
                └── ...

maya/scripts/
└── maya_usd_camera_export.py
```

---

## Technical Notes

- **Units:** Maya aperture values (inches) are automatically converted to USD standard (millimeters)
- **Coordinate System:** Maya Y-up is preserved; Unreal handles axis conversion
- **Frame Rate:** Exported from Maya's current time unit setting
- **Transform Order:** Uses translate → rotateXYZ → scale (standard USD order)

---

## Release Log

**v2.0** (December 2025)
- Added CameraLink Unreal plugin with toolbar button
- Complete rewrite of Maya export using stepped animation sampling
- Added live reload documentation
- Simplified Unreal import with automatic Level Sequence detection
- Added debug utilities for troubleshooting
- Improved metadata for frame range and FPS

**v1.0** (September 2025)
- Initial release
- Basic Maya → Unreal camera transfer via USDA

---

## Tested Platforms

- Maya 2025.3
- Unreal Engine 5.6
- Windows 11

---

## Credits

**Developer**
- Catherine Azelby — [catherineazelby.com](https://catherineazelby.com/)

**Icons**
- Camera icon from [Lucide Icons](https://lucide.dev/) (ISC License)