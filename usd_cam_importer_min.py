# usd_cam_importer_min.py
# Minimal Unreal Python: import a USD camera (.usdc) using Unreal's built-in USD importer.
# NO custom transform or focal math — same behavior as the manual USD Import path.

import os
from typing import Optional
import unreal

def _norm(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/")

def _ensure_dest(dest_path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(dest_path):
        unreal.EditorAssetLibrary.make_directory(dest_path)

def _find_level_sequence_under(path: str, name_hint: Optional[str] = None):
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    for data in reg.get_assets_by_path(path, recursive=True):
        if data.asset_class == "LevelSequence":
            if name_hint is None or data.asset_name == name_hint:
                return data.get_asset()
    return None

def import_usdc_camera_to_sequence(
    usdc_path: str,
    dest_path: str = "/Game/Sequences",
    asset_name: Optional[str] = None,
    replace_existing: bool = True,
    save: bool = True,
):
    """
    Imports the USD file with Unreal's USD importer (same as the UI), and opens the created Level Sequence.
    - usdc_path: filesystem path to .usdc
    - dest_path: Content Browser folder (e.g. "/Game/Sequences")
    - asset_name: target Level Sequence name; if None, uses "LS_<filename>"
    """
    usdc_path = _norm(usdc_path)
    _ensure_dest(dest_path)

    if not asset_name:
        base = os.path.splitext(os.path.basename(usdc_path))[0]
        asset_name = f"LS_{base}"

    # Prepare an automated import task (use importer defaults, no custom options)
    task = unreal.AssetImportTask()
    task.filename = usdc_path
    task.destination_path = dest_path
    task.destination_name = asset_name
    task.automated = True
    task.replace_existing = replace_existing
    task.save = save

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    # Prefer what the task reports as created
    imported_paths = list(task.get_editor_property("imported_object_paths") or [])
    seq = None
    for obj_path in imported_paths:
        asset = unreal.load_asset(obj_path)
        if isinstance(asset, unreal.LevelSequence):
            seq = asset
            break

    # Fallback: search by path/name
    if not seq:
        seq = _find_level_sequence_under(dest_path, asset_name)

    if not seq:
        unreal.log_warning("[USD Camera] Import finished, but no Level Sequence was found. Imported objects: {}".format(imported_paths))
        return None

    # Open the sequence
    try:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    except Exception:
        pass

    unreal.log("[USD Camera] Imported '{}' into Level Sequence '{}' under '{}'".format(usdc_path, seq.get_name(), dest_path))
    return seq

# Convenience wrapper to keep existing call-sites working
def run_import_with_path(path: str):
    return import_usdc_camera_to_sequence(path, dest_path="/Game/Sequences", asset_name=None)








