"""
Unreal USD Camera Importer - CameraLink
Imports a USD camera with animation into Unreal Engine and creates a Level Sequence.

USAGE
-----
This is called automatically by the CameraLink C++ plugin when you select a USD file.
"""

import os
import unreal

def import_camera(file_path: str):
    """
    Import USD camera with animation into Unreal.
    
    Args:
        file_path: Path to the .usda file to import
        
    This uses the UsdStageActor approach which streams USD data
    and can generate a LevelSequence from animated timeSamples.
    """
    if not file_path:
        unreal.log_error("[CameraLink] No file path provided!")
        return None
    
    # Normalize path with forward slashes
    file_path = file_path.replace("\\", "/")
    abs_file_path = os.path.abspath(file_path)
    
    if not os.path.exists(abs_file_path):
        unreal.log_error(f"[CameraLink] File not found: {abs_file_path}")
        return None
    
    unreal.log("=" * 60)
    unreal.log("[CameraLink] Starting camera import")
    unreal.log(f"[CameraLink] File: {abs_file_path}")
    
    # Get file size to verify it has animation data
    file_size = os.path.getsize(abs_file_path)
    unreal.log(f"[CameraLink] File size: {file_size} bytes")
    if file_size < 1000:
        unreal.log_warning("[CameraLink] File seems small - may not contain animation data")
    
    # Read USD metadata first
    metadata = _read_usd_metadata(abs_file_path)
    
    # Import via stage actor
    result = _import_via_stage_actor(abs_file_path, metadata)
    
    if result and result.get("success"):
        unreal.log("=" * 60)
        unreal.log("[CameraLink] SUCCESS - Camera imported")
        if result.get("has_animation"):
            seq_name = result.get("level_sequence").get_name() if result.get("level_sequence") else "Unknown"
            unreal.log(f"[CameraLink] Animation: frames {metadata.get('start_frame', '?')}-{metadata.get('end_frame', '?')} @ {metadata.get('fps', '?')}fps")
            unreal.log(f"[CameraLink] Level Sequence: {seq_name} (transient)")
            unreal.log("")
            unreal.log("[CameraLink] TO RENDER WITH USD CAMERA (live-linked):")
            unreal.log(f"[CameraLink]   1. Open '{seq_name}' sequence")
            unreal.log("[CameraLink]   2. Add Camera Cut track → set to imported camera")
            unreal.log("[CameraLink]   3. Add other animation/subsequences INTO this sequence")
            unreal.log("[CameraLink]   4. Render from this sequence")
            unreal.log("")
            unreal.log("[CameraLink] TO CONVERT TO NATIVE UNREAL (for use in other sequences):")
            unreal.log("[CameraLink]   1. Select UsdStageActor in Outliner")
            unreal.log("[CameraLink]   2. USD Stage Editor → Actions → Import")
            unreal.log("[CameraLink]   3. This creates a native CineCameraActor + saved sequence")
            unreal.log("")
            unreal.log("[CameraLink] TO UPDATE FROM MAYA:")
            unreal.log("[CameraLink]   1. Export updated camera from Maya")
            unreal.log("[CameraLink]   2. Select UsdStageActor → USD Stage Editor → Reload")
            unreal.log("[CameraLink]   NOTE: Reload removes any manually added tracks/actors")
        unreal.log("=" * 60)
    
    return result


def _read_usd_metadata(file_path: str):
    """
    Read animation metadata from USD file.
    Returns dict with has_animation, start_frame, end_frame, fps.
    """
    metadata = {
        "has_animation": False,
        "start_frame": 1,
        "end_frame": 120,
        "fps": 24
    }
    
    try:
        from pxr import Sdf, Usd, UsdGeom
        
        stage = Usd.Stage.Open(file_path)
        if not stage:
            unreal.log_warning("[CameraLink] Could not open stage for metadata")
            return metadata
        
        # Read USD stage-level timing metadata
        usd_fps = stage.GetTimeCodesPerSecond()
        usd_start = stage.GetStartTimeCode()
        usd_end = stage.GetEndTimeCode()
        
        unreal.log(f"[CameraLink] USD Stage Metadata:")
        unreal.log(f"  timeCodesPerSecond: {usd_fps}")
        unreal.log(f"  startTimeCode: {usd_start}")
        unreal.log(f"  endTimeCode: {usd_end}")
        
        # Check for CameraLink custom metadata
        root_layer = stage.GetRootLayer()
        custom_data = root_layer.customLayerData or {}
        
        if custom_data.get("cameralink_has_animation"):
            unreal.log("[CameraLink] Found CameraLink custom metadata")
            metadata["has_animation"] = True
            metadata["start_frame"] = custom_data.get("cameralink_start_frame", metadata["start_frame"])
            metadata["end_frame"] = custom_data.get("cameralink_end_frame", metadata["end_frame"])
            metadata["fps"] = custom_data.get("cameralink_fps", metadata["fps"])
        else:
            # Fallback: check for time samples on prims
            unreal.log("[CameraLink] No custom metadata, scanning for time samples...")
            for prim in stage.Traverse():
                if prim.IsA(UsdGeom.Xformable):
                    xformable = UsdGeom.Xformable(prim)
                    for op in xformable.GetOrderedXformOps():
                        times = op.GetTimeSamples()
                        if times and len(times) > 1:
                            metadata["has_animation"] = True
                            metadata["start_frame"] = min(times)
                            metadata["end_frame"] = max(times)
                            metadata["fps"] = usd_fps if usd_fps else 24
                            unreal.log(f"[CameraLink] Found animation from time samples: {len(times)} samples")
                            break
                    if metadata["has_animation"]:
                        break
        
        unreal.log(f"[CameraLink] Final Metadata: animation={metadata['has_animation']}, "
                   f"frames={metadata['start_frame']}-{metadata['end_frame']}, fps={metadata['fps']}")
        
    except ImportError:
        unreal.log_warning("[CameraLink] pxr module not available - cannot read metadata")
        unreal.log_warning("[CameraLink] Will import camera but may not have correct timing")
    except Exception as e:
        unreal.log_warning(f"[CameraLink] Could not read metadata: {e}")
    
    return metadata


def _import_via_stage_actor(file_path: str, metadata: dict):
    """
    Import USD via UsdStageActor - ALWAYS creates new actor (like LayoutLink).
    User manually reloads existing actors via USD Stage Editor.
    """
    try:
        # Get world
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        
        if not world:
            unreal.log_error("[CameraLink] No editor world available")
            return None
        
        # ALWAYS spawn new stage actor (like LayoutLink does)
        location = unreal.Vector(0, 0, 0)
        rotation = unreal.Rotator(0, 0, 0)
        
        stage_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.UsdStageActor.static_class(),
            location,
            rotation
        )
        
        if not stage_actor:
            unreal.log_error("[CameraLink] Failed to spawn UsdStageActor")
            return None
        
        # Set descriptive label (like LayoutLink uses "MayaLayoutImport")
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        stage_actor.set_actor_label(f"CameraLink_{base_name}")
        unreal.log(f"[CameraLink] Spawned UsdStageActor: {stage_actor.get_name()}")
        
        # Set the root layer
        stage_actor.set_editor_property("root_layer", {"file_path": file_path})
        stage_actor.set_editor_property("time", 1.0)
        
        unreal.log("[CameraLink] Root layer set successfully")
        
        # Setup Level Sequence for animation
        level_sequence = None
        has_animation = metadata.get("has_animation", False)
        
        if has_animation:
            unreal.log("[CameraLink] Setting up animation...")
            
            # Get the Level Sequence that USD Stage Actor automatically creates
            level_sequence = stage_actor.get_editor_property("level_sequence")
            
            if level_sequence:
                unreal.log(f"[CameraLink] Found Level Sequence: {level_sequence.get_name()}")
                
                # Configure timing
                fps = int(metadata.get("fps", 24))
                start_frame = int(metadata.get("start_frame", 1))
                end_frame = int(metadata.get("end_frame", 120))
                
                unreal.log(f"[CameraLink] Configuring sequence: {start_frame}-{end_frame} @ {fps}fps")
                
                frame_rate = unreal.FrameRate(numerator=fps, denominator=1)
                level_sequence.set_display_rate(frame_rate)
                level_sequence.set_tick_resolution(frame_rate)
                
                level_sequence.set_playback_start(start_frame)
                level_sequence.set_playback_end(end_frame)
                
                # Set view range with padding
                level_sequence.set_view_range_start(float(start_frame - 10))
                level_sequence.set_view_range_end(float(end_frame + 10))
                
                # Set working range to match playback
                level_sequence.set_work_range_start(float(start_frame))
                level_sequence.set_work_range_end(float(end_frame))
                
                unreal.log(f"[CameraLink] ✓ Sequence configured: {start_frame}-{end_frame} @ {fps}fps")
                
                # Open in Sequencer
                unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(level_sequence)
                unreal.log(f"[CameraLink] Opened Level Sequence: {level_sequence.get_path_name()}")
                
            else:
                unreal.log_warning("[CameraLink] Animation detected but no Level Sequence found!")
                unreal.log_warning("[CameraLink] Animation data is in USD but may not play automatically")
        else:
            unreal.log("[CameraLink] No animation detected - imported as static camera")
        
        return {
            "success": True,
            "stage_actor": stage_actor,
            "level_sequence": level_sequence,
            "has_animation": has_animation
        }
        
    except Exception as e:
        unreal.log_error(f"[CameraLink] Import failed: {e}")
        import traceback
        unreal.log(traceback.format_exc())
        return {"success": False, "error": str(e)}


def print_usd_debug(file_path: str):
    """
    Debug helper: Print USD file structure info.
    Call this to verify your USD file has animation data.
    
    Args:
        file_path: Path to the .usda file to inspect
    """
    if not file_path:
        unreal.log_error("[CameraLink Debug] No file path provided!")
        return
    
    file_path = file_path.replace("\\", "/")
    
    try:
        from pxr import Usd, UsdGeom
        
        stage = Usd.Stage.Open(file_path)
        if not stage:
            unreal.log_error("[CameraLink Debug] Could not open stage")
            return
        
        unreal.log("=" * 60)
        unreal.log("[CameraLink Debug] File structure:")
        
        root_layer = stage.GetRootLayer()
        custom_data = root_layer.customLayerData or {}
        if custom_data:
            unreal.log(f"  Custom metadata: {custom_data}")
        
        unreal.log("")
        unreal.log("  Prims:")
        for prim in stage.Traverse():
            unreal.log(f"    {prim.GetPath()} (type: {prim.GetTypeName()})")
            
            if prim.IsA(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(prim)
                for op in xformable.GetOrderedXformOps():
                    times = op.GetTimeSamples()
                    if times:
                        unreal.log(f"      Transform op '{op.GetOpName()}': {len(times)} time samples")
                        if len(times) <= 5:
                            unreal.log(f"        Frames: {times}")
                        else:
                            unreal.log(f"        Frames: {times[0]} ... {times[-1]}")
            
            if prim.IsA(UsdGeom.Camera):
                camera = UsdGeom.Camera(prim)
                focal_attr = camera.GetFocalLengthAttr()
                times = focal_attr.GetTimeSamples()
                if times:
                    unreal.log(f"      FocalLength: {len(times)} time samples")
        
        unreal.log("=" * 60)
        
    except ImportError:
        unreal.log_error("[CameraLink Debug] pxr module not available")
    except Exception as e:
        unreal.log_error(f"[CameraLink Debug] Error: {e}")
        import traceback
        unreal.log(traceback.format_exc())