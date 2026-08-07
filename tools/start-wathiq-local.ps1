param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

function Quote-PowerShellLiteral {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return "'" + $Value.Replace("'", "''") + "'"
}

function Start-ServiceWindow {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$Command,

        [hashtable]$Environment = @{}
    )

    if (-not (Test-Path -LiteralPath $WorkingDirectory -PathType Container)) {
        throw "Working directory was not found: $WorkingDirectory"
    }

    $segments = @(
        '$Host.UI.RawUI.WindowTitle = ' + (Quote-PowerShellLiteral $Title),
        'Set-Location -LiteralPath ' + (Quote-PowerShellLiteral $WorkingDirectory)
    )

    foreach ($entry in $Environment.GetEnumerator() | Sort-Object Name) {
        $segments += '$env:' + $entry.Key + ' = ' + (Quote-PowerShellLiteral ([string]$entry.Value))
    }

    $segments += $Command
    $commandText = '& { ' + ($segments -join '; ') + ' }'
    $encodedCommand = [Convert]::ToBase64String(
        [System.Text.Encoding]::Unicode.GetBytes($commandText)
    )

    $process = Start-Process `
        -FilePath $PowerShellExe `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encodedCommand) `
        -PassThru

    Write-Host ("Started {0} (PID {1})" -f $Title, $process.Id)
}

$araGenreRoot = Join-Path $RepoRoot "aragenre"
$araSegRoot = Join-Path $RepoRoot "wathiq-araseg-service"
$ocrProjectPath = Join-Path $RepoRoot "eArchive.OcrService\eArchive.OcrService.csproj"
$backendProjectPath = Join-Path $RepoRoot "eArchiveSystem\eArchiveSystem.csproj"
$araSegBaseManifestPath = Join-Path $araSegRoot "models\pa\manifest.json"
$araSegMicroManifestPath = Join-Path $araSegRoot "models\pa\micro\manifest.json"

foreach ($requiredPath in @(
    $araGenreRoot,
    $araSegRoot,
    $ocrProjectPath,
    $backendProjectPath,
    $araSegBaseManifestPath,
    $araSegMicroManifestPath
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path was not found: $requiredPath"
    }
}

Start-ServiceWindow `
    -Title "Wathiq - AraGenre" `
    -WorkingDirectory $araGenreRoot `
    -Command "python -m uvicorn app.main:app --host 0.0.0.0 --port 8001"

Start-ServiceWindow `
    -Title "Wathiq - AraSeg" `
    -WorkingDirectory $araSegRoot `
    -Environment @{
        WATHIQ_ARASEG_INTERNAL_TOKENIZED_ENDPOINT_ENABLED = "true"
        WATHIQ_ARASEG_PA_BASE_MANIFEST_PATH = $araSegBaseManifestPath
        WATHIQ_ARASEG_PA_MICRO_MANIFEST_PATH = $araSegMicroManifestPath
    } `
    -Command "python -m uvicorn --app-dir src --factory wathiq_araseg.app:create_app --host 127.0.0.1 --port 8000"

Start-ServiceWindow `
    -Title "Wathiq - OCR" `
    -WorkingDirectory (Split-Path -Parent $ocrProjectPath) `
    -Command ("dotnet run --project " + (Quote-PowerShellLiteral $ocrProjectPath) + " --launch-profile http")

Start-ServiceWindow `
    -Title "Wathiq - Backend" `
    -WorkingDirectory (Split-Path -Parent $backendProjectPath) `
    -Command ("dotnet run --project " + (Quote-PowerShellLiteral $backendProjectPath) + " --launch-profile http")
