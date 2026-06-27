<#
.SYNOPSIS
    Foolproof installer for self-host-fusion360-mcp on Windows.

.DESCRIPTION
    1. Finds a suitable Python (>=3.10).
    2. Copies the Fusion add-in into your Fusion 'API\AddIns' folder.
    3. Generates the shared token and writes the add-in settings.
    4. Creates a venv and installs the MCP server.
    5. Safely merges the server into Claude Desktop's config (your other
       servers are preserved; a backup is taken).

    Re-runnable (idempotent). Compatible with Windows PowerShell 5.1.

.PARAMETER Port        Bridge port the add-in listens on (default 9000).
.PARAMETER Python      Path to a specific python.exe to use.
.PARAMETER NoClaude    Skip editing claude_desktop_config.json.
.PARAMETER Http        Configure the Claude entry to use HTTP transport instead of stdio.
#>
[CmdletBinding()]
param(
    [int]$Port = 9000,
    [string]$Python = "",
    [switch]$NoClaude,
    [switch]$Http
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Info($m)  { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)    { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m)  { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)   { Write-Host "[X] $m" -ForegroundColor Red; exit 1 }

$RepoRoot = Split-Path $PSScriptRoot -Parent
Info "Repo: $RepoRoot"

# --- 1. Python -------------------------------------------------------------
function Resolve-PythonExe([string]$Preferred) {
    $tries = @()
    if ($Preferred) { $tries += ,@($Preferred) }
    $tries += ,@("py", "-3")
    $tries += ,@("python")
    $tries += ,@("python3")
    foreach ($t in $tries) {
        $exe = $t[0]
        $pre = @()
        if ($t.Count -gt 1) { $pre = $t[1..($t.Count - 1)] }
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $out = & $exe @pre -c "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if (-not $out) { continue }
        $lines = @($out -split "`r?`n" | Where-Object { $_ -ne "" })
        if ($lines.Count -lt 2) { continue }
        $ver = $lines[1].Split('.')
        if ([int]$ver[0] -ge 3 -and [int]$ver[1] -ge 10) { return $lines[0] }
    }
    return $null
}

Info "Looking for Python >= 3.10 ..."
$PyExe = Resolve-PythonExe $Python
if (-not $PyExe) { Die "No Python >= 3.10 found. Install from https://www.python.org/downloads/ (tick 'Add to PATH') and re-run." }
Ok "Python: $PyExe"

# --- 2. Copy add-in into Fusion ------------------------------------------
$AddInsDir = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\AddIns"
$AutodeskDir = Join-Path $env:APPDATA "Autodesk"
if (-not (Test-Path $AutodeskDir)) {
    Warn "Autodesk folder not found at $AutodeskDir — is Fusion 360 installed for this user? Continuing anyway."
}
New-Item -ItemType Directory -Force -Path $AddInsDir | Out-Null
$Dest = Join-Path $AddInsDir "Fusion360MCP"
$Src = Join-Path $RepoRoot "addin\Fusion360MCP"
if (-not (Test-Path $Src)) { Die "Add-in source not found at $Src" }
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
Copy-Item $Src $Dest -Recurse -Force
Ok "Add-in copied to $Dest"

# --- 3. Token + add-in settings ------------------------------------------
$CfgDir = Join-Path $HOME ".fusion-mcp"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
& $PyExe (Join-Path $RepoRoot "install\gen_token.py") | Out-Null
Ok "Token ready at $(Join-Path $CfgDir 'token')"

$AddinSettings = [ordered]@{
    port                 = $Port
    bind                 = "127.0.0.1"
    allow_arbitrary_code = $false
    request_timeout      = 30
}
($AddinSettings | ConvertTo-Json) | Set-Content -Path (Join-Path $CfgDir "addin.json") -Encoding UTF8
Ok "Add-in settings written (port $Port)"

# --- 4. venv + install ----------------------------------------------------
$Venv = Join-Path $RepoRoot ".venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Info "Creating venv ..."
    & $PyExe -m venv $Venv
}
Info "Installing server (this may take a minute) ..."
& $VenvPy -m pip install --quiet --upgrade pip
$installTarget = $RepoRoot
if ($Http) { $installTarget = "$RepoRoot[http]" }
& $VenvPy -m pip install --quiet -e $installTarget
$FusionExe = Join-Path $Venv "Scripts\fusion-mcp.exe"
if (-not (Test-Path $FusionExe)) { Die "Install failed: $FusionExe missing." }
Ok "Server installed: $FusionExe"

# --- 5. Claude Desktop config --------------------------------------------
if (-not $NoClaude) {
    Info "Merging into Claude Desktop config ..."
    $mergeArgs = @((Join-Path $RepoRoot "install\claude_config_merge.py"), "--name", "fusion360", "--command", $FusionExe)
    if ($Http) {
        # For HTTP transport the server is launched to serve; Claude connects as a
        # remote connector instead. We still register a stdio launcher by default.
        $mergeArgs += @("--arg", "run", "--arg", "--transport", "--arg", "http")
    }
    & $VenvPy @mergeArgs
    Ok "Claude Desktop config updated (existing servers preserved; backup taken)."
} else {
    Warn "Skipped Claude config (-NoClaude)."
}

# --- Done -----------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Ok "Installation complete. / 安装完成。"
Write-Host ""
Write-Host "Next steps / 后续步骤:" -ForegroundColor White
Write-Host "  1. Start Fusion 360 and open (or create) a design."
Write-Host "     启动 Fusion 360，打开或新建一个设计。"
Write-Host "  2. Utilities > ADD-INS > Scripts and Add-Ins > select 'Fusion360MCP' > Run."
Write-Host "     实用程序 > 加载项 > 脚本和加载项 > 选择 'Fusion360MCP' > 运行。"
Write-Host "     (It is set to Run on Startup, so future launches are automatic.)"
Write-Host "  3. Fully quit and reopen Claude Desktop. / 完全退出并重启 Claude Desktop。"
Write-Host ""
Write-Host "Verify anytime / 随时自检:" -ForegroundColor White
Write-Host "  `"$FusionExe`" doctor"
Write-Host "============================================================" -ForegroundColor Green
