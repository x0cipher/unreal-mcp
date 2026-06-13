// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "HAL/Runnable.h"
#include "HAL/ThreadSafeBool.h"

class UUnrealMCPBridge;
class FSocket;

/**
 * Worker thread that owns the TCP accept loop for the MCP bridge.
 *
 * Protocol: each client opens a connection, sends a single JSON object
 * { "type": <command>, "params": { ... } }, reads the JSON response, then the
 * server closes the connection. One command per connection keeps framing trivial.
 */
class FMCPServerRunnable : public FRunnable
{
public:
	FMCPServerRunnable(UUnrealMCPBridge* InBridge, TSharedPtr<FSocket> InListenerSocket);
	virtual ~FMCPServerRunnable();

	// FRunnable interface
	virtual bool Init() override;
	virtual uint32 Run() override;
	virtual void Stop() override;
	virtual void Exit() override;

private:
	/** Reads one full JSON request from a connected client, dispatches it, and sends the response. */
	void HandleConnection(const TSharedPtr<FSocket>& Client);

	UUnrealMCPBridge* Bridge;
	TSharedPtr<FSocket> ListenerSocket;
	FThreadSafeBool bRunning;
};
