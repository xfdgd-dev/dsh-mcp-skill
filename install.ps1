# Install this skill into the local DeepSeek Harness skills directory.
#
#   .\install.ps1              -> %USERPROFILE%\.dsh\skills\mcp-setup
#   .\install.ps1 -Force       -> overwrite an existing copy
#   .\install.ps1 -Target D:\other\skills

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (-not $Target) {
    $dshHome = $env:DSH_HOME
    if (-not $dshHome) { $dshHome = Join-Path $env:USERPROFILE '.dsh' }
    $Target = Join-Path $dshHome 'skills\mcp-setup'
}

$source = $PSScriptRoot

Write-Host "source : $source"
Write-Host "target : $Target"

if (Test-Path $Target) {
    if (-not $Force) {
        Write-Host ""
        Write-Host "已经存在：$Target" -ForegroundColor Yellow
        Write-Host "加 -Force 覆盖，或先手动删掉它。"
        exit 1
    }
    Remove-Item $Target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Target | Out-Null

# 只复制 skill 本体，别把 .git / README / LICENSE 塞进 skill 目录
Copy-Item (Join-Path $source 'SKILL.md') $Target -Force
$scripts = Join-Path $source 'scripts'
if (Test-Path $scripts) {
    Copy-Item $scripts (Join-Path $Target 'scripts') -Recurse -Force
}

Write-Host ""
Write-Host "装好了。DSH 的 skill 目录带文件监听，通常不用重启。" -ForegroundColor Green
Write-Host "在对话里说「装个 MCP 插件」，或输入 /mcp-setup 试试。"
