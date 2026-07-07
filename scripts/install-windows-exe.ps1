[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Source = "dist\delegation.exe",
    [string]$InstallDir = "",
    [switch]$Build,
    [switch]$InstallDependencies,
    [switch]$SkipBuildSmoke,
    [switch]$AddToPath,
    [switch]$NoSmoke
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Resolve-RepoPath {
    param([string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $RepoRoot $PathValue
}

if (-not $InstallDir) {
    if (-not $env:LOCALAPPDATA) {
        throw "LOCALAPPDATA is not set. Pass -InstallDir explicitly."
    }
    $InstallDir = Join-Path $env:LOCALAPPDATA "DelegationHQ\bin"
}

if ($Build) {
    $BuildScript = Join-Path $PSScriptRoot "build-windows-exe.ps1"
    $BuildArgs = @("-Python", $Python)
    if ($InstallDependencies) {
        $BuildArgs += "-InstallDependencies"
    }
    if ($SkipBuildSmoke) {
        $BuildArgs += "-SkipSmoke"
    }

    & $BuildScript @BuildArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$ResolvedSource = Resolve-RepoPath $Source
if (-not (Test-Path -LiteralPath $ResolvedSource)) {
    Write-Error "Source executable not found: $ResolvedSource. Build it first or pass -Build."
    exit 1
}

$ResolvedInstallDir = Resolve-RepoPath $InstallDir
New-Item -ItemType Directory -Force -Path $ResolvedInstallDir | Out-Null

$Target = Join-Path $ResolvedInstallDir "delegation.exe"
Copy-Item -LiteralPath $ResolvedSource -Destination $Target -Force

if (-not $NoSmoke) {
    # Smoke commands: delegation.exe --version; delegation.exe doctor --skip-github
    & $Target --version
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Installed executable version check failed: $Target --version"
        exit $LASTEXITCODE
    }

    & $Target doctor --skip-github
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Installed executable smoke check failed: $Target doctor --skip-github"
        exit $LASTEXITCODE
    }
}

if ($AddToPath) {
    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $PathEntries = @()
    if (-not [string]::IsNullOrWhiteSpace($CurrentPath)) {
        $PathEntries = $CurrentPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    }

    $AlreadyPresent = $false
    foreach ($Entry in $PathEntries) {
        if ($Entry.TrimEnd("\") -ieq $ResolvedInstallDir.TrimEnd("\")) {
            $AlreadyPresent = $true
            break
        }
    }

    if (-not $AlreadyPresent) {
        $NewPath = ($PathEntries + $ResolvedInstallDir) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        Write-Host "Added to user PATH: $ResolvedInstallDir"
        Write-Host "Open a new terminal before running delegation from PATH."
    }
}

Write-Host "Installed: $Target"
Write-Host "Try: delegation demo"
