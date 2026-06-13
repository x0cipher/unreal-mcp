// Copyright Epic Games, Inc. All Rights Reserved.

#include "UnrealMCPModule.h"

#define LOCTEXT_NAMESPACE "FUnrealMCPModule"

DEFINE_LOG_CATEGORY_STATIC(LogUnrealMCP, Log, All);

void FUnrealMCPModule::StartupModule()
{
	UE_LOG(LogUnrealMCP, Display, TEXT("UnrealMCP module started"));
}

void FUnrealMCPModule::ShutdownModule()
{
	UE_LOG(LogUnrealMCP, Display, TEXT("UnrealMCP module shut down"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUnrealMCPModule, UnrealMCP)
