<#
.SYNOPSIS
快速保存当前 Git 仓库改动，并可自动推送到远程分支。

.DESCRIPTION
脚本会自动寻找当前所在的 Git 仓库根目录，检查改动，
执行 `git add -A`、创建提交，并默认推送到当前分支对应的 `origin` 远程分支。

.PARAMETER Message
提交说明。

.PARAMETER Type
提交类型前缀，默认 `chore`。

.PARAMETER SkipPush
只创建本地提交，不推送。

.PARAMETER Timestamp
在提交说明末尾自动附加时间戳。

.EXAMPLE
Get-Help .\Git_Version_Toolkit\scripts\git-save.ps1 -Full

.EXAMPLE
.\Git_Version_Toolkit\scripts\git-save.ps1 "保存当前开发进度"

.EXAMPLE
.\Git_Version_Toolkit\scripts\git-save.ps1 "保存当前开发进度" -Timestamp
#>
param(
  [Parameter(Position = 0)]
  [string]$Message,
  [string]$Type = "chore",
  [switch]$SkipPush,
  [switch]$Timestamp
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Text) {
  Write-Host "[git-save] $Text"
}

function Invoke-Git([string[]]$Args) {
  & "C:\Program Files\Git\cmd\git.exe" @Args
}

function Find-GitRepoRoot([string]$StartPath) {
  $current = Resolve-Path $StartPath
  while ($null -ne $current) {
    $gitPath = Join-Path $current ".git"
    if (Test-Path $gitPath) {
      return $current.Path
    }
    $parent = Split-Path $current.Path -Parent
    if (-not $parent -or $parent -eq $current.Path) {
      break
    }
    $current = Resolve-Path $parent
  }
  return $null
}

$repoRoot = Find-GitRepoRoot (Get-Location).Path
if (-not $repoRoot) {
  $repoRoot = Find-GitRepoRoot (Split-Path -Parent $PSScriptRoot)
}
if (-not $repoRoot) {
  throw "No Git repository found from current location or script location."
}

Set-Location $repoRoot

$branch = (Invoke-Git @("-C", $repoRoot, "branch", "--show-current")).Trim()
if (-not $branch) {
  throw "Cannot determine current git branch."
}

$statusShort = Invoke-Git @("-C", $repoRoot, "status", "--short")
if (-not $statusShort) {
  Write-Step "No changes detected. Nothing to save."
  exit 0
}

if (-not $Message) {
  $Message = Read-Host "Enter a short save message"
}

if (-not $Message) {
  throw "Commit message cannot be empty."
}

$timestampText = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$finalMessage = if ($Timestamp) {
  "$Type`: $Message [$timestampText]"
} else {
  "$Type`: $Message"
}

Write-Step "Repository: $repoRoot"
Write-Step "Branch: $branch"
Write-Step "Current changes:"
Invoke-Git @("-C", $repoRoot, "status", "--short")

Write-Step "Staging all changes..."
Invoke-Git @("-C", $repoRoot, "add", "-A")

Write-Step "Creating commit: $finalMessage"
Invoke-Git @("-C", $repoRoot, "commit", "-m", $finalMessage)

if ($SkipPush) {
  Write-Step "Commit created. Push skipped."
  exit 0
}

Write-Step "Pushing branch '$branch' to origin..."
Invoke-Git @("-C", $repoRoot, "push", "origin", $branch)

Write-Step "Save complete."
