param(
    [switch]$Execute,
    [switch]$DeleteFiles,
    [switch]$IncludeAuditLogs,
    [switch]$IncludeNotifications,
    [string]$BackendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$ConnectionString,
    [string]$DatabaseName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectPath = Join-Path $PSScriptRoot "ClearUploadedDocuments\ClearUploadedDocuments.csproj"

$toolArgs = @(
    "--backend-root", $BackendRoot
)

if ($Execute) {
    $toolArgs += "--execute"
}

if ($DeleteFiles) {
    $toolArgs += "--delete-files"
}

if ($IncludeAuditLogs) {
    $toolArgs += "--include-audit-logs"
}

if ($IncludeNotifications) {
    $toolArgs += "--include-notifications"
}

if ($ConnectionString) {
    $toolArgs += @("--connection-string", $ConnectionString)
}

if ($DatabaseName) {
    $toolArgs += @("--database-name", $DatabaseName)
}

dotnet run --project $projectPath -- @toolArgs
