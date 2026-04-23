<#
.SYNOPSIS
Install Git Version Toolkit into another project.

.DESCRIPTION
Copies the current `Git_Version_Toolkit` directory into a target project path.
Useful when you want to reuse the same toolkit across multiple repositories.

.PARAMETER TargetPath
Target project root path where the toolkit folder should be installed.

.PARAMETER ToolkitFolderName
Folder name to create in the target project. Default is `Git_Version_Toolkit`.

.PARAMETER Overwrite
Overwrite existing target toolkit folder if it already exists.

.EXAMPLE
.\install.ps1 -TargetPath D:\my-project

.EXAMPLE
.\install.ps1 -TargetPath D:\my-project -Overwrite
#>
param(
  [Parameter(Mandatory = $true)]
  [string]$TargetPath,
  [string]$ToolkitFolderName = "Git_Version_Toolkit",
  [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Text) {
  Write-Host "[install] $Text"
}

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolvedTarget = Resolve-Path -LiteralPath $TargetPath -ErrorAction SilentlyContinue
if (-not $resolvedTarget) {
  throw "Target path does not exist: $TargetPath"
}

$targetRoot = $resolvedTarget.Path
$destination = Join-Path $targetRoot $ToolkitFolderName

if ((Resolve-Path $sourceRoot).Path -eq $destination) {
  throw "Target path already points to the current toolkit folder."
}

if (Test-Path -LiteralPath $destination) {
  if (-not $Overwrite) {
    throw "Target toolkit folder already exists: $destination. Use -Overwrite to replace it."
  }
  Write-Step "Removing existing toolkit folder..."
  Remove-Item -LiteralPath $destination -Recurse -Force
}

Write-Step "Installing toolkit to: $destination"
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$excludeNames = @(".git", "release")
Get-ChildItem -LiteralPath $sourceRoot -Force | Where-Object {
  $excludeNames -notcontains $_.Name
} | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
}

Write-Step "Installation complete."
Write-Step "You can now use:"
Write-Host "  $ToolkitFolderName\git-save.cmd `"save current progress`""
Write-Host "  .\$ToolkitFolderName\scripts\git-tag-release.ps1 v0.1.0 `"initial stable version`""
