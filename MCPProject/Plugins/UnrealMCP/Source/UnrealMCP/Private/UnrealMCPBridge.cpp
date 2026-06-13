// Copyright Epic Games, Inc. All Rights Reserved.

#include "UnrealMCPBridge.h"
#include "MCPServerRunnable.h"

#include "Sockets.h"
#include "SocketSubsystem.h"
#include "HAL/RunnableThread.h"
#include "Interfaces/IPv4/IPv4Endpoint.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Async/Async.h"

#include "IPythonScriptPlugin.h"
#include "PythonScriptTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogUnrealMCPBridge, Log, All);

namespace
{
	const TCHAR* MCPServerHost = TEXT("127.0.0.1");
	constexpr uint16 MCPServerPort = 55557;

	/** Serializes a JSON object to a compact string. */
	FString SerializeJson(const TSharedPtr<FJsonObject>& JsonObject)
	{
		FString Output;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Output);
		FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
		return Output;
	}
}

void UUnrealMCPBridge::Initialize(FSubsystemCollectionBase& Collection)
{
	UE_LOG(LogUnrealMCPBridge, Display, TEXT("UnrealMCPBridge initializing"));

	bIsRunning = false;
	ListenerSocket = nullptr;
	ServerThread = nullptr;
	Port = MCPServerPort;
	FIPv4Address::Parse(MCPServerHost, ServerAddress);

	StartServer();
}

void UUnrealMCPBridge::Deinitialize()
{
	UE_LOG(LogUnrealMCPBridge, Display, TEXT("UnrealMCPBridge shutting down"));
	StopServer();
}

void UUnrealMCPBridge::StartServer()
{
	if (bIsRunning)
	{
		UE_LOG(LogUnrealMCPBridge, Warning, TEXT("Server already running"));
		return;
	}

	ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
	if (!SocketSubsystem)
	{
		UE_LOG(LogUnrealMCPBridge, Error, TEXT("Failed to get socket subsystem"));
		return;
	}

	TSharedPtr<FSocket> NewListener = MakeShareable(SocketSubsystem->CreateSocket(NAME_Stream, TEXT("UnrealMCPListener"), false));
	if (!NewListener.IsValid())
	{
		UE_LOG(LogUnrealMCPBridge, Error, TEXT("Failed to create listener socket"));
		return;
	}

	NewListener->SetReuseAddr(true);
	NewListener->SetNonBlocking(true);

	const FIPv4Endpoint Endpoint(ServerAddress, Port);
	if (!NewListener->Bind(*Endpoint.ToInternetAddr()))
	{
		UE_LOG(LogUnrealMCPBridge, Error, TEXT("Failed to bind to %s:%d"), *ServerAddress.ToString(), Port);
		return;
	}

	if (!NewListener->Listen(8))
	{
		UE_LOG(LogUnrealMCPBridge, Error, TEXT("Failed to listen on %s:%d"), *ServerAddress.ToString(), Port);
		return;
	}

	ListenerSocket = NewListener;
	bIsRunning = true;

	ServerThread = FRunnableThread::Create(
		new FMCPServerRunnable(this, ListenerSocket),
		TEXT("UnrealMCPServerThread"),
		0, TPri_Normal);

	if (!ServerThread)
	{
		UE_LOG(LogUnrealMCPBridge, Error, TEXT("Failed to create server thread"));
		StopServer();
		return;
	}

	UE_LOG(LogUnrealMCPBridge, Display, TEXT("MCP server listening on %s:%d"), *ServerAddress.ToString(), Port);
}

void UUnrealMCPBridge::StopServer()
{
	if (!bIsRunning)
	{
		return;
	}

	bIsRunning = false;

	if (ServerThread)
	{
		ServerThread->Kill(true);
		delete ServerThread;
		ServerThread = nullptr;
	}

	if (ListenerSocket.IsValid())
	{
		ListenerSocket->Close();
		ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenerSocket.Get());
		ListenerSocket.Reset();
	}

	UE_LOG(LogUnrealMCPBridge, Display, TEXT("MCP server stopped"));
}

FString UUnrealMCPBridge::ExecuteCommand(const FString& CommandType, const TSharedPtr<FJsonObject>& Params)
{
	TPromise<FString> Promise;
	TFuture<FString> Future = Promise.GetFuture();

	AsyncTask(ENamedThreads::GameThread, [this, CommandType, Params, Promise = MoveTemp(Promise)]() mutable
	{
		TSharedPtr<FJsonObject> Response = MakeShared<FJsonObject>();
		TSharedPtr<FJsonObject> Result;

		if (CommandType == TEXT("ping"))
		{
			Result = HandlePing(Params);
		}
		else if (CommandType == TEXT("execute_python"))
		{
			Result = HandleExecutePython(Params);
		}
		else
		{
			Response->SetStringField(TEXT("status"), TEXT("error"));
			Response->SetStringField(TEXT("error"), FString::Printf(TEXT("Unknown command: %s"), *CommandType));
			Promise.SetValue(SerializeJson(Response));
			return;
		}

		bool bSuccess = true;
		if (Result->HasField(TEXT("success")))
		{
			bSuccess = Result->GetBoolField(TEXT("success"));
		}

		if (bSuccess)
		{
			Response->SetStringField(TEXT("status"), TEXT("success"));
			Response->SetObjectField(TEXT("result"), Result);
		}
		else
		{
			Response->SetStringField(TEXT("status"), TEXT("error"));
			Response->SetStringField(TEXT("error"),
				Result->HasField(TEXT("error")) ? Result->GetStringField(TEXT("error")) : TEXT("Command failed"));
		}

		Promise.SetValue(SerializeJson(Response));
	});

	return Future.Get();
}

TSharedPtr<FJsonObject> UUnrealMCPBridge::HandlePing(const TSharedPtr<FJsonObject>& /*Params*/)
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("message"), TEXT("pong"));
	return Result;
}

TSharedPtr<FJsonObject> UUnrealMCPBridge::HandleExecutePython(const TSharedPtr<FJsonObject>& Params)
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();

	FString Code;
	if (!Params.IsValid() || !Params->TryGetStringField(TEXT("code"), Code))
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("error"), TEXT("Missing 'code' parameter"));
		return Result;
	}

	IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
	if (!Python)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("error"), TEXT("PythonScriptPlugin is not loaded. Enable the Python Editor Script Plugin."));
		return Result;
	}

	// Python initializes lazily, so it can be unavailable for the first few seconds
	// after the editor boots. Force it up rather than failing the first call.
	if (!Python->IsPythonAvailable())
	{
		Python->ForceEnablePythonAtRuntime();
	}
	if (!Python->IsPythonAvailable())
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("error"), TEXT("Python is not available yet (still initializing). Retry shortly."));
		return Result;
	}

	FPythonCommandEx Command;
	Command.Command = Code;
	// ExecuteFile handles multi-line scripts; Public scope persists state across calls (like the console).
	Command.ExecutionMode = EPythonCommandExecutionMode::ExecuteFile;
	Command.FileExecutionScope = EPythonFileExecutionScope::Public;

	const bool bOk = Python->ExecPythonCommandEx(Command);

	// Forward captured log output (prints, warnings, errors) so the agent can see what happened.
	TArray<TSharedPtr<FJsonValue>> LogLines;
	for (const FPythonLogOutputEntry& Entry : Command.LogOutput)
	{
		TSharedPtr<FJsonObject> Line = MakeShared<FJsonObject>();
		Line->SetStringField(TEXT("type"), LexToString(Entry.Type));
		Line->SetStringField(TEXT("output"), Entry.Output);
		LogLines.Add(MakeShared<FJsonValueObject>(Line));
	}

	Result->SetBoolField(TEXT("success"), bOk);
	Result->SetStringField(TEXT("command_result"), Command.CommandResult);
	Result->SetArrayField(TEXT("log"), LogLines);
	if (!bOk)
	{
		Result->SetStringField(TEXT("error"),
			Command.CommandResult.IsEmpty() ? TEXT("Python execution failed (see log)") : Command.CommandResult);
	}

	return Result;
}
