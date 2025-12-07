
"""
Unreal USD Camera Importer
Imports a USD camera with animation into Unreal Engine and creates a Level Sequence.

USAGE
-----
1) Place this file in your project's Content/Python folder (or plugin's Content/Python)
2) In Unreal's Python console:
       import unreal_usd_camera_import
       unreal_usd_camera_import.import_camera(r"C:/path/to/camera.usda")
"""

import os
import unreal


def import_camera(file_path: str):
    """
    Import USD camera with animation into Unreal.
    Creates a UsdStageActor AND a saved Level Sequence asset.
    """
    if not file_path:
        unreal.log_error("[USD Import] No file path provided!")
        return None
    
    # Normalize path
    file_path = file_path.replace("\\", "/")
    abs_file_path = os.path.abspath(file_path)
    
    if not os.path.exists(abs_file_path):
        unreal.log_error(f"[USD Import] File not found: {abs_file_path}")
        return None
    
    unreal.log("=" * 60)
    unreal.log("[USD Import] Starting camera import")
    unreal.log(f"[USD Import] File: {abs_file_path}")
    
    # Read USD metadata
    metadata = _read_usd_metadata(abs_file_path)
    
    # Get base name for assets
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Import via stage actor
    stage_actor = _create_stage_actor(abs_file_path, base_name)
    
    if not stage_actor:
        unreal.log_error("[USD Import] Failed to create stage actor")
        return None
    
    # ALWAYS create and save a Level Sequence
    level_sequence = _create_and_save_level_sequence(stage_actor, base_name, metadata)
    
    if level_sequence:
        # Open in Sequencer
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(level_sequence)
        
        unreal.log("=" * 60)
        unreal.log("[USD Import] SUCCESS!")
        unreal.log(f"[USD Import] Stage Actor: {stage_actor.get_actor_label()}")
        unreal.log(f"[USD Import] Level Sequence: /Game/Cinematics/LS_{base_name}")
        unreal.log(f"[USD Import] Animation: frames {metadata.get('start_frame')}-{metadata.get('end_frame')} @ {metadata.get('fps')}fps")
        unreal.log("[USD Import] → Sequence saved to Content/Cinematics/")
        unreal.log("[USD Import] → You can now add this as a Subsequence in other sequences!")
        unreal.log("=" * 60)
        
        return {
            "success": True,
            "stage_actor": stage_actor,
            "level_sequence": level_sequence,
            "sequence_path": f"/Game/Cinematics/LS_{base_name}"
        }
    else:
        unreal.log_warning("[USD Import] Stage actor created but Level Sequence failed")
        return {
            "success": True,
            "stage_actor": stage_actor,
            "level_sequence": None
        }


def _read_usd_metadata(file_path: str):
    """Read animation metadata from USD file."""
    metadata = {
        "has_animation": False,
        "start_frame": 1,
        "end_frame": 100,
        "fps": 24,
    }
    
    try:
        from pxr import Sdf, Usd, UsdGeom
        
        stage = Usd.Stage.Open(file_path)
        if not stage:
            return metadata
        
        # Get timing from stage
        metadata["fps"] = stage.GetTimeCodesPerSecond() or 24
        metadata["start_frame"] = stage.GetStartTimeCode() or 1
        metadata["end_frame"] = stage.GetEndTimeCode() or 100
        
        # Check for custom metadata
        root_layer = stage.GetRootLayer()
        custom_data = root_layer.customLayerData or {}
        
        if custom_data.get("layoutlink_has_animation"):
            metadata["has_animation"] = True
            metadata["start_frame"] = custom_data.get("layoutlink_start_frame", metadata["start_frame"])
            metadata["end_frame"] = custom_data.get("layoutlink_end_frame", metadata["end_frame"])
            metadata["fps"] = custom_data.get("layoutlink_fps", metadata["fps"])
        
        # Check for time samples
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
        
        unreal.log(f"[USD Import] Metadata: frames {metadata['start_frame']}-{metadata['end_frame']}, fps={metadata['fps']}")
        
    except ImportError:
        unreal.log_warning("[USD Import] pxr module not available - using defaults")
    except Exception as e:
        unreal.log_warning(f"[USD Import] Could not read metadata: {e}")
    
    return metadata


def _create_stage_actor(file_path: str, base_name: str):
    """Create and configure the UsdStageActor."""
    try:
        # Get editor world
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        
        if not world:
            unreal.log_error("[USD Import] No editor world")
            return None
        
        # Spawn stage actor
        stage_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.UsdStageActor.static_class(),
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0)
        )
        
        if not stage_actor:
            return None
        
        # Configure
        stage_actor.set_actor_label(f"USD_Cam_{base_name}")
        stage_actor.set_editor_property("root_layer", {"file_path": file_path})
        stage_actor.set_editor_property("time", 0.0)
        
        unreal.log(f"[USD Import] Created UsdStageActor: {stage_actor.get_actor_label()}")
        
        return stage_actor
        
    except Exception as e:
        unreal.log_error(f"[USD Import] Stage actor creation failed: {e}")
        return None


def _create_and_save_level_sequence(stage_actor, base_name: str, metadata: dict):
    """
    Create a Level Sequence that drives the UsdStageActor's Time property.
    This sequence is SAVED to Content/Cinematics/ so it can be used as a Subsequence.
    """
    try:
        start_frame = int(metadata.get("start_frame", 1))
        end_frame = int(metadata.get("end_frame", 100))
        fps = int(metadata.get("fps", 24))
        
        # Asset path
        sequence_path = "/Game/Cinematics"
        sequence_name = f"LS_{base_name}"
        full_asset_path = f"{sequence_path}/{sequence_name}"
        
        # Ensure directory exists
        if not unreal.EditorAssetLibrary.does_directory_exist(sequence_path):
            unreal.EditorAssetLibrary.make_directory(sequence_path)
            unreal.log(f"[USD Import] Created directory: {sequence_path}")
        
        # Delete existing sequence with same name
        if unreal.EditorAssetLibrary.does_asset_exist(full_asset_path):
            unreal.EditorAssetLibrary.delete_asset(full_asset_path)
            unreal.log(f"[USD Import] Replaced existing sequence: {full_asset_path}")
        
        # Create Level Sequence
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        level_sequence = asset_tools.create_asset(
            sequence_name,
            sequence_path,
            unreal.LevelSequence,
            unreal.LevelSequenceFactoryNew()
        )
        
        if not level_sequence:
            unreal.log_error("[USD Import] Failed to create Level Sequence asset")
            return None
        
        unreal.log(f"[USD Import] Created Level Sequence: {full_asset_path}")
        
        # Configure timing
        frame_rate = unreal.FrameRate(fps, 1)
        level_sequence.set_display_rate(frame_rate)
        level_sequence.set_playback_start(start_frame)
        level_sequence.set_playback_end(end_frame)
        level_sequence.set_view_range_start(float(start_frame - 10))
        level_sequence.set_view_range_end(float(end_frame + 10))
        
        # Bind the stage actor
        binding = level_sequence.add_possessable(stage_actor)
        
        if binding:
            unreal.log("[USD Import] Bound stage actor to sequence")
            
            # Add Time track to drive USD animation
            movie_scene = level_sequence.get_movie_scene()
            binding_id = binding.get_id()
            
            try:
                # Create float track for Time property
                time_track = movie_scene.add_track(unreal.MovieSceneFloatTrack, binding_id)
                
                if time_track:
                    time_track.set_property_name_and_path("Time", "Time")
                    
                    # Add section
                    time_section = time_track.add_section()
                    time_section.set_start_frame(start_frame)
                    time_section.set_end_frame(end_frame)
                    
                    # Try to add keyframes for Time property
                    # Start frame: Time = start_frame, End frame: Time = end_frame
                    try:
                        channels = time_section.get_all_channels()
                        if channels:
                            float_channel = channels[0]
                            
                            # Add keyframes
                            time_start = unreal.FrameNumber(start_frame)
                            time_end = unreal.FrameNumber(end_frame)
                            
                            float_channel.add_key(time_start, float(start_frame), 0.0)
                            float_channel.add_key(time_end, float(end_frame), 0.0)
                            
                            unreal.log(f"[USD Import] Added Time keyframes: {start_frame} -> {end_frame}")
                    except Exception as e:
                        unreal.log_warning(f"[USD Import] Could not add keyframes automatically: {e}")
                        unreal.log("[USD Import] Please manually keyframe Time: frame 1 = 1.0, last frame = end value")
                    
            except Exception as e:
                unreal.log_warning(f"[USD Import] Could not add Time track: {e}")
        
        # IMPORTANT: Save the sequence asset!
        unreal.EditorAssetLibrary.save_asset(full_asset_path)
        unreal.log(f"[USD Import] Saved Level Sequence to: {full_asset_path}")
        
        return level_sequence
        
    except Exception as e:
        unreal.log_error(f"[USD Import] Level Sequence creation failed: {e}")
        import traceback
        unreal.log(traceback.format_exc())
        return None


def print_usd_debug(file_path: str):
    """Debug helper: Print USD file structure info."""
    if not file_path:
        unreal.log_error("[USD Debug] No file path provided!")
        return
    
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
        
        unreal.log("  Prims:")
        for prim in stage.Traverse():
            unreal.log(f"    {prim.GetPath()} ({prim.GetTypeName()})")
            
            if prim.IsA(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(prim)
                for op in xformable.GetOrderedXformOps():
                    times = op.GetTimeSamples()
                    if times:
                        unreal.log(f"      {op.GetOpName()}: {len(times)} samples")
        
        unreal.log("=" * 60)
        
    except Exception as e:
        unreal.log_error(f"[USD Debug] Error: {e}")