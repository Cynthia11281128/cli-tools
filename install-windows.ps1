$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$windowsDir = Join-Path $repoRoot "windows"
$sourceCmd = Join-Path $windowsDir "cli-tools.cmd"
$sourceNative = Join-Path $windowsDir "cli-tools-native.ps1"

if (!(Test-Path -LiteralPath $sourceCmd -PathType Leaf)) {
    throw "Missing Windows entrypoint: $sourceCmd"
}
if (!(Test-Path -LiteralPath $sourceNative -PathType Leaf)) {
    throw "Missing Windows native implementation: $sourceNative"
}

$targets = @(
    (Join-Path $HOME ".local\bin"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps")
)

foreach ($dir in $targets) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Remove-Item -LiteralPath (Join-Path $dir "cli-tools.ps1") -Force -ErrorAction SilentlyContinue
    Copy-Item -Force $sourceCmd (Join-Path $dir "cli-tools.cmd")
    Copy-Item -Force $sourceNative (Join-Path $dir "cli-tools-native.ps1")
}

$installDir = Join-Path $HOME ".local\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()
if (-not [string]::IsNullOrWhiteSpace($userPath)) {
    $parts = $userPath -split ";" | Where-Object { $_ -ne "" }
}
if (-not ($parts | Where-Object { $_.TrimEnd("\") -ieq $installDir.TrimEnd("\") })) {
    [Environment]::SetEnvironmentVariable("Path", ((@($installDir) + $parts) -join ";"), "User")
}

$envParts = $env:Path -split ";" | Where-Object { $_ -ne "" }
if (-not ($envParts | Where-Object { $_.TrimEnd("\") -ieq $installDir.TrimEnd("\") })) {
    $env:Path = (@($installDir) + $envParts) -join ";"
}

Write-Host "Installed Windows cli-tools entrypoints:"
foreach ($dir in $targets) {
    Write-Host "  $dir"
}
Write-Host ""
Write-Host "Run: cli-tools list"
Write-Host "If the command is not found, close and reopen PowerShell."
