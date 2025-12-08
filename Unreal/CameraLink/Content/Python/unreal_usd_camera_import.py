# unreal_usd_camera_import.py
# Minimal, robust initial importer for USDA camera files.
#
# Usage:
#   import importlib, unreal_usd_camera_import
#   importlib.reload(unreal_usd_camera_import)
#   metadata = {"has_animation": True, "fps": 24, "start_frame": 1, "end_frame": 350}
#   unreal_usd_camera_import.import_camera(r"C:\path\to\camera.usda", metadata)
#
# Important: This script is intended ONLY for the initial import. After that use Unreal's native "Reload Stage" button
# to refresh the stage when you re-export/overwrite the same .usda file from Maya.

import unreal
import os
import time
import traceback

# --------------------------
# Helper: apply metadata (playback range + fps) to a LevelSequence
# --------------------------
def apply_metadata_to_sequence(level_sequence, start_frame=1, end_frame=1, fps=24):
    """Set display/tick rates, playback start/end, view range, and try to set movie scene playback range."""
    if not level_sequence:
        unreal.log_warning("[USDImport] apply_metadata_to_sequence: no level_sequence supplied")
        return False
    try:
        start_frame = int(start_frame)
        end_frame = int(end_frame)
        fps = int(fps)
        unreal.log(f"[USDImport] Applying metadata -> sequence={level_sequence.get_name()} start={start_frame} end={end_frame} fps={fps}")

        # frame rate
        frame_rate = unreal.FrameRate(numerator=fps, denominator=1)
        try:
            level_sequence.set_display_rate(frame_rate)
            level_sequence.set_tick_resolution(frame_rate)
        except Exception:
            try:
                level_sequence.set_editor_property("display_rate", frame_rate)
                level_sequence.set_editor_property("tick_resolution", frame_rate)
            except Exception as e:
                unreal.log_warning(f"[USDImport] Warning: could not set frame rate on sequence: {e}")

        # set playback and view ranges on LevelSequence
        try:
            level_sequence.set_playback_start(start_frame)
            level_sequence.set_playback_end(end_frame)
            level_sequence.set_view_range_start(float(max(0, start_frame - 10)))
            level_sequence.set_view_range_end(float(end_frame + 10))
        except Exception as e:
            unreal.log_warning(f"[USDImport] Could not set playback range on LevelSequence directly: {e}")

        # Try movie scene
        try:
            movie_scene = level_sequence.get_movie_scene()
            if movie_scene:
                duration = float(end_frame - start_frame + 1)
                if hasattr(movie_scene, "set_playback_range"):
                    movie_scene.set_playback_range(float(start_frame), duration)
                else:
                    try:
                        movie_scene.set_editor_property("playback_start", float(start_frame))
                        movie_scene.set_editor_property("playback_end", float(end_frame))
                    except Exception:
                        pass
        except Exception:
            pass

        # Re-open so UI updates
        try:
            unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(level_sequence)
        except Exception:
            pass

        unreal.log("[USDImport] Metadata application finished")
        return True
    except Exception:
        unreal.log_error("[USDImport] apply_metadata_to_sequence exception:\n" + traceback.format_exc())
        return False


# --------------------------
# Utility: safe way to get all actors (use EditorActorSubsystem if available)
# --------------------------
def _get_all_level_actors():
    try:
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        return actor_subsystem.get_all_level_actors()
    except Exception:
        # fallback
        return unreal.EditorLevelLibrary.get_all_level_actors()


# --------------------------
# Core: find or spawn UsdStageActor and point to file
# --------------------------
def _find_usdstageactor_by_label(label):
    for actor in _get_all_level_actors():
        try:
            if isinstance(actor, unreal.UsdStageActor) and actor.get_actor_label() == label:
                return actor
        except Exception:
            pass
    return None


def _set_stage_actor_root(stage_actor, file_path):
    """Set root_layer on the actor (defensive), then try force reload via UsdStageEditorLibrary."""
    if not stage_actor:
        return False
    try:
        abs_path = os.path.abspath(file_path).replace("\\", "/")
        try:
            stage_actor.set_editor_property("root_layer", {"file_path": abs_path})
        except Exception:
            try:
                stage_actor.set_editor_property("root_layer", abs_path)
            except Exception:
                try:
                    setattr(stage_actor, "root_layer", {"file_path": abs_path})
                except Exception as e:
                    unreal.log_error(f"[USDImport] Failed to set root_layer on stage actor: {e}")
                    return False

        # Tell the USD editor to reload stage content
        try:
            unreal.UsdStageEditorLibrary.file_reload()
        except Exception:
            # not fatal
            pass

        return True
    except Exception:
        unreal.log_error("[USDImport] _set_stage_actor_root exception:\n" + traceback.format_exc())
        return False


def _spawn_stage_actor(file_path, actor_label):
    """Spawn UsdStageActor and set label; return actor or None."""
    try:
        # spawn in world origin
        loc = unreal.Vector(0, 0, 0)
        rot = unreal.Rotator(0, 0, 0)
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.UsdStageActor.static_class(), loc, rot)
        if not actor:
            unreal.log_error("[USDImport] spawn_actor_from_class returned None")
            return None
        actor.set_actor_label(actor_label)
        success = _set_stage_actor_root(actor, file_path)
        if not success:
            unreal.log_warning("[USDImport] spawned actor but failed to set root layer")
        return actor
    except Exception:
        unreal.log_error("[USDImport] _spawn_stage_actor exception:\n" + traceback.format_exc())
        return None


# --------------------------
# Main function: initial import (as requested: do only initial import; subsequent updates via Reload Stage)
# --------------------------
def import_usda_to_stage(file_path: str, metadata: dict):
    """
    Minimal initial importer for USDA camera files. Returns a dict with success/stage_actor.
    metadata expected keys: has_animation (bool), fps (int), start_frame (int), end_frame (int)
    """
    try:
        unreal.log("============================================================")
        unreal.log(f"[USD Import] initial import called for: {file_path}")

        if not os.path.exists(file_path):
            unreal.log_error("[USD Import] File does not exist: " + str(file_path))
            return {"success": False, "error": "file_missing"}

        # collect metadata
        has_animation = bool(metadata.get("has_animation", False))
        fps = int(metadata.get("fps", 24))
        start_frame = int(metadata.get("start_frame", 1))
        end_frame = int(metadata.get("end_frame", start_frame))

        unreal.log(f"[USD Import] metadata: has_animation={has_animation}, frames={start_frame}-{end_frame}, fps={fps}")

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        actor_label = f"USD_Camera_{base_name}"

        # First, try to find an existing stage actor with that label. If found, reuse it.
        stage_actor = _find_usdstageactor_by_label(actor_label)
        if stage_actor:
            unreal.log(f"[USD Import] Found existing UsdStageActor '{actor_label}' - reusing it and setting root to the new file.")
            ok = _set_stage_actor_root(stage_actor, file_path)
            if not ok:
                unreal.log_warning("[USD Import] Warning: setting root_layer on existing actor failed.")
        else:
            unreal.log(f"[USD Import] No existing UsdStageActor '{actor_label}' found - spawning a new one.")
            stage_actor = _spawn_stage_actor(file_path, actor_label)
            if not stage_actor:
                unreal.log_error("[USD Import] Failed to spawn UsdStageActor.")
                return {"success": False, "error": "spawn_failed"}

        # After setting the root layer, the engine creates a transient LevelSequence (may be created asynchronously).
        # Wait briefly for the transient LevelSequence to appear. Poll for up to N seconds.
        seq = None
        wait_seconds = 3.0   # short wait so editor isn't blocked too long
        poll_interval = 0.12
        elapsed = 0.0
        while elapsed < wait_seconds:
            try:
                seq = stage_actor.get_editor_property("level_sequence")
                if seq:
                    break
            except Exception:
                seq = None
            time.sleep(poll_interval)
            elapsed += poll_interval

        if not seq:
            # Log a helpful diagnostic: list all UsdStageActors and whether they have sequences
            unreal.log_warning("[USD Import] LevelSequence not available immediately after import. Listing existing UsdStageActors and their level_sequence property:")
            for a in _get_all_level_actors():
                try:
                    if isinstance(a, unreal.UsdStageActor):
                        try:
                            ls = a.get_editor_property("level_sequence")
                        except Exception:
                            ls = None
                        unreal.log(f"  Actor: {a.get_actor_label()} name:{a.get_name()} level_sequence:{'YES' if ls else 'NO'}")
                except Exception:
                    pass

            # Still return success — stage actor exists and user can hit Reload Stage manually.
            unreal.log("[USD Import] Import completed but LevelSequence not found immediately. Please click Reload Stage in the USD Stage Editor; the sequence should appear and you can then press Play.")
            unreal.log("============================================================")
            return {"success": True, "stage_actor": stage_actor, "level_sequence": None}

        # We found a sequence — apply metadata to it immediately so editor shows proper brackets on first import
        try:
            apply_metadata_to_sequence(seq, start_frame, end_frame, fps)
        except Exception:
            unreal.log_warning("[USD Import] Failed to apply metadata to LevelSequence")

        unreal.log("[USD Import] Initial import complete and sequence configured.")
        unreal.log("============================================================")
        return {"success": True, "stage_actor": stage_actor, "level_sequence": seq}

    except Exception:
        unreal.log_error("[USD Import] Exception in import_usda_to_stage:\n" + traceback.format_exc())
        return {"success": False, "error": "exception"}


# --------------------------
# Backwards-compatible wrapper: plugin may call import_camera
# --------------------------
def import_camera(file_path: str, metadata: dict = None):
    if metadata is None:
        metadata = {}
    try:
        if "fps" in metadata:
            metadata["fps"] = int(metadata["fps"])
        if "start_frame" in metadata:
            metadata["start_frame"] = int(metadata["start_frame"])
        if "end_frame" in metadata:
            metadata["end_frame"] = int(metadata["end_frame"])
    except Exception:
        pass
    return import_usda_to_stage(file_path, metadata)

