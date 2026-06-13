// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "UnrealMCPBridge.generated.h"

class FMCPServerRunnable;
class FSocket;
class FJsonObject;

/**
 * Editor subsystem that hosts the MCP bridge: a local TCP server inside the
 * Unreal Editor. External MCP clients connect, send JSON commands, and the
 * bridge marshals execution onto the game thread before replying.
 */
UCLASS()
class UNREALMCP_API UUnrealMCPBridge : public UEditorSubsystem
{
	GENERATED_BODY()

public:
	// UEditorSubsystem interface
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	void StartServer();
	void StopServer();
	bool IsRunning() const { return bIsRunning; }

	/**
	 * Dispatches a command on the game thread and returns the serialized JSON response.
	 * Called from the server worker thread; blocks until the game thread completes.
	 */
	FString ExecuteCommand(const FString& CommandType, const TSharedPtr<FJsonObject>& Params);

private:
	// Command handlers (run on the game thread). Each returns a "result" object that
	// may set a boolean "success" field and, on failure, an "error" string.
	TSharedPtr<FJsonObject> HandlePing(const TSharedPtr<FJsonObject>& Params);
	TSharedPtr<FJsonObject> HandleExecutePython(const TSharedPtr<FJsonObject>& Params);

	bool bIsRunning = false;
	TSharedPtr<FSocket> ListenerSocket;
	FRunnableThread* ServerThread = nullptr;

	FIPv4Address ServerAddress;
	uint16 Port = 0;
};
