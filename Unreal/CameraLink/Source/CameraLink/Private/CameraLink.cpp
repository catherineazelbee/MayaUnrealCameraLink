// Copyright Epic Games, Inc. All Rights Reserved.

#include "CameraLink.h"
#include "CameraLinkStyle.h"
#include "CameraLinkCommands.h"
#include "Misc/MessageDialog.h"
#include "ToolMenus.h"
#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"
#include "Framework/Application/SlateApplication.h"
#include "IPythonScriptPlugin.h"
#include "Modules/ModuleManager.h"

static const FName CameraLinkTabName("CameraLink");

#define LOCTEXT_NAMESPACE "FCameraLinkModule"

void FCameraLinkModule::StartupModule()
{
	FCameraLinkStyle::Initialize();
	FCameraLinkStyle::ReloadTextures();

	FCameraLinkCommands::Register();
	
	PluginCommands = MakeShareable(new FUICommandList);

	PluginCommands->MapAction(
		FCameraLinkCommands::Get().PluginAction,
		FExecuteAction::CreateRaw(this, &FCameraLinkModule::PluginButtonClicked),
		FCanExecuteAction());

	UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FCameraLinkModule::RegisterMenus));
}

void FCameraLinkModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);
	UToolMenus::UnregisterOwner(this);
	FCameraLinkStyle::Shutdown();
	FCameraLinkCommands::Unregister();
}

void FCameraLinkModule::PluginButtonClicked()
{
	// Get the desktop platform for file dialog
	IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
	if (!DesktopPlatform)
	{
		FMessageDialog::Open(EAppMsgType::Ok, 
			LOCTEXT("NoDesktopPlatform", "Could not open file dialog."));
		return;
	}

	// Get parent window handle
	const void* ParentWindowHandle = FSlateApplication::Get().GetActiveTopLevelWindow()->GetNativeWindow()->GetOSWindowHandle();

	// Open file dialog
	TArray<FString> OutFiles;
	bool bOpened = DesktopPlatform->OpenFileDialog(
		ParentWindowHandle,
		TEXT("Select USD Camera File"),
		FPaths::GetProjectFilePath(),  // Default path
		TEXT(""),                       // Default file
		TEXT("USD Files (*.usda;*.usd)|*.usda;*.usd|All Files (*.*)|*.*"),
		EFileDialogFlags::None,
		OutFiles
	);

	if (bOpened && OutFiles.Num() > 0)
	{
		FString SelectedFile = OutFiles[0];
		
		// Normalize path separators for Python (use forward slashes)
		SelectedFile = SelectedFile.Replace(TEXT("\\"), TEXT("/"));
		
		// Execute Python import
		ExecutePythonImport(SelectedFile);
	}
}

void FCameraLinkModule::ExecutePythonImport(const FString& FilePath)
{
	// Check if Python plugin is available
	IPythonScriptPlugin* PythonPlugin = FModuleManager::GetModulePtr<IPythonScriptPlugin>("PythonScriptPlugin");
	
	if (!PythonPlugin)
	{
		FMessageDialog::Open(EAppMsgType::Ok,
			LOCTEXT("NoPython", "Python Script Plugin is not available. Please enable it in Plugins."));
		return;
	}

	// Build Python command to import camera
	// This calls our import module with the selected file path
	FString PythonCommand = FString::Printf(
		TEXT("import unreal_usd_camera_import; unreal_usd_camera_import.import_camera(r\"%s\")"),
		*FilePath
	);

	// Execute the Python command
	TArray<FString> CommandArgs;
	bool bSuccess = PythonPlugin->ExecPythonCommand(*PythonCommand);

	if (!bSuccess)
	{
		FMessageDialog::Open(EAppMsgType::Ok,
			FText::Format(
				LOCTEXT("PythonError", "Failed to execute Python import.\n\nMake sure 'unreal_usd_camera_import.py' is in your project's Content/Python folder.\n\nFile: {0}"),
				FText::FromString(FilePath)
			));
	}
}

void FCameraLinkModule::RegisterMenus()
{
	FToolMenuOwnerScoped OwnerScoped(this);

	// Add to Window menu
	{
		UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Window");
		{
			FToolMenuSection& Section = Menu->FindOrAddSection("WindowLayout");
			Section.AddMenuEntryWithCommandList(FCameraLinkCommands::Get().PluginAction, PluginCommands);
		}
	}

	// Add toolbar button
	{
		UToolMenu* ToolbarMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.LevelEditorToolBar.PlayToolBar");
		{
			FToolMenuSection& Section = ToolbarMenu->FindOrAddSection("PluginTools");
			{
				FToolMenuEntry& Entry = Section.AddEntry(FToolMenuEntry::InitToolBarButton(FCameraLinkCommands::Get().PluginAction));
				Entry.SetCommandList(PluginCommands);
			}
		}
	}
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FCameraLinkModule, CameraLink)