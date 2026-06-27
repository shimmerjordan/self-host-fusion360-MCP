<#
.SYNOPSIS
    Uninstall self-host-fusion360-mcp: remove the Fusion add-in and the Claude
    Desktop config entry. The token, venv, and ~/.fusion-mcp settings are left
    in place unless -Purge is given.

.PARAMETER Purge   Also delete the venv and ~/.fusion-mcp (token + settings + logs).
#>
[CmdletBinding()]
param([switch]$Purge)

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }

$RepoRoot = Split-Path $PSScriptRoot -Parent

# 1. Remove add-in
$Dest = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\AddIns\Fusion360MCP"
if (Test-Path $Dest) {
    Remove-Item $Dest -Recurse -Force
    Ok "Removed add-in: $Dest"
} else {
    Warn "Add-in not found (already removed?)."
}

# 2. Remove Claude config entry
$Venv = Join-Path $RepoRoot ".venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
$Py = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
$merge = Join-Path $RepoRoot "install\claude_config_merge.py"
if (Test-Path $merge) {
    & $Py $merge --name fusion360 --remove
    Ok "Removed 'fusion360' from Claude Desktop config (if present)."
}

# 3. Optional purge
if ($Purge) {
    $CfgDir = Join-Path $HOME ".fusion-mcp"
    if (Test-Path $CfgDir) { Remove-Item $CfgDir -Recurse -Force; Ok "Purged $CfgDir" }
    if (Test-Path $Venv) { Remove-Item $Venv -Recurse -Force; Ok "Purged venv" }
} else {
    Warn "Token, venv, and ~/.fusion-mcp kept. Re-run with -Purge to delete them."
}

Write-Host ""
Ok "Uninstall complete. Restart Fusion and Claude Desktop to finish. / 卸载完成，请重启 Fusion 与 Claude Desktop。"
