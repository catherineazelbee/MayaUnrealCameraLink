# Maya → Unreal USD Camera Pipeline

A streamlined pipeline for transferring animated cameras from Maya to Unreal Engine using USD format.

---

## Features

- Export Maya cameras with full animation to .usda format
- One-click import into Unreal via toolbar button
- Import creates a Level Sequence with animated CineCameraActor
- Live reload support for iterative workflows
- Preserves transform animation, focal length, aperture, focus distance, and f-stop
- Automatic aspect ratio matching from Maya render settings (e.g., 1920×1080 → 16:9)
- Proper unit conversion for focus distance based on Maya scene units

---

## Demo Video
# Setup Demo Video
[![Watch the video]([thumbnail-image.png)](https://vimeo.com/YOUR_VIDEO_ID](https://vimeo.com/1146015631/f2f2e253ce?share=copy))

---

## Requirements

### Maya
- Maya 2025.3+ (tested on 2025.3 and 2026)
- USD Python bindings (`pxr`) available inside Maya
- PySide6 (included with Maya 2024+)

### Unreal Engine
- Unreal Engine 5.3+
- Enabled plugins:
  - **USD Importer**
  - **USD Core**
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

2. Open 'maya_usd_camera_export.py' in Maya's Script Editor (Python tab) and press **Ctrl + Enter** to run the entire script. The CameraLink panel will dock to the right side of Maya (can be moved if desired)

3. In the CameraLink UI:
- Select your camera in the viewport, then click Select Camera
- Set the frame range (or click "Get from Timeline")
- Choose a .usda output path via Browse
- Click Export Camera to USDA

4. You'll see a confirmation message with export details.

**What gets exported:**
- Camera transform animation (translate, rotate, scale) per frame
- Focal length (with animation if keyed)
- Film aperture adjusted to match Maya render resolution aspect ratio
- Focus distance (converted from Maya scene units to cm)
- F-stop / aperture
- Custom metadata for Unreal import (FPS, frame range, resolution)

---

### Step 2: Import into Unreal

1. Click the **CameraLink** button in the toolbar (camera icon)

2. In the file browser, select your `.usda` camera file you exported from Maya

3. The camera imports and the Level Sequence opens in Sequencer automatically

**What gets created:**
- A `UsdStageActor` that references your USD file
- A transient Level Sequence with the animated camera
- Proper frame range and FPS settings

---

## Using the Imported Camera

### Option A: Render with USD Camera (Live-Linked)

Best for iterative workflows where you're still adjusting the camera in Maya.

1. Open the imported USD sequence
2. Add a **Camera Cut track** → set to the imported camera
3. Add your other animation/subsequences **INTO this sequence**
4. Render from this sequence

**Pros:** Camera updates automatically when you reload the USD stage  
**Cons:** Sequence is transient; other content must be added to it (not vice versa)

### Option B: Convert to Native Unreal

Best when camera is finalized and you need to use it in existing sequences.

1. Select the `UsdStageActor` in the Outliner
2. Open **USD Stage Editor** → **Actions** → **Import**
3. This creates a native `CineCameraActor` and a saved Level Sequence

**Pros:** Can be used in any sequence, fully native Unreal asset  
**Cons:** Loses live USD link; must re-import for updates

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

**What to look for:**
- **Time samples** should match your frame count (e.g., 350 frames = 350 samples)
- If you see **1 time sample**, animation didn't export — re-export from Maya
- **Custom metadata** confirms FPS, frame range, and aspect ratio are correct

### Common issues:

| Problem | Solution |
|---------|----------|
| Camera is blurry/wrong DOF | Check Maya camera's Focus Distance attribute (default 5 is usually blurry, try value 100) |
| Wrong aspect ratio | Verify Maya Render Settings resolution is set correctly before export |
| Animation timing off | Ensure Maya and Unreal are using the same FPS |
| No camera animation in Unreal | Use Unreal debugging in Python console (above) |
| Camera animation not being rendered in Unreal | Ensure the imported camera is set as the CameraCutTrack in Level Sequencer |
| Sequence won't add to master | USD sequences are transient; use Actions → Import to convert |
| Project won't build after adding plugin | Ensure all plugin dependencies are downloaded before adding CameraLink |

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

- **Aperture/Aspect Ratio:** Uses industry-standard 36mm horizontal aperture. Vertical aperture is automatically calculated from Maya's render resolution to match any aspect ratio (16:9, 21:9, 4:3, etc.) regardless of Maya camera filmback settings
- **Focus Distance:** Converted from Maya scene units (mm/cm/m/in/ft/yd) to centimeters for USD
- **Frame Rate:** Retrieved via MEL `currentTimeUnitToFPS()` to support all FPS settings including custom values
- **Coordinate System:** Maya Y-up is preserved; Unreal handles axis conversion
- **Transform Order:** Uses translate → rotateXYZ → scale

---

## Release Log

**v2.0** (December 2025)
- Added CameraLink Unreal plugin with toolbar button
- Complete rewrite of Maya export with professional dockable UI
- Aspect ratio now derived from Maya render settings (not camera filmback)
- Focus distance properly converted based on Maya scene units
- F-stop now transfers correctly
- FPS detection via MEL for custom frame rate support
- Added two-workflow documentation (live USD vs native conversion)
- Warning about reload removing manual sequence edits
- Added debug utilities for troubleshooting
- Improved error handling and logging

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
