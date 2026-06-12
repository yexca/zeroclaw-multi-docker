param(
    [int]$Id = 0,
    [int]$HostPort = 0,
    [string]$MatrixUserId = "",
    [string]$ExternalPeers = "",
    [string]$ProactiveTarget = "",
    [switch]$NoComposeEdit,
    [switch]$NoEnvEdit,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$ComposePath = Join-Path $Root "docker-compose.yml"
$EnvPath = Join-Path $Root ".env"
$EnvExamplePath = Join-Path $Root ".env.example"
$InstancesDir = Join-Path $Root "instances"

function Say($Message) {
    Write-Host "[add-agent] $Message"
}

function Write-TextFile($Path, $Content) {
    if ($DryRun) {
        Say "dry-run: would write $Path"
        return
    }
    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Append-TextFile($Path, $Content) {
    if ($DryRun) {
        Say "dry-run: would append to $Path"
        return
    }
    Add-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Ensure-Directory($Path) {
    if (Test-Path -LiteralPath $Path) {
        return
    }
    if ($DryRun) {
        Say "dry-run: would create directory $Path"
        return
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Get-NextAgentId {
    if (-not (Test-Path -LiteralPath $InstancesDir)) {
        return 1
    }
    $ids = Get-ChildItem -LiteralPath $InstancesDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^agent(\d+)$' } |
        ForEach-Object { [int]$Matches[1] }
    if (-not $ids) {
        return 1
    }
    return (($ids | Measure-Object -Maximum).Maximum + 1)
}

function Ensure-EnvFile {
    if ($NoEnvEdit -or (Test-Path -LiteralPath $EnvPath)) {
        return
    }
    if (-not (Test-Path -LiteralPath $EnvExamplePath)) {
        throw ".env is missing and .env.example was not found"
    }
    if ($DryRun) {
        Say "dry-run: would copy .env.example to .env"
        return
    }
    Copy-Item -LiteralPath $EnvExamplePath -Destination $EnvPath
}

function Upsert-EnvLine($Lines, $Key, $Value) {
    $pattern = "^\s*$([regex]::Escape($Key))="
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $pattern) {
            if ([string]::IsNullOrWhiteSpace(($Lines[$i] -split "=", 2)[1])) {
                $Lines[$i] = "$Key=$Value"
            }
            return $Lines
        }
    }
    $Lines += "$Key=$Value"
    return $Lines
}

function Merge-Mapping($Current, $Key, $Value) {
    $items = @()
    $found = $false
    foreach ($item in ($Current -split ",")) {
        $trimmed = $item.Trim()
        if (-not $trimmed) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -eq 2 -and $parts[0].Trim() -eq $Key) {
            $items += "$Key=$Value"
            $found = $true
        } else {
            $items += $trimmed
        }
    }
    if (-not $found) {
        $items += "$Key=$Value"
    }
    return ($items -join ",")
}

function Upsert-EnvMapping($Lines, $Key, $MapKey, $MapValue) {
    if ([string]::IsNullOrWhiteSpace($MapValue)) {
        return $Lines
    }

    $pattern = "^\s*$([regex]::Escape($Key))="
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $pattern) {
            $current = ($Lines[$i] -split "=", 2)[1]
            $Lines[$i] = "$Key=$(Merge-Mapping $current $MapKey $MapValue)"
            return $Lines
        }
    }
    $Lines += "$Key=$MapKey=$MapValue"
    return $Lines
}

function Ensure-AgentEnv($AgentName, $AgentId, $Port) {
    if ($NoEnvEdit) {
        return
    }
    Ensure-EnvFile
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return
    }

    $prefix = "AGENT$AgentId"
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in Get-Content -LiteralPath $EnvPath) {
        $lines.Add($line)
    }

    if (-not ($lines -match "^\s*# Agent $AgentId\s*$")) {
        $lines.Add("")
        $lines.Add("# Agent $AgentId")
    }

    $lines = Upsert-EnvLine $lines "${prefix}_HOST_PORT" "$Port"
    $lines = Upsert-EnvLine $lines "${prefix}_MATRIX_USER_ID" $MatrixUserId
    $lines = Upsert-EnvLine $lines "${prefix}_MATRIX_DEVICE_ID" "ZEROCLAW_AGENT$AgentId"
    $lines = Upsert-EnvLine $lines "${prefix}_MATRIX_ACCESS_TOKEN" ""
    $lines = Upsert-EnvLine $lines "${prefix}_MATRIX_PASSWORD" ""
    $lines = Upsert-EnvLine $lines "${prefix}_MATRIX_RECOVERY_KEY" ""
    $lines = Upsert-EnvLine $lines "${prefix}_MATRIX_EXTERNAL_PEERS" $ExternalPeers
    $lines = Upsert-EnvMapping $lines "PROACTIVE_AGENTS" $AgentName "http://${AgentName}:42617/webhook"
    $lines = Upsert-EnvMapping $lines "PROACTIVE_CHANNELS" $AgentName "matrix.home"
    $lines = Upsert-EnvMapping $lines "PROACTIVE_TARGETS" $AgentName $ProactiveTarget

    Write-TextFile $EnvPath $lines
}

function Ensure-WorkspaceFiles($AgentName, $AgentId) {
    $agentDir = Join-Path $InstancesDir $AgentName
    $workspaceDir = Join-Path $agentDir "workspace"
    $dataDir = Join-Path $agentDir "data"

    Ensure-Directory $agentDir
    Ensure-Directory $workspaceDir
    Ensure-Directory $dataDir

    $files = @{
        "AGENTS.md" = "# Agent $AgentId`n`nDescribe this agent's working rules here.`n"
        "IDENTITY.md" = "# Identity`n`nName, role, voice, and boundaries for $AgentName.`n"
        "SOUL.md" = "# Soul`n`nPersonality notes for $AgentName.`n"
        "MEMORY.md" = "# Memory`n`nStable memories for $AgentName.`n"
        "TOOLS.md" = "# Tools`n`nTool preferences and constraints for $AgentName.`n"
        "USER.md" = "# User`n`nUser preferences visible to $AgentName.`n"
        "HEARTBEAT.md" = "# Heartbeat`n`n- [paused] Add proactive tasks for $AgentName here.`n"
    }

    foreach ($entry in $files.GetEnumerator()) {
        $path = Join-Path $workspaceDir $entry.Key
        if (Test-Path -LiteralPath $path) {
            continue
        }
        Write-TextFile $path $entry.Value
    }
}

function Get-AgentServiceBlock($AgentName, $AgentId, $Port) {
    $upper = "AGENT$AgentId"
    $template = @'
  ${AgentName}:
    <<: *zeroclaw-common
    container_name: zeroclaw-matrix-${AgentName}
    volumes:
      - ./bootstrap:/bootstrap:ro
      - ./instances/${AgentName}:/zeroclaw-data
    ports:
      - "127.0.0.1:${${upper}_HOST_PORT:-${Port}}:42617"
    environment:
      <<: *zeroclaw-common-env
      BOT_NAME: ${AgentName}
      MATRIX_USER_ID: "${${upper}_MATRIX_USER_ID:-}"
      MATRIX_DEVICE_ID: "${${upper}_MATRIX_DEVICE_ID:-ZEROCLAW_AGENT${AgentId}}"
      MATRIX_RECOVERY_KEY: "${${upper}_MATRIX_RECOVERY_KEY:-}"
      MATRIX_RECOVER_KEY: "${${upper}_MATRIX_RECOVER_KEY:-}"
      MATRIX_EXTERNAL_PEERS: "${${upper}_MATRIX_EXTERNAL_PEERS:-}"
      MATRIX_PEERS: "${${upper}_MATRIX_PEERS:-}"
      ZEROCLAW_channels__matrix__home__access_token: "${${upper}_MATRIX_ACCESS_TOKEN:-}"
      ZEROCLAW_channels__matrix__home__password: "${${upper}_MATRIX_PASSWORD:-}"

'@
    return $template.
        Replace('${AgentName}', $AgentName).
        Replace('${upper}', $upper).
        Replace('${Port}', [string]$Port).
        Replace('${AgentId}', [string]$AgentId)
}

function Ensure-ComposeService($AgentName, $AgentId, $Port) {
    if ($NoComposeEdit) {
        return
    }
    if (-not (Test-Path -LiteralPath $ComposePath)) {
        throw "docker-compose.yml was not found"
    }

    $compose = Get-Content -LiteralPath $ComposePath -Raw
    if ($compose -match "(?m)^  $([regex]::Escape($AgentName)):\s*$") {
        Say "$AgentName already exists in docker-compose.yml"
        return
    }

    $block = Get-AgentServiceBlock $AgentName $AgentId $Port
    $proactiveMatch = [regex]::Match($compose, "(?m)^  proactive:\s*$")
    if (-not $proactiveMatch.Success) {
        throw "Could not find the proactive service insertion point"
    }
    $compose = $compose.Substring(0, $proactiveMatch.Index) + $block + $compose.Substring($proactiveMatch.Index)

    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in ($compose -split "\r?\n", -1)) {
        $lines.Add($line)
    }
    $proactiveIndex = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^  proactive:\s*$") {
            $proactiveIndex = $i
            break
        }
    }
    if ($proactiveIndex -ge 0) {
        $dependsIndex = -1
        for ($i = $proactiveIndex + 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^  [A-Za-z0-9_-]+:\s*$") {
                break
            }
            if ($lines[$i] -match "^\s{4}depends_on:\s*$") {
                $dependsIndex = $i
                break
            }
        }
        if ($dependsIndex -ge 0) {
            $hasDependency = $false
            $insertIndex = $dependsIndex + 1
            while ($insertIndex -lt $lines.Count -and $lines[$insertIndex] -match "^\s{6}-\s+") {
                if ($lines[$insertIndex] -match "^\s{6}-\s+$([regex]::Escape($AgentName))\s*$") {
                    $hasDependency = $true
                }
                $insertIndex++
            }
            if (-not $hasDependency) {
                $lines.Insert($insertIndex, "      - $AgentName")
                $compose = $lines -join "`r`n"
            }
        }
    }

    Write-TextFile $ComposePath $compose
}

if ($Id -le 0) {
    $Id = Get-NextAgentId
}
if ($HostPort -le 0) {
    $HostPort = 42640 + $Id
}

$AgentName = "agent$Id"

Say "scaffolding $AgentName on host port $HostPort"
Ensure-WorkspaceFiles $AgentName $Id
Ensure-AgentEnv $AgentName $Id $HostPort
Ensure-ComposeService $AgentName $Id $HostPort

Say "done"
Say "Next: fill ${AgentName}'s Matrix values in .env and edit instances/${AgentName}/workspace/*.md."
Say "Start it with: docker compose up -d $AgentName"

