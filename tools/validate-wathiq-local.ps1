param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendSolutionPath = Join-Path $RepoRoot "eArchiveSystem\eArchiveSystem.sln"
$OcrProjectPath = Join-Path $RepoRoot "eArchive.OcrService\eArchive.OcrService.csproj"
$AraSegRoot = Join-Path $RepoRoot "wathiq-araseg-service"
$AraGenreRoot = Join-Path $RepoRoot "aragenre"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host ("==> {0}" -f $Description)

    & $Action

    if ($LASTEXITCODE -ne 0) {
        throw ("Step failed: {0}" -f $Description)
    }
}

foreach ($requiredPath in @(
    $BackendSolutionPath,
    $OcrProjectPath,
    $AraSegRoot,
    $AraGenreRoot
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path was not found: $requiredPath"
    }
}

try {
    Invoke-Step "Build eArchiveSystem solution" {
        dotnet build $BackendSolutionPath
    }

    $solutionIncludesOcr = Select-String -Path $BackendSolutionPath -Pattern 'eArchive\.OcrService\.csproj' -Quiet
    if ($solutionIncludesOcr) {
        Write-Host ""
        Write-Host "==> Build eArchive.OcrService project"
        Write-Host "Skipped because eArchive.OcrService.csproj is already included in eArchiveSystem.sln."
    }
    else {
        Invoke-Step "Build eArchive.OcrService project" {
            dotnet build $OcrProjectPath
        }
    }

    Invoke-Step "Compile wathiq-araseg-service Python sources" {
        Push-Location $AraSegRoot
        try {
            python -m compileall -q src
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Step "Import wathiq-araseg-service application factory" {
        Push-Location $AraSegRoot
        try {
            python -c "import sys; sys.path.insert(0, 'src'); from wathiq_araseg.app import create_app; print('AraSeg import OK')"
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Step "Compile aragenre Python sources" {
        Push-Location $AraGenreRoot
        try {
            python -m compileall -q app
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Step "Import aragenre FastAPI app" {
        Push-Location $AraGenreRoot
        try {
            python -c "import sys; sys.path.insert(0, '.'); from app.main import app; print('AraGenre import OK')"
        }
        finally {
            Pop-Location
        }
    }
}
catch {
    Write-Error $_
    exit 1
}
