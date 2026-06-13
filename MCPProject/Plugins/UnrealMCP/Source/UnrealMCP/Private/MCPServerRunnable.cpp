// Copyright Epic Games, Inc. All Rights Reserved.

#include "MCPServerRunnable.h"
#include "UnrealMCPBridge.h"
#include "Sockets.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"

DEFINE_LOG_CATEGORY_STATIC(LogUnrealMCPServer, Log, All);

// Max time we will wait to accumulate a single request before giving up on a connection.
static const double GRequestTimeoutSeconds = 30.0;

FMCPServerRunnable::FMCPServerRunnable(UUnrealMCPBridge* InBridge, TSharedPtr<FSocket> InListenerSocket)
	: Bridge(InBridge)
	, ListenerSocket(InListenerSocket)
	, bRunning(true)
{
}

FMCPServerRunnable::~FMCPServerRunnable()
{
}

bool FMCPServerRunnable::Init()
{
	return true;
}

uint32 FMCPServerRunnable::Run()
{
	UE_LOG(LogUnrealMCPServer, Display, TEXT("MCP server thread started"));

	while (bRunning)
	{
		bool bHasPending = false;
		if (ListenerSocket.IsValid() && ListenerSocket->HasPendingConnection(bHasPending) && bHasPending)
		{
			FSocket* RawClient = ListenerSocket->Accept(TEXT("UnrealMCPClient"));
			if (RawClient)
			{
				TSharedPtr<FSocket> Client = MakeShareable(RawClient);
				Client->SetNonBlocking(false);
				HandleConnection(Client);
				Client->Close();
				Client.Reset();
			}
		}

		// Avoid a tight spin while idle.
		FPlatformProcess::Sleep(0.02f);
	}

	UE_LOG(LogUnrealMCPServer, Display, TEXT("MCP server thread stopped"));
	return 0;
}

void FMCPServerRunnable::HandleConnection(const TSharedPtr<FSocket>& Client)
{
	FString Accumulated;
	uint8 Buffer[65536];
	const double StartTime = FPlatformTime::Seconds();

	while (bRunning)
	{
		int32 BytesRead = 0;
		const bool bRecvOk = Client->Recv(Buffer, sizeof(Buffer) - 1, BytesRead);

		if (bRecvOk && BytesRead > 0)
		{
			Buffer[BytesRead] = 0;
			Accumulated += FString(UTF8_TO_TCHAR(reinterpret_cast<const ANSICHAR*>(Buffer)));

			// Try to parse what we have so far. A successful parse means the request is complete.
			TSharedPtr<FJsonObject> JsonObject;
			TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Accumulated);
			if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
			{
				FString CommandType;
				if (!JsonObject->TryGetStringField(TEXT("type"), CommandType))
				{
					UE_LOG(LogUnrealMCPServer, Warning, TEXT("Request missing 'type' field: %s"), *Accumulated);
					return;
				}

				TSharedPtr<FJsonObject> Params;
				const TSharedPtr<FJsonObject>* ParamsPtr = nullptr;
				if (JsonObject->TryGetObjectField(TEXT("params"), ParamsPtr) && ParamsPtr)
				{
					Params = *ParamsPtr;
				}
				else
				{
					Params = MakeShared<FJsonObject>();
				}

				UE_LOG(LogUnrealMCPServer, Display, TEXT("Dispatching command: %s"), *CommandType);
				const FString Response = Bridge->ExecuteCommand(CommandType, Params);

				FTCHARToUTF8 Utf8Response(*Response);
				int32 BytesSent = 0;
				Client->Send(reinterpret_cast<const uint8*>(Utf8Response.Get()), Utf8Response.Length(), BytesSent);
				return;
			}
			// Not yet a complete JSON document — keep reading.
		}
		else if (!bRecvOk)
		{
			// Connection closed or errored before we got a full request.
			return;
		}

		if (FPlatformTime::Seconds() - StartTime > GRequestTimeoutSeconds)
		{
			UE_LOG(LogUnrealMCPServer, Warning, TEXT("Request timed out after %.0fs"), GRequestTimeoutSeconds);
			return;
		}
	}
}

void FMCPServerRunnable::Stop()
{
	bRunning = false;
}

void FMCPServerRunnable::Exit()
{
}
