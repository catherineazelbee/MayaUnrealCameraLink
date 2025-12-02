// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Modules/ModuleManager.h"

class FToolBarBuilder;
class FMenuBuilder;

class FCameraLinkModule : public IModuleInterface
{
public:

	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	
	/** Called when toolbar button is clicked - opens file dialog */
	void PluginButtonClicked();
	
private:

	void RegisterMenus();

	/** Execute Python import script with the given USD file path */
	void ExecutePythonImport(const FString& FilePath);


private:
	TSharedPtr<class FUICommandList> PluginCommands;
};
