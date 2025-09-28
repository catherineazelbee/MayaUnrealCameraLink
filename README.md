
---

## Requirements

### Maya
- Maya 2025.3 (tested)
- USD Python bindings (`pxr`) available inside Maya
- Access to `maya.cmds` and `maya.api.OpenMaya`

### Unreal
- Unreal Engine 5.3 (tested; Python 3.9)
- Enabled plugins:
  - **USD Importer**
  - **Python Editor Script Plugin**
  - **Editor Scripting Utilities**

---

## Workflow

### 1. Export from Maya

1. Run `maya_usd_camera_export.py` in Maya (Script Editor → Python tab).
2. The UI lets you:
   - Select a **camera**.
   - Choose a **.usdc output path**.
   - Set **frame range** and **step** (defaults from the timeline).
3. Click **Export Camera to USDC**.  
   You’ll see a confirmation toast, and the file is saved.

**What gets authored**
- Camera prim named after the Maya transform.
- Keys written at every requested frame:
  - `worldMatrix` (verbatim from Maya).
  - `focalLength`, `clippingRange`.
- Static filmback/aperture values, with conversion **inches → mm**.

---

### 2. Import into Unreal

#### Option A — Python Console
1. Make sure your project has a folder: YourProject/Content/Python/
2. Place both scripts in that folder:
- `usd_cam_importer_min.py`
- `usd_cam_EXECUTE.py`
3. In Unreal’s Python console:
```python
import importlib, usd_cam_importer_min as imp
importlib.reload(imp)
imp.run_import_with_path("C:/absolute/path/to/camera.usdc")
```
#### Option B — Execute Python Script
1. Make sure your project has a folder: YourProject/Content/Python/
2. Place both scripts in that folder:
- `usd_cam_importer_min.py`
- `usd_cam_EXECUTE.py`
3. Open usd_cam_EXECUTE.py and edit the path to your camera file:
```python
USDC_PATH = r"C:/Users/you/Downloads/camera.usdc"
```
4. In Unreal’s top menu, go to:
Tools → Execute Python Script…
and select usd_cam_EXECUTE.py
5. The camera will be imported into /Game/Sequences as a Level Sequence (named LS_<filename> by default) and opened in Sequencer.

**Note**  
- It is recommended that any detailed camera adjustments outside of basic transforms (e.g., depth of field, focus distance, lens presets, filmback changes, cinematic settings) be done directly inside Unreal.  
- The plugin correctly imports transforms, focal length, clipping planes, and filmback values, but advanced cinematic features should be managed natively in Unreal for the best results.


