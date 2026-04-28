param(
    [ValidateSet("quick", "full")]
    [string]$Mode = "quick",
    [string]$OutputPath = "",
    [string]$Subnet = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-HostPython {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @($pyLauncher.Source, "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    throw "Python 3 was not found in PATH. Install Python 3.11+ and try again."
}

function Get-NmapPath {
    $command = Get-Command nmap.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "C:\Program Files (x86)\Nmap\nmap.exe",
        "C:\Program Files\Nmap\nmap.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Nmap was not found. Install Nmap for Windows and try again."
}

function Ensure-Venv {
    param(
        [string]$AgentDir
    )

    $venvDir = Join-Path $AgentDir ".venv"
    $pythonExe = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Host "[setup] Creating virtual environment at $venvDir"
        $hostPython = Get-HostPython
        $hostPythonArgs = @()
        if ($hostPython.Length -gt 1) {
            $hostPythonArgs = $hostPython[1..($hostPython.Length - 1)]
        }
        & $hostPython[0] @hostPythonArgs -m venv $venvDir
    }

    return $pythonExe
}

function Install-AgentDependencies {
    param(
        [string]$PythonExe,
        [string]$AgentDir
    )

    Push-Location $AgentDir
    try {
        Write-Host "[setup] Installing hardware-agent dependencies"
        & $PythonExe -m pip install --upgrade pip
        & $PythonExe -m pip install -e .
    }
    finally {
        Pop-Location
    }
}

function Resolve-VulnersScript {
    param(
        [string]$NmapPath,
        [string]$AgentDir
    )

    & $NmapPath --script-help vulners *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[setup] Using vulners script bundled with Nmap"
        return "vulners"
    }

    $nseDir = Join-Path $AgentDir "resources\nse"
    $vulnersPath = Join-Path $nseDir "vulners.nse"
    New-Item -ItemType Directory -Path $nseDir -Force | Out-Null

    if (-not (Test-Path $vulnersPath)) {
        Write-Host "[setup] Downloading vulners.nse into $vulnersPath"
        Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "https://raw.githubusercontent.com/vulnersCom/nmap-vulners/master/vulners.nse" `
            -OutFile $vulnersPath
    }
    else {
        Write-Host "[setup] Using cached local vulners.nse"
    }

    return $vulnersPath
}

$agentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Ensure-Venv -AgentDir $agentDir
Install-AgentDependencies -PythonExe $pythonExe -AgentDir $agentDir

$nmapPath = Get-NmapPath
$resolvedVulnersScript = Resolve-VulnersScript -NmapPath $nmapPath -AgentDir $agentDir
$defaultScripts = @(
    $resolvedVulnersScript
    "smb2-security-mode"
    "smb-protocols"
    "ssh-auth-methods"
    "ssh2-enum-algos"
    "http-title"
    "http-server-header"
    "http-methods"
    "ssl-cert"
)

$resolvedOutputPath = if ($OutputPath) {
    $OutputPath
}
elseif ($env:AGENT_OUTPUT_PATH) {
    $env:AGENT_OUTPUT_PATH
}
else {
    Join-Path $agentDir "artifacts\lab-scan.json"
}

$env:AGENT_NMAP_PATH = $nmapPath
$env:AGENT_SCAN_MODE = $Mode
if (-not $env:AGENT_NMAP_SCRIPTS) {
    $env:AGENT_NMAP_SCRIPTS = ($defaultScripts -join ",")
}
$env:AGENT_MIN_CVSS = if ($env:AGENT_MIN_CVSS) { $env:AGENT_MIN_CVSS } else { "5.0" }
$env:AGENT_MAX_WORKERS = if ($env:AGENT_MAX_WORKERS) { $env:AGENT_MAX_WORKERS } else { "4" }
$env:AGENT_HOST_BATCH_SIZE = if ($env:AGENT_HOST_BATCH_SIZE) { $env:AGENT_HOST_BATCH_SIZE } else { "8" }
$env:AGENT_OUTPUT_PATH = $resolvedOutputPath

if ($Subnet) {
    $env:AGENT_SCAN_SUBNET = $Subnet
}

Write-Host "[run] Nmap path: $env:AGENT_NMAP_PATH"
Write-Host "[run] Scripts: $env:AGENT_NMAP_SCRIPTS"
if ($env:AGENT_SCAN_SUBNET) {
    Write-Host "[run] Subnet: $env:AGENT_SCAN_SUBNET"
}
else {
    Write-Host "[run] Subnet: auto-detected from the active IPv4 interface"
}
Write-Host "[run] Output: $env:AGENT_OUTPUT_PATH"

Push-Location (Join-Path $agentDir "src")
try {
    & $pythonExe -m agent.main
}
finally {
    Pop-Location
}
