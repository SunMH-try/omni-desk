<#
.SYNOPSIS
创建并推送一个带说明的 Git 标签。

.DESCRIPTION
脚本会自动寻找当前所在的 Git 仓库根目录，检查工作区是否干净，
然后创建注释标签并推送到远程仓库。

.PARAMETER Tag
标签名称，例如 `v0.1.0`。

.PARAMETER Message
标签说明。

.PARAMETER Force
若标签已存在，则删除并重建。

.EXAMPLE
Get-Help .\Git_Version_Toolkit\scripts\git-tag-release.ps1 -Full

.EXAMPLE
.\Git_Version_Toolkit\scripts\git-tag-release.ps1 v0.1.0 "初始稳定版本"
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Tag,
  [Parameter(Position = 1)]
  [string]$Message,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Text) {
  Write-Host "[git-tag] $Text"
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
if ($statusShort) {
  throw "Working tree is not clean. Please commit or stash changes before tagging."
}

if (-not $Message) {
  $Message = Read-Host "Enter tag description"
}

if (-not $Message) {
  $Message = "Release $Tag"
}

$existingTag = (Invoke-Git @("-C", $repoRoot, "tag", "--list", $Tag)).Trim()
if ($existingTag -and -not $Force) {
  throw "Tag '$Tag' already exists. Use -Force to replace it."
}

Write-Step "Repository: $repoRoot"
Write-Step "Branch: $branch"
Write-Step "Tag: $Tag"
Write-Step "Message: $Message"

if ($existingTag -and $Force) {
  Write-Step "Deleting existing local tag..."
  Invoke-Git @("-C", $repoRoot, "tag", "-d", $Tag)
}

Write-Step "Fetching latest remote tags..."
Invoke-Git @("-C", $repoRoot, "fetch", "--tags", "origin")

if ($existingTag -and $Force) {
  Write-Step "Deleting existing remote tag..."
  Invoke-Git @("-C", $repoRoot, "push", "origin", ":refs/tags/$Tag")
}

Write-Step "Creating annotated tag..."
Invoke-Git @("-C", $repoRoot, "tag", "-a", $Tag, "-m", $Message)

Write-Step "Pushing tag to origin..."
Invoke-Git @("-C", $repoRoot, "push", "origin", $Tag)

Write-Step "Tag release complete."
