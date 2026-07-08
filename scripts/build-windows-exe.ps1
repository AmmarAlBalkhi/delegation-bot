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
$DelegationScript = Join-Path $RepoRoot "scripts\delegation.py"

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

    & $ExecutablePath --version
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

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

    $SmokeWorkspace = Join-Path $SmokeDir "exe-local-workspace"
    & $ExecutablePath workspace-init --path $SmokeWorkspace --owner exe-smoke --plan --force
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath workspace-status --path $SmokeWorkspace
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath agent-add exe_cli_agent --workspace $SmokeWorkspace --command "$ExecutablePath --version" --capability read.workspace --allowed-data workspace --evidence command_output --force
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath agent-run exe_cli_agent --workspace $SmokeWorkspace --execute --confirm LOCAL_AGENT_EXECUTION
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath app-plan
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath app-state --workspace $SmokeWorkspace
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath cockpit --workspace $SmokeWorkspace
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath app-dashboard --workspace $SmokeWorkspace --preview-agent exe_cli_agent
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath timeline --workspace $SmokeWorkspace
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath approval-preview exe_cli_agent --workspace $SmokeWorkspace
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath action-request exe_cli_agent --workspace $SmokeWorkspace --action read.workspace --target workspace --summary "EXE smoke agent requests read access."
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath app-export --workspace $SmokeWorkspace --output (Join-Path $SmokeWorkspace ".delegation\cockpit") --preview-agent exe_cli_agent
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath app-serve --workspace $SmokeWorkspace --dry-run
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath agents "examples\ai-harness-control-plane.yaml" --registry "examples\agent-passports.yaml"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath agent-gate "examples\ai-harness-control-plane.yaml" implementer --action create_pull_request --target repository --approval pull_request --ledger (Join-Path $SmokeDir "exe-smoke.jsonl") --write
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath approval-inbox --ledger (Join-Path $SmokeDir "exe-smoke.jsonl")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath approval-decision --ledger (Join-Path $SmokeDir "exe-smoke.jsonl") --action-id agent_gate.implementer.create_pull_request --decision approve --approver exe-smoke
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $AgentResultPath = Join-Path $SmokeDir "agent-result.json"
    @{
        schema_version = "delegation.agent-result.v1"
        action_id = "agent_gate.implementer.create_pull_request"
        agent_id = "implementer"
        status = "completed"
        summary = "EXE smoke custom agent returned controlled result evidence."
        changed_resources = @("repository")
        runprint_recording_id = "rec-agent-result-exe-smoke"
        evidence_bundle_id = "bundle-agent-result-exe-smoke"
        artifacts = @(@{
            id = "run-ledger"
            kind = "jsonl"
            path = ".delegation\exe-smoke.jsonl"
        })
    } | ConvertTo-Json -Depth 6 | Set-Content -Path $AgentResultPath -Encoding UTF8

    & $ExecutablePath agent-result-ingest --ledger (Join-Path $SmokeDir "exe-smoke.jsonl") --action-id agent_gate.implementer.create_pull_request --result $AgentResultPath
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath evidence-ingest --ledger (Join-Path $SmokeDir "exe-smoke.jsonl") --tool test-reporter --tool-kind test --action-id agent_gate.implementer.create_pull_request --recording-id rec-evidence-exe-smoke --bundle-id bundle-evidence-exe-smoke --artifact "test-report:junit:artifacts\tests.xml" --summary "EXE smoke recorded generic evidence."
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath runprint-ingest --ledger (Join-Path $SmokeDir "exe-smoke.jsonl") --action-id agent_gate.implementer.create_pull_request --recording-id rec-exe-smoke --bundle-id bundle-exe-smoke --artifact "run-ledger:jsonl:.delegation\exe-smoke.jsonl" --summary "EXE smoke recorded evidence."
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ExecutablePath agent-audit --ledger (Join-Path $SmokeDir "exe-smoke.jsonl")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& $Python $DelegationScript artifacts --dist $ResolvedDistPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python $DelegationScript artifacts --dist $ResolvedDistPath --check
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ChecksumsPath = Join-Path $ResolvedDistPath "SHA256SUMS.txt"
$ManifestPath = Join-Path $ResolvedDistPath "artifacts-manifest.json"
Write-Host "Built: $ExecutablePath"
Write-Host "Checksums: $ChecksumsPath"
Write-Host "Manifest: $ManifestPath"
