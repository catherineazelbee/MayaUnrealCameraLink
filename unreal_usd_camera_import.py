"""
Unreal USD Camera Importer
Imports a USD camera with animation into Unreal Engine and creates a Level Sequence.

Based on working LayoutLink import pattern.

USAGE
-----
1) Place this file in your project's Content/Python folder
2) In Unreal's Python console:
       import unreal_usd_camera_import
       unreal_usd_camera_import.import_camera()
"""

import os
import unreal

# Hard-coded import path (use forward slashes for Unreal)
USD_FILE_PATH = "C:/Users/cathe/Downloads/camera.usda"


def import_camera(file_path: str = None):
    """
    Import USD camera with animation into Unreal.
    
    This uses the UsdStageActor approach which streams USD data
    and can generate a LevelSequence from animated timeSamples.
    """
    if file_path is None:
        file_path = USD_FILE_PATH
    
    # Normalize path with forward slashes
    file_path = file_path.replace("\\", "/")
    abs_file_path = os.path.abspath(file_path)
    
    if not os.path.exists(abs_file_path):
        unreal.log_error(f"[USD Import] File not found: {abs_file_path}")
        return None
    
    unreal.log("=" * 60)
    unreal.log("[USD Import] Starting camera import")
    unreal.log(f"[USD Import] File: {abs_file_path}")
    
    # Get file size to verify it has animation data
    file_size = os.path.getsize(abs_file_path)
    unreal.log(f"[USD Import] File size: {file_size} bytes")
    if file_size < 1000:
        unreal.log_warning("[USD Import] File seems small - may not contain animation data")
    
    # Read USD metadata first
    metadata = _read_usd_metadata(abs_file_path)
    
    # Import via stage actor (matching your working plugin)
    result = _import_via_stage_actor(abs_file_path, metadata)
    
    if result and result.get("success"):
        unreal.log("=" * 60)
        unreal.log("[USD Import] SUCCESS - Camera imported")
        if result.get("has_animation"):
            unreal.log(f"[USD Import] Animation: frames {metadata.get('start_frame', '?')}-{metadata.get('end_frame', '?')} @ {metadata.get('fps', '?')}fps")
            unreal.log("[USD Import] → Press PLAY in Sequencer to see animation")
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
        "fps": 24,
        "animated_count": 0
    }
    
    try:
        from pxr import Sdf, Usd, UsdGeom
        
        stage = Usd.Stage.Open(file_path)
        if not stage:
            unreal.log_warning("[USD Import] Could not open stage for metadata")
            return metadata
        
        # Get timing from stage
        metadata["fps"] = stage.GetTimeCodesPerSecond() or 24
        metadata["start_frame"] = stage.GetStartTimeCode() or 1
        metadata["end_frame"] = stage.GetEndTimeCode() or 120
        
        # Check for custom metadata
        root_layer = stage.GetRootLayer()
        custom_data = root_layer.customLayerData or {}
        
        if custom_data.get("layoutlink_has_animation"):
            metadata["has_animation"] = True
            metadata["start_frame"] = custom_data.get("layoutlink_start_frame", metadata["start_frame"])
            metadata["end_frame"] = custom_data.get("layoutlink_end_frame", metadata["end_frame"])
            metadata["fps"] = custom_data.get("layoutlink_fps", metadata["fps"])
            metadata["animated_count"] = custom_data.get("layoutlink_animated_objects", 0)
        
        # Also check for time samples on prims (in case metadata wasn't written)
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(prim)
                for op in xformable.GetOrderedXformOps():
                    times = op.GetTimeSamples()
                    if times and len(times) > 1:
                        metadata["has_animation"] = True
                        metadata["start_frame"] = min(metadata["start_frame"], min(times))
                        metadata["end_frame"] = max(metadata["end_frame"], max(times))
                        break
        
        unreal.log(f"[USD Import] Metadata: animation={metadata['has_animation']}, "
                   f"frames={metadata['start_frame']}-{metadata['end_frame']}, fps={metadata['fps']}")
        
    except ImportError:
        unreal.log_warning("[USD Import] pxr module not available - using defaults")
    except Exception as e:
        unreal.log_warning(f"[USD Import] Could not read metadata: {e}")
    
    return metadata


def _import_via_stage_actor(file_path: str, metadata: dict):
    """
    Import USD via UsdStageActor - matching your working LayoutLink pattern.
    """
    try:
        # Get world
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        
        if not world:
            unreal.log_error("[USD Import] No editor world available")
            return None
        
        # Spawn stage actor
        location = unreal.Vector(0, 0, 0)
        rotation = unreal.Rotator(0, 0, 0)
        
        stage_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.UsdStageActor.static_class(),
            location,
            rotation
        )
        
        if not stage_actor:
            unreal.log_error("[USD Import] Failed to spawn UsdStageActor")
            return None
        
        unreal.log(f"[USD Import] Spawned UsdStageActor: {stage_actor.get_name()}")
        
        # Set descriptive label
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        stage_actor.set_actor_label(f"USD_Camera_{base_name}")
        
        # Set the root layer (matching your working plugin's exact pattern)
        stage_actor.set_editor_property("root_layer", {"file_path": file_path})
        stage_actor.set_editor_property("time", 0.0)
        
        unreal.log("[USD Import] Root layer set successfully")
        
        # Setup Level Sequence for animation
        level_sequence = None
        has_animation = metadata.get("has_animation", False)
        
        if has_animation:
            unreal.log("[USD Import] Setting up animation...")
            
            # Get the Level Sequence that USD Stage Actor automatically creates
            level_sequence = stage_actor.get_editor_property("level_sequence")
            
            if level_sequence:
                unreal.log(f"[USD Import] Found Level Sequence: {level_sequence.get_name()}")
                
                # Configure timing
                fps = int(metadata.get("fps", 24))
                start_frame = int(metadata.get("start_frame", 1))
                end_frame = int(metadata.get("end_frame", 120))
                
                frame_rate = unreal.FrameRate(numerator=fps, denominator=1)
                level_sequence.set_display_rate(frame_rate)
                level_sequence.set_tick_resolution(frame_rate)
                
                level_sequence.set_playback_start(start_frame)
                level_sequence.set_playback_end(end_frame)
                
                # Set view range with padding
                level_sequence.set_view_range_start(float(start_frame - 10))
                level_sequence.set_view_range_end(float(end_frame + 10))
                
                unreal.log(f"[USD Import] Configured sequence: {start_frame}-{end_frame} @ {fps}fps")
                
                # Open in Sequencer
                unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(level_sequence)
                unreal.log("[USD Import] Opened Level Sequence in Sequencer")
                
            else:
                unreal.log_warning("[USD Import] Animation detected but no Level Sequence found!")
                unreal.log_warning("[USD Import] Animation data is in USD but may not play automatically")
        else:
            unreal.log("[USD Import] No animation detected - imported as static camera")
        
        return {
            "success": True,
            "stage_actor": stage_actor,
            "level_sequence": level_sequence,
            "has_animation": has_animation
        }
        
    except Exception as e:
        unreal.log_error(f"[USD Import] Import failed: {e}")
        import traceback
        unreal.log(traceback.format_exc())
        return {"success": False, "error": str(e)}





def print_usd_debug(file_path: str = None):
    """
    Debug helper: Print USD file structure info.
    Call this to verify your USD file has animation data.
    """
    if file_path is None:
        file_path = USD_FILE_PATH
    
    file_path = file_path.replace("\\", "/")
    
    try:
        from pxr import Usd, UsdGeom
        
        stage = Usd.Stage.Open(file_path)
        if not stage:
            unreal.log_error("[USD Debug] Could not open stage")
            return
        
        unreal.log("=" * 60)
        unreal.log("[USD Debug] File structure:")
        unreal.log(f"  TimeCodesPerSecond: {stage.GetTimeCodesPerSecond()}")
        unreal.log(f"  StartTimeCode: {stage.GetStartTimeCode()}")
        unreal.log(f"  EndTimeCode: {stage.GetEndTimeCode()}")
        
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
        unreal.log_error("[USD Debug] pxr module not available")
    except Exception as e:
        unreal.log_error(f"[USD Debug] Error: {e}")
        import traceback
        unreal.log(traceback.format_exc())


# Convenience function to run on import
if __name__ == "__main__":
    import_camera()