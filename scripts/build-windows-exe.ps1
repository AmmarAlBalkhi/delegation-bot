[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$InstallDependencies,
    [switch]$SkipSmoke,
    [string]$DistPath = "dist",
    [string]$WorkPath = "build\pyinstaller"
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

$ResolvedDistPath = Resolve-RepoPath $DistPath
$ResolvedWorkPath = Resolve-RepoPath $WorkPath
$SpecPath = Join-Path $ResolvedWorkPath "spec"
$EntryPoint = Join-Path $RepoRoot "scripts\delegation.py"

if ($InstallDependencies) {
    & $Python -m pip install -e ".[exe]"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& $Python -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller is not available. Run: $Python -m pip install -e `".[exe]`""
    exit $LASTEXITCODE
}

$DataFolders = @(
    @{ Source = "examples"; Dest = "examples" },
    @{ Source = "playbooks"; Dest = "playbooks" },
    @{ Source = "schemas"; Dest = "schemas" }
)

$DataFiles = @(
    @{ Source = "LICENSE"; Dest = "." },
    @{ Source = "NOTICE"; Dest = "." },
    @{ Source = "README.md"; Dest = "." }
)

$PyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--console",
    "--name", "delegation",
    "--distpath", $ResolvedDistPath,
    "--workpath", $ResolvedWorkPath,
    "--specpath", $SpecPath,
    "--copy-metadata", "delegationhq"
)

foreach ($Item in $DataFolders) {
    $Source = Join-Path $RepoRoot $Item.Source
    $PyInstallerArgs += @("--add-data", "$Source;$($Item.Dest)")
}

foreach ($Item in $DataFiles) {
    $Source = Join-Path $RepoRoot $Item.Source
    $PyInstallerArgs += @("--add-data", "$Source;$($Item.Dest)")
}

$PyInstallerArgs += $EntryPoint

& $Python @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ExecutablePath = Join-Path $ResolvedDistPath "delegation.exe"
if (-not (Test-Path -LiteralPath $ExecutablePath)) {
    Write-Error "Expected executable was not created: $ExecutablePath"
    exit 1
}

if (-not $SkipSmoke) {
    $SmokeDir = Join-Path $RepoRoot ".delegation"
    New-Item -ItemType Directory -Force -Path $SmokeDir | Out-Null

    & $ExecutablePath demo --ledger (Join-Path $SmokeDir "exe-smoke.jsonl")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $SmokeHarnessfile = Join-Path $SmokeDir "exe-Harnessfile.yaml"
    & $ExecutablePath init --goal "prepare this repo for safe AI delegation" --output $SmokeHarnessfile --force
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath validate $SmokeHarnessfile
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host "Built: $ExecutablePath"
