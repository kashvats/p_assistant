$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wheel = $args[0]
if (-not $Wheel) {
  $Wheel = Get-ChildItem (Join-Path $Root "dist\living_assistant-*.whl") | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $Wheel -or -not (Test-Path $Wheel)) { throw "Living Assistant wheel not found." }
$ChecksumFile = if ($env:LIVING_ASSISTANT_CHECKSUM_FILE) { $env:LIVING_ASSISTANT_CHECKSUM_FILE } else { Join-Path $Root "SHA256SUMS.txt" }
if (-not (Test-Path $ChecksumFile)) { throw "Checksum manifest not found: $ChecksumFile" }
$WheelName = Split-Path $Wheel -Leaf
$ExpectedSha = $null
Get-Content $ChecksumFile | ForEach-Object {
  if ($_ -match '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
    $ListedName = Split-Path $Matches[2] -Leaf
    if ($ListedName -eq $WheelName) { $ExpectedSha = $Matches[1].ToLowerInvariant() }
  }
}
if (-not $ExpectedSha) { throw "No checksum entry found for $WheelName" }
$Extras = if ($env:LIVING_ASSISTANT_EXTRAS) { $env:LIVING_ASSISTANT_EXTRAS } else { "desktop,browser,voice,wakeword,connectors,security" }
python (Join-Path $Root "scripts\install.py") install $Wheel --extras $Extras --sha256 $ExpectedSha
$Bin = Join-Path $env:LOCALAPPDATA "LivingAssistant\Runtime\bin"
Write-Host ""
Write-Host "Installed verified versioned runtime. Add this directory to your user PATH if desired:"
Write-Host "  $Bin"
Write-Host "Then run: organism doctor"
