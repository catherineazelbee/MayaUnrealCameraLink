// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class CameraLink : ModuleRules
{
	public CameraLink(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		
		PublicIncludePaths.AddRange(
			new string[] {
			}
		);
				
		PrivateIncludePaths.AddRange(
			new string[] {
			}
		);
			
		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
			}
		);
			
		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"Projects",
				"CoreUObject",
				"Engine",
				"Slate",
				"SlateCore",
				"USDStage",
				"DesktopPlatform",
				"PythonScriptPlugin"
			}
		);
		
if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(
				new string[] {
					"UnrealEd",
					"LevelEditor",
					"ToolMenus"
				});
		}
	}
}